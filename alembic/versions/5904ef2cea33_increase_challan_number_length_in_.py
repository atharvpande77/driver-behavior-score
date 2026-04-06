"""increase challan number length in challans table

Revision ID: 5904ef2cea33
Revises: c0ad646021fb
Create Date: 2026-04-06 12:11:36.674418

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5904ef2cea33'
down_revision: Union[str, Sequence[str], None] = 'c0ad646021fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "challans",
        "source_id",
        existing_type=sa.String(length=16),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "challans_fetch_logs",
        "source_id",
        existing_type=sa.String(length=16),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "challans",
        "updated_at",
        existing_type=sa.TIMESTAMP(),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "challans_fetch_logs",
        "source_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    op.alter_column(
        "challans",
        "source_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    op.alter_column(
        "challans",
        "updated_at",
        existing_type=sa.TIMESTAMP(),
        server_default=None,
        existing_nullable=False,
    )
