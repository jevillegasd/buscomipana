"""initial schema: extensions + all core tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-11

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

RELATIONSHIP_TYPES = (
    "parent", "child", "sibling", "spouse", "grandparent", "grandchild",
    "aunt_or_uncle", "niece_or_nephew", "cousin", "guardian", "friend", "other",
)
_RELATIONSHIP_TYPES_SQL = ",".join(f"'{v}'" for v in RELATIONSHIP_TYPES)


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "fuzzystrmatch"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "cube"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "earthdistance"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("full_name", sa.String(200)),
        sa.Column("blood_type", sa.String(6)),
        sa.Column("birth_date", sa.Date),
        sa.Column("national_id_number", sa.String(50)),
        sa.Column("birth_place", sa.String(200)),
        sa.Column("nationality", sa.String(100)),
        sa.Column("sex_at_birth", sa.String(20)),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "blood_type IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')", name="ck_users_blood_type"
        ),
        sa.CheckConstraint("role IN ('user','responder','admin')", name="ck_users_role"),
        sa.CheckConstraint("status IN ('active','deactivated')", name="ck_users_status"),
        sa.CheckConstraint(
            "sex_at_birth IN ('male','female','intersex','prefer_not_to_say')", name="ck_users_sex_at_birth"
        ),
    )
    op.create_index(
        "users_phone_active_uq", "users", ["phone_number"], unique=True, postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index("ix_users_full_name_trgm", "users", ["full_name"], postgresql_using="gin", postgresql_ops={"full_name": "gin_trgm_ops"})

    op.create_table(
        "otp_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("code_hash", sa.String(200), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="sms"),
        sa.Column("attempt_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("purpose IN ('signup_or_login','phone_change')", name="ck_otp_purpose"),
        sa.CheckConstraint("channel IN ('web','sms','ivr_call','ussd')", name="ck_otp_channel"),
    )
    op.create_index("ix_otp_phone_purpose_expires", "otp_verifications", ["phone_number", "purpose", "expires_at"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("device_label", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "trusted_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_trusted_devices_phone", "trusted_devices", ["phone_number"])

    op.create_table(
        "phone_number_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("old_phone_number", sa.String(32), nullable=False),
        sa.Column("new_phone_number", sa.String(32), nullable=False),
        sa.Column("verified_via_otp_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("otp_verifications.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "relative_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("requester_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("relationship_label", sa.String(20)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("requester_user_id", "target_user_id", name="uq_relative_link_pair"),
        sa.CheckConstraint("requester_user_id <> target_user_id", name="ck_relative_link_no_self"),
        sa.CheckConstraint("status IN ('pending','accepted','declined','revoked')", name="ck_relative_link_status"),
        sa.CheckConstraint(
            f"relationship_label IS NULL OR relationship_label IN ({_RELATIONSHIP_TYPES_SQL})",
            name="ck_relative_link_relationship",
        ),
    )

    op.create_table(
        "responder_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("organization_name", sa.String(200), nullable=False),
        sa.Column("credential_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("verified_by_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.String(1000)),
        sa.CheckConstraint("status IN ('pending','verified','revoked')", name="ck_responder_credential_status"),
    )

    op.create_table(
        "pings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("subject_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reported_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "is_proxy",
            sa.Boolean,
            sa.Computed("reported_by_user_id IS DISTINCT FROM subject_user_id", persisted=True),
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("message", sa.String(500)),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("location_accuracy_m", sa.Integer),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("channel_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('ok','distress','unknown')", name="ck_pings_status"),
        sa.CheckConstraint("channel IN ('web','sms','ivr_call','ussd')", name="ck_pings_channel"),
    )
    op.create_index("ix_pings_subject_created", "pings", ["subject_user_id", "created_at"])
    op.create_index("ix_pings_reported_by_created", "pings", ["reported_by_user_id", "created_at"])

    op.create_table(
        "pongs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("ping_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pings.id"), nullable=False),
        sa.Column("responder_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("message", sa.String(500)),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("audience IN ('directed','broadcast')", name="ck_pongs_audience"),
        sa.CheckConstraint("channel IN ('web','sms','ivr_call','ussd')", name="ck_pongs_channel"),
    )
    op.create_index("ix_pongs_ping_id", "pongs", ["ping_id"])

    op.create_table(
        "missing_person_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("reporter_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_full_name", sa.String(200), nullable=False),
        sa.Column("subject_phone_number", sa.String(32), nullable=False),
        sa.Column("relationship", sa.String(20)),
        sa.Column("last_known_latitude", sa.Numeric(9, 6)),
        sa.Column("last_known_longitude", sa.Numeric(9, 6)),
        sa.Column("missing_since", sa.Date),
        sa.Column("missing_location_description", sa.String(300)),
        sa.Column("last_known_clothing", sa.String(500)),
        sa.Column("body_marks", sa.String(500)),
        sa.Column("notes", sa.String(1000)),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("matched_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("matched_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open','matched','closed')", name="ck_missing_report_status"),
        sa.CheckConstraint(
            f"relationship IS NULL OR relationship IN ({_RELATIONSHIP_TYPES_SQL})",
            name="ck_missing_report_relationship",
        ),
    )
    op.create_index("ix_missing_person_reports_reporter", "missing_person_reports", ["reporter_user_id"])
    op.create_index(
        "ix_missing_person_reports_name_trgm",
        "missing_person_reports",
        ["subject_full_name"],
        postgresql_using="gin",
        postgresql_ops={"subject_full_name": "gin_trgm_ops"},
    )

    op.create_table(
        "missing_person_match_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("missing_person_reports.id"), nullable=False),
        sa.Column("candidate_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("phone_similarity_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("name_similarity_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("location_score", sa.Numeric(4, 3)),
        sa.Column("combined_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("confirmed", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("report_id", "candidate_user_id", name="uq_report_candidate"),
    )
    op.create_index("ix_candidates_report_score", "missing_person_match_candidates", ["report_id", "combined_score"])

    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "missing_person_report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("missing_person_reports.id"),
            unique=True,
        ),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("storage_backend", sa.String(10), nullable=False),
        sa.Column("storage_key", sa.String(300), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("consent_public_use", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("consent_ai_processing", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("consent_recorded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("purpose IN ('profile_photo','missing_person_photo')", name="ck_media_assets_purpose"),
        sa.CheckConstraint("storage_backend IN ('local','s3')", name="ck_media_assets_storage_backend"),
    )
    op.create_index("ix_media_assets_owner_purpose", "media_assets", ["owner_user_id", "purpose", "created_at"])

    op.create_table(
        "inbound_sms_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("provider_message_id", sa.String(200), nullable=False, unique=True),
        sa.Column("from_phone_number", sa.String(32), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("parsed_intent", sa.String(20)),
        sa.Column("resulting_ping_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pings.id")),
        sa.Column("raw_payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "parsed_intent IN ('ping_ok','ping_sos','pong','unrecognized')", name="ck_inbound_sms_intent"
        ),
    )

    op.create_table(
        "sms_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("to_phone_number", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="infobip"),
        sa.Column("provider_message_id", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(1000)),
        sa.Column("related_ping_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pings.id")),
        sa.Column("related_otp_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("otp_verifications.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "purpose IN ('otp','ping_notification','pong_notification','missing_person_match')",
            name="ck_sms_outbox_purpose",
        ),
        sa.CheckConstraint("status IN ('queued','sent','delivered','failed')", name="ck_sms_outbox_status"),
    )

    op.create_table(
        "ping_analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("ping_ref_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("pepper_version", sa.SmallInteger, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("is_proxy", sa.Boolean, nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("ping_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_pong_latency_seconds", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ping_analytics_created", "ping_analytics_events", ["ping_created_at"])
    op.create_index("ix_ping_analytics_subject_hash", "ping_analytics_events", ["subject_hash"])


def downgrade() -> None:
    op.drop_table("ping_analytics_events")
    op.drop_table("sms_outbox")
    op.drop_table("inbound_sms_messages")
    op.drop_table("media_assets")
    op.drop_table("missing_person_match_candidates")
    op.drop_table("missing_person_reports")
    op.drop_table("pongs")
    op.drop_table("pings")
    op.drop_table("responder_credentials")
    op.drop_table("relative_links")
    op.drop_table("phone_number_changes")
    op.drop_table("trusted_devices")
    op.drop_table("auth_sessions")
    op.drop_table("otp_verifications")
    op.drop_table("users")
