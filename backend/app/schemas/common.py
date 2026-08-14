import re
from typing import Annotated

from pydantic import AfterValidator

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
# Deliberately simple (not RFC 5322) -- good enough to catch typos before an
# SMTP round-trip; the real check is whether the send succeeds.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_e164(value: str) -> str:
    if not _E164_RE.match(value):
        raise ValueError("phone_number must be in E.164 format, e.g. +573001234567")
    return value


def validate_email(value: str) -> str:
    if not _EMAIL_RE.match(value):
        raise ValueError("email must be a valid email address")
    return value


PhoneNumber = Annotated[str, AfterValidator(validate_e164)]
EmailAddress = Annotated[str, AfterValidator(validate_email)]
