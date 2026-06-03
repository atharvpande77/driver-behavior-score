"""add source ip and source port to telematics events

Revision ID: 0f1d7b7e8c21
Revises: 7b2506f3fcc3
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0f1d7b7e8c21"
down_revision: Union[str, Sequence[str], None] = "7b2506f3fcc3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("telematics_events", sa.Column("source_ip", sa.String(length=64), nullable=True))
    op.add_column("telematics_events", sa.Column("source_port", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("telematics_events", "source_port")
    op.drop_column("telematics_events", "source_ip")
