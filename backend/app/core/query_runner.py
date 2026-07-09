import asyncio
import time
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User

logger = logging.getLogger("query_runner")

# ── Module-level cache for rls_enabled setting ───────────────────────────────
_rls_enabled_cache: dict = {"value": True, "fetched_at": 0.0}
_RLS_CACHE_TTL = 30  # seconds


async def _is_rls_enabled(db: AsyncSession) -> bool:
    """
    Check the global rls_enabled setting with a 30-second TTL cache.
    Returns True if RLS is enabled (default when no setting exists).
    """
    now = time.monotonic()
    if now - _rls_enabled_cache["fetched_at"] < _RLS_CACHE_TTL:
        return _rls_enabled_cache["value"]

    try:
        from app.models import RLSGlobalSetting
        result = await db.execute(
            select(RLSGlobalSetting.value).where(RLSGlobalSetting.key == "rls_enabled")
        )
        row = result.scalar_one_or_none()
        enabled = row != "false" if row is not None else True
    except Exception:
        # Table might not exist yet — default to enabled
        enabled = True

    _rls_enabled_cache["value"] = enabled
    _rls_enabled_cache["fetched_at"] = now
    return enabled


async def apply_rls_to_query(
    raw_query: str,
    connector_id: str,
    table_name: str,
    user: User,
    db: AsyncSession,
    dialect: str = "",
) -> str:
    """
    Injects RLS WHERE clauses directly into the query's matching SELECT nodes.
    Only applies to SELECT statements — writes pass through unchanged.
    """
    if not raw_query.strip().upper().startswith('SELECT'):
        return raw_query

    # GAP 4: Global RLS kill switch — if disabled, skip all filtering
    if not await _is_rls_enabled(db):
        return raw_query

    # GAP 1: Superadmin bypass — never apply RLS filters to superadmins
    if user.is_superadmin:
        return raw_query

    from app.core.rls import resolve_rls_filters
    from app.core.packages import resolve_package_rls_filters

    direct_clauses  = await resolve_rls_filters(connector_id, table_name, user, db)
    package_clauses = await resolve_package_rls_filters(connector_id, table_name, user, db)
    clauses = direct_clauses + package_clauses

    if not clauses:
        return raw_query

    combined = " AND ".join(f"({c})" for c in clauses)

    # Attempt AST-based RLS injection directly to the matching table's SELECT node
    import sqlglot
    from sqlglot import exp
    try:
        tree = sqlglot.parse_one(raw_query, read=dialect or None)
        from app.tools.sql_helpers import _table_matches

        modified = False
        for select_node in tree.find_all(exp.Select):
            has_match = False
            for tbl in select_node.find_all(exp.Table):
                # Ensure the table node belongs to the current Select statement (not nested)
                if tbl.find_ancestor(exp.Select) is select_node:
                    if _table_matches(tbl.name, tbl.db, table_name):
                        has_match = True
                        break

            if has_match:
                rls_cond = sqlglot.parse_one(combined, into=exp.Condition)
                where = select_node.args.get("where")
                if where:
                    where.set("this", exp.and_(where.this, rls_cond))
                else:
                    select_node.where(rls_cond, copy=False)
                modified = True

        if modified:
            return tree.sql(dialect=dialect or None)
    except Exception as e:
        logger.warning(
            "AST manager-scoped RLS injection failed (%s); falling back to subquery wrapping: %s",
            e,
            raw_query[:200]
        )

    # Fallback to subquery wrapping (original behavior)
    wrapped = f"SELECT * FROM ({raw_query}) AS __rls_wrapped__ WHERE {combined}"
    return wrapped
