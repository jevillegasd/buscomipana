"""Fail-fast guard against shipping local-dev placeholder secrets to a real
deployment. Runs once at process startup (see main.py) and is a no-op for
ENV=local, so it never affects local dev or the test suite (which both run
with the default, unset ENV)."""

_PLACEHOLDER_VALUES = {"change-me", "change-me-to-a-long-random-value"}
_MIN_SECRET_LENGTH = 32
_LOCAL_DEV_DB_PASSWORDS = ("bmp_local_password", "fms_local_password")


def _is_weak(value: str) -> bool:
    return value in _PLACEHOLDER_VALUES or len(value) < _MIN_SECRET_LENGTH


def check_secrets(settings) -> None:
    if settings.is_local:
        return

    problems = []
    for name, value in [
        ("JWT_SECRET", settings.jwt_secret),
        ("ADMIN_SESSION_SECRET", settings.admin_session_secret),
        ("ANALYTICS_PEPPER", settings.analytics_pepper),
    ]:
        if _is_weak(value):
            problems.append(f"{name} is missing, a placeholder, or shorter than {_MIN_SECRET_LENGTH} characters")

    if settings.sms_gateway == "infobip" and _is_weak(settings.infobip_webhook_shared_secret):
        problems.append(
            f"INFOBIP_WEBHOOK_SHARED_SECRET is missing, a placeholder, or shorter than {_MIN_SECRET_LENGTH} characters"
        )

    if any(pw in settings.database_url for pw in _LOCAL_DEV_DB_PASSWORDS):
        problems.append("DATABASE_URL still contains the local-dev default Postgres password")

    if not settings.cookie_secure:
        problems.append("COOKIE_SECURE is false -- auth cookies would be sent over plain HTTP")

    if problems:
        bullet_list = "\n".join(f"  - {p}" for p in problems)
        raise RuntimeError(
            f"Refusing to start with ENV={settings.env!r} and insecure configuration:\n{bullet_list}\n"
            "Generate real secrets (e.g. `python -c \"import secrets;"
            ' print(secrets.token_urlsafe(48))"`) and set them via environment variables before deploying.'
        )
