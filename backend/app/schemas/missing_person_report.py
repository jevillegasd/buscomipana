import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MissingPersonReportStatus, RelationshipType
from app.schemas.common import PhoneNumber


class MissingPersonReportCreateIn(BaseModel):
    subject_full_name: str = Field(min_length=1, max_length=200)
    subject_phone_number: PhoneNumber
    relationship: RelationshipType | None = None
    notes: str | None = Field(default=None, max_length=1000)
    last_known_latitude: float | None = Field(default=None, ge=-90, le=90)
    last_known_longitude: float | None = Field(default=None, ge=-180, le=180)
    missing_since: date | None = None
    missing_location_description: str | None = Field(default=None, max_length=300)
    last_known_clothing: str | None = Field(default=None, max_length=500)
    body_marks: str | None = Field(default=None, max_length=500)


class MissingPersonReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reporter_user_id: uuid.UUID
    subject_full_name: str
    subject_phone_number: str
    relationship: RelationshipType | None
    notes: str | None
    last_known_latitude: float | None
    last_known_longitude: float | None
    missing_since: date | None
    missing_location_description: str | None
    last_known_clothing: str | None
    body_marks: str | None
    status: MissingPersonReportStatus
    matched_user_id: uuid.UUID | None
    matched_at: datetime | None
    created_at: datetime
    has_photo: bool = False


class MissingPersonMatchCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    candidate_user_id: uuid.UUID
    phone_similarity_score: float
    name_similarity_score: float
    location_score: float | None
    combined_score: float
    confirmed: bool | None
    created_at: datetime
