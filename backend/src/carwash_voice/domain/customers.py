"""Customer service: lookup and upsert."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from carwash_voice.db.models import Customer
from carwash_voice.domain.errors import InvalidInputError, NotFoundError
from carwash_voice.domain.phone import normalize_phone, normalize_registration


def get_customer(session: Session, customer_id: int) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} not found")
    return customer


def find_customer(
    session: Session, phone: str | None = None, car_registration: str | None = None
) -> Customer | None:
    """Find by phone first, then by car registration."""
    norm_phone = normalize_phone(phone)
    if norm_phone:
        found = session.scalar(select(Customer).where(Customer.phone == norm_phone))
        if found:
            return found
    reg = normalize_registration(car_registration)
    if reg:
        return session.scalar(
            select(Customer).where(Customer.car_registration == reg).order_by(Customer.id)
        )
    return None


def upsert_customer(
    session: Session,
    name: str | None = None,
    phone: str | None = None,
    car_registration: str | None = None,
    preferred_language: str | None = None,
) -> Customer:
    """Create a customer or update the matching one (by phone, else registration).

    Only the fields that are provided overwrite stored values.
    """
    norm_phone = normalize_phone(phone)
    reg = normalize_registration(car_registration)
    if not any([name, norm_phone, reg]):
        raise InvalidInputError("Need at least a name, phone or car registration")

    customer = find_customer(session, phone=norm_phone, car_registration=reg)
    if customer is None:
        customer = Customer()
        session.add(customer)
    for attr, value in (
        ("name", name.strip() if name else None),
        ("phone", norm_phone),
        ("car_registration", reg),
        ("preferred_language", preferred_language),
    ):
        if value:
            setattr(customer, attr, value)
    session.commit()
    return customer
