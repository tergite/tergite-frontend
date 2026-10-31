"""Store the backends' websocket nonces

Revision ID: c001c281888c
Revises: a86487b30732
Create Date: 2026-10-31 03:27:08.357827

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import libs.storage.sql.tables

# revision identifiers, used by Alembic.
revision: str = "c001c281888c"
down_revision: Union[str, Sequence[str], None] = "a86487b30732"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "bcc_nonces",
        sa.Column(
            "row_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("device_name", sa.String(), nullable=True),
        sa.Column(
            "expires_at",
            libs.storage.sql.tables.UtcDateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("nonce"),
    )
    with op.batch_alter_table("bcc_nonces", schema=None) as batch_op:
        batch_op.create_index("ix_bcc_nonces_expires_at", ["expires_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("bcc_nonces", schema=None) as batch_op:
        batch_op.drop_index("ix_bcc_nonces_expires_at")

    op.drop_table("bcc_nonces")
