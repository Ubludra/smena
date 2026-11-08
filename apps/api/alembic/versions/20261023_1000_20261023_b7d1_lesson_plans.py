"""lesson_plans — teacher lesson plan entity

Revision ID: 20261023_b7d1
Revises: 20261022_a1f3
Create Date: 2026-10-23

One JSONB-backed document entity per the product decision: ``objectives`` and
``stages`` are validated lists stored as JSONB — a plan is written and read
as a single document, child tables would buy nothing for v1.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261023_b7d1"
down_revision = "20261022_a1f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("class_name", sa.String(length=32), nullable=False),
        sa.Column("lesson_date", sa.Date(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column(
            "objectives",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "stages",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("homework", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_plans")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_lesson_plans_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0",
            name=op.f("ck_lesson_plans_title_not_blank"),
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name=op.f("ck_lesson_plans_duration_positive"),
        ),
    )
    op.create_index(
        "ix_lesson_plans_owner_updated",
        "lesson_plans",
        ["owner_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_lesson_plans_owner_date",
        "lesson_plans",
        ["owner_id", sa.text("lesson_date")],
    )


def downgrade() -> None:
    op.drop_index("ix_lesson_plans_owner_date", table_name="lesson_plans")
    op.drop_index("ix_lesson_plans_owner_updated", table_name="lesson_plans")
    op.drop_table("lesson_plans")
