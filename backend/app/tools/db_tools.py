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


# ─────────────────────────────────────────────────────────────────────────────
# Redis-backed TTL Query Cache
# ─────────────────────────────────────────────────────────────────────────────

import redis.asyncio as aioredis
import pickle
import pyarrow as pa
import io
from app.core.config import settings

class _QueryCache:
    """
    Distributed Redis cache with PyArrow IPC serialization.
    Keys: "db_cache:{connector_id}:{sql_fingerprint}"
    """
    _TTL_SECONDS = 120
    _PREFIX = "db_cache"

    def __init__(self):
        self._redis = aioredis.from_url(settings.REDIS_URL)

    def _key(self, connector_id: str, sql: str) -> str:
        return f"{self._PREFIX}:{connector_id}:{sql_fingerprint(sql)}"

    async def get(self, connector_id: str, sql: str) -> Optional[Any]:
        try:
            k = self._key(connector_id, sql)
            raw = await self._redis.get(k)
            if not raw:
                return None

            meta_len = int.from_bytes(raw[:4], "little")
            meta = pickle.loads(raw[4:4+meta_len])

            if "is_dict" in meta:
                return meta["data"]

            qr = QueryResult(
                columns=meta["columns"],
                rows=meta["rows"],
                row_count=meta["row_count"],
                duration_ms=meta["duration_ms"]
            )

            arrow_data = raw[4+meta_len:]
            if arrow_data:
                with pa.ipc.open_stream(io.BytesIO(arrow_data)) as reader:
                    qr.pa_table = reader.read_all()

            return qr
        except Exception as e:
            logger.warning("Cache get failed: %s", e)
            return None

    async def set(self, connector_id: str, sql: str, data: Any, tables: List[str] = None) -> None:
        try:
            k = self._key(connector_id, sql)

            meta = {"tables": tables or []}
            arrow_bytes = b""

            if isinstance(data, dict):
                meta["is_dict"] = True
                meta["data"] = data
            elif isinstance(data, QueryResult):
                meta.update({
                    "columns": data.columns,
                    "rows": data.rows,
                    "row_count": data.row_count,
                    "duration_ms": data.duration_ms
                })
                if data.pa_table is not None:
                    sink = io.BytesIO()
                    with pa.ipc.new_stream(sink, data.pa_table.schema) as writer:
                        writer.write_table(data.pa_table)
                    arrow_bytes = sink.getvalue()

            meta_blob = pickle.dumps(meta)
            packet = len(meta_blob).to_bytes(4, "little") + meta_blob + arrow_bytes

            await self._redis.setex(k, self._TTL_SECONDS, packet)

            if tables:
                for t in tables:
                    t_key = f"{self._PREFIX}_tables:{connector_id}:{t}"
                    await self._redis.sadd(t_key, k)
                    await self._redis.expire(t_key, self._TTL_SECONDS)
        except Exception as e:
            logger.warning("Cache set failed: %s", e)

    async def invalidate(self, connector_id: str, table_name: Optional[str] = None) -> None:
        try:
            if table_name:
                t_key = f"{self._PREFIX}_tables:{connector_id}:{table_name}"
                keys = await self._redis.smembers(t_key)
                if keys:
                    await self._redis.delete(*keys)
                    await self._redis.delete(t_key)
            else:
                pattern = f"{self._PREFIX}:{connector_id}:*"
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
        except Exception as e:
            logger.warning("Cache invalidation failed: %s", e)


_cache = _QueryCache()


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
    if not await check_connector_permission(db_id, "read", ctx.user, ctx.db):
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
        if await check_table_permission(db_id, full_name, "read", ctx.user, ctx.db, _cache=cache):
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
    if not await check_connector_permission(db_id, op, ctx.user, ctx.db):
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
# Tool: Create Record
# ─────────────────────────────────────────────────────────────────────────────

