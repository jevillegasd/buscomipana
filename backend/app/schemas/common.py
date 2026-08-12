import re
from typing import Annotated

from pydantic import AfterValidator

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def validate_e164(value: str) -> str:
    if not _E164_RE.match(value):
        raise ValueError("phone_number must be in E.164 format, e.g. +573001234567")
    return value


PhoneNumber = Annotated[str, AfterValidator(validate_e164)]
