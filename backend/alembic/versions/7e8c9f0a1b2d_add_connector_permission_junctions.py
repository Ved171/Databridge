"""add_connector_permission_junctions

Revision ID: 7e8c9f0a1b2d
Revises: 666ef30e748c
Create Date: 2026-06-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e8c9f0a1b2d'
down_revision: Union[str, None] = '666ef30e748c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Drop tables if they already exist from Base.metadata.create_all
    bind = op.get_bind()
    bind.execute(sa.text("DROP TABLE IF EXISTS connector_permission_departments CASCADE"))
    bind.execute(sa.text("DROP TABLE IF EXISTS connector_permission_roles CASCADE"))

    # 1. Create connector_permission_departments table
    op.create_table(
        'connector_permission_departments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('connector_permission_id', sa.UUID(), nullable=False),
        sa.Column('department_id', sa.UUID(), nullable=False),
        sa.Column('is_deny', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_read', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_create', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_update', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_delete', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['connector_permission_id'], ['connector_permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('connector_permission_id', 'department_id')
    )

    # 2. Create connector_permission_roles table
    op.create_table(
        'connector_permission_roles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('connector_permission_id', sa.UUID(), nullable=False),
        sa.Column('role_id', sa.UUID(), nullable=False),
        sa.Column('is_deny', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_read', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_create', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_update', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_delete', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['connector_permission_id'], ['connector_permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('connector_permission_id', 'role_id')
    )


def downgrade() -> None:
    # 1. Drop the two junction tables
    op.drop_table('connector_permission_roles')
    op.drop_table('connector_permission_departments')