async def tool_create_record(
    ctx: ToolContext,
    db_id: str,
    table_or_collection: str,
    data: dict,
) -> str:
    connector = await _get_active_connector(ctx, db_id)
    if not connector:
        return f"Error: Database '{db_id}' not found."
    if not await check_connector_permission(db_id, "create", ctx.user, ctx.db):
        return f"Error: Permission denied -- no CREATE access on '{connector.name}'."

    from app.core.deps import check_table_permission
    if not await check_table_permission(db_id, table_or_collection, "create", ctx.user, ctx.db):
        return f"Error: Permission denied -- no 'CREATE' access on table/collection '{table_or_collection}'."


    db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()

    try:
        if db_type == "mongodb":
            query = json.dumps({"collection": table_or_collection, "operation": "insertOne", "document": data})
        elif db_type == "elasticsearch":
            query = json.dumps({"index": table_or_collection, "operation": "index", "document": data})
        elif db_type == "salesforce":
            query = json.dumps({"operation": "insert", "object": table_or_collection, "data": data})
        elif db_type == "redis":
            key = data.get("key") or f"{table_or_collection}:{data.get('id', 'new')}"
            query = json.dumps({"command": "SET", "args": [key, json.dumps(data)]})
        else:
            cols = ", ".join(data.keys())
            vals = ", ".join(_safe_val(v) for v in data.values())
            query = f"INSERT INTO {table_or_collection} ({cols}) VALUES ({vals}) RETURNING *"

        if query.strip().startswith("{"):
            rls_policies = await _get_rls_policies(ctx, db_id)
            if rls_policies:
                user_ctx = _build_user_context(ctx.user)
                from app.tools.nosql_rls import apply_rls_nosql
                query = apply_rls_nosql(query, db_type, rls_policies, user_ctx)
                try:
                    q_obj = json.loads(query)
                    if isinstance(q_obj, dict) and "error" in q_obj:
                        return f"Error: Permission denied -- {q_obj['error']}"
                except Exception:
                    pass

        result = await _execute_on_connector(connector, query)
        result["operation"] = "create"
        result["table"] = table_or_collection
        await _cache.invalidate(db_id, table_name=table_or_collection)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Error creating record in '{connector.name}'.{table_or_collection}: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# Tool: Update Record
# ─────────────────────────────────────────────────────────────────────────────

async def tool_update_record(
    ctx: ToolContext,
    db_id: str,
    table_or_collection: str,
    record_id: str,
    id_field: str,
    updates: dict,
) -> str:
    connector = await _get_active_connector(ctx, db_id)
    if not connector:
        return f"Error: Database '{db_id}' not found."
    if not await check_connector_permission(db_id, "update", ctx.user, ctx.db):
        return f"Error: Permission denied -- no UPDATE access on '{connector.name}'."

    from app.core.deps import check_table_permission
    if not await check_table_permission(db_id, table_or_collection, "update", ctx.user, ctx.db):
        return f"Error: Permission denied -- no 'UPDATE' access on table/collection '{table_or_collection}'."


    db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()

    try:
        if db_type == "mongodb":
            query = json.dumps({"collection": table_or_collection, "operation": "updateOne", "filter": {id_field: record_id}, "update": {"$set": updates}})
        elif db_type == "salesforce":
            query = json.dumps({"operation": "update", "object": table_or_collection, "id": record_id, "data": updates})
        elif db_type == "redis":
            query = json.dumps({"command": "SET", "args": [record_id, json.dumps(updates)]})
        else:
            set_clause = ", ".join(f"{k} = {_safe_val(v)}" for k, v in updates.items())
            id_val = _safe_val(record_id)
            query = f"UPDATE {table_or_collection} SET {set_clause} WHERE {id_field} = {id_val}"

        if query.strip().startswith("{"):
            rls_policies = await _get_rls_policies(ctx, db_id)
            if rls_policies:
                user_ctx = _build_user_context(ctx.user)
                from app.tools.nosql_rls import apply_rls_nosql
                query = apply_rls_nosql(query, db_type, rls_policies, user_ctx)
                try:
                    q_obj = json.loads(query)
                    if isinstance(q_obj, dict) and "error" in q_obj:
                        return f"Error: Permission denied -- {q_obj['error']}"
                except Exception:
                    pass

        result = await _execute_on_connector(connector, query)
        result["operation"] = "update"
        result["table"] = table_or_collection
        result["record_id"] = record_id
        await _cache.invalidate(db_id, table_name=table_or_collection)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Error updating record in '{connector.name}'.{table_or_collection}: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# Tool: Delete Record
