import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import RelationshipType, RelativeLinkStatus
from app.schemas.common import PhoneNumber


class RelativeLinkRequestIn(BaseModel):
    target_phone_number: PhoneNumber
    relationship_label: RelationshipType | None = None


class RelativeLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_user_id: uuid.UUID
    target_user_id: uuid.UUID
    relationship_label: RelationshipType | None
    status: RelativeLinkStatus
    requested_at: datetime
    responded_at: datetime | None
