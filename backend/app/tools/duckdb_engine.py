"""
app/tools/duckdb_engine.py

DuckDB-powered in-memory federation engine for cross-database queries.

Responsibilities:
  1. Accept per-connector QueryResult objects (columns + rows)
  2. Register each as a typed DuckDB in-memory relation (via pandas DataFrame)
  3. Execute a federation SQL query (JOINs, aggregations, filters) across all tables
  4. Return a single unified QueryResult

Uses sqlglot to:
   Validate & normalise federation SQL before DuckDB execution
   Transpile dialect-specific SQL between connectors
   Parse SQL ASTs for injection detection
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

import duckdb
import pyarrow as pa
import sqlglot
from sqlglot import errors as sg_errors

from app.connectors.base import QueryResult

logger = logging.getLogger(__name__)

#  Dialect mapping: connector_type -> sqlglot dialect name 
SQLGLOT_DIALECT_MAP: Dict[str, str] = {
    "postgres":    "postgres",
    "postgresql":  "postgres",
    "mysql":       "mysql",
    "mssql":       "tsql",
    "sqlite":      "sqlite",
    "snowflake":   "snowflake",
    "bigquery":    "bigquery",
    "oracle":      "oracle",
    "duckdb":      "duckdb",
    # NoSQL / non-SQL connectors are intentionally absent -- they bypass validation
}

#  Dangerous statement types blocked via AST check 
_BLOCKED_STATEMENT_TYPES = {
    "Drop", "TruncateTable", "AlterTable", "AlterColumn",
    "Grant", "Revoke", "Use", "Kill",
}


# 
# Cross-database join link registry
# 
# Key: "source_db.source_table.source_column" (lowercased)
# Val: {"target_db": ..., "target_table": ..., "target_column": ...}

CROSS_DB_LINKS: Dict[str, Dict[str, str]] = {}


def register_cross_db_link(
    src_db: str, src_table: str, src_col: str,
    tgt_db: str, tgt_table: str, tgt_col: str,
) -> None:
    """Register a bidirectional cross-database join link."""
    fwd = f"{src_db}.{src_table}.{src_col}".lower()
    rev = f"{tgt_db}.{tgt_table}.{tgt_col}".lower()
    CROSS_DB_LINKS[fwd] = {"target_db": tgt_db, "target_table": tgt_table, "target_column": tgt_col}
    CROSS_DB_LINKS[rev] = {"target_db": src_db, "target_table": src_table, "target_column": src_col}
    logger.info("Registered cross-DB link: %s <-> %s", fwd, rev)


def get_join_hint(db_name: str, table_name: str, column_name: str) -> Optional[Dict[str, str]]:
    """Look up a cross-database join hint for a given column."""
    key = f"{db_name}.{table_name}.{column_name}".lower()
    return CROSS_DB_LINKS.get(key)


def load_cross_db_links_from_schema(schema_json: dict) -> None:
    """Populate the link registry from a schema JSON's cross_database_relationships."""
    for rel in schema_json.get("cross_database_relationships", []):
        try:
            register_cross_db_link(
                rel["source_db"], rel["source_table"], rel["source_column"],
                rel["target_db"], rel["target_table"], rel["target_column"],
            )
        except KeyError as e:
            logger.warning("Skipping malformed cross-DB relationship (missing %s): %s", e, rel)



# 
# Public helpers
# 

def translate_query(sql: str, from_dialect: str, to_dialect: str) -> str:
    """
    Transpile a SQL statement between two dialects using sqlglot.
    Example: translate_query(mysql_sql, "mysql", "postgres")

    Falls back to the original string if translation fails, so callers
    are never blocked -- just log a warning.
    """
    if from_dialect == to_dialect or not sql.strip() or sql.strip().startswith("{"):
        return sql
    try:
        result = sqlglot.transpile(sql, read=from_dialect, write=to_dialect, pretty=False)
        return result[0] if result else sql
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sqlglot translation failed (%s -> %s): %s -- using original",
            from_dialect, to_dialect, exc,
        )
        return sql


def validate_sql(sql: str, dialect: str = "") -> Optional[str]:  # "" = generic ANSI
    """
    Parse the SQL with sqlglot.

    Returns
    -------
    None      -- SQL is valid
    str       -- human-readable parse / safety error

    Non-SQL queries (JSON-encoded NoSQL commands) are always accepted.
    """
    stripped = sql.strip()
    if not stripped or stripped.startswith("{"):
        return None  # NoSQL or empty -- skip

    try:
        tree = sqlglot.parse_one(stripped, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)
    except sg_errors.ParseError as exc:
        return f"SQL parse error: {exc}"

    # AST-based safety check: block dangerous top-level statements
    stmt_type = type(tree).__name__
    if stmt_type in _BLOCKED_STATEMENT_TYPES:
        return f"Statement type '{stmt_type}' is not permitted."

    return None  # all good