# ─────────────────────────────────────────────────────────────────────────────

async def tool_delete_record(
    ctx: ToolContext,
    db_id: str,
    table_or_collection: str,
    record_id: str,
    id_field: str = "id",
) -> str:
    connector = await _get_active_connector(ctx, db_id)
    if not connector:
        return f"Error: Database '{db_id}' not found."
    if not await check_connector_permission(db_id, "delete", ctx.user, ctx.db):
        return f"Error: Permission denied -- no DELETE access on '{connector.name}'."

    from app.core.deps import check_table_permission
    if not await check_table_permission(db_id, table_or_collection, "delete", ctx.user, ctx.db):
        return f"Error: Permission denied -- no 'DELETE' access on table/collection '{table_or_collection}'."


    db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()

    try:
        if db_type == "mongodb":
            query = json.dumps({"collection": table_or_collection, "operation": "deleteOne", "filter": {id_field: record_id}})
        elif db_type == "salesforce":
            query = json.dumps({"operation": "delete", "object": table_or_collection, "id": record_id})
        elif db_type == "redis":
            query = json.dumps({"command": "DEL", "args": [record_id]})
        else:
            id_val = _safe_val(record_id)
            query = f"DELETE FROM {table_or_collection} WHERE {id_field} = {id_val}"

        if query.strip().startswith("{"):
            rls_policies = await _get_rls_policies(ctx, db_id)
            if rls_policies:
                user_ctx = _build_user_context(ctx.user)
                from app.tools.nosql_rls import apply_rls_nosql
                query = apply_rls_nosql(query, db_type, rls_policies, user_ctx)
                try:
                    q_obj = json.loads(query)
                    if isinstance(q_obj, dict) and "error" in q_obj:
                        return f"Error: Permission denied -- {q_obj['error']}"
                except Exception:
                    pass

        result = await _execute_on_connector(connector, query)
        result["operation"] = "delete"
        result["table"] = table_or_collection
        result["record_id"] = record_id
        await _cache.invalidate(db_id, table_name=table_or_collection)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Error deleting record from '{connector.name}'.{table_or_collection}: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# AST Pushdown Planner
# ─────────────────────────────────────────────────────────────────────────────

