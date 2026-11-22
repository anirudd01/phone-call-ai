"""Admin REST API (X-Admin-Key) and the bridge-facing outbound-job endpoints (bearer token)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse

from carwash_voice.api import schemas
from carwash_voice.api.deps import SessionDep, SettingsDep, require_admin, require_bridge
from carwash_voice.db.models import Actor, JobStatus, TicketStatus
from carwash_voice.db.session import run_db
from carwash_voice.domain import calls, customers, outbound, tickets
from carwash_voice.domain.errors import ConflictError, InvalidInputError, NotFoundError
from carwash_voice.transports.plivo.dialer import DialError
from carwash_voice.voice.recording import LocalRecordingStore

router = APIRouter(prefix="/api", tags=["admin"], dependencies=[Depends(require_admin)])
bridge_router = APIRouter(
    prefix="/api/bridge", tags=["bridge"], dependencies=[Depends(require_bridge)]
)


def _bad(exc: InvalidInputError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def _missing(exc: NotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


# --- tickets -----------------------------------------------------------------


@router.get("/tickets", response_model=list[schemas.TicketOut])
def list_tickets(
    session: SessionDep, status: TicketStatus | None = None, limit: int = 100, offset: int = 0
):
    return tickets.list_tickets(session, status=status, limit=limit, offset=offset)


@router.get("/tickets/{public_ref}", response_model=schemas.TicketDetailOut)
def get_ticket(public_ref: str, session: SessionDep):
    try:
        return tickets.get_ticket(session, public_ref)
    except NotFoundError as exc:
        raise _missing(exc) from exc
    except InvalidInputError as exc:
        raise _bad(exc) from exc


@router.patch("/tickets/{public_ref}", response_model=schemas.TicketDetailOut)
def update_ticket(public_ref: str, body: schemas.TicketPatch, session: SessionDep):
    try:
        ticket = tickets.get_ticket(session, public_ref)
        if body.status is not None:
            tickets.update_status(session, ticket, body.status, actor=Actor.STAFF)
        if body.priority is not None:
            ticket.priority = body.priority
            session.commit()
        if body.note:
            tickets.add_note(session, ticket, body.note, actor=Actor.STAFF)
        session.refresh(ticket)
        return ticket
    except NotFoundError as exc:
        raise _missing(exc) from exc
    except InvalidInputError as exc:
        raise _bad(exc) from exc


# --- customers ---------------------------------------------------------------


@router.get("/customers/{customer_id}", response_model=schemas.CustomerOut)
def get_customer(customer_id: int, session: SessionDep):
    try:
        return customers.get_customer(session, customer_id)
    except NotFoundError as exc:
        raise _missing(exc) from exc


# --- calls -------------------------------------------------------------------


@router.get("/calls", response_model=list[schemas.CallOut])
def list_calls(session: SessionDep, limit: int = 50, offset: int = 0):
    return calls.list_calls(session, limit=limit, offset=offset)


@router.get("/calls/{call_id}", response_model=schemas.CallOut)
def get_call(call_id: str, session: SessionDep):
    try:
        return calls.get_call(session, call_id)
    except NotFoundError as exc:
        raise _missing(exc) from exc


@router.get("/calls/{call_id}/audio")
def get_call_audio(call_id: str, session: SessionDep, settings: SettingsDep):
    try:
        call = calls.get_call(session, call_id)
    except NotFoundError as exc:
        raise _missing(exc) from exc
    file = None
    if call.audio_path:
        try:
            file = LocalRecordingStore(settings.recordings_dir).resolve(call.audio_path)
        except ValueError:
            file = None
    if file is None or not file.is_file():
        raise HTTPException(status_code=404, detail="No audio stored for this call")
    return FileResponse(file, media_type="audio/wav", filename=f"{call_id}.wav")


# --- outbound jobs (admin) ---------------------------------------------------


@router.post("/outbound-jobs", response_model=schemas.OutboundJobOut, status_code=201)
def create_outbound_job(body: schemas.OutboundJobIn, session: SessionDep):
    try:
        return outbound.create_job(
            session,
            message=body.message,
            ticket_ref=body.ticket_ref,
            customer_id=body.customer_id,
            purpose=body.purpose,
        )
    except NotFoundError as exc:
        raise _missing(exc) from exc
    except InvalidInputError as exc:
        raise _bad(exc) from exc


@router.get("/outbound-jobs", response_model=list[schemas.OutboundJobOut])
def list_outbound_jobs(session: SessionDep, status: JobStatus | None = None, limit: int = 100):
    return outbound.list_jobs(session, status=status, limit=limit)


@router.post("/outbound-jobs/{job_id}/dial", response_model=schemas.OutboundJobOut)
async def dial_outbound_job(job_id: int, request: Request):
    """Place the phone call for a queued job through the phone provider (Plivo).

    Database work runs in a worker thread so live call audio on the event loop never waits.
    """
    factory = request.app.state.session_factory
    try:
        job = await run_db(factory, outbound.claim_for_dialling, job_id)
    except NotFoundError as exc:
        raise _missing(exc) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        await request.app.state.dialer.dial(job_id, job.phone)
    except DialError as exc:
        await run_db(factory, outbound.set_job_status, job_id, JobStatus.FAILED, str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await run_db(factory, outbound.get_job, job_id)


@router.post("/outbound-jobs/{job_id}/status", response_model=schemas.OutboundJobOut)
def set_outbound_job_status_admin(
    job_id: int, body: schemas.JobStatusIn, session: SessionDep, force: bool = False
):
    """Staff override, for example to re-queue a failed job.

    A job that is dialling may have a live call, so changing it needs `?force=true` (for a job
    left stuck by a server crash).
    """
    try:
        job = outbound.get_job(session, job_id)
        if job.status == JobStatus.DIALLING and not force:
            raise HTTPException(
                status_code=409,
                detail="Job is dialling and a call may be live; add ?force=true if it is stuck",
            )
        return outbound.set_job_status(session, job_id, body.status, body.outcome_note)
    except NotFoundError as exc:
        raise _missing(exc) from exc


# --- outbound jobs (bridge) --------------------------------------------------


@bridge_router.get("/outbound-jobs/next", response_model=schemas.OutboundJobOut)
def next_outbound_job(session: SessionDep):
    job = outbound.next_queued_job(session)
    if job is None:
        return Response(status_code=204)
    return job


@bridge_router.post("/outbound-jobs/{job_id}/status", response_model=schemas.OutboundJobOut)
def set_outbound_job_status(job_id: int, body: schemas.JobStatusIn, session: SessionDep):
    try:
        return outbound.set_job_status(session, job_id, body.status, body.outcome_note)
    except NotFoundError as exc:
        raise _missing(exc) from exc
