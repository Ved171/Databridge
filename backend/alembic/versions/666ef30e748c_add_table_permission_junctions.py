"""add_table_permission_junctions

Revision ID: 666ef30e748c
Revises: c4ec42c60dc6
Create Date: 2026-06-08 17:19:17.382329

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '666ef30e748c'
down_revision: Union[str, None] = 'c4ec42c60dc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Drop tables if they already exist from Base.metadata.create_all
    bind = op.get_bind()
    bind.execute(sa.text("DROP TABLE IF EXISTS table_permission_departments CASCADE"))
    bind.execute(sa.text("DROP TABLE IF EXISTS table_permission_roles CASCADE"))

    # 1. Create table_permission_departments table
    op.create_table(
        'table_permission_departments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('table_permission_id', sa.UUID(), nullable=False),
        sa.Column('department_id', sa.UUID(), nullable=False),
        sa.Column('is_deny', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_read', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_create', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_update', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_delete', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['table_permission_id'], ['table_permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('table_permission_id', 'department_id')
    )

    # 2. Create table_permission_roles table
    op.create_table(
        'table_permission_roles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('table_permission_id', sa.UUID(), nullable=False),
        sa.Column('role_id', sa.UUID(), nullable=False),
        sa.Column('is_deny', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_read', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_create', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_update', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_delete', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['table_permission_id'], ['table_permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('table_permission_id', 'role_id')
    )

    # 3. Migrate existing single-role permission rows
    bind = op.get_bind()
    roles_res = bind.execute(sa.text("SELECT id, slug FROM roles")).all()
    roles_map = {row[1]: row[0] for row in roles_res}

    # Fetch all table permission rows that have applies_to_role set
    old_perms = bind.execute(
        sa.text(
            "SELECT id, applies_to_role, can_read, can_create, can_update, can_delete "
            "FROM table_permissions "
            "WHERE applies_to_role IS NOT NULL"
        )
    ).all()

    import uuid
    for row in old_perms:
        old_perm_id = row[0]
        old_role_str = row[1]
        can_read_val = row[2]
        can_create_val = row[3]
        can_update_val = row[4]
        can_delete_val = row[5]

        # Map the old role to the new role ID
        # Normalization:
        # 'superadmin', 'super_admin', 'admin' -> superadmin
        # 'manager' -> manager
        # 'member', 'viewer', 'workspace_admin', etc -> member
        role_slug = 'member'
        if old_role_str in ('superadmin', 'super_admin', 'admin'):
            role_slug = 'superadmin'
        elif old_role_str == 'manager':
            role_slug = 'manager'

        mapped_role_id = roles_map.get(role_slug)
        if mapped_role_id:
            bind.execute(
                sa.text(
                    "INSERT INTO table_permission_roles (id, table_permission_id, role_id, is_deny, can_read, can_create, can_update, can_delete) "
                    "VALUES (:id, :table_permission_id, :role_id, false, :can_read, :can_create, :can_update, :can_delete)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "table_permission_id": old_perm_id,
                    "role_id": mapped_role_id,
                    "can_read": can_read_val,
                    "can_create": can_create_val,
                    "can_update": can_update_val,
                    "can_delete": can_delete_val
                }
            )

    # 4. Drop applies_to_role column from table_permissions
    with op.batch_alter_table('table_permissions') as batch_op:
        batch_op.drop_constraint('table_permissions_connector_id_table_name_applies_to_user_i_key', type_='unique')
        batch_op.drop_column('applies_to_role')


def downgrade() -> None:
    # 1. Add column applies_to_role back
    with op.batch_alter_table('table_permissions') as batch_op:
        batch_op.add_column(sa.Column('applies_to_role', sa.VARCHAR(), nullable=True))

    # 2. Reconstruct applies_to_role from table_permission_roles
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE table_permissions "
            "SET applies_to_role = ( "
            "    SELECT slug FROM roles "
            "    JOIN table_permission_roles ON table_permission_roles.role_id = roles.id "
            "    WHERE table_permission_roles.table_permission_id = table_permissions.id "
            "    LIMIT 1"
            ") "
            "WHERE EXISTS ( "
            "    SELECT 1 FROM table_permission_roles "
            "    WHERE table_permission_roles.table_permission_id = table_permissions.id "
            ")"
        )
    )

    # 3. Re-create the unique constraint
    with op.batch_alter_table('table_permissions') as batch_op:
        batch_op.create_unique_constraint(
            'table_permissions_connector_id_table_name_applies_to_user_i_key',
            ['connector_id', 'table_name', 'applies_to_user_id', 'applies_to_role']
        )

    # 4. Drop the two junction tables
    op.drop_table('table_permission_roles')
    op.drop_table('table_permission_departments')
