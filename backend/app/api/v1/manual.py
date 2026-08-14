from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.services import manual_service

router = APIRouter(tags=["manual"])


@router.get("/manual", response_class=HTMLResponse)
async def get_manual() -> HTMLResponse:
    """Public and unauthenticated -- linked from the login screen, before
    anyone has signed in. Single source of truth for the user manual lives
    at app/content/manual.html."""
    return HTMLResponse(content=manual_service.get_manual_html())
