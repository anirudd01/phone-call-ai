"""Phone number and car registration normalisation."""

from __future__ import annotations

import re

import phonenumbers

from carwash_voice.domain.errors import InvalidInputError

DEFAULT_REGION = "IN"


def normalize_phone(raw: str | None) -> str | None:
    """Return the number in E.164 (India is the default region), or None if blank.

    Raises InvalidInputError when the text is not a valid phone number.
    """
    if raw is None or not raw.strip():
        return None
    try:
        parsed = phonenumbers.parse(raw.strip(), DEFAULT_REGION)
    except phonenumbers.NumberParseException as exc:
        raise InvalidInputError(f"'{raw}' is not a valid phone number") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise InvalidInputError(f"'{raw}' is not a valid phone number")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def normalize_registration(raw: str | None) -> str | None:
    """Upper-case a car registration and drop spaces and hyphens (KA 01 AB 1234 -> KA01AB1234)."""
    if raw is None:
        return None
    cleaned = re.sub(r"[\s\-]", "", raw).upper()
    return cleaned or None
