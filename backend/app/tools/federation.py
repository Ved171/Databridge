"""
app/tools/federation.py
-----------------------
Federated query execution, pushdown optimisation, and mirror-table logic
extracted from db_tools.
"""
from __future__ import annotations

import asyncio
import json
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from app.connectors.base import QueryResult
from app.core.deps import check_connector_permission
from app.models import Connector, User
from app.tools.db_tools import (
    ToolContext,
    _get_active_connector,
    _execute_on_connector,
    _execute_on_connector_raw,
    _connector_sqlglot_dialect,
)
from app.tools.duckdb_engine import (
    duckdb_engine, make_table_alias,
    SQLGLOT_DIALECT_MAP,
)
from app.tools.query_cache import query_cache as _cache

logger = logging.getLogger(__name__)


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
    if not await check_connector_permission(str(connector.id), "read", ctx.user, ctx.db):
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
