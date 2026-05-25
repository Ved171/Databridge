"""
app/connectors/redis_conn.py -- Redis connector
Config: {"host": "localhost", "port": 6379, "password": "", "db": 0}
"""
import time
import json
from typing import List
from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class RedisConnector(BaseConnector):

    def _get_client(self):
        import redis.asyncio as aioredis
        cfg = self.config
        return aioredis.Redis(
            host=cfg.get("host", "localhost"),
            port=int(cfg.get("port", 6379)),
            password=cfg.get("password") or None,
            db=int(cfg.get("db", 0)),
            decode_responses=True,
        )

    async def test_connection(self) -> bool:
        r = self._get_client()
        try:
            await r.ping()
            return True
        finally:
            await r.aclose()

    async def get_schema(self) -> List[TableInfo]:
        """
        Redis doesn't have schemas. We infer 'tables' from key prefixes.
        e.g., "user:123", "session:abc" -> tables "user", "session"
        """
        r = self._get_client()
        try:
            keys = await r.keys("*")
            prefixes: dict = {}
            for key in keys[:200]:  # sample 200 keys
                parts = key.split(":")
                prefix = parts[0] if len(parts) > 1 else "_default"
                if prefix not in prefixes:
                    prefixes[prefix] = []
                prefixes[prefix].append(key)

            tables = []
            for prefix, sample_keys in prefixes.items():
                # Sample one key to infer structure
                sample = await r.get(sample_keys[0])
                columns = [ColumnInfo(name="key", type="string", primary_key=True)]
                if sample:
                    try:
                        data = json.loads(sample)
                        if isinstance(data, dict):
                            columns += [ColumnInfo(name=k, type=type(v).__name__) for k, v in data.items()]
                        else:
                            columns.append(ColumnInfo(name="value", type=type(data).__name__))
                    except Exception:
                        columns.append(ColumnInfo(name="value", type="string"))

                tables.append(TableInfo(name=prefix, columns=columns, row_count=len(sample_keys)))
            return tables
        finally:
            await r.aclose()

    async def execute_query(self, query_json: str) -> QueryResult:
        """
        query_json: {"command": "GET", "args": ["key"]}
        or: {"command": "SCAN", "pattern": "user:*", "count": 100}
        or: {"command": "HGETALL", "args": ["hash_key"]}
        """
        r = self._get_client()
        try:
            start = time.time()
            q = json.loads(query_json)
            cmd = q.get("command", "SCAN").upper()
            duration_ms = None

            if cmd == "SCAN":
                pattern = q.get("pattern", "*")
                count = q.get("count", 100)
                _, keys = await r.scan(match=pattern, count=count)
                results = []
                for key in keys[:100]:
                    val = await r.get(key)
                    results.append({"key": key, "value": val or ""})
                duration_ms = (time.time() - start) * 1000
                if not results:
                    return QueryResult(columns=["key", "value"], rows=[], row_count=0, duration_ms=duration_ms)
                columns = list(results[0].keys())
                rows = [[str(r_item.get(c, "")) for c in columns] for r_item in results]
                return QueryResult(columns=columns, rows=rows, row_count=len(rows), duration_ms=duration_ms)

            elif cmd == "GET":
                val = await r.get(q["args"][0])
                duration_ms = (time.time() - start) * 1000
                return QueryResult(columns=["value"], rows=[[val or ""]], row_count=1, duration_ms=duration_ms)

            elif cmd == "HGETALL":
                data = await r.hgetall(q["args"][0])
                duration_ms = (time.time() - start) * 1000
                if not data:
                    return QueryResult(columns=[], rows=[], row_count=0, duration_ms=duration_ms)
                columns = list(data.keys())
                return QueryResult(columns=columns, rows=[list(data.values())], row_count=1, duration_ms=duration_ms)

            else:
                # Generic command
                result = await r.execute_command(cmd, *q.get("args", []))
                duration_ms = (time.time() - start) * 1000
                return QueryResult(columns=["result"], rows=[[str(result)]], row_count=1, duration_ms=duration_ms)

        finally:
            await r.aclose()

    def get_schema_prompt(self, tables) -> str:
        lines = ["Redis Key Prefixes (output as JSON command):"]
        for t in tables:
            cols = ", ".join(c.name for c in t.columns)
            lines.append(f"Prefix: {t.name} | Fields: {cols} (~{t.row_count} keys)")
        lines.append('\nFor scanning keys: {"command": "SCAN", "pattern": "prefix:*", "count": 100}')
        lines.append('For getting a value: {"command": "GET", "args": ["key"]}')
        lines.append('For hash: {"command": "HGETALL", "args": ["hash_key"]}')
        return "\n".join(lines)
