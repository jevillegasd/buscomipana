import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RelativeLinkStatus, ResponderCredentialStatus
from app.models.relative_link import RelativeLink, ResponderCredential


async def can_view_location(db: AsyncSession, *, viewer_id: uuid.UUID, subject_id: uuid.UUID) -> bool:
    """Single gate used everywhere a ping's location is serialized, and also
    reused by media_asset_service for profile-photo access (a photo is at
    least as identifying as a lat/lng pair, so it gets the same trust
    boundary). TRUE if the viewer is the subject, an accepted relative_links
    row connects them (either direction), or the viewer holds a verified
    responder credential. Everyone else still sees alive/distress status --
    just not lat/lng (or the photo)."""
    if viewer_id == subject_id:
        return True

    link_result = await db.execute(
        select(RelativeLink.id).where(
            RelativeLink.status == RelativeLinkStatus.accepted,
            or_(
                (RelativeLink.requester_user_id == viewer_id) & (RelativeLink.target_user_id == subject_id),
                (RelativeLink.requester_user_id == subject_id) & (RelativeLink.target_user_id == viewer_id),
            ),
        )
    )
    if link_result.scalar_one_or_none() is not None:
        return True

    responder_result = await db.execute(
        select(ResponderCredential.id).where(
            ResponderCredential.user_id == viewer_id,
            ResponderCredential.status == ResponderCredentialStatus.verified,
        )
    )
    return responder_result.scalar_one_or_none() is not None
