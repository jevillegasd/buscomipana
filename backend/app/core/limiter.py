from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings

settings = get_settings()


def get_client_ip(request: Request) -> str:
    # CF-Connecting-IP is set by Cloudflare's edge and can't be overridden by
    # the client -- Cloudflare always overwrites it, regardless of what a
    # request arrives with. Only trusted when trust_cloudflare_headers is on
    # (see core/config.py), i.e. when the origin is verifiably unreachable
    # except through Cloudflare; otherwise this would let a client spoof
    # their way past the rate limit by just setting the header themselves.
    if settings.trust_cloudflare_headers:
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip)