def apply_pushdown_optimizations(
    queries: List[Dict[str, str]],
    federation_sql: str,
    connector_map: Dict[str, Connector],
) -> Tuple[List[Dict[str, str]], int]:
    if not federation_sql:
        return queries, 0

    try:
        import sqlglot
        from sqlglot import exp
        fed_ast = sqlglot.parse_one(federation_sql)
    except Exception as e:
        logger.warning("Failed to parse federation_sql for pushdown: %s", e)
        return queries, 0

    alias_to_cols = {}
    for col in fed_ast.find_all(exp.Column):
        alias = col.text("table").lower()
        col_name = col.text("this")
        if alias:
            if alias not in alias_to_cols:
                alias_to_cols[alias] = set()
            alias_to_cols[alias].add(col_name)

    def get_conjuncts(expression):
        if isinstance(expression, exp.And):
            return get_conjuncts(expression.this) + get_conjuncts(expression.expression)
        return [expression]

    def get_referenced_aliases(expression):
        aliases = set()
        for col in expression.find_all(exp.Column):
            alias = col.text("table").lower()
            if alias:
                aliases.add(alias)
        return aliases

    import copy
    def strip_alias_prefix(expression):
        expr_copy = copy.deepcopy(expression)
        for col in expr_copy.find_all(exp.Column):
            col.set("table", "")
        return expr_copy

    alias_to_predicates = {}
    where_clause = fed_ast.find(exp.Where)
    if where_clause:
        conjuncts = get_conjuncts(where_clause.this)
        for conj in conjuncts:
            aliases = get_referenced_aliases(conj)
            if len(aliases) == 1:
                alias = list(aliases)[0]
                if alias not in alias_to_predicates:
                    alias_to_predicates[alias] = []
                alias_to_predicates[alias].append(conj)

    optimized_queries = []
    pushdowns_applied = 0

    for q_item in queries:
        q_copy = dict(q_item)
        db_id = q_item.get("db_id")
        query_sql = q_item.get("query")
        alias = q_item.get("table_alias") or ""
        alias_lower = alias.lower()

        connector = connector_map.get(db_id)
        if not connector or not query_sql or query_sql.strip().startswith("{"):
            optimized_queries.append(q_copy)
            continue

        from app.connectors.base import get_connector_capabilities
        caps = get_connector_capabilities(str(connector.type))
        dialect = _connector_sqlglot_dialect(connector)

        try:
            sub_ast = sqlglot.parse_one(query_sql, read=dialect)
        except Exception as parse_err:
            logger.warning("Failed to parse sub-query for pushdown: %s", parse_err)
            optimized_queries.append(q_copy)
            continue

        applied_projection = False
        applied_predicate = False

        if caps.supports_projection_pushdown and alias_lower in alias_to_cols:
            referenced_cols = alias_to_cols[alias_lower]
            has_star = any(isinstance(expr, exp.Star) for expr in sub_ast.expressions)
            if has_star and referenced_cols:
                new_exprs = [exp.column(col_name) for col_name in sorted(referenced_cols)]
                sub_ast.set("expressions", new_exprs)
                applied_projection = True

        if caps.supports_predicate_pushdown and alias_lower in alias_to_predicates:
            preds = alias_to_predicates[alias_lower]
            pushed_cond = None
            for p in preds:
                stripped = strip_alias_prefix(p)
                if pushed_cond is None:
                    pushed_cond = stripped
                else:
                    pushed_cond = exp.And(this=pushed_cond, expression=stripped)

            if pushed_cond:
                existing_where = sub_ast.find(exp.Where)
                if existing_where:
                    combined = exp.And(this=existing_where.this, expression=pushed_cond)
                    existing_where.set("this", combined)
                else:
                    sub_ast.set("where", exp.Where(this=pushed_cond))
                applied_predicate = True

        if applied_projection or applied_predicate:
            q_copy["query"] = sub_ast.sql(dialect=dialect)
            pushdowns_applied += 1
            logger.info(
                "Applied pushdown on %s (alias: %s): projection=%s, predicate=%s",
                connector.name, alias, applied_projection, applied_predicate
            )

        optimized_queries.append(q_copy)

    return optimized_queries, pushdowns_applied


# ─────────────────────────────────────────────────────────────────────────────
# Tool: Execute Federated Query (DuckDB)
# ─────────────────────────────────────────────────────────────────────────────

