"""Add license fields to models

Revision ID: 2bdc9f07c75e
Revises: 0001_core_data_layer
Create Date: 2026-05-31 05:02:47.495271
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "2bdc9f07c75e"
down_revision: str | None = "0001_core_data_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("models")}
    with op.batch_alter_table("models") as batch_op:
        if "actual_license" not in existing:
            batch_op.add_column(sa.Column("actual_license", sa.String(length=160)))
        if "user_license_notes" not in existing:
            batch_op.add_column(sa.Column("user_license_notes", sa.Text()))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("models")}
    with op.batch_alter_table("models") as batch_op:
        if "user_license_notes" in existing:
            batch_op.drop_column("user_license_notes")
        if "actual_license" in existing:
            batch_op.drop_column("actual_license")
