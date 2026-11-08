"""files: optional attachment to a material

Revision ID: 20261031_c3e5
Revises: 20261025_b2d4
Create Date: 2026-10-31

A file uploaded from a material's page gains a server-validated link to it
(``material_id``, ownership-checked at upload). ON DELETE SET NULL: deleting
the material keeps the blob visible in the «Файлы» drawer — an uploaded
document is never silently destroyed by an unrelated delete. Partial index:
only attached rows are queried together (the vast majority are not).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261031_c3e5"
down_revision = "20261025_b2d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_files_material_id_materials",
        "files",
        "materials",
        ["material_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_files_material",
        "files",
        ["material_id"],
        postgresql_where=sa.text("material_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_files_material", table_name="files")
    op.drop_constraint("fk_files_material_id_materials", "files", type_="foreignkey")
    op.drop_column("files", "material_id")
