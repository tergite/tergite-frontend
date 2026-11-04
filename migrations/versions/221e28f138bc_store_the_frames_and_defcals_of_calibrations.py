"""Store the frames and defcals of calibrations

Revision ID: 221e28f138bc
Revises: 136bb71e3a90
Create Date: 2026-11-03 15:04:36.722899

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "221e28f138bc"
down_revision: Union[str, Sequence[str], None] = "136bb71e3a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("calibrations", "calibrations_logs")
_COLUMNS = ("frames", "defcals")


def upgrade() -> None:
    """Upgrade schema: calibrations may carry the device's frames and its gates' defcals"""
    for table in _TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in _COLUMNS:
                batch_op.add_column(
                    sa.Column(column, sa.JSON(none_as_null=True), nullable=True)
                )


def downgrade() -> None:
    """Downgrade schema."""
    for table in reversed(_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in reversed(_COLUMNS):
                batch_op.drop_column(column)
