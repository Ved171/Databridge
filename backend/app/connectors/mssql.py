"""
app/connectors/mssql.py -- Microsoft SQL Server connector
Config: {"host": "...", "port": 1433, "user": "...", "password": "...", "database": "..."}
"""
import time
from typing import List
from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class MSSQLConnector(BaseConnector):

    def _get_conn(self):
        import pyodbc
        cfg = self.config
        # Safely parse port to avoid ValueError/connection failure on empty string input
        port_val = cfg.get("port")
        port = int(port_val) if port_val and str(port_val).strip() else 1433
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={cfg['host']},{port};"
            f"DATABASE={cfg['database']};"
            f"UID={cfg['user']};PWD={cfg['password']};"
            f"Connection Timeout={cfg.get('connect_timeout', 10)};"
        )
        # SSL / TLS encryption options (required for Azure SQL, AWS RDS, etc.)
        if str(cfg.get('encrypt', '')).lower() in ('true', 'yes', '1'):
            conn_str += "Encrypt=yes;"
        if str(cfg.get('trust_server_certificate', '')).lower() in ('true', 'yes', '1'):
            conn_str += "TrustServerCertificate=yes;"
        return pyodbc.connect(conn_str, timeout=int(cfg.get('connect_timeout', 10)))

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
            cur.execute("""
                SELECT t.TABLE_SCHEMA, t.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE,
                       c.IS_NULLABLE,
                       CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as IS_PK
                FROM INFORMATION_SCHEMA.TABLES t
                JOIN INFORMATION_SCHEMA.COLUMNS c
                  ON t.TABLE_NAME = c.TABLE_NAME AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
                LEFT JOIN (
                    SELECT ku.COLUMN_NAME, ku.TABLE_NAME, ku.TABLE_SCHEMA
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                      ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                    WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                ) pk ON pk.TABLE_NAME = t.TABLE_NAME AND pk.TABLE_SCHEMA = t.TABLE_SCHEMA
                         AND pk.COLUMN_NAME = c.COLUMN_NAME
                WHERE t.TABLE_TYPE = 'BASE TABLE'
                ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
            """)
            rows = cur.fetchall()
            conn.close()
            return rows
        rows = await loop.run_in_executor(None, _schema)

        tables_map = {}
        for row in rows:
            key = f"{row[0]}.{row[1]}"
            if key not in tables_map:
                tables_map[key] = {"name": row[1], "schema": row[0], "columns": []}
            tables_map[key]["columns"].append(ColumnInfo(
                name=row[2], type=row[3],
                nullable=(row[4] == "YES"), primary_key=bool(row[5])
            ))
        return [TableInfo(name=v["name"], columns=v["columns"], schema=v["schema"])
                for v in tables_map.values()]

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
                
                # Stream in chunks of 10k to manage memory
                while True:
                    chunk = cur.fetchmany(10000)
                    if not chunk:
                        break
                    
                    if not preview_rows:
                        preview_rows = [list(r) for r in chunk[:500]]
                    
                    # Transpose chunk into columnar format for Arrow
                    cols_data = [list(c) for c in zip(*chunk)]
                    arrays = [pa.array(c) for c in cols_data]
                    batch = pa.RecordBatch.from_arrays(arrays, names=columns)
                    batches.append(batch)
                    total_count += len(chunk)
                
                pa_table = pa.Table.from_batches(batches) if batches else pa.Table.from_arrays([pa.array([], type=pa.string()) for _ in columns], names=columns)
                conn.close()
                return columns, preview_rows, total_count, pa_table
            else:
                conn.commit()
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
