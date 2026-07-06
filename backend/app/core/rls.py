import re
import logging
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import resolve_managed_users
from app.models import User

logger = logging.getLogger("rls")

async def resolve_rls_context(user: User, db: AsyncSession) -> dict:
    """
    Builds the full RLS substitution context for a given user.
    This dict is passed into placeholder substitution at query time.
    """
    managed_user_ids = await resolve_managed_users(str(user.id), db)

    # Resolve EmployeeCodes for managed users
    # EmployeeCode is the stable cross-DB join key -- never use EmployeeId
    managed_codes = []
    if managed_user_ids:
        res = await db.execute(
            select(User.employee_code)
            .where(
                User.id.in_(managed_user_ids),
                User.is_active == True,
            )
        )
        managed_codes = [r for r in res.scalars().all() if r]

    return {
        # User identity
        "user.id":            str(user.id),
        "user.email":         user.email,
        "user.name":          user.name,
        "user.employee_code": user.employee_code or "",

        # Manager scope
        "manager.managed_user_ids":    ",".join(managed_user_ids),
        "manager.managed_codes":       ",".join(managed_codes),
        "manager.managed_codes_quoted": ",".join(f"'{c}'" for c in managed_codes),
        "manager.managed_count":       str(len(managed_codes)),
        "manager.is_manager":          "true" if managed_user_ids else "false",
    }


def substitute_placeholders(query: str, context: dict) -> tuple[str, bool]:
    """
    Replaces {placeholder} tokens in a query string with resolved values.
    Returns (substituted_query, had_any_placeholders).

    Raises ValueError if an unresolvable placeholder is found --
    never silently pass an unsubstituted placeholder to the DB.
    """
    found = set(re.findall(r'\{([\w.]+)\}', query))

    if not found:
        return query, False

    unresolvable = found - set(context.keys())
    if unresolvable:
        raise ValueError(
            f"Query contains unresolvable placeholders: {unresolvable}. "
            f"Available: {set(context.keys())}"
        )

    result = query
    for key, value in context.items():
        result = result.replace(f"{{{key}}}", value)

    return result, True


async def resolve_rls_filters(
    connector_id: str,
    table_name: str,
    user: User,
    db: AsyncSession
) -> list[str]:
    """
    Returns a list of WHERE clause fragments to AND into the query.
    Returns [] if no filters apply -- query runs unfiltered.
    """
    from app.core.deps import resolve_department_chain, _table_name_matches
    from app.models import TableRLSFilter

    role_chain = [str(user.role_id)] if user.role_id else []
    dept_chain = await resolve_department_chain(user.department_id, db)

    conditions = []
    if user.id:
        conditions.append(TableRLSFilter.applies_to_user_id == str(user.id))
    if role_chain:
        conditions.append(TableRLSFilter.applies_to_role_id.in_(role_chain))
    if dept_chain:
        conditions.append(TableRLSFilter.applies_to_dept_id.in_(dept_chain))

    if not conditions:
        return []

    filters_res = await db.execute(
        select(TableRLSFilter).where(
            TableRLSFilter.connector_id == connector_id,
            TableRLSFilter.is_active == True,
            or_(*conditions)
        )
    )
    all_filters = filters_res.scalars().all()
    filters = [f for f in all_filters if _table_name_matches(f.table_name, table_name)]

    context = await resolve_rls_context(user, db)
    clauses = []

    for f in filters:
        try:
            substituted, _ = substitute_placeholders(f.filter_expression, context)
            clauses.append(substituted)
        except ValueError as e:
            # Log and skip bad filter -- never silently pass bad SQL
            logger.error(f"RLS filter {f.id} substitution failed: {e}")
            continue

    return clauses
