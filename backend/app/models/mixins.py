import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    # default=uuid.uuid4 generates the id client-side so the ORM has it available
    # immediately after flush (needed before commit) and so tests can run against
    # SQLite, which has no gen_random_uuid(). server_default remains a safety net
    # for rows inserted outside the ORM.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
