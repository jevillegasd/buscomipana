from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import BloodType, SexAtBirth, UserRole, UserStatus
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.types import str_enum


class User(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "users_phone_active_uq",
            "phone_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    blood_type: Mapped[BloodType | None] = mapped_column(str_enum(BloodType, 6))
    birth_date: Mapped[date | None] = mapped_column(Date)
    national_id_number: Mapped[str | None] = mapped_column(String(50))
    birth_place: Mapped[str | None] = mapped_column(String(200))
    nationality: Mapped[str | None] = mapped_column(String(100))
    sex_at_birth: Mapped[SexAtBirth | None] = mapped_column(str_enum(SexAtBirth, 20))
    # No FK here to the current profile photo -- media_asset_service looks up
    # the most recent media_assets row for (owner_user_id, purpose=profile_photo)
    # instead, the same "latest X for this user" pattern matching_service.py
    # already uses for ping locations. Avoids a circular FK with media_assets
    # (which itself references users.id) and lets photo history be queried
    # without a migration every time the "current" pointer would need updating.
    role: Mapped[UserRole] = mapped_column(str_enum(UserRole, 20), nullable=False, default=UserRole.user)
    status: Mapped[UserStatus] = mapped_column(
        str_enum(UserStatus, 20), nullable=False, default=UserStatus.active
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
