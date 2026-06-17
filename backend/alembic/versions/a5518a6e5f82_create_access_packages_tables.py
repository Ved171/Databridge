"""create_access_packages_tables

Revision ID: a5518a6e5f82
Revises: e261faeefb4b
Create Date: 2026-06-09 08:10:00.344708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5518a6e5f82'
down_revision: Union[str, None] = 'e261faeefb4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. access_packages
    if 'access_packages' not in tables:
        op.create_table('access_packages',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('slug', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('color', sa.String(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
            sa.UniqueConstraint('slug')
        )

    # 2. package_connector_rules
    if 'package_connector_rules' not in tables:
        op.create_table('package_connector_rules',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('package_id', sa.UUID(), nullable=False),
            sa.Column('connector_id', sa.String(), nullable=False),
            sa.Column('is_deny', sa.Boolean(), nullable=False),
            sa.Column('can_read', sa.Boolean(), nullable=False),
            sa.Column('can_create', sa.Boolean(), nullable=False),
            sa.Column('can_update', sa.Boolean(), nullable=False),
            sa.Column('can_delete', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['package_id'], ['access_packages.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('package_id', 'connector_id')
        )

    # 3. package_table_rules
    if 'package_table_rules' not in tables:
        op.create_table('package_table_rules',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('package_id', sa.UUID(), nullable=False),
            sa.Column('connector_id', sa.String(), nullable=False),
            sa.Column('table_name', sa.String(), nullable=False),
            sa.Column('is_deny', sa.Boolean(), nullable=False),
            sa.Column('can_read', sa.Boolean(), nullable=False),
            sa.Column('can_create', sa.Boolean(), nullable=False),
            sa.Column('can_update', sa.Boolean(), nullable=False),
            sa.Column('can_delete', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['package_id'], ['access_packages.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('package_id', 'connector_id', 'table_name')
        )

    # 4. package_rls_filters
    if 'package_rls_filters' not in tables:
        op.create_table('package_rls_filters',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('package_id', sa.UUID(), nullable=False),
            sa.Column('connector_id', sa.String(), nullable=False),
            sa.Column('table_name', sa.String(), nullable=False),
            sa.Column('filter_expression', sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(['package_id'], ['access_packages.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )

    # 5. package_department_assignments
    if 'package_department_assignments' not in tables:
        op.create_table('package_department_assignments',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('package_id', sa.UUID(), nullable=False),
            sa.Column('department_id', sa.UUID(), nullable=False),
            sa.Column('valid_from', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_by', sa.UUID(), nullable=True),
            sa.Column('assigned_by', sa.UUID(), nullable=False),
            sa.Column('assigned_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ),
            sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
            sa.ForeignKeyConstraint(['package_id'], ['access_packages.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('package_id', 'department_id')
        )

    # 6. package_role_assignments
    if 'package_role_assignments' not in tables:
        op.create_table('package_role_assignments',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('package_id', sa.UUID(), nullable=False),
            sa.Column('role_id', sa.UUID(), nullable=False),
            sa.Column('valid_from', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_by', sa.UUID(), nullable=True),
            sa.Column('assigned_by', sa.UUID(), nullable=False),
            sa.Column('assigned_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ),
            sa.ForeignKeyConstraint(['package_id'], ['access_packages.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], ),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('package_id', 'role_id')
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    for t in [
        'package_role_assignments',
        'package_department_assignments',
        'package_rls_filters',
        'package_table_rules',
        'package_connector_rules',
        'access_packages'
    ]:
        if t in tables:
            op.drop_table(t)

