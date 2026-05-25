"""
app/connectors/oracle.py -- Oracle Database connector
Config: {"host": "...", "port": 1521, "service_name": "ORCL", "user": "...", "password": "..."}
"""
import time
from typing import List
from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class OracleConnector(BaseConnector):

    def _get_conn(self):
        import cx_Oracle
        cfg = self.config
        dsn = cx_Oracle.makedsn(
            cfg["host"],
            int(cfg.get("port", 1521)),
            service_name=cfg.get("service_name", "ORCL")
        )
        return cx_Oracle.connect(user=cfg["user"], password=cfg["password"], dsn=dsn)

    async def test_connection(self) -> bool:
        import asyncio
        loop = asyncio.get_event_loop()
        def _test():
            conn = self._get_conn()
            conn.cursor().execute("SELECT 1 FROM DUAL")
            conn.close()
        await loop.run_in_executor(None, _test)
        return True

    async def get_schema(self) -> List[TableInfo]:
        import asyncio
        loop = asyncio.get_event_loop()
        def _schema():
            conn = self._get_conn()
            cur = conn.cursor()
            schema = self.config.get("schema", self.config["user"].upper())
            cur.execute("""
                SELECT c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.NULLABLE,
                       CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END IS_PK
                FROM ALL_TAB_COLUMNS c
                LEFT JOIN (
                    SELECT cc.COLUMN_NAME, cc.TABLE_NAME
                    FROM ALL_CONSTRAINTS con
                    JOIN ALL_CONS_COLUMNS cc ON con.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                    WHERE con.CONSTRAINT_TYPE = 'P' AND con.OWNER = :schema
                ) pk ON pk.TABLE_NAME = c.TABLE_NAME AND pk.COLUMN_NAME = c.COLUMN_NAME
                WHERE c.OWNER = :schema
                ORDER BY c.TABLE_NAME, c.COLUMN_ID
            """, schema=schema)
            rows = cur.fetchall()
            conn.close()
            return rows
        rows = await loop.run_in_executor(None, _schema)

        tables_map = {}
        for row in rows:
            tname = row[0]
            if tname not in tables_map:
                tables_map[tname] = []
            tables_map[tname].append(ColumnInfo(
                name=row[1], type=row[2],
                nullable=(row[3] == "Y"), primary_key=bool(row[4])
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
                
                # Stream in chunks of 10k
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
