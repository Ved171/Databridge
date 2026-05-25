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


def apply_rls(
    query: str,
    policies: List,  # List of RLSPolicy objects
    table_name: str,
    user_context: Dict,
) -> str:
    """
    Apply Row-Level Security filters to a SELECT query.
    
    Injects WHERE clauses based on RLS policies for the user.
    
    Args:
        query: The SELECT query.
        policies: List of RLSPolicy objects applicable to this user.
        table_name: The table name to filter.
        user_context: Dict with user ID, email, name, etc.
        
    Returns:
        Modified query with RLS conditions injected.
    """
    if not query.strip().upper().startswith("SELECT") or not policies:
        return query
    
    # Build RLS WHERE conditions
    rls_conditions = []
    
    for policy in policies:
        # Each policy has a filter_expression (SQL WHERE clause)
        if hasattr(policy, "filter_expression") and policy.filter_expression:
            # Substitute user variables in the filter
            filter_expr = str(policy.filter_expression)
            
            # Simple substitution: replace {user_id}, {user_email}, {user_name}
            filter_expr = filter_expr.replace("{user_id}", str(user_context.get("id", "")))
            filter_expr = filter_expr.replace("{user_email}", str(user_context.get("email", "")))
            filter_expr = filter_expr.replace("{user_name}", str(user_context.get("name", "")))
            
            rls_conditions.append(f"({filter_expr})")
    
    if not rls_conditions:
        return query
    
    # Combine RLS conditions with OR
    combined_rls = " OR ".join(rls_conditions)
    
    # Try to inject into WHERE clause using simple string replacement
    # (in production, use sqlglot AST for safety)
    where_pattern = re.compile(r"\bWHERE\b", re.IGNORECASE)
    
    if where_pattern.search(query):
        # Replace first WHERE with WHERE (...) AND (...rls_conditions...)
        new_query = where_pattern.sub(
            f"WHERE ({combined_rls}) AND ",
            query,
            count=1
        )
        return new_query
    else:
        # No WHERE clause -- append one
        # Insert before any ORDER BY, GROUP BY, LIMIT, etc.
        insert_pattern = re.compile(r"\b(ORDER BY|GROUP BY|LIMIT|OFFSET)\b", re.IGNORECASE)
        match = insert_pattern.search(query)
        
        if match:
            insert_pos = match.start()
            new_query = query[:insert_pos] + f" WHERE {combined_rls} " + query[insert_pos:]
            return new_query
        else:
            # Append WHERE clause at the end
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
