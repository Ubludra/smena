"""assignments — teacher-tracked assignments

Revision ID: 20261023_d9e2
Revises: 20261023_b7d1
Create Date: 2026-10-23

No student/submission tables: v1 tracks what the teacher assigned. The
related-material link is SET NULL so library cleanup never destroys
assignment history.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261023_d9e2"
down_revision = "20261023_b7d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("class_name", sa.String(length=32), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("related_material_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_assignments_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["related_material_id"],
            ["materials.id"],
            name=op.f("fk_assignments_related_material_id_materials"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0",
            name=op.f("ck_assignments_title_not_blank"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'done', 'archived')",
            name=op.f("ck_assignments_status_known"),
        ),
    )
    op.create_index(
        "ix_assignments_owner_updated",
        "assignments",
        ["owner_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_assignments_owner_due",
        "assignments",
        ["owner_id", sa.text("due_at")],
    )


def downgrade() -> None:
    op.drop_index("ix_assignments_owner_due", table_name="assignments")
    op.drop_index("ix_assignments_owner_updated", table_name="assignments")
    op.drop_table("assignments")
