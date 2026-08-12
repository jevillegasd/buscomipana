"""rename users.sex_at_birth -> distinguishable_gender, users.birth_place -> residence_place

distinguishable_gender is presentation-based (what a rescuer can observe/use
to identify someone), not a legal/registry fact -- 'intersex' doesn't fit
that framing, so existing 'intersex' rows are folded into 'other' before the
column is renamed. That fold is lossy: downgrade cannot tell which 'other'
rows used to be 'intersex', so it maps all 'other' rows to 'prefer_not_to_say'
instead of guessing.

Revision ID: 0002_rename_gender_and_residence
Revises: 0001_initial_schema
Create Date: 2026-08-12

"""
from alembic import op

revision = "0002_rename_gender_and_residence"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET sex_at_birth = 'other' WHERE sex_at_birth = 'intersex'")
    op.drop_constraint("ck_users_sex_at_birth", "users", type_="check")
    op.alter_column("users", "sex_at_birth", new_column_name="distinguishable_gender")
    op.create_check_constraint(
        "ck_users_distinguishable_gender",
        "users",
        "distinguishable_gender IN ('male','female','other','prefer_not_to_say')",
    )
    op.alter_column("users", "birth_place", new_column_name="residence_place")


def downgrade() -> None:
    op.alter_column("users", "residence_place", new_column_name="birth_place")
    op.drop_constraint("ck_users_distinguishable_gender", "users", type_="check")
    op.execute("UPDATE users SET distinguishable_gender = 'prefer_not_to_say' WHERE distinguishable_gender = 'other'")
    op.alter_column("users", "distinguishable_gender", new_column_name="sex_at_birth")
    op.create_check_constraint(
        "ck_users_sex_at_birth",
        "users",
        "sex_at_birth IN ('male','female','intersex','prefer_not_to_say')",
    )
