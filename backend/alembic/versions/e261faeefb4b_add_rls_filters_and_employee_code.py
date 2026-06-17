"""add_rls_filters_and_employee_code

Revision ID: e261faeefb4b
Revises: 795c016406d8
Create Date: 2026-06-09 07:58:49.803959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e261faeefb4b'
down_revision: Union[str, None] = '795c016406d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # 1. users.employee_code
    columns = [c['name'] for c in inspector.get_columns('users')]
    if 'employee_code' not in columns:
        op.add_column('users', sa.Column('employee_code', sa.String(), nullable=True))
        op.create_index(op.f('ix_users_employee_code'), 'users', ['employee_code'], unique=True)

    # 2. table_rls_filters table
    tables = inspector.get_table_names()
    if 'table_rls_filters' not in tables:
        op.create_table('table_rls_filters',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('connector_id', sa.String(), nullable=False),
            sa.Column('table_name', sa.String(), nullable=False),
            sa.Column('filter_expression', sa.Text(), nullable=False),
            sa.Column('applies_to_role_id', sa.UUID(), nullable=True),
            sa.Column('applies_to_dept_id', sa.UUID(), nullable=True),
            sa.Column('applies_to_user_id', sa.UUID(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(['applies_to_role_id'], ['roles.id'], ),
            sa.ForeignKeyConstraint(['applies_to_dept_id'], ['departments.id'], ),
            sa.ForeignKeyConstraint(['applies_to_user_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.CheckConstraint(
                "applies_to_role_id IS NOT NULL OR applies_to_dept_id IS NOT NULL OR applies_to_user_id IS NOT NULL",
                name='rls_filter_must_have_target'
            )
        )

    # 3. Re-create foreign keys if requested by autogenerate
    # We can run these if the constraints exist.
    # To keep it robust, we wrap it or do it if they exist.
    try:
        op.drop_constraint('fk_connector_permission_depts_revoked_by', 'connector_permission_departments', type_='foreignkey')
        op.create_foreign_key(None, 'connector_permission_departments', 'users', ['revoked_by'], ['id'])
    except Exception:
        pass
    try:
        op.drop_constraint('fk_connector_permission_roles_revoked_by', 'connector_permission_roles', type_='foreignkey')
        op.create_foreign_key(None, 'connector_permission_roles', 'users', ['revoked_by'], ['id'])
    except Exception:
        pass
    try:
        op.drop_constraint('fk_connector_permissions_revoked_by', 'connector_permissions', type_='foreignkey')
        op.create_foreign_key(None, 'connector_permissions', 'users', ['revoked_by'], ['id'])
    except Exception:
        pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'table_rls_filters' in tables:
        op.drop_table('table_rls_filters')

    columns = [c['name'] for c in inspector.get_columns('users')]
    if 'employee_code' in columns:
        op.drop_index(op.f('ix_users_employee_code'), table_name='users')
        op.drop_column('users', 'employee_code')

