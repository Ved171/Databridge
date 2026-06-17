"""add_rls_global_settings

Revision ID: b3f7d2e4a891
Revises: a5518a6e5f82
Create Date: 2026-06-15 08:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f7d2e4a891'
down_revision: Union[str, None] = 'a5518a6e5f82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'rls_global_settings' not in tables:
        op.create_table('rls_global_settings',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('key', sa.String(), nullable=False),
            sa.Column('value', sa.String(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('updated_by', sa.UUID(), nullable=True),
            sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('key'),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'rls_global_settings' in tables:
        op.drop_table('rls_global_settings')