async def tool_execute_federated_query(
    ctx: ToolContext,
    queries: List[Dict[str, str]],
    federation_sql: str,
) -> str:
    """
    Execute per-database extraction queries in parallel and join them using DuckDB.
    Pass an empty queries list to run federation_sql purely against mirrored tables.
    """
    start_time = time.monotonic()

    if not queries and not federation_sql:
        return "Error: No queries or federation_sql provided."

    import hashlib
    fed_payload_str = json.dumps({"queries": queries, "federation_sql": federation_sql}, sort_keys=True)
    fed_hash = hashlib.sha256(fed_payload_str.encode("utf-8")).hexdigest()
    fed_cache_key = f"fed_cache:{fed_hash}"

    redis_client = _cache._redis
    try:
        cached_val = await redis_client.get(fed_cache_key)
        if cached_val:
            cache_duration_ms = (time.monotonic() - start_time) * 1000.0
            logger.info("[METRICS] (CACHE HIT) total_execution_ms=%.2f", cache_duration_ms)
            return cached_val.decode("utf-8")
    except Exception as cache_err:
        logger.warning("Federation cache lookup failed: %s", cache_err)

    db_ids = [q.get("db_id") for q in queries if q.get("db_id")]

    all_connectors = []
    if db_ids:
        stmt = select(Connector).where(Connector.is_active == True, Connector.id.in_(db_ids))
        result = await ctx.db.execute(stmt)
        all_connectors = result.scalars().all()

    accessible: List[Connector] = []
    for c in all_connectors:
        if await check_connector_permission(c.id, "read", ctx.user, ctx.db):
            accessible.append(c)

    if db_ids and not accessible:
        return "Error: No accessible databases found or permission denied."

    connector_map = {c.id: c for c in accessible}

    optimized_queries, pushdowns_applied = apply_pushdown_optimizations(
        queries, federation_sql, connector_map
    )

    async def _run_one(q_item: dict) -> Tuple[str, Optional[QueryResult], dict]:
        db_id = q_item.get("db_id")
        query = q_item.get("query")

        connector = connector_map.get(db_id)
        if not connector or not query:
            return db_id or "unknown", None, {"db_id": db_id, "error": "Missing connector, query, or permission denied"}

        alias = q_item.get("table_alias") or make_table_alias(connector.name)

        cached_qr = await _cache.get(db_id, query)
        if cached_qr and isinstance(cached_qr, QueryResult):
            logger.info("Federated sub-query cache hit: db_id=%s", db_id)
            summary = {
                "db_id": db_id, "db_name": connector.name, "db_type": str(connector.type),
                "table_alias": alias, "row_count": cached_qr.row_count,
                "columns": cached_qr.columns, "duration_ms": 0, "query": query, "from_cache": True,
            }
            return alias, cached_qr, summary

        try:
            raw_qr = await _execute_on_connector_raw(connector, query)

            import sqlglot
            from sqlglot import exp
            tables = []
            try:
                parsed = sqlglot.parse_one(query, read=_connector_sqlglot_dialect(connector))
                if parsed:
                    tables = [t.name for t in parsed.find_all(exp.Table)]
            except Exception:
                pass
            await _cache.set(db_id, query, raw_qr, tables=tables)

            summary = {
                "db_id": db_id, "db_name": connector.name, "db_type": str(connector.type),
                "table_alias": alias, "row_count": raw_qr.row_count,
                "columns": raw_qr.columns, "duration_ms": round(raw_qr.duration_ms, 2), "query": query,
            }
            return alias, raw_qr, summary
        except Exception as e:
            logger.error("Sub-query failed db_id=%s error=%s", db_id, str(e))
            return alias, None, {
                "db_id": db_id, "db_name": connector.name,
                "table_alias": alias, "error": str(e), "query": query,
            }

    subqueries_start = time.monotonic()
    tasks = [_run_one(q) for q in optimized_queries]
    gathered = await asyncio.gather(*tasks)
    subqueries_duration_ms = (time.monotonic() - subqueries_start) * 1000.0

    qr_map: Dict[str, QueryResult] = {}
    sub_results: List[dict] = []
    for alias, qr, summary in gathered:
        sub_results.append(summary)
        if qr is not None:
            qr_map[alias] = qr

    failed = [s for s in sub_results if "error" in s]
    if failed:
        return json.dumps({
            "error": "Sub-query failed -- aborting federation.",
            "failed_queries": failed,
            "successful_queries": [s for s in sub_results if "error" not in s],
        }, indent=2, default=str)

    table_to_alias_map: Dict[str, str] = {}
    import sqlglot
    from sqlglot import exp
    for q_item in optimized_queries:
        db_id = q_item.get("db_id")
        query = q_item.get("query")
        if not db_id or not query:
            continue
        connector = connector_map.get(db_id)
        if not connector:
            continue
        alias = q_item.get("table_alias") or make_table_alias(connector.name)

        try:
            dialect = _connector_sqlglot_dialect(connector)
            parsed = sqlglot.parse_one(query, read=dialect)
            if parsed:
                for table in parsed.find_all(exp.Table):
                    parts = []
                    for key in ["catalog", "db", "this"]:
                        node = table.args.get(key)
                        if node:
                            val = node.name if hasattr(node, "name") else str(node)
                            val_clean = val.replace('"', '').replace("'", "").strip()
                            if val_clean:
                                parts.append(val_clean)
                    full_name = ".".join(parts).lower()
                    bare_name = parts[-1].lower() if parts else ""
                    if full_name:
                        table_to_alias_map[full_name] = alias
                    if bare_name:
                        table_to_alias_map[bare_name] = alias
        except Exception as e:
            logger.warning("Failed to parse subquery for table mapping: %s", e)

    federated_result = None
    federation_error = None

    duckdb_start = time.monotonic()
    if federation_sql:
        try:
            fed_qr = duckdb_engine.run_federation(
                tables=qr_map,
                federation_sql=federation_sql,
                table_to_alias_map=table_to_alias_map,
            )
            federated_result = {
                "columns": fed_qr.columns,
                "rows": fed_qr.rows[:500],
                "row_count": fed_qr.row_count,
                "duration_ms": round(fed_qr.duration_ms, 2),
                "federation_sql": federation_sql,
            }
        except Exception as e:
            logger.warning("DuckDB federation failed: %s -- falling back to raw results", e)
            federation_error = str(e)
    duckdb_duration_ms = (time.monotonic() - duckdb_start) * 1000.0

    response_payload: dict = {
        "databases_queried": len(sub_results),
        "sub_query_results": sub_results,
    }

    if federated_result:
        response_payload["federated_result"] = federated_result
    elif federation_error:
        response_payload["federation_error"] = federation_error
        response_payload["raw_results"] = [
            {
                "db_name": s.get("db_name", "Unknown"),
                "columns": s.get("columns", []),
                "rows": qr_map[s["table_alias"]].rows[:200] if s.get("table_alias") in qr_map else [],
            }
            for s in sub_results
        ]

    total_duration_ms = (time.monotonic() - start_time) * 1000.0
    logger.info(
        "[METRICS] total_execution_ms=%.2f connector_execution_ms=%.2f duckdb_join_ms=%.2f tables=%d pushdowns=%d",
        total_duration_ms, subqueries_duration_ms, duckdb_duration_ms, len(queries), pushdowns_applied
    )

    response_json_str = json.dumps(response_payload, indent=2, default=str)

    try:
        await redis_client.setex(fed_cache_key, 300, response_json_str)
    except Exception as cache_err:
        logger.warning("Failed to cache federation results: %s", cache_err)

    return response_json_str


