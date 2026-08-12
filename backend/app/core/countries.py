"""Which countries BuscoMiPana currently supports, keyed by E.164 calling
code. This is the single source of truth for both the signup/login country
gate (auth_service.request_login_otp) and for picking which privacy policy
document applies to a user (services/policy_service.py) -- expanding to a new
country means adding one entry here plus a policy doc, nothing else."""

CALLING_CODE_TO_COUNTRY = {
    "57": "CO",  # Colombia
    "971": "AE",  # United Arab Emirates
}


def resolve_country(phone_number: str) -> str | None:
    """phone_number is expected in E.164 form (+<calling code><subscriber
    number>, see schemas/common.PhoneNumber). Matches the longest calling
    code first so a future 3-digit code that shares a prefix with a 2-digit
    one (e.g. +5 vs +57) can't be matched by the shorter one instead."""
    digits = phone_number.lstrip("+")
    for code in sorted(CALLING_CODE_TO_COUNTRY, key=len, reverse=True):
        if digits.startswith(code):
            return CALLING_CODE_TO_COUNTRY[code]
    return None


def is_allowed_phone_number(phone_number: str) -> bool:
    return resolve_country(phone_number) is not None
