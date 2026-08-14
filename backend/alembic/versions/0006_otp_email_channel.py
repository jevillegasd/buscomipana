"""otp_verifications: allow 'email' as a channel value

Email is a fallback OTP delivery channel (see auth_service/email_service) for
when SMS is unreliable/blocked for a given carrier or country -- it's only
ever set on otp_verifications.channel, not pings/pongs, so only that table's
check constraint needs updating.

Revision ID: 0006_otp_email_channel
Revises: 0005_otp_external_verification
Create Date: 2026-08-13

"""
from alembic import op

revision = "0006_otp_email_channel"
down_revision = "0005_otp_external_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_otp_channel", "otp_verifications", type_="check")
    op.create_check_constraint(
        "ck_otp_channel", "otp_verifications", "channel IN ('web','sms','ivr_call','ussd','email')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM otp_verifications WHERE channel = 'email'")
    op.drop_constraint("ck_otp_channel", "otp_verifications", type_="check")
    op.create_check_constraint(
        "ck_otp_channel", "otp_verifications", "channel IN ('web','sms','ivr_call','ussd')"
    )
