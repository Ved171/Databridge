"""create_departments_and_roles

Revision ID: 1d742c6d8773
Revises: 
Create Date: 2026-06-08 11:14:18.159641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text
import uuid
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = '1d742c6d8773'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 0. Create base tables in their historical/initial state if they do not exist
    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('email', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('hashed_password', sa.String(), nullable=False),
            sa.Column('is_superadmin', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('role', sa.String(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email')
        )
        # Update inspector table list
        tables.append('users')

    if 'workspaces' not in tables:
        op.create_table(
            'workspaces',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('slug', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('slug')
        )
        tables.append('workspaces')

    if 'workspace_members' not in tables:
        op.create_table(
            'workspace_members',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('workspace_id', sa.UUID(), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=False),
            sa.Column('role', sa.String(), nullable=False, server_default='member'),
            sa.Column('joined_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('workspace_id', 'user_id')
        )
        tables.append('workspace_members')

    if 'connectors' not in tables:
        op.create_table(
            'connectors',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('workspace_id', sa.UUID(), nullable=True),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('type', sa.String(), nullable=False),
            sa.Column('encrypted_config', sa.Text(), nullable=False),
            sa.Column('schema_cache', sa.JSON(), nullable=True),
            sa.Column('schema_cached_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
            sa.Column('created_by', sa.UUID(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        tables.append('connectors')

    if 'connector_permissions' not in tables:
        op.create_table(
            'connector_permissions',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('connector_id', sa.UUID(), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=True),
            sa.Column('can_create', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('can_read', sa.Boolean(), nullable=True, server_default='true'),
            sa.Column('can_update', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('can_delete', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('granted_by', sa.UUID(), nullable=True),
            sa.Column('granted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['connector_id'], ['connectors.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('connector_id', 'user_id')
        )
        tables.append('connector_permissions')

    if 'table_permissions' not in tables:
        op.create_table(
            'table_permissions',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('connector_id', sa.UUID(), nullable=False),
            sa.Column('table_name', sa.String(), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=True),
            sa.Column('applies_to_role', sa.String(), nullable=True),
            sa.Column('can_create', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('can_read', sa.Boolean(), nullable=True, server_default='true'),
            sa.Column('can_update', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('can_delete', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('granted_by', sa.UUID(), nullable=True),
            sa.Column('granted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['connector_id'], ['connectors.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('connector_id', 'table_name', 'user_id', 'applies_to_role', name='table_permissions_connector_id_table_name_applies_to_user_i_key')
        )
        tables.append('table_permissions')

    if 'rls_policies' not in tables:
        op.create_table(
            'rls_policies',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('connector_id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('table_name', sa.String(), nullable=False),
            sa.Column('filter_expr', sa.Text(), nullable=False),
            sa.Column('applies_to_user_id', sa.UUID(), nullable=True),
            sa.Column('applies_to_role', sa.String(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['connector_id'], ['connectors.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['applies_to_user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        tables.append('rls_policies')

    # 1. Create roles table
    if 'roles' not in tables:
        op.create_table(
            'roles',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        tables.append('roles')

    # 2. Create departments table
    if 'departments' not in tables:
        op.create_table(
            'departments',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('slug', sa.String(), nullable=False),
            sa.Column('color', sa.String(), nullable=True, server_default='1E40AF'),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
            sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('default_role_id', sa.UUID(), nullable=True),
            sa.Column('parent_department_id', sa.UUID(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['default_role_id'], ['roles.id'], ),
            sa.ForeignKeyConstraint(['parent_department_id'], ['departments.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
            sa.UniqueConstraint('slug')
        )
        tables.append('departments')

    # 3. Add department_id FK to users
    columns = [c['name'] for c in inspector.get_columns('users')]
    if 'department_id' not in columns:
        op.add_column('users', sa.Column('department_id', sa.UUID(), nullable=True))
        op.create_foreign_key('fk_users_department', 'users', 'departments', ['department_id'], ['id'])

    # 4. Seed default departments if table is empty
    bind = op.get_bind()
    res = bind.execute(text("SELECT count(*) FROM departments"))
    count = res.scalar()
    if count == 0:
        default_depts = [
            ("HR", "hr", "1E40AF"),
            ("Engineering", "engineering", "047857"),
            ("Finance", "finance", "B45309"),
            ("Infra", "infra", "6D28D9"),
            ("Legal", "legal", "BE185D"),
        ]
        for name, slug, color in default_depts:
            dept_id = str(uuid.uuid4())
            bind.execute(
                text(
                    "INSERT INTO departments (id, name, slug, color, is_active, is_system, created_at) "
                    "VALUES (:id, :name, :slug, :color, true, true, :created_at)"
                ),
                {
                    "id": dept_id,
                    "name": name,
                    "slug": slug,
                    "color": color,
                    "created_at": datetime.utcnow()
                }
            )


def downgrade() -> None:
    op.drop_constraint('fk_users_department', 'users', type_='foreignkey')
    op.drop_column('users', 'department_id')
    op.drop_table('departments')
    op.drop_table('roles')

