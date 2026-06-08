"""
app/tools/sql_helpers.py
──────────────────────────
SQL operation classification and RLS injection helpers.

Replaces the functions that were in nl_query.py.
"""
from __future__ import annotations

import re
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def classify_operation(query: str) -> str:
    """
    Classify a SQL/NoSQL query into operation type: read, create, update, delete, or write.
    
    Args:
        query: The SQL or NoSQL query string.
        
    Returns:
        One of: "read", "create", "update", "delete", "write".
    """
    if not query:
        return "read"
    
    # For NoSQL JSON queries, be conservative
    if query.strip().startswith("{"):
        try:
            import json
            obj = json.loads(query.strip())
            operation = obj.get("operation", "read").lower()
            return operation
        except Exception:
            return "read"
    
    # SQL query classification using regex
    query_upper = query.strip().upper()
    
    # Remove leading comments
    while query_upper.startswith("--") or query_upper.startswith("/*"):
        lines = query_upper.split("\n", 1)
        if len(lines) > 1:
            query_upper = lines[1].strip().upper()
        else:
            break
    
    # Determine operation type
    if query_upper.startswith("SELECT"):
        return "read"
    elif query_upper.startswith("INSERT"):
        return "create"
    elif query_upper.startswith("UPDATE"):
        return "update"
    elif query_upper.startswith("DELETE"):
        return "delete"
    elif query_upper.startswith("MERGE"):
        return "write"
    elif query_upper.startswith("CALL") or query_upper.startswith("EXEC"):
        # Stored procedures -- assume read unless obviously write
        return "read"
    else:
        # Default to write for unknown operations
        return "write"


def _escape_sql_string(value: str) -> str:
    """Escape single quotes in a value that will be interpolated into a SQL literal."""
    return value.replace("'", "''")


def _resolve_rls_filter(filter_expr: str, user_context: Dict) -> str:
    """
    Substitute user-context placeholders in a filter expression.

    Supports both ``{user_id}`` / ``{user.id}`` style placeholders.
    Values are escaped for safe embedding in SQL string literals.
    """
    user_id = _escape_sql_string(str(user_context.get("id", "")))
    user_email = _escape_sql_string(str(user_context.get("email", "")))
    user_name = _escape_sql_string(str(user_context.get("name", "")))

    result = filter_expr
    result = result.replace("{user_id}", user_id)
    result = result.replace("{user_email}", user_email)
    result = result.replace("{user_name}", user_name)
    result = result.replace("{user.id}", user_id)
    result = result.replace("{user.email}", user_email)
    result = result.replace("{user.name}", user_name)
    return result


def _collect_rls_conditions(
    policies: List,
    table_name: str,
    user_context: Dict,
) -> str:
    """
    Build the combined RLS condition string for *table_name* from matching
    policies.  Returns ``""`` when no policy matches.
    """
    given_full = table_name.strip().lower()
    given_bare = given_full.rsplit(".", 1)[-1]

    parts: List[str] = []
    for policy in policies:
        if not getattr(policy, "filter_expr", None):
            continue
        policy_table = (getattr(policy, "table_name", "") or "").strip().lower()
        if not policy_table:
            continue
        policy_bare = policy_table.rsplit(".", 1)[-1]
        if policy_table != given_full and policy_bare != given_bare:
            continue

        resolved = _resolve_rls_filter(str(policy.filter_expr), user_context)
        parts.append(f"({resolved})")
        logger.debug(
            "RLS: matched policy '%s' for table '%s'",
            getattr(policy, "name", "?"),
            table_name,
        )

    if not parts:
        return ""
    return " OR ".join(parts)


def _table_matches(table_node_name: str, table_node_schema: str, target: str) -> bool:
    """Return True if a sqlglot Table node matches *target* (e.g. ``master.Employee``)."""
    target_lower = target.strip().lower()
    node_name = table_node_name.lower()
    node_schema = table_node_schema.lower() if table_node_schema else ""

    if "." in target_lower:
        tgt_schema, tgt_bare = target_lower.split(".", 1)
        if node_schema:
            return node_schema == tgt_schema and node_name == tgt_bare
        return node_name == tgt_bare
    return node_name == target_lower


