import asyncio
import os
import sys

# Add backend root to path to resolve app.* imports correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import engine
from sqlalchemy import text

async def run_migrations():
    print("Starting database schema migrations...")
    async with engine.begin() as conn:
        # 1. Auto-migrate rls_policies columns if they are missing
        try:
            is_postgres = "postgresql" in str(engine.url)
            if is_postgres:
                await conn.execute(text("ALTER TABLE rls_policies ADD COLUMN IF NOT EXISTS filter_expr_nosql JSON;"))
                await conn.execute(text("ALTER TABLE rls_policies ALTER COLUMN filter_expr DROP NOT NULL;"))
                print("PostgreSQL rls_policies auto-migration succeeded")
            else:
                try:
                    await conn.execute(text("ALTER TABLE rls_policies ADD COLUMN filter_expr_nosql JSON;"))
                    print("SQLite/Other rls_policies auto-migration succeeded")
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Auto-migration of rls_policies failed: {e}")

        # 2. Auto-migrate package_department_assignments: add role_id column & unique constraint
        try:
            is_postgres = "postgresql" in str(engine.url)
            if is_postgres:
                await conn.execute(text(
                    "ALTER TABLE package_department_assignments ADD COLUMN IF NOT EXISTS role_id UUID REFERENCES roles(id);"
                ))
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'package_department_assignments_package_id_department_id_key'
                        ) THEN
                            ALTER TABLE package_department_assignments
                                DROP CONSTRAINT package_department_assignments_package_id_department_id_key;
                        END IF;
                    END $$;
                """))
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'package_department_assignments_package_id_department_id_rol_key'
                        ) THEN
                            ALTER TABLE package_department_assignments
                                ADD CONSTRAINT package_department_assignments_package_id_department_id_rol_key
                                UNIQUE (package_id, department_id, role_id);
                        END IF;
                    END $$;
                """))
                print("PostgreSQL package_department_assignments role_id migration succeeded")
            else:
                try:
                    await conn.execute(text(
                        "ALTER TABLE package_department_assignments ADD COLUMN role_id UUID REFERENCES roles(id);"
                    ))
                    print("SQLite package_department_assignments role_id migration succeeded")
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Auto-migration of package_department_assignments failed: {e}")

        # 3. Auto-migrate connector_permission_departments: add role_id column & unique constraint
        try:
            is_postgres = "postgresql" in str(engine.url)
            if is_postgres:
                await conn.execute(text(
                    "ALTER TABLE connector_permission_departments ADD COLUMN IF NOT EXISTS role_id UUID REFERENCES roles(id);"
                ))
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'connector_permission_departme_connector_permission_id_depar_key'
                        ) THEN
                            ALTER TABLE connector_permission_departments
                                DROP CONSTRAINT connector_permission_departme_connector_permission_id_depar_key;
                        END IF;
                    END $$;
                """))
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'conn_perm_depts_conn_perm_dept_role_key'
                        ) THEN
                            ALTER TABLE connector_permission_departments
                                ADD CONSTRAINT conn_perm_depts_conn_perm_dept_role_key
                                UNIQUE (connector_permission_id, department_id, role_id);
                        END IF;
                    END $$;
                """))
                print("PostgreSQL connector_permission_departments role_id migration succeeded")
            else:
                try:
                    await conn.execute(text(
                        "ALTER TABLE connector_permission_departments ADD COLUMN role_id UUID REFERENCES roles(id);"
                    ))
                    print("SQLite connector_permission_departments role_id migration succeeded")
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Auto-migration of connector_permission_departments failed: {e}")

        # 4. Auto-migrate table_permission_departments: add role_id column & unique constraint
        try:
            is_postgres = "postgresql" in str(engine.url)
            if is_postgres:
                await conn.execute(text(
                    "ALTER TABLE table_permission_departments ADD COLUMN IF NOT EXISTS role_id UUID REFERENCES roles(id);"
                ))
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'table_permission_departments_table_permission_id_department_key'
                        ) THEN
                            ALTER TABLE table_permission_departments
                                DROP CONSTRAINT table_permission_departments_table_permission_id_department_key;
                        END IF;
                    END $$;
                """))
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'table_perm_depts_table_perm_dept_role_key'
                        ) THEN
                            ALTER TABLE table_permission_departments
                                ADD CONSTRAINT table_perm_depts_table_perm_dept_role_key
                                UNIQUE (table_permission_id, department_id, role_id);
                        END IF;
                    END $$;
                """))
                print("PostgreSQL table_permission_departments role_id migration succeeded")
            else:
                try:
                    await conn.execute(text(
                        "ALTER TABLE table_permission_departments ADD COLUMN role_id UUID REFERENCES roles(id);"
                    ))
                    print("SQLite table_permission_departments role_id migration succeeded")
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Auto-migration of table_permission_departments failed: {e}")

    print("Database schema migrations completed.")

if __name__ == "__main__":
    asyncio.run(run_migrations())
