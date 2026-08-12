from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"

    # Display brand name (used in the FastAPI title, OTP/notification SMS text)
    # vs. the lowercase slug used for identifiers (DB name, docker project name,
    # package names) -- kept as one setting rather than duplicated literals so
    # a future rebrand doesn't mean re-grepping the codebase again.
    app_name: str = "Buscomipana"

    database_url: str = "postgresql+asyncpg://fms:fms_local_password@localhost:5432/buscomipana"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"
    jwt_access_token_ttl_minutes: int = 30
    jwt_refresh_token_ttl_days: int = 30

    # Separate from jwt_secret on purpose -- it signs the SQLAdmin ops panel's
    # browser session cookie, a different trust boundary than API bearer
    # tokens, so the two secrets must be able to be rotated independently and
    # a leak of one must not compromise the other.
    admin_session_secret: str = "change-me"

    analytics_pepper: str = "change-me"
    analytics_pepper_version: int = 1

    sms_gateway: str = "mock"
    infobip_base_url: str = ""
    infobip_api_key: str = ""
    infobip_sender_id: str = "Buscomipana"
    infobip_webhook_shared_secret: str = "change-me"

    # OTP codes go through Infobip's dedicated 2FA product (/2fa/2/...), not
    # the generic SMS API -- several Colombian carriers reject OTP traffic
    # sent over the generic route ("Account not provisioned for the
    # requested channel", error 592 / REJECTED_NETWORK). Leave both blank to
    # have InfobipGateway auto-provision a 2FA Application + Message
    # Template on first use (see infobip_gateway.py); once provisioned it
    # logs the IDs so they can be pinned here instead of re-provisioning a
    # new pair on every process restart.
    infobip_2fa_application_id: str = ""
    infobip_2fa_message_id: str = ""

    admin_phone_numbers: str = ""

    otp_code_length: int = 6
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5
    # Minimum time between two OTP sends for the same phone number+purpose --
    # separate from the per-IP slowapi rate limit on the endpoint, this caps
    # SMS spend even from a single caller retrying aggressively. The frontend
    # surfaces this as a disabled "Reenviar código" button with a countdown.
    otp_resend_cooldown_seconds: int = 60

    # "Remember this browser" cookie: minted on logout (see auth_service.
    # remember_device), lets a later /auth/otp/request from the same browser
    # for the same phone number skip sending/verifying a code entirely.
    remember_device_cookie_name: str = "bmp_remember_device"
    remember_device_ttl_days: int = 10

    # Browser clients authenticate via HttpOnly cookies (set alongside the JSON
    # token response) so a page reload doesn't need JS to manage tokens at all.
    # Non-browser clients (mobile, tests, third-party integrations) keep using
    # the Authorization: Bearer header from the JSON body -- both are accepted
    # by get_current_user.
    frontend_origin: str = "http://localhost:5173"
    access_token_cookie_name: str = "bmp_access_token"
    refresh_token_cookie_name: str = "bmp_refresh_token"
    cookie_secure: bool = False

    # When the deployment sits behind Cloudflare (Tunnel or proxied DNS), every
    # request carries a CF-Connecting-IP header set by Cloudflare's edge -- the
    # per-IP rate limiter (core/limiter.py) needs that instead of the raw
    # socket peer, which would otherwise just be Caddy/cloudflared's address
    # for every request. Only ever enable this when the origin is verifiably
    # unreachable except through Cloudflare (e.g. Tunnel with no published
    # host ports) -- otherwise a client can set this header themselves and
    # spoof their way past the rate limit entirely.
    trust_cloudflare_headers: bool = False

    # Media storage: local | s3. Local writes under media_local_path (a mounted
    # volume in docker-compose); s3 is the production-ready path but is
    # unverified in this environment (no AWS credentials to test against).
    media_storage_backend: str = "local"
    media_local_path: str = "./media"
    media_max_upload_bytes: int = 8 * 1024 * 1024
    media_s3_bucket: str = ""
    media_s3_region: str = "us-east-1"
    media_s3_access_key_id: str = ""
    media_s3_secret_access_key: str = ""
    media_s3_endpoint_url: str = ""

    @property
    def is_local(self) -> bool:
        return self.env == "local"

    @property
    def admin_phone_number_list(self) -> list[str]:
        return [p.strip() for p in self.admin_phone_numbers.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
