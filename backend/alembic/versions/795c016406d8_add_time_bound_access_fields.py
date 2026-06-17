"""add_time_bound_access_fields

Revision ID: 795c016406d8
Revises: 8f1c9a2b3d4e
Create Date: 2026-06-09 07:17:27.669558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '795c016406d8'
down_revision: Union[str, None] = '8f1c9a2b3d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Add columns to connector_permissions
    cp_cols = [c['name'] for c in inspector.get_columns('connector_permissions')]
    if 'valid_from' not in cp_cols:
        op.add_column('connector_permissions', sa.Column('valid_from', sa.DateTime(), nullable=True))
    if 'expires_at' not in cp_cols:
        op.add_column('connector_permissions', sa.Column('expires_at', sa.DateTime(), nullable=True))
    if 'revoked_at' not in cp_cols:
        op.add_column('connector_permissions', sa.Column('revoked_at', sa.DateTime(), nullable=True))
    if 'revoked_by' not in cp_cols:
        op.add_column('connector_permissions', sa.Column('revoked_by', sa.UUID(), nullable=True))
    if 'grant_reason' not in cp_cols:
        op.add_column('connector_permissions', sa.Column('grant_reason', sa.String(), nullable=True))
    try:
        op.create_foreign_key('fk_connector_permissions_revoked_by', 'connector_permissions', 'users', ['revoked_by'], ['id'], ondelete='SET NULL')
    except Exception:
        pass

    # 2. Add columns to connector_permission_departments
    cpd_cols = [c['name'] for c in inspector.get_columns('connector_permission_departments')]
    if 'valid_from' not in cpd_cols:
        op.add_column('connector_permission_departments', sa.Column('valid_from', sa.DateTime(), nullable=True))
    if 'expires_at' not in cpd_cols:
        op.add_column('connector_permission_departments', sa.Column('expires_at', sa.DateTime(), nullable=True))
    if 'revoked_at' not in cpd_cols:
        op.add_column('connector_permission_departments', sa.Column('revoked_at', sa.DateTime(), nullable=True))
    if 'revoked_by' not in cpd_cols:
        op.add_column('connector_permission_departments', sa.Column('revoked_by', sa.UUID(), nullable=True))
    if 'grant_reason' not in cpd_cols:
        op.add_column('connector_permission_departments', sa.Column('grant_reason', sa.String(), nullable=True))
    try:
        op.create_foreign_key('fk_connector_permission_depts_revoked_by', 'connector_permission_departments', 'users', ['revoked_by'], ['id'], ondelete='SET NULL')
    except Exception:
        pass

    # 3. Add columns to connector_permission_roles
    cpr_cols = [c['name'] for c in inspector.get_columns('connector_permission_roles')]
    if 'valid_from' not in cpr_cols:
        op.add_column('connector_permission_roles', sa.Column('valid_from', sa.DateTime(), nullable=True))
    if 'expires_at' not in cpr_cols:
        op.add_column('connector_permission_roles', sa.Column('expires_at', sa.DateTime(), nullable=True))
    if 'revoked_at' not in cpr_cols:
        op.add_column('connector_permission_roles', sa.Column('revoked_at', sa.DateTime(), nullable=True))
    if 'revoked_by' not in cpr_cols:
        op.add_column('connector_permission_roles', sa.Column('revoked_by', sa.UUID(), nullable=True))
    if 'grant_reason' not in cpr_cols:
        op.add_column('connector_permission_roles', sa.Column('grant_reason', sa.String(), nullable=True))
    try:
        op.create_foreign_key('fk_connector_permission_roles_revoked_by', 'connector_permission_roles', 'users', ['revoked_by'], ['id'], ondelete='SET NULL')
    except Exception:
        pass


def downgrade() -> None:
    # 3. Drop columns and foreign key from connector_permission_roles
    op.drop_constraint('fk_connector_permission_roles_revoked_by', 'connector_permission_roles', type_='foreignkey')
    op.drop_column('connector_permission_roles', 'grant_reason')
    op.drop_column('connector_permission_roles', 'revoked_by')
    op.drop_column('connector_permission_roles', 'revoked_at')
    op.drop_column('connector_permission_roles', 'expires_at')
    op.drop_column('connector_permission_roles', 'valid_from')

    # 2. Drop columns and foreign key from connector_permission_departments
    op.drop_constraint('fk_connector_permission_depts_revoked_by', 'connector_permission_departments', type_='foreignkey')
    op.drop_column('connector_permission_departments', 'grant_reason')
    op.drop_column('connector_permission_departments', 'revoked_by')
    op.drop_column('connector_permission_departments', 'revoked_at')
    op.drop_column('connector_permission_departments', 'expires_at')
    op.drop_column('connector_permission_departments', 'valid_from')

    # 1. Drop columns and foreign key from connector_permissions
    op.drop_constraint('fk_connector_permissions_revoked_by', 'connector_permissions', type_='foreignkey')
    op.drop_column('connector_permissions', 'grant_reason')
    op.drop_column('connector_permissions', 'revoked_by')
    op.drop_column('connector_permissions', 'revoked_at')
    op.drop_column('connector_permissions', 'expires_at')
    op.drop_column('connector_permissions', 'valid_from')
