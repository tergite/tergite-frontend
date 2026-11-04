"""Drop the context class of notice templates

Revision ID: 01f3a918b5dd
Revises: b109440758fe
Create Date: 2026-10-26 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "01f3a918b5dd"
down_revision: Union[str, Sequence[str], None] = "b109440758fe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("notice_templates", schema=None) as batch_op:
        batch_op.drop_column("context_cls_path")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("notice_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("context_cls_path", sa.VARCHAR(), nullable=True))
