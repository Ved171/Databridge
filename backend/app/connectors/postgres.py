import ssl as _ssl
import time
import asyncpg
from typing import Any, Dict, List, Optional

from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class PostgresConnector(BaseConnector):
    """Connector for PostgreSQL databases."""

    def _build_ssl_context(self) -> Optional[_ssl.SSLContext]:
        """Build an SSL context from config if SSL is requested."""
        cfg = self.config
        use_ssl = cfg.get("use_ssl") or cfg.get("ssl") or cfg.get("sslmode")
        if not use_ssl:
            return None
        if isinstance(use_ssl, str) and use_ssl.lower() in ("true", "1", "yes", "require", "verify-ca", "verify-full"):
            ctx = _ssl.create_default_context()
            ca_cert = cfg.get("ssl_ca") or cfg.get("sslrootcert")
            if ca_cert:
                ctx.load_verify_locations(ca_cert)
            elif use_ssl.lower() not in ("verify-ca", "verify-full"):
                # For cloud Postgres (RDS, Supabase) -- don't verify if no CA provided
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
            return ctx
        return None

    async def _get_conn(self):
        cfg = self.config
        ssl_ctx = self._build_ssl_context()
        kwargs: Dict[str, Any] = {
            "host": cfg["host"],
            "port": int(cfg.get("port", 5432)),
            "user": cfg["user"],
            "password": cfg["password"],
            "database": cfg["database"],
            "timeout": int(cfg.get("connect_timeout", 10)),
        }
        if ssl_ctx:
            kwargs["ssl"] = ssl_ctx
        return await asyncpg.connect(**kwargs)

    async def test_connection(self) -> bool:
        conn = await self._get_conn()
        try:
            await conn.execute("SELECT 1")
            return True
        finally:
            await conn.close()

    async def get_schema(self) -> List[TableInfo]:
        conn = await self._get_conn()
        try:
            # Get all user tables across all schemas
            tables_rows = await conn.fetch("""
                SELECT table_schema, table_name FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog') 
                  AND table_type = 'BASE TABLE'
                ORDER BY table_schema, table_name
            """)

            tables = []
            for table_row in tables_rows:
                table_name = table_row["table_name"]
                table_schema = table_row["table_schema"]

                # Get columns for specific table and schema
                col_rows = await conn.fetch("""
                    SELECT
                        c.column_name,
                        c.data_type,
                        c.is_nullable,
                        CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_pk
                    FROM information_schema.columns c
                    LEFT JOIN (
                        SELECT ku.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage ku
                            ON tc.constraint_name = ku.constraint_name
                            AND tc.table_schema = ku.table_schema
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                        AND tc.table_name = $1 AND tc.table_schema = $2
                    ) pk ON pk.column_name = c.column_name
                    WHERE c.table_name = $1 AND c.table_schema = $2
                    ORDER BY c.ordinal_position
                """, table_name, table_schema)

                columns = [
                    ColumnInfo(
                        name=r["column_name"],
                        type=r["data_type"],
                        nullable=r["is_nullable"] == "YES",
                        primary_key=r["is_pk"],
                    )
                    for r in col_rows
                ]

                # Approximate row count for specific schema.table
                # Note: reltuples is -1 if the table has never been analyzed
                count_row = await conn.fetchrow("""
                    SELECT GREATEST(0, reltuples)::bigint as cnt 
                    FROM pg_class n
                    JOIN pg_namespace ns ON n.relnamespace = ns.oid
                    WHERE n.relname = $1 AND ns.nspname = $2
                """, table_name, table_schema)
                row_count = int(count_row["cnt"]) if count_row else 0

                tables.append(TableInfo(
                    name=table_name, 
                    columns=columns, 
                    row_count=row_count,
                    schema=table_schema
                ))

            return tables
        finally:
            await conn.close()

    async def execute_query(self, sql: str) -> QueryResult:
        conn = await self._get_conn()
        try:
            start = time.time()
            # Use a server-side cursor for large datasets
            async with conn.transaction():
                cursor = await conn.cursor(sql)
                
                # Fetch first chunk to get columns
                first_chunk = await cursor.fetch(1000)
                if not first_chunk:
                    return QueryResult(columns=[], rows=[], row_count=0, duration_ms=(time.time() - start) * 1000)
                
                columns = list(first_chunk[0].keys())
                
                import pyarrow as pa
                batches = []
                
                def make_batch(rows):
                    cols_data = [list(r.values()) for r in rows]
                    transposed = [list(c) for c in zip(*cols_data)]
                    return pa.RecordBatch.from_arrays([pa.array(c) for c in transposed], names=columns)

                batches.append(make_batch(first_chunk))
                total_count = len(first_chunk)

                # Stream remaining rows
                while True:
                    chunk = await cursor.fetch(10000)
                    if not chunk:
                        break
                    batches.append(make_batch(chunk))
                    total_count += len(chunk)

                pa_table = pa.Table.from_batches(batches)
                duration_ms = (time.time() - start) * 1000

                # Return only a preview in the 'rows' field to avoid JSON explosion
                preview_rows = [list(r.values()) for r in first_chunk[:500]]

                return QueryResult(
                    columns=columns,
                    rows=preview_rows,
                    row_count=total_count,
                    duration_ms=duration_ms,
                    pa_table=pa_table
                )
        finally:
            await conn.close()
