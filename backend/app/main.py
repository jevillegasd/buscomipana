from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.admin import register_admin
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.logging import configure_logging
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.startup_checks import check_secrets

configure_logging()
settings = get_settings()
check_secrets(settings)

app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.1.0",
    # The interactive docs pull JS/CSS from a CDN and hand out the full API
    # surface/schema -- fine for local dev, not something to leave open on a
    # deployed instance.
    docs_url="/docs" if settings.is_local else None,
    redoc_url="/redoc" if settings.is_local else None,
    openapi_url="/openapi.json" if settings.is_local else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    # A wildcard origin is rejected by browsers once credentials are allowed, so
    # this must be an explicit origin -- the frontend now authenticates via an
    # HttpOnly cookie (see api/v1/auth.py), which requires allow_credentials.
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
# Separate signing key from the JWT secret -- these protect two different
# trust boundaries (API bearer tokens vs. the SQLAdmin browser session), and
# reusing one key for both means compromising either secret compromises both.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.admin_session_secret,
    https_only=settings.cookie_secure,
)

app.include_router(api_router)
register_admin(app)


@app.get("/health")
async def health():
    return {"status": "ok"}
