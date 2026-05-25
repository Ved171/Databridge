"""
app/connectors/sqlite.py -- SQLite connector
"""
import time
import aiosqlite
from typing import Any, Dict, List
from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class SQLiteConnector(BaseConnector):
    """Connector for SQLite databases. Config: {"path": "/path/to/db.sqlite"}"""

    async def test_connection(self) -> bool:
        async with aiosqlite.connect(self.config["path"]) as db:
            await db.execute("SELECT 1")
        return True

    async def get_schema(self) -> List[TableInfo]:
        async with aiosqlite.connect(self.config["path"]) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            table_names = [r["name"] for r in await cursor.fetchall()]

            tables = []
            for name in table_names:
                cur = await db.execute(f"PRAGMA table_info(`{name}`)")
                rows = await cur.fetchall()
                columns = [
                    ColumnInfo(
                        name=r["name"], type=r["type"],
                        nullable=not r["notnull"], primary_key=bool(r["pk"])
                    ) for r in rows
                ]
                cnt = await db.execute(f"SELECT COUNT(*) FROM `{name}`")
                row_count = (await cnt.fetchone())[0]
                tables.append(TableInfo(name=name, columns=columns, row_count=row_count))
        return tables

    async def execute_query(self, sql: str) -> QueryResult:
        start = time.time()
        async with aiosqlite.connect(self.config["path"]) as db:
            cursor = await db.execute(sql)
            
            if not cursor.description:
                return QueryResult(columns=[], rows=[], row_count=0, duration_ms=(time.time() - start) * 1000)

            columns = [desc[0] for desc in cursor.description]
            
            import pyarrow as pa
            batches = []
            total_count = 0
            preview_rows = []

            # Stream in chunks of 10k
            while True:
                chunk = await cursor.fetchmany(10000)
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
