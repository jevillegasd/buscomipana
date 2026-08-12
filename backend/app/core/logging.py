import logging

from app.core.config import get_settings


def configure_logging() -> None:
    # Root logger defaults to WARNING, which silently drops the INFO-level
    # "MOCK SMS to ..." lines MockGateway logs -- without this, there's no way
    # to see a mock OTP/notification in `docker compose logs backend` at all.
    settings = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.is_local else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
