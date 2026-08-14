import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("services.email")

settings = get_settings()


def render_otp_email_subject() -> str:
    return f"Tu código de {settings.app_name}"


def render_otp_email_body(code: str) -> str:
    return (
        f"Tu código de verificación de {settings.app_name} es: {code}\n\n"
        f"Este código vence en {settings.otp_ttl_minutes} minutos. Si no lo solicitaste, "
        "ignora este mensaje."
    )


def _send_sync(to_address: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address
    message["To"] = to_address
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)


async def send_otp_email(to_address: str, code: str) -> bool:
    """Returns whether the SMTP send succeeded -- never raises, mirroring how
    NotificationGateway.send_* reports failure via GatewaySendResult.accepted
    instead of an exception (see auth_service._create_and_send_otp)."""
    try:
        await asyncio.to_thread(
            _send_sync, to_address, render_otp_email_subject(), render_otp_email_body(code)
        )
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("OTP email send failed for %s: %s", to_address, exc)
        return False
