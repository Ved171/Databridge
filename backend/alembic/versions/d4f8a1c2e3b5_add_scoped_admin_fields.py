"""add_scoped_admin_fields

Revision ID: d4f8a1c2e3b5
Revises: b3f7d2e4a891
Create Date: 2026-06-16 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f8a1c2e3b5'
down_revision: Union[str, None] = 'b3f7d2e4a891'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. connector_permissions: allow_share_access
    cp_cols = [c['name'] for c in inspector.get_columns('connector_permissions')]
    if 'allow_share_access' not in cp_cols:
        op.add_column('connector_permissions', sa.Column(
            'allow_share_access', sa.Boolean(), nullable=False, server_default=sa.text('false')
        ))

    # 2. connector_permissions: granted_by_user_id
    if 'granted_by_user_id' not in cp_cols:
        op.add_column('connector_permissions', sa.Column(
            'granted_by_user_id', sa.UUID(), nullable=True
        ))
    try:
        op.create_foreign_key(
            'fk_connector_permissions_granted_by',
            'connector_permissions', 'users',
            ['granted_by_user_id'], ['id'],
            ondelete='SET NULL'
        )
    except Exception:
        pass

    # 3. table_permissions: granted_by_user_id
    tp_cols = [c['name'] for c in inspector.get_columns('table_permissions')]
    if 'granted_by_user_id' not in tp_cols:
        op.add_column('table_permissions', sa.Column(
            'granted_by_user_id', sa.UUID(), nullable=True
        ))
    try:
        op.create_foreign_key(
            'fk_table_permissions_granted_by',
            'table_permissions', 'users',
            ['granted_by_user_id'], ['id'],
            ondelete='SET NULL'
        )
    except Exception:
        pass


def downgrade() -> None:
    # 3. table_permissions
    op.drop_constraint('fk_table_permissions_granted_by', 'table_permissions', type_='foreignkey')
    op.drop_column('table_permissions', 'granted_by_user_id')

    # 2. connector_permissions
    op.drop_constraint('fk_connector_permissions_granted_by', 'connector_permissions', type_='foreignkey')
    op.drop_column('connector_permissions', 'granted_by_user_id')

    # 1. connector_permissions
    op.drop_column('connector_permissions', 'allow_share_access')
