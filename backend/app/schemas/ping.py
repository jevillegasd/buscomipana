import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Channel, PingStatus, PongAudience


class PingCreateIn(BaseModel):
    subject_user_id: uuid.UUID | None = None
    status: PingStatus
    message: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_m: int | None = None


class PingOut(BaseModel):
    id: uuid.UUID
    subject_user_id: uuid.UUID
    reported_by_user_id: uuid.UUID
    is_proxy: bool
    status: PingStatus
    message: str | None
    latitude: float | None
    longitude: float | None
    location_accuracy_m: int | None
    channel: Channel
    created_at: datetime


class PongCreateIn(BaseModel):
    message: str | None = Field(default=None, max_length=500)
    audience: PongAudience = PongAudience.directed


class PongOut(BaseModel):
    id: uuid.UUID
    ping_id: uuid.UUID
    responder_user_id: uuid.UUID
    audience: PongAudience
    message: str | None
    channel: Channel
    created_at: datetime