# ─────────────────────────────────────────────────────────────────────────────
# Tool: Mirror Table
# ─────────────────────────────────────────────────────────────────────────────

async def tool_mirror_table(
    ctx: ToolContext,
    db_id: str,
    table_name: str,
) -> str:
    connector = await _get_active_connector(ctx, db_id)
    if not connector:
        return f"Error: Database '{db_id}' not found."
    if not await check_connector_permission(db_id, "read", ctx.user, ctx.db):
        return f"Error: Permission denied (Read) on '{connector.name}'."

    if ";" in table_name or "--" in table_name:
        return "Error: Invalid table name format."

    parts = table_name.split('.')
    quoted_table = ".".join([f'"{p}"' for p in parts])
    query = f"SELECT * FROM {quoted_table}"

    try:
        raw_qr = await _execute_on_connector_raw(connector, query)
        if not raw_qr.columns:
            return f"Error: Table '{table_name}' returned no columns."

        safe_alias = make_table_alias(f"{connector.name}_{table_name}")
        duckdb_engine.mirror_table(safe_alias, raw_qr)

        return (
            f"Success: Mirrored {raw_qr.row_count} rows from '{table_name}' into persistent table '{safe_alias}'. "
            f"You can now query '{safe_alias}' directly in federated SQL without providing a sub-query for it."
        )
    except Exception as e:
        logger.error("Mirror table failed db_id=%s table=%s error=%s", db_id, table_name, str(e))
        return f"Error mirroring table '{table_name}': {str(e)}"


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