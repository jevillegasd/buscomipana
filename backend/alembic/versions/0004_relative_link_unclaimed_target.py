"""relative_links: allow an unclaimed target (no account yet)

target_user_id becomes nullable and a target_phone_number column is added --
requesting a relative link for a phone number with no account yet now
creates a "pending, unclaimed" row (target_user_id NULL, target_phone_number
set) instead of being rejected outright. See
relative_link_service.request_link / resolve_open_links_for_new_user.

Revision ID: 0004_relative_link_unclaimed
Revises: 0003_add_policy_acceptances
Create Date: 2026-08-12

"""
import sqlalchemy as sa

from alembic import op

revision = "0004_relative_link_unclaimed"
down_revision = "0003_add_policy_acceptances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("relative_links", sa.Column("target_phone_number", sa.String(32)))
    op.alter_column("relative_links", "target_user_id", nullable=True)
    op.create_check_constraint(
        "ck_relative_link_target_present",
        "relative_links",
        "target_user_id IS NOT NULL OR target_phone_number IS NOT NULL",
    )
    # Prevents the same requester from filing two pending requests against the
    # same not-yet-registered number -- a plain unique constraint on
    # (requester_user_id, target_phone_number) can't do this because most rows
    # have target_phone_number NULL (claimed links), so it's scoped to exactly
    # the unclaimed rows this is meant to dedupe.
    op.create_index(
        "uq_relative_link_pending_phone",
        "relative_links",
        ["requester_user_id", "target_phone_number"],
        unique=True,
        postgresql_where=sa.text("target_user_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_relative_link_pending_phone", table_name="relative_links")
    op.drop_constraint("ck_relative_link_target_present", "relative_links", type_="check")
    # Unclaimed rows have no target_user_id -- can't be restored to NOT NULL
    # without deleting them first, since they'd violate the constraint.
    op.execute("DELETE FROM relative_links WHERE target_user_id IS NULL")
    op.alter_column("relative_links", "target_user_id", nullable=False)
    op.drop_column("relative_links", "target_phone_number")
