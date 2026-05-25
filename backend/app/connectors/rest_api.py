import time
import json
import httpx
from typing import Any, Dict, List

from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class RestAPIConnector(BaseConnector):
    """
    Connector for REST APIs.
    Config: {
        "base_url": "https://api.example.com",
        "auth_type": "bearer|api_key|basic|none",
        "auth_value": "...",
        "endpoints": [
            {"name": "employees", "path": "/employees", "method": "GET"}
        ]
    }
    For NL->Query, the LLM generates a JSON action:
    {"endpoint": "employees", "params": {"department": "hr"}}
    """

    def _get_headers(self) -> Dict[str, str]:
        cfg = self.config
        auth_type = cfg.get("auth_type", "none")
        headers = {"Content-Type": "application/json"}
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {cfg['auth_value']}"
        elif auth_type == "api_key":
            key_name = cfg.get("api_key_header", "X-API-Key")
            headers[key_name] = cfg["auth_value"]
        elif auth_type == "basic":
            import base64
            encoded = base64.b64encode(cfg["auth_value"].encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        return headers

    async def test_connection(self) -> bool:
        cfg = self.config
        endpoints = cfg.get("endpoints", [])
        if not endpoints:
            return True
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                cfg["base_url"] + endpoints[0]["path"],
                headers=self._get_headers(),
                timeout=10,
            )
            resp.raise_for_status()
        return True

    async def get_schema(self) -> List[TableInfo]:
        cfg = self.config
        endpoints = cfg.get("endpoints", [])
        tables = []

        async with httpx.AsyncClient() as client:
            for ep in endpoints:
                try:
                    resp = await client.get(
                        cfg["base_url"] + ep["path"],
                        headers=self._get_headers(),
                        timeout=10,
                    )
                    data = resp.json()
                    # If list, infer from first item
                    items = data if isinstance(data, list) else data.get("data") or data.get("results") or [data]
                    columns = []
                    if items:
                        sample = items[0] if isinstance(items[0], dict) else {}
                        columns = [ColumnInfo(name=k, type=type(v).__name__) for k, v in sample.items()]

                    tables.append(TableInfo(name=ep["name"], columns=columns))
                except Exception:
                    tables.append(TableInfo(name=ep["name"], columns=[]))

        return tables

    async def execute_query(self, sql: str) -> QueryResult:
        """
        sql here is actually a JSON action from the LLM:
        {"endpoint": "employees", "params": {...}, "method": "GET"}
        """
        cfg = self.config
        start = time.time()
        action = json.loads(sql)

        endpoints = {ep["name"]: ep for ep in cfg.get("endpoints", [])}
        ep = endpoints.get(action["endpoint"], {})
        path = ep.get("path", f"/{action['endpoint']}")

        async with httpx.AsyncClient() as client:
            method = action.get("method", "GET").upper()
            params = action.get("params", {})
            if method == "GET":
                resp = await client.get(cfg["base_url"] + path, headers=self._get_headers(), params=params)
            else:
                resp = await client.request(method, cfg["base_url"] + path, headers=self._get_headers(), json=params)

            data = resp.json()
            duration_ms = (time.time() - start) * 1000

        items = data if isinstance(data, list) else data.get("data") or data.get("results") or [data]
        if not items or not isinstance(items[0], dict):
            return QueryResult(columns=["result"], rows=[[json.dumps(data)]], row_count=1, duration_ms=duration_ms)

        columns = list(items[0].keys())
        rows = [[str(item.get(c, "")) for c in columns] for item in items]
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), duration_ms=duration_ms)

    def get_schema_prompt(self, tables):
        lines = ["REST API Endpoints (output as JSON action):"]
        for t in tables:
            cols = ", ".join(c.name for c in t.columns)
            lines.append(f"Endpoint: {t.name} | Fields: {cols}")
        lines.append('\nRespond with JSON: {"endpoint": "...", "params": {...}, "method": "GET"}')
        return "\n".join(lines)
