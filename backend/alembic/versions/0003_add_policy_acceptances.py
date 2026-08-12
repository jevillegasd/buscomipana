"""add policy_acceptances table

Revision ID: 0003_add_policy_acceptances
Revises: 0002_rename_gender_and_residence
Create Date: 2026-08-12

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_add_policy_acceptances"
down_revision = "0002_rename_gender_and_residence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("policy_country", sa.String(2), nullable=False),
        sa.Column("policy_version", sa.String(20), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_policy_acceptances_user", "policy_acceptances", ["user_id", "accepted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_policy_acceptances_user", table_name="policy_acceptances")
    op.drop_table("policy_acceptances")
