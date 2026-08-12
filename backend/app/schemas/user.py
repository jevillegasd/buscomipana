import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import BloodType, SexAtBirth, UserRole, UserStatus


class UserMeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone_number: str
    full_name: str | None
    blood_type: BloodType | None
    birth_date: date | None
    national_id_number: str | None
    birth_place: str | None
    nationality: str | None
    sex_at_birth: SexAtBirth | None
    role: UserRole
    status: UserStatus
    created_at: datetime
    has_profile_photo: bool = False


class UserPublicOut(BaseModel):
    """Reduced view of another user -- no phone number. national_id_number is
    only ever populated by the endpoint when the viewer passes
    visibility_service.can_view_location (same trust boundary as location and
    the profile photo); everyone else gets None there, same as location gating
    for pings."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str | None
    blood_type: BloodType | None
    birth_date: date | None
    birth_place: str | None
    nationality: str | None
    sex_at_birth: SexAtBirth | None
    national_id_number: str | None = None
    has_profile_photo: bool = False


class UserUpdateIn(BaseModel):
    full_name: str | None = None
    blood_type: BloodType | None = None
    birth_date: date | None = None
    national_id_number: str | None = None
    birth_place: str | None = None
    nationality: str | None = None
    sex_at_birth: SexAtBirth | None = None
