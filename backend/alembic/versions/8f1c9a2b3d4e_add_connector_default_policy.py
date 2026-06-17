"""Add default_policy column to connectors table for F-06 default-deny enforcement.

Revision ID: 8f1c9a2b3d4e
Revises: 7e8c9f0a1b2d
Create Date: 2026-06-08

This migration adds the default_policy column to the connectors table:
- Existing connectors default to 'allow_all' (backward compatible)
- New connectors will default to 'deny_all' (closed by default)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f1c9a2b3d4e'
down_revision = '7e8c9f0a1b2d'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('connectors')]
    if 'default_policy' not in columns:
        # Add default_policy column with server_default='allow_all' for backward compatibility
        op.add_column('connectors', sa.Column('default_policy', sa.String(), nullable=False, server_default='allow_all'))


def downgrade():
    # Remove the column
    op.drop_column('connectors', 'default_policy')
