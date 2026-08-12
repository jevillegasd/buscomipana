import pytest

from app.core.config import Settings
from app.core.startup_checks import check_secrets


def _prod_settings(**overrides) -> Settings:
    base = {
        "env": "production",
        "jwt_secret": "a" * 32,
        "admin_session_secret": "b" * 32,
        "analytics_pepper": "c" * 32,
        "sms_gateway": "infobip",
        "infobip_webhook_shared_secret": "d" * 32,
        "database_url": "postgresql+asyncpg://user:realpassword@db:5432/app",
        "cookie_secure": True,
    }
    base.update(overrides)
    return Settings(**base)


def test_check_secrets_is_a_noop_when_env_is_local():
    check_secrets(Settings())  # defaults are all placeholders, but env="local"


def test_check_secrets_passes_with_fully_configured_production_settings():
    check_secrets(_prod_settings())  # should not raise


@pytest.mark.parametrize(
    "overrides",
    [
        {"jwt_secret": "change-me"},
        {"admin_session_secret": "too-short"},
        {"analytics_pepper": "change-me-to-a-long-random-value"},
        {"infobip_webhook_shared_secret": "change-me"},
        {"database_url": "postgresql+asyncpg://bmp:bmp_local_password@postgres:5432/buscomipana"},
        {"cookie_secure": False},
    ],
)
def test_check_secrets_rejects_each_weak_setting(overrides):
    with pytest.raises(RuntimeError, match="Refusing to start"):
        check_secrets(_prod_settings(**overrides))
