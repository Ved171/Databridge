"""create_roles_and_managers

Revision ID: a298413ab9bf
Revises: 1d742c6d8773
Create Date: 2026-06-08 11:21:26.020239

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text
import uuid
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = 'a298413ab9bf'
down_revision: Union[str, None] = '1d742c6d8773'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Add columns to roles table if they do not exist
    roles_columns = [c['name'] for c in inspector.get_columns('roles')]
    if 'slug' not in roles_columns:
        op.add_column('roles', sa.Column('slug', sa.String(), nullable=False))
    if 'level' not in roles_columns:
        op.add_column('roles', sa.Column('level', sa.Integer(), nullable=False))
    if 'color' not in roles_columns:
        op.add_column('roles', sa.Column('color', sa.String(), nullable=True, server_default='1E40AF'))
    if 'is_system' not in roles_columns:
        op.add_column('roles', sa.Column('is_system', sa.Boolean(), nullable=True, server_default='false'))
    if 'is_active' not in roles_columns:
        op.add_column('roles', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    if 'deleted_at' not in roles_columns:
        op.add_column('roles', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    if 'parent_role_id' not in roles_columns:
        op.add_column('roles', sa.Column('parent_role_id', sa.UUID(), nullable=True))
    if 'created_at' not in roles_columns:
        op.add_column('roles', sa.Column('created_at', sa.DateTime(), nullable=True))

    roles_constraints = [c['name'] for c in inspector.get_unique_constraints('roles')]
    if 'uq_roles_slug' not in roles_constraints:
        try:
            op.create_unique_constraint('uq_roles_slug', 'roles', ['slug'])
        except Exception:
            pass

    try:
        op.create_foreign_key('fk_roles_parent_role', 'roles', 'roles', ['parent_role_id'], ['id'])
    except Exception:
        pass

    # 3. Seed default roles idempotently
    bind = op.get_bind()
    res = bind.execute(text("SELECT count(*) FROM roles"))
    count = res.scalar()
    if count == 0:
        member_id = str(uuid.uuid4())
        manager_id = str(uuid.uuid4())
        superadmin_id = str(uuid.uuid4())
        
        # Insert Superadmin
        bind.execute(
            text(
                "INSERT INTO roles (id, name, slug, level, color, is_system, is_active, created_at) "
                "VALUES (:id, 'Superadmin', 'superadmin', 3, 'BE185D', true, true, :created_at)"
            ),
            {"id": superadmin_id, "created_at": datetime.utcnow()}
        )
        # Insert Manager referencing Superadmin
        bind.execute(
            text(
                "INSERT INTO roles (id, name, slug, level, color, is_system, is_active, parent_role_id, created_at) "
                "VALUES (:id, 'Manager', 'manager', 2, '047857', false, true, :parent_id, :created_at)"
            ),
            {"id": manager_id, "parent_id": superadmin_id, "created_at": datetime.utcnow()}
        )
        # Insert Member referencing Manager
        bind.execute(
            text(
                "INSERT INTO roles (id, name, slug, level, color, is_system, is_active, parent_role_id, created_at) "
                "VALUES (:id, 'Member', 'member', 1, '1E40AF', false, true, :parent_id, :created_at)"
            ),
            {"id": member_id, "parent_id": manager_id, "created_at": datetime.utcnow()}
        )

    # 4. Create user_manager_assignments table
    if 'user_manager_assignments' not in tables:
        op.create_table(
            'user_manager_assignments',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('manager_user_id', sa.UUID(), nullable=False),
            sa.Column('member_user_id', sa.UUID(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['manager_user_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['member_user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('manager_user_id', 'member_user_id', name='uq_manager_member')
        )

    # 5. Create user_role_history table
    if 'user_role_history' not in tables:
        op.create_table(
            'user_role_history',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=False),
            sa.Column('old_role_id', sa.UUID(), nullable=True),
            sa.Column('new_role_id', sa.UUID(), nullable=True),
            sa.Column('changed_at', sa.DateTime(), nullable=False),
            sa.Column('changed_by', sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
            sa.ForeignKeyConstraint(['new_role_id'], ['roles.id'], ),
            sa.ForeignKeyConstraint(['old_role_id'], ['roles.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

    # 6. Add role_id FK to users
    users_columns = [c['name'] for c in inspector.get_columns('users')]
    if 'role_id' not in users_columns:
        op.add_column('users', sa.Column('role_id', sa.UUID(), nullable=True))
        op.create_foreign_key('fk_users_role', 'users', 'roles', ['role_id'], ['id'])

    # 7. Migrate users' roles based on old role string
    if 'role' in users_columns:
        roles_res = bind.execute(text("SELECT id, slug FROM roles")).all()
        roles_map = {row[1]: row[0] for row in roles_res}
        
        superadmin_id_val = roles_map.get("superadmin")
        manager_id_val = roles_map.get("manager")
        member_id_val = roles_map.get("member")
        
        if superadmin_id_val:
            bind.execute(
                text("UPDATE users SET role_id = :role_id WHERE role IN ('superadmin', 'super_admin', 'admin')"),
                {"role_id": superadmin_id_val}
            )
        if manager_id_val:
            bind.execute(
                text("UPDATE users SET role_id = :role_id WHERE role = 'manager'"),
                {"role_id": manager_id_val}
            )
        if member_id_val:
            bind.execute(
                text("UPDATE users SET role_id = :role_id WHERE role IN ('member', 'viewer')"),
                {"role_id": member_id_val}
            )
            
        # Default any other roles (like workspace_admin) to member
        if member_id_val:
            bind.execute(
                text("UPDATE users SET role_id = :role_id WHERE role_id IS NULL"),
                {"role_id": member_id_val}
            )

        # 8. Drop the old users.role column
        op.drop_column('users', 'role')


def downgrade() -> None:
    op.add_column('users', sa.Column('role', sa.VARCHAR(), nullable=True))
    
    bind = op.get_bind()
    bind.execute(
        text(
            "UPDATE users SET role = (SELECT slug FROM roles WHERE roles.id = users.role_id) "
            "WHERE role_id IS NOT NULL"
        )
    )
    
    op.drop_constraint('fk_users_role', 'users', type_='foreignkey')
    op.drop_column('users', 'role_id')
    op.drop_table('user_role_history')
    op.drop_table('user_manager_assignments')
    op.drop_constraint('fk_roles_parent_role', 'roles', type_='foreignkey')
    op.drop_constraint('uq_roles_slug', 'roles', type_='unique')
    op.drop_column('roles', 'created_at')
    op.drop_column('roles', 'parent_role_id')
    op.drop_column('roles', 'deleted_at')
    op.drop_column('roles', 'is_active')
    op.drop_column('roles', 'is_system')
    op.drop_column('roles', 'color')
    op.drop_column('roles', 'level')
    op.drop_column('roles', 'slug')

