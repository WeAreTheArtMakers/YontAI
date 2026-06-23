"""core data layer

Revision ID: 0001_core_data_layer
Revises:
Create Date: 2026-05-31
"""

from collections.abc import Sequence

from alembic import op

from yontai.db import models as _models  # noqa: F401
from yontai.db.base import Base

revision: str = "0001_core_data_layer"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
