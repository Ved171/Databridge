"""
app/tools/db_tools.py
─────────────────────────────────────────────────────────────────────────────
Central source-of-truth for ALL DataBridge tool functions.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import check_connector_permission
from app.core.security import decrypt_credential
from app.connectors.registry import get_connector
from app.connectors.base import QueryResult
from app.models import Connector, User, RLSPolicy
from app.tools.sql_helpers import (
    classify_operation, apply_rls, build_rich_schema_prompt,
)
from app.tools.duckdb_engine import (
    duckdb_engine, make_table_alias,
    translate_query, validate_sql, sql_fingerprint,
    SQLGLOT_DIALECT_MAP,
    normalize_query_casings, load_cross_db_links_from_schema,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tool context
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ToolContext:
    user: User
    db: AsyncSession


from app.tools.query_cache import query_cache as _cache


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_active_connector(ctx: ToolContext, db_id: str) -> Optional[Connector]:
    result = await ctx.db.execute(select(Connector).where(Connector.id == db_id))
    return result.scalar_one_or_none()


async def _get_rls_policies(ctx: ToolContext, db_id: str) -> list:
    from sqlalchemy import select, or_, and_, cast, String, func

    user_id_str = str(ctx.user.id)
    user_role_str = (ctx.user.role or "member").strip().lower()

    result = await ctx.db.execute(
        select(RLSPolicy).where(
            RLSPolicy.connector_id == db_id,
            RLSPolicy.is_active == True,
            or_(
                RLSPolicy.applies_to_user_id == user_id_str,
                func.lower(cast(RLSPolicy.applies_to_role, String)) == user_role_str,
                and_(RLSPolicy.applies_to_user_id.is_(None), RLSPolicy.applies_to_role.is_(None))
            )
        )
    )
    policies = result.scalars().all()
    if policies:
        logger.info("RLS: found %d active policies for connector=%s user=%s (role=%s)",
                     len(policies), db_id, user_id_str, user_role_str)
    return policies


def _build_user_context(user: User) -> dict:
    return {
        "id":    str(user.id),
        "email": user.email,
        "name":  getattr(user, "name", ""),
    }


def _connector_sqlglot_dialect(connector: Connector) -> str:
    db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()
    return SQLGLOT_DIALECT_MAP.get(db_type, "")


async def _execute_on_connector(connector: Connector, query: str) -> dict:
    dialect = _connector_sqlglot_dialect(connector)
    if dialect:
        query = normalize_query_casings(query, dialect, connector.schema_cache)
    config = json.loads(decrypt_credential(connector.encrypted_config))
    adapter = get_connector(connector.type, config)
    res = await adapter.execute_query(query)
    res.columns = [c.strip() for c in res.columns]
    res.rows = [[v.strip() if isinstance(v, str) else v for v in row] for row in res.rows]
    return {
        "db_name":      connector.name,
        "db_type":      str(connector.type),
        "columns":      res.columns,
        "rows":         res.rows[:200],
        "row_count":    res.row_count,
        "is_truncated": res.row_count > 200,
        "duration_ms":  round(res.duration_ms, 2),
    }


async def _execute_on_connector_raw(connector: Connector, query: str) -> QueryResult:
    dialect = _connector_sqlglot_dialect(connector)
    if dialect:
        query = normalize_query_casings(query, dialect, connector.schema_cache)
    config = json.loads(decrypt_credential(connector.encrypted_config))
    adapter = get_connector(connector.type, config)
    res = await adapter.execute_query(query)
    res.columns = [c.strip() for c in res.columns]
    res.rows = [[v.strip() if isinstance(v, str) else v for v in row] for row in res.rows]
    return res


# ── Dangerous SQL patterns blocked before execution ──────────────────────────
# These bypass our table-level permission checks because sqlglot cannot extract
# table names from dynamic SQL inside EXEC/sp_executesql string parameters.
_BLOCKED_SQL_PATTERNS = re.compile(
    r'\b('
    r'EXEC(?:UTE)?\b'
    r'|sp_executesql'
    r'|xp_cmdshell'
    r'|xp_regread'
    r'|xp_fileexist'
    r'|OPENROWSET'
    r'|OPENQUERY'
    r'|OPENDATASOURCE'
    r'|DBCC\b'
    r'|BULK\s+INSERT'
    r'|RECONFIGURE'
    r')'
    , re.IGNORECASE
)

# System catalog views that expose metadata and should be blocked for non-admin users
_BLOCKED_SYSTEM_TABLES = re.compile(
    r'\b('
    r'sys\.'
    r'|INFORMATION_SCHEMA\.'
    r'|msdb\.'
    r'|master\.sys\.'
    r'|tempdb\.sys\.'
    r')'
    , re.IGNORECASE
)


def _validate_query(query: str, dialect: str) -> Optional[str]:
    """Validate query syntax and block dangerous patterns."""
    # Block dangerous commands that bypass table permission checks
    if _BLOCKED_SQL_PATTERNS.search(query):
        return "Blocked: EXEC, sp_executesql, and dynamic SQL commands are not permitted."
    if _BLOCKED_SYSTEM_TABLES.search(query):
        return "Blocked: Direct access to system catalog views (sys.*, INFORMATION_SCHEMA.*) is not permitted."
    return validate_sql(query, dialect=dialect)


def _safe_val(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    escaped = str(v).replace("'", "''")
    return f"'{escaped}'"


# ─────────────────────────────────────────────────────────────────────────────
# Atlas overlay helper
# ─────────────────────────────────────────────────────────────────────────────

def _overlay_atlas_knowledge(tables: List[dict], connector_id: str) -> List[dict]:
    """
    Merge atlas tribal knowledge (gotcha, learned_filter, summary, aggregation)
    into a list of table dicts fetched from the live schema cache.
    Atlas fields win over empty schema fields; schema fields win if atlas is absent.
    """
    try:
        from app.services.atlas_builder import get_atlas_builder
        builder = get_atlas_builder()
        atlas = builder.load_connector_atlas_by_id(connector_id)
        if not atlas:
            return tables

        atlas_tables: Dict[str, dict] = {}
        for at in atlas.get("tables", []):
            name = at.get("name", "")
            schema = at.get("schema", "")
            key = f"{schema}.{name}".lower() if schema else name.lower()
            atlas_tables[key] = at

        enriched = []
        for t in tables:
            t_name = t.get("name", "")
            t_schema = t.get("schema", "")
            key = f"{t_schema}.{t_name}".lower() if t_schema else t_name.lower()

            at = atlas_tables.get(key) or atlas_tables.get(t_name.lower())
            if at:
                merged = dict(t)
                for field in ("summary", "gotcha", "learned_filter", "aggregation"):
                    if at.get(field):
                        merged[field] = at[field]
                enriched.append(merged)
            else:
                enriched.append(t)

        return enriched
    except Exception as e:
        logger.warning("Atlas overlay failed for connector %s: %s", connector_id, e)
        return tables


# ─────────────────────────────────────────────────────────────────────────────
# Tool: List Databases
# ─────────────────────────────────────────────────────────────────────────────

def _get_query_format_hint(db_type: str) -> str:
    hints = {
        "mongodb":       'JSON aggregation pipeline: {"collection":"...","pipeline":[...]}',
        "elasticsearch": 'JSON DSL: {"index":"...","query":{...}}',
        "redis":         'JSON command: {"command":"SCAN","pattern":"prefix:*"}',
        "salesforce":    "SOQL: SELECT Id, Name FROM Account WHERE ...",
        "rest_api":      'JSON params: {"endpoint":"...","method":"GET","params":{...}}',
    }
    return hints.get(db_type.lower(), "SQL")


async def tool_list_available_databases(ctx: ToolContext) -> str:
    from app.services.atlas_builder import get_atlas_builder
    builder = get_atlas_builder()
    all_atlases = builder.load_all_atlases()

    stmt = select(Connector).where(Connector.is_active == True)
    result = await ctx.db.execute(stmt)
    connectors = result.scalars().all()

    if not connectors:
        return "No active databases found."

    output = ["### Available Databases\n"]
    found = False
    for c in connectors:
        if not await check_connector_permission(c.id, "read", ctx.user, ctx.db):
            continue
        found = True
        db_type = str(c.type)
        nl_format = _get_query_format_hint(db_type)
        schema_status = "[OK] Schema cached" if c.schema_cache else "[!] Schema not cached"

        # Atlas status
        atlas = all_atlases.get(str(c.id))
        if atlas:
            meta = atlas.get("metadata", {})
            atlas_status = "[OK] Atlas ready ({meta.get('table_count', '?')} tables, updated {meta.get('last_updated', '?')[:10]})"
        else:
            atlas_status = "[!] No atlas -- run create_atlases.py"

        output.append(
            f"- **ID**: `{c.id}`\n"
            f"  - **Name**: {c.name}\n"
            f"  - **Type**: {db_type}\n"
            f"  - **Query Format**: {nl_format}\n"
            f"  - **Schema**: {schema_status}\n"
            f"  - **Atlas**: {atlas_status}"
        )
    return "\n".join(output) if found else "No databases accessible with your permissions."


# ─────────────────────────────────────────────────────────────────────────────
# Tool: Get Schema  (live schema + atlas overlay)
# ─────────────────────────────────────────────────────────────────────────────

async def tool_get_database_schema(
    ctx: ToolContext,
    db_id: str,
    schema: Optional[str] = None,
    table_names: Optional[List[str]] = None,
) -> str:
    connector = await _get_active_connector(ctx, db_id)
    if not connector:
        return f"Error: Database '{db_id}' not found."
    if not await check_connector_permission(str(connector.id), "read", ctx.user, ctx.db):
        return "Error: Permission denied (Read)."
    if not connector.schema_cache:
        return "Error: Schema not cached. Admin must run refresh-schema."

    tables = connector.schema_cache.get("tables", [])
    if schema:
        tables = [t for t in tables if t.get("schema") == schema]

    if table_names:
        filtered_tables = []
        for t in tables:
            t_schema = t.get("schema")
            t_name = t.get("name")
            full_name = f"{t_schema}.{t_name}" if t_schema else t_name
            if t_name in table_names or full_name in table_names:
                filtered_tables.append(t)
        tables = filtered_tables

    # Filter tables user is not authorized to read
    from app.core.deps import check_table_permission
    allowed_tables = []
    cache = {}
    for t in tables:
        t_schema = t.get("schema")
        t_name = t.get("name")
        full_name = f"{t_schema}.{t_name}" if t_schema else t_name
        if await check_table_permission(str(connector.id), full_name, "read", ctx.user, ctx.db, _cache=cache):
            allowed_tables.append(t)
    tables = allowed_tables

    # Overlay atlas tribal knowledge on top of live schema
    tables = _overlay_atlas_knowledge(tables, str(db_id))


    return build_rich_schema_prompt(tables=tables, connector_type=str(connector.type))


# ─────────────────────────────────────────────────────────────────────────────
# Tool: Global Schema Awareness  (atlas-first)
# ─────────────────────────────────────────────────────────────────────────────

async def tool_get_global_schema_awareness(ctx: ToolContext) -> str:
    from app.services.atlas_builder import get_atlas_builder
    builder = get_atlas_builder()
    all_atlases = builder.load_all_atlases()

    stmt = select(Connector).where(Connector.is_active == True)
    result = await ctx.db.execute(stmt)
    connectors = result.scalars().all()

    if not connectors:
        return "No active databases found."

    output = ["# Global DataBridge Schema\n"]
    found = False
    for c in connectors:
        if not await check_connector_permission(c.id, "read", ctx.user, ctx.db):
            continue
        found = True

        # Prefer atlas tables (enriched); fall back to raw schema_cache
        atlas = all_atlases.get(str(c.id))
        if atlas:
            tables = atlas.get("tables", [])
            source_label = "atlas"
        else:
            tables = (c.schema_cache or {}).get("tables", [])
            source_label = "schema cache"

        # Filter tables user is not authorized to read
        from app.core.deps import check_table_permission
        allowed_tables = []
        cache = {}
        for t in tables:
            t_schema = t.get("schema")
            t_name = t.get("name")
            full_name = f"{t_schema}.{t_name}" if t_schema else t_name
            if await check_table_permission(c.id, full_name, "read", ctx.user, ctx.db, _cache=cache):
                allowed_tables.append(t)
        tables = allowed_tables

        schemas: dict = {}

        for t in tables:
            sch = t.get("schema") or "default"
            entry = t["name"]
            # Append a [INFO] marker if the table has tribal knowledge
            has_knowledge = any(t.get(f) for f in ("gotcha", "learned_filter", "summary", "aggregation"))
            if has_knowledge:
                entry += " [INFO]"
            schemas.setdefault(sch, []).append(entry)

        output.append(f"## {c.name} (ID: `{c.id}`, Type: {c.type}) [{source_label}]")
        if schemas:
            for sch, tbls in schemas.items():
                output.append(f"  **{sch}**: {', '.join(f'`{t}`' for t in tbls)}")
        else:
            output.append("  *No tables cached*")
        output.append("")

    # Load cross-database link registry from atlases
    try:
        for atlas in all_atlases.values():
            load_cross_db_links_from_schema(atlas)
    except Exception as e:
        logger.warning("Failed to load cross-DB links from atlases: %s", e)

    return "\n".join(output) if found else "No accessible databases."


async def _check_query_table_permissions(
    connector_id: str,
    query: str,
    operation: str,
    user: User,
    db: AsyncSession,
    dialect: str,
) -> Optional[str]:
    """
    Checks table permissions for SQL or NoSQL query.
    Returns None if allowed, or an error message string if blocked.
    """
    from app.core.deps import check_table_permission
    from app.models import TablePermission

    # Check if table permissions exist for this connector first to avoid unnecessary parsing
    exist_stmt = select(TablePermission.id).where(TablePermission.connector_id == connector_id).limit(1)
    exist_res = await db.execute(exist_stmt)
    if not exist_res.scalar_one_or_none():
        return None

    # If it is a NoSQL query (starts with '{'):
    if query.strip().startswith("{"):
        try:
            q_obj = json.loads(query)
            if isinstance(q_obj, dict):
                tbl = q_obj.get("collection") or q_obj.get("index") or q_obj.get("object") or q_obj.get("table")
                if tbl:
                    allowed = await check_table_permission(connector_id, tbl, operation, user, db)
                    if not allowed:
                        return f"Error: Permission denied -- no '{operation.upper()}' access on table/collection '{tbl}'."
        except Exception:
            return "Error: Permission denied -- failed to parse NoSQL query payload."
    else:
        # SQL query
        import sqlglot
        from sqlglot import exp
        try:
            parsed = sqlglot.parse_one(query, read=dialect)
            if not parsed:
                return "Error: Permission denied -- empty query."
            
            tables = []
            for t in parsed.find_all(exp.Table):
                schema = t.db
                name = t.name
                if schema:
                    tables.append(f"{schema}.{name}")
                else:
                    tables.append(name)
            
            if not tables:
                return None

            for tbl in tables:
                allowed = await check_table_permission(connector_id, tbl, operation, user, db)
                if not allowed:
                    return f"Error: Permission denied -- no '{operation.upper()}' access on table '{tbl}'."
        except Exception as e:
            return f"Error: Permission denied -- query parsing failed: {str(e)}."

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Tool: Execute Query (READ + WRITE)
# ─────────────────────────────────────────────────────────────────────────────

async def tool_execute_query(ctx: ToolContext, db_id: str, query: str) -> str:
    connector = await _get_active_connector(ctx, db_id)

    if not connector:
        return f"Error: Database '{db_id}' not found."

    dialect = _connector_sqlglot_dialect(connector)

    validation_error = _validate_query(query, dialect)
    if validation_error:
        return f"Error: Query validation failed -- {validation_error}"

    op = classify_operation(query)
    if not await check_connector_permission(str(connector.id), op, ctx.user, ctx.db):
        return f"Error: Permission denied -- no '{op.upper()}' access on '{connector.name}'."

    table_error = await _check_query_table_permissions(
        connector_id=db_id,
        query=query,
        operation=op,
        user=ctx.user,
        db=ctx.db,
        dialect=dialect
    )
    if table_error:
        return table_error


    rls_policies = await _get_rls_policies(ctx, db_id)
    if rls_policies:
        user_ctx = _build_user_context(ctx.user)
        db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()
        if query.strip().startswith("{"):
            # NoSQL RLS injection
            from app.tools.nosql_rls import apply_rls_nosql
            query = apply_rls_nosql(query, db_type, rls_policies, user_ctx)
            try:
                q_obj = json.loads(query)
                if isinstance(q_obj, dict) and "error" in q_obj:
                    return f"Error: Permission denied -- {q_obj['error']}"
            except Exception:
                pass
        elif op == "read":
            # SQL RLS injection — pass each schema-qualified table once
            tables_in_cache = (connector.schema_cache or {}).get("tables", [])
            applied_tables = set()
            for table in tables_in_cache:
                bare_name = table["name"]
                schema_prefix = table.get("schema")
                full_name = f"{schema_prefix}.{bare_name}" if schema_prefix else bare_name
                if full_name.lower() in applied_tables:
                    continue
                applied_tables.add(full_name.lower())
                query = apply_rls(query, rls_policies, full_name, user_ctx, dialect=dialect)

    # F-08: Apply Manager-Scoped Row-Level Security
    if op == "read" and not query.strip().startswith("{"):
        from app.core.query_runner import apply_rls_to_query
        import sqlglot
        from sqlglot import exp
        try:
            parsed = sqlglot.parse_one(query, read=dialect)
            if parsed:
                applied_filters = set()
                for t in parsed.find_all(exp.Table):
                    schema = t.db
                    name = t.name
                    full_name = f"{schema}.{name}" if schema else name
                    if full_name.lower() not in applied_filters:
                        applied_filters.add(full_name.lower())
                        query = await apply_rls_to_query(query, db_id, full_name, ctx.user, ctx.db, dialect=dialect)
        except Exception as e:
            logger.error("Failed to apply manager-scoped RLS to query: %s", e)

    if op == "read":
        cached = await _cache.get(db_id, query)
        if cached:
            cached["from_cache"] = True
            return json.dumps(cached, indent=2, default=str)

    try:
        data = await _execute_on_connector(connector, query)
        import sqlglot
        from sqlglot import exp
        tables = []
        try:
            if not query.strip().startswith("{"):
                parsed = sqlglot.parse_one(query, read=dialect)
                if parsed:
                    tables = [t.name for t in parsed.find_all(exp.Table)]
        except Exception:
            pass

        if op == "read":
            await _cache.set(db_id, query, data, tables=tables)
        else:
            if tables:
                for t in tables:
                    await _cache.invalidate(db_id, table_name=t)
            else:
                await _cache.invalidate(db_id)

        return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error("Query failed db_id=%s error=%s", db_id, str(e))
        return f"Error executing query on '{connector.name}': {str(e)}"





# ─────────────────────────────────────────────────────────────────────────────
# Tool: Record Discovery
# ─────────────────────────────────────────────────────────────────────────────

async def tool_record_discovery(
    ctx: ToolContext,
    table_name: str,
    summary: Optional[str] = None,
    gotcha: Optional[str] = None,
    aggregation: Optional[str] = None,
    learned_filter: Optional[str] = None,
) -> str:
    if not any([summary, gotcha, aggregation, learned_filter]):
        return "Nothing recorded - please provide at least one of: summary, gotcha, aggregation, learned_filter."

    stmt = select(Connector).where(Connector.is_active == True)
    result = await ctx.db.execute(stmt)
    connectors = result.scalars().all()

    found_tables = []

    for connector in connectors:
        if not await check_connector_permission(connector.id, "read", ctx.user, ctx.db):
            continue

        tables = (connector.schema_cache or {}).get("tables", [])
        for table in tables:
            t_schema = table.get("schema")
            t_name = table.get("name")
            full_path = f"{connector.name}.{t_schema}.{t_name}" if t_schema else f"{connector.name}.{t_name}"
            schema_path = f"{t_schema}.{t_name}" if t_schema else t_name

            if table_name.lower() in [full_path.lower(), schema_path.lower(), t_name.lower()]:
                found_tables.append((connector, table))

    if not found_tables:
        return f"Table '{table_name}' not found in the atlas. Use 'get_global_schema_awareness' to find the exact path."

    if len(found_tables) > 1:
        options = [
            f"{c.name}.{t.get('schema')}.{t.get('name')}" if t.get('schema') else f"{c.name}.{t.get('name')}"
            for c, t in found_tables
        ]
        return f"Table '{table_name}' is ambiguous. Did you mean one of: {', '.join(options)}?"

    connector, table = found_tables[0]

    recorded = []
    if summary is not None:
        table["summary"] = summary
        recorded.append("summary")
    if gotcha is not None:
        table["gotcha"] = gotcha
        recorded.append("gotcha")
    if aggregation is not None:
        table["aggregation"] = aggregation
        recorded.append("aggregation")
    if learned_filter is not None:
        table["learned_filter"] = learned_filter
        recorded.append("learned_filter")

    # 1. Persist to DB schema_cache
    flag_modified(connector, "schema_cache")
    await ctx.db.commit()

    # 2. Write to atlas file so get_database_schema picks it up immediately
    try:
        from app.services.atlas_builder import get_atlas_builder
        builder = get_atlas_builder()
        atlas = builder.load_connector_atlas_by_id(str(connector.id))

        if atlas:
            t_schema = table.get("schema", "")
            t_name = table.get("name", "")
            key = f"{t_schema}.{t_name}".lower() if t_schema else t_name.lower()

            atlas_tables = atlas.get("tables", [])
            matched = False
            for at in atlas_tables:
                at_key = f"{at.get('schema','')}.{at.get('name','')}".lower() if at.get("schema") else at.get("name","").lower()
                if at_key == key or at.get("name","").lower() == t_name.lower():
                    for field in ("summary", "gotcha", "aggregation", "learned_filter"):
                        if locals().get(field) is not None:
                            at[field] = locals()[field]
                    matched = True
                    break

            if not matched:
                # Add as new entry
                atlas_tables.append({
                    "name": t_name,
                    "schema": t_schema,
                    **{f: locals()[f] for f in ("summary", "gotcha", "aggregation", "learned_filter") if locals()[f] is not None}
                })
                atlas["tables"] = atlas_tables

            from datetime import datetime
            atlas["metadata"]["last_updated"] = datetime.utcnow().isoformat() + "Z"

            builder.build_connector_atlas(
                connector_id=str(connector.id),
                connector_type=atlas["metadata"].get("connector_type", str(connector.type)),
                db_name=atlas["metadata"].get("db_name", connector.name),
                tables=atlas["tables"],
                timestamp=atlas["metadata"]["last_updated"],
            )
            logger.info("Discovery written to atlas for connector %s, table %s", connector.id, table_name)
        else:
            logger.warning("No atlas file found for connector %s -- discovery saved to DB only", connector.id)
    except Exception as e:
        logger.error("Failed to write discovery to atlas: %s", e)

    return f"Discovery recorded for '{table_name}' ({', '.join(recorded)}). Atlas and DB updated -- schema reads will reflect this immediately."