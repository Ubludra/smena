"""assessments & assessment_questions — teacher assessments («Проверочные»)

Revision ID: 20261023_e4f6
Revises: 20261023_d9e2
Create Date: 2026-10-23

Questions live in their own ordered table, cascade-deleted with the parent;
options and the answer key are JSONB columns validated by Pydantic before
they reach the ORM.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261023_e4f6"
down_revision = "20261023_d9e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("class_name", sa.String(length=32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "is_protected", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessments")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_assessments_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0",
            name=op.f("ck_assessments_title_not_blank"),
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name=op.f("ck_assessments_duration_positive"),
        ),
    )
    op.create_index(
        "ix_assessments_owner_updated",
        "assessments",
        ["owner_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_assessments_owner_protected",
        "assessments",
        ["owner_id", sa.text("is_protected")],
    )

    op.create_table(
        "assessment_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "correct",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_questions")),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessments.id"],
            name=op.f("fk_assessment_questions_assessment_id_assessments"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "length(btrim(text)) > 0",
            name=op.f("ck_assessment_questions_text_not_blank"),
        ),
    )
    op.create_index(
        "ix_assessment_questions_assessment",
        "assessment_questions",
        ["assessment_id", sa.text("order_index")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assessment_questions_assessment", table_name="assessment_questions"
    )
    op.drop_table("assessment_questions")
    op.drop_index("ix_assessments_owner_protected", table_name="assessments")
    op.drop_index("ix_assessments_owner_updated", table_name="assessments")
    op.drop_table("assessments")
