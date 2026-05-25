"""
app/connectors/snowflake.py -- Snowflake connector
Config: {"account": "xy12345.us-east-1", "user": "...", "password": "...",
         "database": "...", "schema": "PUBLIC", "warehouse": "COMPUTE_WH", "role": "..."}
"""
import time
from typing import Any, Dict, List
from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class SnowflakeConnector(BaseConnector):

    def _get_conn(self):
        import snowflake.connector
        cfg = self.config
        params = dict(
            account=cfg["account"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg.get("database"),
            schema=cfg.get("schema", "PUBLIC"),
        )
        if cfg.get("warehouse"):
            params["warehouse"] = cfg["warehouse"]
        if cfg.get("role"):
            params["role"] = cfg["role"]
        return snowflake.connector.connect(**params)

    async def test_connection(self) -> bool:
        import asyncio
        loop = asyncio.get_event_loop()
        def _test():
            conn = self._get_conn()
            conn.cursor().execute("SELECT 1")
            conn.close()
        await loop.run_in_executor(None, _test)
        return True

    async def get_schema(self) -> List[TableInfo]:
        import asyncio
        loop = asyncio.get_event_loop()
        def _schema():
            conn = self._get_conn()
            cur = conn.cursor()
            database = self.config.get("database", "")
            schema = self.config.get("schema", "PUBLIC")
            cur.execute(f"""
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM {database}.INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{schema}'
                ORDER BY TABLE_NAME, ORDINAL_POSITION
            """)
            rows = cur.fetchall()
            conn.close()
            return rows
        rows = await loop.run_in_executor(None, _schema)

        tables_map: Dict[str, List] = {}
        for row in rows:
            tname, cname, dtype, nullable = row[0], row[1], row[2], row[3]
            if tname not in tables_map:
                tables_map[tname] = []
            tables_map[tname].append(ColumnInfo(
                name=cname, type=dtype,
                nullable=(nullable == "YES"), primary_key=False
            ))
        return [TableInfo(name=k, columns=v) for k, v in tables_map.items()]

    async def execute_query(self, sql: str) -> QueryResult:
        import asyncio
        import pyarrow as pa
        loop = asyncio.get_event_loop()
        start = time.time()

        def _run():
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(sql)
            
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                batches = []
                total_count = 0
                preview_rows = []
                
                # Snowflake can return large results, stream in chunks of 10k
                while True:
                    chunk = cur.fetchmany(10000)
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
                conn.close()
                return columns, preview_rows, total_count, pa_table
            else:
                conn.close()
                return [], [], 0, None

        columns, rows, row_count, pa_table = await loop.run_in_executor(None, _run)
        duration_ms = (time.time() - start) * 1000
        
        return QueryResult(
            columns=columns, 
            rows=rows, 
            row_count=row_count, 
            duration_ms=duration_ms, 
            pa_table=pa_table
        )
