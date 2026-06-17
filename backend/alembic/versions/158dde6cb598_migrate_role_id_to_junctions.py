"""migrate_role_id_to_junctions

Revision ID: 158dde6cb598
Revises: d4f8a1c2e3b5
Create Date: 2026-06-17 11:43:51.269250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '158dde6cb598'
down_revision: Union[str, None] = 'd4f8a1c2e3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    is_postgres = conn.dialect.name == 'postgresql'

    # 1. Migrate rls_policies (add filter_expr_nosql and make filter_expr nullable)
    rls_columns = [c['name'] for c in inspector.get_columns('rls_policies')]
    if 'filter_expr_nosql' not in rls_columns:
        op.add_column('rls_policies', sa.Column('filter_expr_nosql', sa.JSON(), nullable=True))
    op.alter_column('rls_policies', 'filter_expr', existing_type=sa.Text(), nullable=True)

    # 2. Migrate package_department_assignments
    pda_columns = [c['name'] for c in inspector.get_columns('package_department_assignments')]
    if 'role_id' not in pda_columns:
        op.add_column('package_department_assignments', sa.Column('role_id', sa.UUID(), sa.ForeignKey('roles.id'), nullable=True))

    if is_postgres:
        pda_constraints = inspector.get_unique_constraints('package_department_assignments')
        for const in pda_constraints:
            if set(const['column_names']) == {'package_id', 'department_id'}:
                op.drop_constraint(const['name'], 'package_department_assignments', type_='unique')
        
        has_new_pda_const = any(set(const['column_names']) == {'package_id', 'department_id', 'role_id'} for const in pda_constraints)
        if not has_new_pda_const:
            op.create_unique_constraint(
                'package_department_assignments_package_id_department_id_rol_key',
                'package_department_assignments',
                ['package_id', 'department_id', 'role_id']
            )

    # 3. Migrate connector_permission_departments
    cpd_columns = [c['name'] for c in inspector.get_columns('connector_permission_departments')]
    if 'role_id' not in cpd_columns:
        op.add_column('connector_permission_departments', sa.Column('role_id', sa.UUID(), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=True))

    if is_postgres:
        cpd_constraints = inspector.get_unique_constraints('connector_permission_departments')
        for const in cpd_constraints:
            if set(const['column_names']) == {'connector_permission_id', 'department_id'}:
                op.drop_constraint(const['name'], 'connector_permission_departments', type_='unique')
        
        has_new_cpd_const = any(set(const['column_names']) == {'connector_permission_id', 'department_id', 'role_id'} for const in cpd_constraints)
        if not has_new_cpd_const:
            op.create_unique_constraint(
                'conn_perm_depts_conn_perm_dept_role_key',
                'connector_permission_departments',
                ['connector_permission_id', 'department_id', 'role_id']
            )

    # 4. Migrate table_permission_departments
    tpd_columns = [c['name'] for c in inspector.get_columns('table_permission_departments')]
    if 'role_id' not in tpd_columns:
        op.add_column('table_permission_departments', sa.Column('role_id', sa.UUID(), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=True))

    if is_postgres:
        tpd_constraints = inspector.get_unique_constraints('table_permission_departments')
        for const in tpd_constraints:
            if set(const['column_names']) == {'table_permission_id', 'department_id'}:
                op.drop_constraint(const['name'], 'table_permission_departments', type_='unique')
        
        has_new_tpd_const = any(set(const['column_names']) == {'table_permission_id', 'department_id', 'role_id'} for const in tpd_constraints)
        if not has_new_tpd_const:
            op.create_unique_constraint(
                'table_perm_depts_table_perm_dept_role_key',
                'table_permission_departments',
                ['table_permission_id', 'department_id', 'role_id']
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    is_postgres = conn.dialect.name == 'postgresql'

    # Downgrade 4. table_permission_departments
    if is_postgres:
        tpd_constraints = inspector.get_unique_constraints('table_permission_departments')
        for const in tpd_constraints:
            if set(const['column_names']) == {'table_permission_id', 'department_id', 'role_id'}:
                op.drop_constraint(const['name'], 'table_permission_departments', type_='unique')
        
        op.create_unique_constraint(
            'table_permission_departments_table_permission_id_department_key',
            'table_permission_departments',
            ['table_permission_id', 'department_id']
        )
    tpd_columns = [c['name'] for c in inspector.get_columns('table_permission_departments')]
    if 'role_id' in tpd_columns:
        op.drop_column('table_permission_departments', 'role_id')

    # Downgrade 3. connector_permission_departments
    if is_postgres:
        cpd_constraints = inspector.get_unique_constraints('connector_permission_departments')
        for const in cpd_constraints:
            if set(const['column_names']) == {'connector_permission_id', 'department_id', 'role_id'}:
                op.drop_constraint(const['name'], 'connector_permission_departments', type_='unique')
        
        op.create_unique_constraint(
            'connector_permission_departme_connector_permission_id_depar_key',
            'connector_permission_departments',
            ['connector_permission_id', 'department_id']
        )
    cpd_columns = [c['name'] for c in inspector.get_columns('connector_permission_departments')]
    if 'role_id' in cpd_columns:
        op.drop_column('connector_permission_departments', 'role_id')

    # Downgrade 2. package_department_assignments
    if is_postgres:
        pda_constraints = inspector.get_unique_constraints('package_department_assignments')
        for const in pda_constraints:
            if set(const['column_names']) == {'package_id', 'department_id', 'role_id'}:
                op.drop_constraint(const['name'], 'package_department_assignments', type_='unique')
        
        op.create_unique_constraint(
            'package_department_assignments_package_id_department_id_key',
            'package_department_assignments',
            ['package_id', 'department_id']
        )
    pda_columns = [c['name'] for c in inspector.get_columns('package_department_assignments')]
    if 'role_id' in pda_columns:
        op.drop_column('package_department_assignments', 'role_id')

    # Downgrade 1. rls_policies
    op.alter_column('rls_policies', 'filter_expr', existing_type=sa.Text(), nullable=False)
    rls_columns = [c['name'] for c in inspector.get_columns('rls_policies')]
    if 'filter_expr_nosql' in rls_columns:
        op.drop_column('rls_policies', 'filter_expr_nosql')
