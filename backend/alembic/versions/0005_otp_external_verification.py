"""otp_verifications: support provider-managed OTPs (Infobip 2FA)

code_hash becomes nullable and external_reference is added -- a
provider-managed OTP (see NotificationGateway.verifies_otp_externally) never
gives this app the actual code to hash, only an opaque handle (e.g.
Infobip's pinId) to check against the provider's own verify endpoint later.

Revision ID: 0005_otp_external_verification
Revises: 0004_relative_link_unclaimed
Create Date: 2026-08-13

"""
import sqlalchemy as sa

from alembic import op

revision = "0005_otp_external_verification"
down_revision = "0004_relative_link_unclaimed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("otp_verifications", sa.Column("external_reference", sa.String(64)))
    op.alter_column("otp_verifications", "code_hash", nullable=True)


def downgrade() -> None:
    # Rows sent through a provider-managed OTP have no code_hash to restore --
    # they're deleted rather than left violating the restored NOT NULL.
    op.execute("DELETE FROM otp_verifications WHERE code_hash IS NULL")
    op.alter_column("otp_verifications", "code_hash", nullable=False)
    op.drop_column("otp_verifications", "external_reference")
