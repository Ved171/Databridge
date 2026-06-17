"""add_user_invite_tokens

Revision ID: c4ec42c60dc6
Revises: a298413ab9bf
Create Date: 2026-06-08 11:39:57.622050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4ec42c60dc6'
down_revision: Union[str, None] = 'a298413ab9bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Add columns to users table (initially nullable to allow data migration)
    users_columns = [c['name'] for c in inspector.get_columns('users')]
    if 'force_password_change' not in users_columns:
        op.add_column('users', sa.Column('force_password_change', sa.Boolean(), nullable=True))
    if 'token_version' not in users_columns:
        op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=True))
    if 'deleted_at' not in users_columns:
        op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    # 2. Set default values for all existing user rows
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE users "
            "SET is_active = COALESCE(is_active, true), "
            "    token_version = COALESCE(token_version, 1), "
            "    force_password_change = COALESCE(force_password_change, false)"
        )
    )

    # 3. Apply NOT NULL constraints after seeding defaults
    op.alter_column('users', 'force_password_change', nullable=False)
    op.alter_column('users', 'token_version', nullable=False)
    op.alter_column('users', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)

    # 4. Create user_invite_tokens table (if not exists checks can be handled by Alembic or transactional DDL)
    # NOTE: The existing /auth/register route has been disabled/removed, returning HTTP 410 Gone.
    if 'user_invite_tokens' not in tables:
        op.create_table(
            'user_invite_tokens',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=False),
            sa.Column('token_hash', sa.String(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('token_hash')
        )


def downgrade() -> None:
    op.drop_table('user_invite_tokens')
    op.alter_column('users', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'token_version')
    op.drop_column('users', 'force_password_change')
