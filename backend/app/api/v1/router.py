from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    debug,
    manual,
    missing_person_reports,
    pings,
    policy,
    relative_links,
    responders,
    search,
    users,
    webhooks_infobip,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(policy.router)
api_router.include_router(manual.router)
api_router.include_router(users.router)
api_router.include_router(relative_links.router)
api_router.include_router(pings.router)
api_router.include_router(missing_person_reports.router)
api_router.include_router(search.router)
api_router.include_router(responders.router)
api_router.include_router(admin.router)
api_router.include_router(webhooks_infobip.router)
api_router.include_router(debug.router)