def sql_fingerprint(sql: str) -> str:
    """Return a stable SHA-256 hex digest of normalised SQL (used for caching)."""
    try:
        normalised = sqlglot.parse_one(sql).sql()
    except Exception:
        normalised = sql
    return hashlib.sha256(normalised.encode()).hexdigest()


# 
# Federation engine
# 

class DuckDBFederationEngine:
    """
    Persistent federation engine. Uses a long-lived in-memory DuckDB instance to allow
    mirroring of core reference tables for ultra-fast cross-database joins
    without hitting the source databases repeatedly, while avoiding file locks across containers.
    """

    def __init__(self):
        import os
        # Ensure a temp directory exists for disk-spilling during large federated joins
        # This prevents OOM crashes when joining multi-million row datasets
        temp_dir = os.path.join(os.getcwd(), ".duckdb_temp")
        try:
            os.makedirs(temp_dir, exist_ok=True)
        except Exception:
            # Fallback to current directory if permissions fail
            temp_dir = os.getcwd()

        # Long-lived connection (mostly in-memory, but spills to disk if needed)
        self.con = duckdb.connect(":memory:")
        
        # Performance & Stability Tunables
        temp_dir_normalized = temp_dir.replace('\\', '/')
        self.con.execute(f"SET temp_directory = '{temp_dir_normalized}'")
        self.con.execute("SET memory_limit = '4GB'")  # Cap RAM usage per instance
        self.con.execute("SET max_temp_directory_size = '10GB'") # Cap disk usage
        self.con.execute("SET threads = 4") # Limit CPU contention

    def mirror_table(self, table_name: str, qr: QueryResult) -> None:
        """
        Mirror a QueryResult into a persistent DuckDB table.
        This allows future federation queries to hit the local table directly.
        """
        safe_name = make_table_alias(table_name)
        if not qr.columns:
            return

        # Normalize column names to lowercase for consistent casing
        normalized_columns = [col.lower() for col in qr.columns]

        if qr.pa_table is not None:
            # Rename columns in PyArrow table to lowercase
            pa_table = qr.pa_table.rename_columns(normalized_columns)
        elif qr.rows:
            # Transpose rows to columns for Arrow to avoid dictionary allocation overhead
            cols_data = [list(c) for c in zip(*qr.rows)]
            arrays = [pa.array(c) for c in cols_data]
            pa_table = pa.Table.from_arrays(arrays, names=normalized_columns)
        else:
            pa_table = pa.Table.from_arrays([pa.array([], type=pa.string()) for _ in normalized_columns], names=normalized_columns)
        
        # Register temporarily using from_arrow to copy it into a real table
        temp_alias = f"temp_{safe_name}"
        self.con.from_arrow(pa_table).create_view(temp_alias, replace=True)
        try:
            self.con.execute(f"CREATE OR REPLACE TABLE {safe_name} AS SELECT * FROM {temp_alias}")
            logger.info("Mirrored table %s into persistent DuckDB (%d rows).", safe_name, len(qr.rows))
        finally:
            self.con.execute(f"DROP VIEW IF EXISTS {temp_alias}")

    def run_federation(
        self,
        tables: Dict[str, QueryResult],
        federation_sql: str,
        row_limit: int = 2000,
        table_to_alias_map: Optional[Dict[str, str]] = None,
    ) -> QueryResult:
        """
        Parameters
        ----------
        tables : {alias: QueryResult}
            One entry per connector result.  Alias == sanitised connector name
            (see `make_table_alias`).
        federation_sql : str
            DuckDB-compatible SQL referencing the table aliases.
        row_limit : int
            Hard cap on result rows (prevents runaway memory usage).
        table_to_alias_map : dict, optional
            A mapping of referenced table names to their registered views/aliases.

        Returns
        -------
        QueryResult with unified columns/rows from the federation.
        """
        # Validate federation SQL before touching DuckDB
        err = validate_sql(federation_sql, dialect="duckdb")
        if err:
            raise ValueError(f"Invalid federation SQL: {err}")

        # Normalise to DuckDB dialect
        try:
            federation_sql = sqlglot.parse_one(federation_sql, read="duckdb").sql(dialect="duckdb")
        except Exception:
            pass  # keep original on normalisation failure

        # We use a cursor to avoid mutating the main connection state concurrently
        cursor = self.con.cursor()
        try:
            registered: List[str] = []
            column_mapping: Dict[str, Dict[str, str]] = {}  # Maps alias -> {original_col: lower_col}
            
            for alias, qr in tables.items():
                safe_alias = make_table_alias(alias)
                if not qr.columns:
                    # Register empty table so SQL doesn't break
                    cursor.execute(f"CREATE TEMPORARY TABLE {safe_alias} (placeholder VARCHAR)")
                    continue
                
                # Normalize column names to lowercase for consistent casing
                normalized_columns = [col.lower() for col in qr.columns]
                column_mapping[safe_alias] = dict(zip(qr.columns, normalized_columns))
                
                if qr.pa_table is not None:
                    # Rename columns in PyArrow table to lowercase
                    pa_table = qr.pa_table.rename_columns(normalized_columns)
                elif qr.rows:
                    cols_data = [list(c) for c in zip(*qr.rows)]
                    arrays = [pa.array(c) for c in cols_data]
                    pa_table = pa.Table.from_arrays(arrays, names=normalized_columns)
                else:
                    pa_table = pa.Table.from_arrays([pa.array([], type=pa.string()) for _ in normalized_columns], names=normalized_columns)
                
                # Register PyArrow table using from_arrow
                cursor.from_arrow(pa_table).create_view(safe_alias, replace=True)
                registered.append(safe_alias)

            # Rewrite federation_sql to map any table reference with catalog/schema prefixes to their registered views
            # Also normalize column names to lowercase to match the normalized column names in views
            try:
                tree = sqlglot.parse_one(federation_sql, read="duckdb")
                from sqlglot import exp
                
                registered_lower = {r.lower(): r for r in registered}
                table_to_alias_lower = {}
                if table_to_alias_map:
                    table_to_alias_lower = {k.lower().strip(): v for k, v in table_to_alias_map.items()}
                
                modified = False
                for table in tree.find_all(exp.Table):
                    parts = []
                    for key in ["catalog", "db", "this"]:
                        node = table.args.get(key)
                        if node:
                            val = node.name.lower() if hasattr(node, "name") else str(node).lower()
                            val_clean = val.replace('"', '').replace("'", "").strip()
                            if val_clean:
                                parts.append(val_clean)
                    
                    full_name = ".".join(parts)
                    bare_name = parts[-1] if parts else ""
                    
                    matched_alias = None
                    # Try explicit table_to_alias mapping first
                    if full_name in table_to_alias_lower:
                        matched_alias = table_to_alias_lower[full_name]
                    elif bare_name in table_to_alias_lower:
                        matched_alias = table_to_alias_lower[bare_name]
                    else:
                        # Fallback to parts matching registered database/connector aliases
                        for part in parts:
                            if part in registered_lower:
                                matched_alias = registered_lower[part]
                                break
                    
                    if matched_alias:
                        table.set("this", exp.to_identifier(matched_alias))
                        table.set("db", None)
                        table.set("catalog", None)
                        modified = True
                
                # Normalize column names to lowercase
                for col in tree.find_all(exp.Column):
                    col_name = col.name
                    if col_name and col_name != col_name.lower():
                        col.set("this", exp.to_identifier(col_name.lower()))
                        modified = True
                
                if modified:
                    rewritten_sql = tree.sql(dialect="duckdb")
                    logger.info("Rewrote federation SQL to match registered views and normalized columns: %s", rewritten_sql)
                    federation_sql = rewritten_sql
            except Exception as e:
                logger.warning("Error rewriting federation SQL table prefixes: %s", e)

            logger.debug("DuckDB federation: tables=%s sql=%s", registered, federation_sql[:200])

            start = time.time()
            rel = cursor.execute(federation_sql)
            duration_ms = (time.time() - start) * 1000

            columns = [desc[0] for desc in rel.description] if rel.description else []
            rows = rel.fetchmany(row_limit)

            return QueryResult(
                columns=columns,
                rows=[list(r) for r in rows],
                row_count=len(rows),
                duration_ms=duration_ms,
            )
        finally:
            # Unregister virtual tables from the cursor to free memory
            for alias in tables.keys():
                safe_alias = make_table_alias(alias)
                try:
                    cursor.execute(f"DROP VIEW IF EXISTS {safe_alias}")
                except Exception:
                    pass
            cursor.close()

    #  Convenience: run ad-hoc SQL over a single in-memory table 

    def run_inline(self, qr: QueryResult, sql: str) -> QueryResult:
        """
        Apply arbitrary DuckDB SQL to a single QueryResult (e.g. post-filtering,
        ordering, aggregation).  The table is always aliased as ``data``.
        """
        return self.run_federation({"data": qr}, sql)


