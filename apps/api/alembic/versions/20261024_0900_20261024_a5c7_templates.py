"""templates — reusable payloads for plans, assignments and assessments

Revision ID: 20261024_a5c7
Revises: 20261023_e4f6
Create Date: 2026-10-24

One universal table; payload JSONB is validated against the per-entity
create schema on every write, so the DB never stores content the real
endpoints would reject.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261024_a5c7"
down_revision = "20261023_e4f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_templates")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_templates_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0",
            name=op.f("ck_templates_name_not_blank"),
        ),
        sa.CheckConstraint(
            "entity_type IN ('lesson_plan', 'assignment', 'assessment')",
            name=op.f("ck_templates_entity_type_known"),
        ),
    )
    op.create_index(
        "ix_templates_owner_updated",
        "templates",
        ["owner_id", sa.text("updated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_templates_owner_updated", table_name="templates")
    op.drop_table("templates")
