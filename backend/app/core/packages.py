import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    AccessPackage, PackageConnectorRule, PackageTableRule,
    PackageRLSFilter, PackageDepartmentAssignment, PackageRoleAssignment
)
from app.core.deps import resolve_department_chain, is_grant_active

logger = logging.getLogger("packages")


async def resolve_active_packages(
    user,
    db: AsyncSession
) -> list[AccessPackage]:
    """
    Returns all active packages assigned to the user's dept chain
    or exact role. Respects valid_from / expires_at / revoked_at
    on the assignment rows.

    Role matching is individual/direct only -- no hierarchy inheritance.
    For department assignments with a role_id restriction, the user
    must have that exact role for the package to be active.
    """
    role_chain = [str(user.role_id)] if user.role_id else []
    dept_chain = await resolve_department_chain(user.department_id, db)

    dept_assignments = await db.execute(
        select(PackageDepartmentAssignment)
        .where(
            PackageDepartmentAssignment.department_id.in_(dept_chain),
            PackageDepartmentAssignment.revoked_at.is_(None),
        )
    )
    role_assignments = await db.execute(
        select(PackageRoleAssignment)
        .where(
            PackageRoleAssignment.role_id.in_(role_chain),
            PackageRoleAssignment.revoked_at.is_(None),
        )
    )

    package_ids = set()

    # Role assignments: straightforward
    for row in role_assignments.scalars():
        if is_grant_active(row):
            package_ids.add(str(row.package_id))

    # Dept assignments: check role_id restriction
    for row in dept_assignments.scalars():
        if not is_grant_active(row):
            continue
        if row.role_id is not None:
            # Scoped assignment: user must exactly match the role (no inheritance)
            if str(row.role_id) == str(user.role_id):
                package_ids.add(str(row.package_id))
        else:
            # Unscoped assignment: all dept members get access
            package_ids.add(str(row.package_id))

    if not package_ids:
        return []

    packages = await db.execute(
        select(AccessPackage).where(
            AccessPackage.id.in_(package_ids),
            AccessPackage.is_active == True,
        )
    )
    return list(packages.scalars().all())


async def check_connector_via_package(
    connector_id: str,
    operation: str,
    user,
    db: AsyncSession
) -> bool | None:
    """
    Returns True if any active package grants this connector+operation.
    Returns False if any active package explicitly denies it.
    Returns None if no package rule matches -- caller continues to next check.
    """
    flag = f"can_{operation}"
    packages = await resolve_active_packages(user, db)
    if not packages:
        return None

    package_ids = [str(p.id) for p in packages]

    deny = await db.execute(
        select(PackageConnectorRule).where(
            PackageConnectorRule.package_id.in_(package_ids),
            PackageConnectorRule.connector_id == connector_id,
            PackageConnectorRule.is_deny == True,
        )
    )
    if deny.scalars().first() is not None:
        return False

    allow = await db.execute(
        select(PackageConnectorRule).where(
            PackageConnectorRule.package_id.in_(package_ids),
            PackageConnectorRule.connector_id == connector_id,
            PackageConnectorRule.is_deny == False,
            getattr(PackageConnectorRule, flag) == True,
        )
    )
    if allow.scalars().first() is not None:
        return True

    return None


async def check_table_via_package(
    connector_id: str,
    table_name: str,
    operation: str,
    user,
    db: AsyncSession
) -> bool | None:
    """
    Same as check_connector_via_package but for table-level rules.
    Returns True / False / None.
    """
    flag = f"can_{operation}"
    packages = await resolve_active_packages(user, db)
    if not packages:
        return None

    package_ids = [str(p.id) for p in packages]

    # Fetch all table rules for this connector in the user's active packages
    pkg_rules = await db.execute(
        select(PackageTableRule).where(
            PackageTableRule.package_id.in_(package_ids),
            PackageTableRule.connector_id == connector_id
        )
    )
    all_pkg_rules = pkg_rules.scalars().all()

    from app.core.deps import _table_name_matches
    matched_rules = [r for r in all_pkg_rules if _table_name_matches(r.table_name, table_name)]

    # 1. Explicit deny targets check first
    deny_rules = [r for r in matched_rules if r.is_deny]
    if deny_rules:
        return False

    # 2. Allow rules check
    allow_rules = [r for r in matched_rules if not r.is_deny and getattr(r, flag) == True]
    if allow_rules:
        return True

    return None


async def resolve_package_rls_filters(
    connector_id: str,
    table_name: str,
    user,
    db: AsyncSession
) -> list[str]:
    """
    Returns substituted RLS filter expressions from all active packages
    that include a filter for this connector+table.
    Appended to the filters from F-08 resolve_rls_filters().
    """
    if getattr(user, "is_superadmin", False):
        return []

    from app.core.rls import resolve_rls_context, substitute_placeholders

    packages = await resolve_active_packages(user, db)
    if not packages:
        return []

    package_ids = [str(p.id) for p in packages]
    filters_res = await db.execute(
        select(PackageRLSFilter).where(
            PackageRLSFilter.package_id.in_(package_ids),
            PackageRLSFilter.connector_id == connector_id,
        )
    )
    all_filters = filters_res.scalars().all()

    from app.core.deps import _table_name_matches
    filters = [f for f in all_filters if _table_name_matches(f.table_name, table_name)]

    context = await resolve_rls_context(user, db)
    clauses = []
    for f in filters:
        try:
            substituted, _ = substitute_placeholders(f.filter_expression, context)
            clauses.append(substituted)
        except ValueError as e:
            logger.error(f"Package RLS filter {f.id} substitution failed: {e}")
    return clauses
