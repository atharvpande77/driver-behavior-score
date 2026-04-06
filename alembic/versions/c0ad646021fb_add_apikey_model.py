"""add APIKey model

Revision ID: c0ad646021fb
Revises: 388e93fc9a83
Create Date: 2026-04-05 22:23:43.239895

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0ad646021fb'
down_revision: Union[str, Sequence[str], None] = '388e93fc9a83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('dashboard_users', sa.Column('id', sa.UUID(), nullable=True))
    op.execute(sa.text("UPDATE dashboard_users SET id = gen_random_uuid() WHERE id IS NULL"))
    op.alter_column('dashboard_users', 'id', nullable=False, server_default=sa.text('gen_random_uuid()'))
    op.drop_constraint('dashboard_users_pkey', 'dashboard_users', type_='primary')
    op.create_primary_key('dashboard_users_pkey', 'dashboard_users', ['id'])
    op.create_unique_constraint('uq_dashboard_users_email', 'dashboard_users', ['email'])

    op.create_table(
        'api_keys',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('key_prefix', sa.String(length=16), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['dashboard_users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash', name='uq_api_keys_key_hash'),
    )
    op.create_index('ix_api_keys_created_by', 'api_keys', ['created_by'], unique=False)
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_api_keys_key_hash', table_name='api_keys')
    op.drop_index('ix_api_keys_created_by', table_name='api_keys')
    op.drop_table('api_keys')
    op.drop_constraint('uq_dashboard_users_email', 'dashboard_users', type_='unique')
    op.drop_constraint('dashboard_users_pkey', 'dashboard_users', type_='primary')
    op.create_primary_key('dashboard_users_pkey', 'dashboard_users', ['email'])
    op.alter_column('dashboard_users', 'id', server_default=None)
    op.drop_column('dashboard_users', 'id')
