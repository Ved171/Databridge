import re
import ssl as _ssl
import time
import aiomysql
from typing import Any, Dict, List, Optional

from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


# Only allow safe table names: alphanumeric, underscores, dots
_SAFE_TABLE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class MySQLConnector(BaseConnector):
    """Connector for MySQL / MariaDB databases."""

    def _build_ssl_context(self) -> Optional[_ssl.SSLContext]:
        """Build an SSL context from config if SSL is requested."""
        cfg = self.config
        use_ssl = cfg.get("use_ssl") or cfg.get("ssl")
        if not use_ssl:
            return None
        # If it's a boolean-like string, create a default context
        if isinstance(use_ssl, str) and use_ssl.lower() in ("true", "1", "yes"):
            ctx = _ssl.create_default_context()
            # If ca_cert is provided, load it
            ca_cert = cfg.get("ssl_ca")
            if ca_cert:
                ctx.load_verify_locations(ca_cert)
            else:
                # For cloud MySQL (RDS, Azure, PlanetScale) -- don't verify if no CA provided
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
            return ctx
        return None

    async def _get_conn(self):
        cfg = self.config
        ssl_ctx = self._build_ssl_context()
        kwargs: Dict[str, Any] = {
            "host": cfg["host"],
            "port": int(cfg.get("port", 3306)),
            "user": cfg["user"],
            "password": cfg["password"],
            "db": cfg["database"],
            "autocommit": True,
            "charset": cfg.get("charset", "utf8mb4"),
            "connect_timeout": int(cfg.get("connect_timeout", 10)),
        }
        if ssl_ctx:
            kwargs["ssl"] = ssl_ctx
        return await aiomysql.connect(**kwargs)

    async def test_connection(self) -> bool:
        conn = await self._get_conn()
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
            return True
        finally:
            conn.close()

    async def get_schema(self) -> List[TableInfo]:
        cfg = self.config
        conn = await self._get_conn()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT table_name AS table_name FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                table_names = [r["table_name"] for r in await cur.fetchall()]

                tables = []
                for table_name in table_names:
                    await cur.execute("""
                        SELECT
                            COLUMN_NAME as column_name,
                            DATA_TYPE as data_type,
                            IS_NULLABLE as is_nullable,
                            COLUMN_KEY as column_key
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE() AND table_name = %s
                        ORDER BY ORDINAL_POSITION
                    """, (table_name,))
                    col_rows = await cur.fetchall()

                    columns = [
                        ColumnInfo(
                            name=r["column_name"],
                            type=r["data_type"],
                            nullable=r["is_nullable"] == "YES",
                            primary_key=r["column_key"] == "PRI",
                        )
                        for r in col_rows
                    ]

                    # Safe row count -- use parameterized info_schema query
                    # instead of f-string interpolation to prevent SQL injection
                    await cur.execute("""
                        SELECT table_rows AS cnt
                        FROM information_schema.tables
                        WHERE table_schema = DATABASE() AND table_name = %s
                    """, (table_name,))
                    count_row = await cur.fetchone()
                    row_count = int(count_row["cnt"]) if count_row and count_row["cnt"] is not None else None

                    tables.append(TableInfo(
                        name=table_name,
                        columns=columns,
                        row_count=row_count,
                        schema=cfg["database"],
                    ))

                return tables
        finally:
            conn.close()

    async def execute_query(self, sql: str) -> QueryResult:
        conn = await self._get_conn()
        try:
            start = time.time()
            async with conn.cursor() as cur:
                await cur.execute(sql)
                
                if not cur.description:
                    return QueryResult(columns=[], rows=[], row_count=0, duration_ms=(time.time() - start) * 1000)

                columns = [desc[0] for desc in cur.description]
                
                import pyarrow as pa
                batches = []
                total_count = 0
                preview_rows = []

                # Stream in chunks of 10k
                while True:
                    chunk = await cur.fetchmany(10000)
                    if not chunk:
                        break
                    
                    if not preview_rows:
                        preview_rows = [list(r) for r in chunk[:500]]
                    
                    # Transpose chunk
                    cols_data = [list(c) for c in zip(*chunk)]
                    arrays = [pa.array(c) for c in cols_data]
                    batch = pa.RecordBatch.from_arrays(arrays, names=columns)
                    batches.append(batch)
                    total_count += len(chunk)

                pa_table = pa.Table.from_batches(batches) if batches else pa.Table.from_arrays([pa.array([], type=pa.string()) for _ in columns], names=columns)
                duration_ms = (time.time() - start) * 1000

                return QueryResult(
                    columns=columns,
                    rows=preview_rows,
                    row_count=total_count,
                    duration_ms=duration_ms,
                    pa_table=pa_table
                )
        finally:
            conn.close()
