"""rename_table_permissions_user_id

Revision ID: a30328c4d90e
Revises: 158dde6cb598
Create Date: 2026-06-17 11:29:35.016886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a30328c4d90e'
down_revision: Union[str, None] = '158dde6cb598'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('table_permissions')]
    if 'user_id' in columns and 'applies_to_user_id' not in columns:
        op.alter_column('table_permissions', 'user_id', new_column_name='applies_to_user_id')


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('table_permissions')]
    if 'applies_to_user_id' in columns and 'user_id' not in columns:
        op.alter_column('table_permissions', 'applies_to_user_id', new_column_name='user_id')

