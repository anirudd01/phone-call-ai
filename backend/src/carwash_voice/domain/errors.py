"""Domain errors, mapped to HTTP statuses by the API and to spoken replies by the tools."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for expected, user-facing problems."""


class NotFoundError(DomainError):
    pass


class InvalidInputError(DomainError):
    pass


class ConflictError(DomainError):
    """The record is not in a state that allows the change (for example, already dialling)."""
