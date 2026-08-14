"""users: add persistent email association + phone/email verification tracking

Issue #10 fix. Closes an account-takeover hole where an unauthenticated
caller could supply *any* email for *any* phone_number and receive that
number's OTP themselves. Going forward, email-channel OTP delivery only ever
sends to a user's own stored, already-verified email (set via the new
request_email_change/confirm_email_change flow, which requires being
authenticated as that account already) -- never a client-supplied address.

phone_verified_at is backfilled from each phone_number's earliest *consumed*
signup_or_login OTP that was actually delivered over SMS -- accounts with no
such row (i.e. every account that could only have been created through the
vulnerable email-any-address path) come out of this migration with
phone_verified_at still NULL, and will be required to complete a real SMS
verification on next login before phone_verified_at is set (see
auth_service.verify_login_otp) -- effectively revoking any account an
attacker claimed via the hole, since only the real phone's owner can
complete that going forward.

Revision ID: 0007_email_and_phone_verify
Revises: 0006_otp_email_channel
Create Date: 2026-08-13

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_email_and_phone_verify"
down_revision = "0006_otp_email_channel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(320), nullable=True))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))

    # Records which address an email-channel OTP was actually sent to --
    # confirm_email_change checks this matches the new_email being confirmed,
    # so a valid code can only ever confirm the exact address it was sent to.
    op.add_column("otp_verifications", sa.Column("email_address", sa.String(320), nullable=True))

    op.create_index(
        "users_email_active_uq",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND email IS NOT NULL"),
    )

    op.execute(
        """
        UPDATE users u
        SET phone_verified_at = sub.consumed_at
        FROM (
            SELECT DISTINCT ON (phone_number) phone_number, consumed_at
            FROM otp_verifications
            WHERE purpose = 'signup_or_login' AND channel = 'sms' AND consumed_at IS NOT NULL
            ORDER BY phone_number, consumed_at ASC
        ) sub
        WHERE u.phone_number = sub.phone_number
        """
    )

    op.drop_constraint("ck_otp_purpose", "otp_verifications", type_="check")
    op.create_check_constraint(
        "ck_otp_purpose", "otp_verifications", "purpose IN ('signup_or_login','phone_change','email_change')"
    )

    # Mirrors phone_number_changes -- audit trail of every email association/
    # change, each tied to the OTP that proved control of the new address.
    op.create_table(
        "email_changes",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("old_email", sa.String(320)),
        sa.Column("new_email", sa.String(320), nullable=False),
        sa.Column(
            "verified_via_otp_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("otp_verifications.id"),
            nullable=False,
        ),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("email_changes")
    op.execute("DELETE FROM otp_verifications WHERE purpose = 'email_change'")
    op.drop_constraint("ck_otp_purpose", "otp_verifications", type_="check")
    op.create_check_constraint(
        "ck_otp_purpose", "otp_verifications", "purpose IN ('signup_or_login','phone_change')"
    )

    op.drop_column("otp_verifications", "email_address")

    op.drop_index("users_email_active_uq", table_name="users")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email")