def apply_rls(
    query: str,
    policies: List,  # List of RLSPolicy objects
    table_name: str,
    user_context: Dict,
    dialect: str = "",
) -> str:
    """
    Apply Row-Level Security filters to a SELECT query.

    Uses **sqlglot AST traversal** so that every ``SELECT`` branch
    (including each side of a ``UNION``, subqueries, CTEs) receives
    the correct RLS ``WHERE`` clause.  Falls back to regex-based
    injection when sqlglot cannot parse the query.

    Args:
        query: The SELECT query.
        policies: List of RLSPolicy objects applicable to this user.
        table_name: The table name to filter (e.g. ``"Employee"`` or ``"master.Employee"``).
        user_context: Dict with user id, email, name, etc.
        dialect: sqlglot dialect string (e.g. ``"postgres"``, ``"tsql"``).

    Returns:
        Modified query with RLS conditions injected.
    """
    if not query.strip().upper().startswith("SELECT") or not policies:
        return query

    combined_rls = _collect_rls_conditions(policies, table_name, user_context)
    if not combined_rls:
        return query

    # ── Fast pre-check: is the table even mentioned? ──────────────────────
    given_bare = table_name.strip().lower().rsplit(".", 1)[-1]
    if not re.search(r'\b' + re.escape(given_bare) + r'\b', query, re.IGNORECASE):
        return query

    # ── AST-based injection (preferred) ──────────────────────────────────
    try:
        import sqlglot
        from sqlglot import exp

        tree = sqlglot.parse_one(query, read=dialect or None)

        modified = False
        for select in tree.find_all(exp.Select):
            # Find tables that are direct children of *this* Select
            has_match = False
            for tbl in select.find_all(exp.Table):
                if tbl.find_ancestor(exp.Select) is select:
                    if _table_matches(tbl.name, tbl.db, table_name):
                        has_match = True
                        break

            if has_match:
                rls_cond = sqlglot.parse_one(combined_rls, into=exp.Condition)
                where = select.args.get("where")
                if where:
                    where.set("this", exp.and_(where.this, rls_cond))
                else:
                    select.where(rls_cond, copy=False)
                modified = True

        if modified:
            result = tree.sql(dialect=dialect or None)
            logger.info("RLS (AST): %s -> %s", query[:200], result[:200])
            return result

        # AST parse succeeded but no matching table found – return as-is
        return query

    except Exception as exc:
        logger.warning(
            "RLS AST injection failed (%s); falling back to regex: %s",
            exc,
            query[:200],
        )

    # ── Regex fallback (legacy) ──────────────────────────────────────────
    return _apply_rls_regex(query, combined_rls)


def _apply_rls_regex(query: str, combined_rls: str) -> str:
    """Regex-based RLS injection – used as a fallback only."""
    where_pattern = re.compile(r"\bWHERE\b", re.IGNORECASE)

    if where_pattern.search(query):
        new_query = where_pattern.sub(
            f"WHERE ({combined_rls}) AND ",
            query,
            count=1,
        )
        return new_query

    insert_pattern = re.compile(
        r"\b(ORDER BY|GROUP BY|LIMIT|OFFSET)\b", re.IGNORECASE
    )
    match = insert_pattern.search(query)
    if match:
        pos = match.start()
        return query[:pos] + f" WHERE {combined_rls} " + query[pos:]

    return query + f" WHERE {combined_rls}"



def build_rich_schema_prompt(tables: List[Dict], connector_type: str = "") -> str:
    """
    Build a formatted markdown schema description for the agent.
    
    This is called from tool_get_database_schema to format table information
    for display/context to the LLM.
    
    Args:
        tables: List of table dicts with name, columns, etc.
        connector_type: The database type (postgres, mysql, etc.).
        
    Returns:
        Formatted markdown string.
    """
    if not tables:
        return "No tables found."
    
    lines = [f"# Schema ({connector_type} database)\n"]
    
    for table in tables:
        table_name = table.get("name", "Unknown")
        schema = table.get("schema", "")
        full_name = f"{schema}.{table_name}" if schema else table_name
        
        lines.append(f"## {full_name}\n")
        
        # Gotchas
        if "gotcha" in table and table["gotcha"]:
            lines.append(f"**⚠ Gotcha**: {table['gotcha']}\n")
        
        # Columns
        columns = table.get("columns", [])
        if columns:
            lines.append("### Columns\n")
            for col in columns:
                if isinstance(col, dict):
                    col_name = col.get("name", "?")
                    col_type = col.get("type", "?")
                    lines.append(f"- `{col_name}` (`{col_type}`)")
                else:
                    lines.append(f"- {col}")
            lines.append("")
        
        # Learned filter
        if "learned_filter" in table and table["learned_filter"]:
            lines.append(f"**Recommended filter**: `{table['learned_filter']}`\n")
        
        # Summary
        if "summary" in table and table["summary"]:
            lines.append(f"**Summary**: {table['summary']}\n")
        
        lines.append("")
    
    return "\n".join(lines)
