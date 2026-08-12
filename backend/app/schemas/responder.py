import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ResponderCredentialStatus


class ResponderApplyIn(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)
    credential_type: str = Field(min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)


class ResponderCredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    organization_name: str
    credential_type: str
    status: ResponderCredentialStatus
    verified_by_admin_id: uuid.UUID | None
    verified_at: datetime | None
    notes: str | None
