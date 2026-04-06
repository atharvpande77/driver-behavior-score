"""fix updated_at: challan

Revision ID: 3064b7ba41e3
Revises: 5904ef2cea33
Create Date: 2026-04-06 12:17:17.255992

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3064b7ba41e3'
down_revision: Union[str, Sequence[str], None] = '5904ef2cea33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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
        "challans",
        "updated_at",
        existing_type=sa.TIMESTAMP(),
        server_default=None,
        existing_nullable=False,
    )
