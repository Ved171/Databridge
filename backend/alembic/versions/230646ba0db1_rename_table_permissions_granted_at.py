"""rename_table_permissions_granted_at

Revision ID: 230646ba0db1
Revises: a30328c4d90e
Create Date: 2026-06-17 11:38:05.819629

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '230646ba0db1'
down_revision: Union[str, None] = 'a30328c4d90e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('table_permissions')]
    if 'granted_at' in columns and 'created_at' not in columns:
        op.alter_column('table_permissions', 'granted_at', new_column_name='created_at')


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('table_permissions')]
    if 'created_at' in columns and 'granted_at' not in columns:
        op.alter_column('table_permissions', 'created_at', new_column_name='granted_at')

