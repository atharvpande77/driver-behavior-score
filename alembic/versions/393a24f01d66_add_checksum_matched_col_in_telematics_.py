"""add checksum_matched col in telematics_events

Revision ID: 393a24f01d66
Revises: 6e475b9b4bc7
Create Date: 2026-06-11 06:53:09.532288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '393a24f01d66'
down_revision: Union[str, Sequence[str], None] = '6e475b9b4bc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('telematics_events', sa.Column('checksum_matched', sa.Boolean(), nullable=True, comment='True if computed checksum matches the received checksum'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('telematics_events', 'checksum_matched')