def make_table_alias(name: str) -> str:
    """
    Convert a connector name to a safe DuckDB table identifier.
    E.g. 'My Postgres DB' -> 'my_postgres_db'
    """
    import re
    alias = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower().strip("_")
    if alias and alias[0].isdigit():
        alias = "t_" + alias
    return alias or "table_0"


# 
# Column / table casing normalization
# 

def normalize_query_casings(
    sql: str,
    dialect: str,
    schema_cache: Optional[Dict],
) -> str:
    """
    Parse a SQL statement with sqlglot, match table/column identifiers
    case-insensitively against the connector's cached schema, and rewrite
    them to use the exact casing stored in the database.

    This prevents quoted-identifier failures on case-sensitive databases
    like PostgreSQL where '"EmployeeId"'  '"employeeid"'.

    Falls back to the original SQL on any error so callers are never blocked.
    """
    if not sql or not sql.strip() or sql.strip().startswith("{") or not schema_cache:
        return sql

    try:
        from sqlglot import exp

        tree = sqlglot.parse_one(sql, read=dialect)

        #  Phase 1: Map table aliases to cached table definitions 
        alias_to_cached: Dict[str, dict] = {}

        for table in tree.find_all(exp.Table):
            t_name = table.name.lower()
            t_db = table.db.lower() if table.db else None
            matched = None

            for cached_t in schema_cache.get("tables", []):
                c_name = cached_t.get("name", "").lower()
                c_schema = (cached_t.get("schema") or "").lower() or None

                if t_db:
                    if c_schema == t_db and c_name == t_name:
                        matched = cached_t
                        break
                else:
                    if c_name == t_name:
                        matched = cached_t
                        break

            if not matched:
                continue

            # Rewrite table identifier casing
            # Force quoting if the name has mixed case (PostgreSQL lowercases unquoted identifiers)
            correct_name = matched["name"]
            needs_quote = correct_name != correct_name.lower()
            this_node = table.args.get("this")
            this_quoted = needs_quote or (this_node.args.get("quoted", False) if this_node else False)
            table.set("this", exp.to_identifier(correct_name, quoted=this_quoted))

            if table.db and matched.get("schema"):
                correct_schema = matched["schema"]
                schema_needs_quote = correct_schema != correct_schema.lower()
                db_node = table.args.get("db")
                db_quoted = schema_needs_quote or (db_node.args.get("quoted", False) if db_node else False)
                table.set("db", exp.to_identifier(correct_schema, quoted=db_quoted))

            # Register for column lookups
            if table.alias:
                alias_to_cached[table.alias.lower()] = matched
            alias_to_cached[t_name] = matched
            if t_db:
                alias_to_cached[f"{t_db}.{t_name}"] = matched

        #  Phase 2: Rewrite column identifier casing 
        for col in tree.find_all(exp.Column):
            col_lower = col.name.lower()
            col_table = col.table.lower() if col.table else ""

            target_name = None

            if col_table and col_table in alias_to_cached:
                # Qualified column -- search the specific table
                for c in alias_to_cached[col_table].get("columns", []):
                    if c.get("name", "").lower() == col_lower:
                        target_name = c["name"]
                        break
            else:
                # Unqualified -- search all referenced tables
                for cached_t in alias_to_cached.values():
                    for c in cached_t.get("columns", []):
                        if c.get("name", "").lower() == col_lower:
                            target_name = c["name"]
                            break
                    if target_name:
                        break

            if target_name:
                # Force quoting if the correct name has mixed case
                # (PostgreSQL lowercases unquoted identifiers)
                needs_quote = target_name != target_name.lower()
                current_quoted = col.this.args.get("quoted", False)
                if target_name != col.name or (needs_quote and not current_quoted):
                    is_quoted = needs_quote or current_quoted
                    col.set("this", exp.to_identifier(target_name, quoted=is_quoted))

        normalised = tree.sql(dialect=dialect)
        if normalised != sql:
            logger.info("Casing normalised: %s -> %s", sql[:200], normalised[:200])
        return normalised

    except Exception as exc:
        logger.warning("Casing normalisation failed (using original SQL): %s", exc)
        return sql


# Singleton -- import and use directly
duckdb_engine = DuckDBFederationEngine()
