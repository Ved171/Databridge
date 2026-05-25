"""
app/connectors/salesforce.py -- Salesforce connector via SOQL
Config: {"username": "...", "password": "...", "security_token": "...",
         "domain": "login"}  # or "test" for sandbox
"""
import time
import json
from typing import List
from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class SalesforceConnector(BaseConnector):

    def _get_sf(self):
        from simple_salesforce import Salesforce
        cfg = self.config
        return Salesforce(
            username=cfg["username"],
            password=cfg["password"],
            security_token=cfg.get("security_token", ""),
            domain=cfg.get("domain", "login"),
        )

    async def test_connection(self) -> bool:
        import asyncio
        loop = asyncio.get_event_loop()
        def _test():
            sf = self._get_sf()
            sf.query("SELECT Id FROM User LIMIT 1")
        await loop.run_in_executor(None, _test)
        return True

    async def get_schema(self) -> List[TableInfo]:
        import asyncio
        loop = asyncio.get_event_loop()
        objects = self.config.get("objects", ["Account", "Contact", "Lead", "Opportunity", "Case"])
        def _schema():
            sf = self._get_sf()
            tables = []
            for obj_name in objects:
                try:
                    desc = getattr(sf, obj_name).describe()
                    fields = desc["fields"]
                    columns = [
                        ColumnInfo(
                            name=f["name"],
                            type=f["type"],
                            nullable=f.get("nillable", True),
                            primary_key=(f["name"] == "Id"),
                        )
                        for f in fields
                    ]
                    tables.append(TableInfo(name=obj_name, columns=columns))
                except Exception:
                    pass
            return tables
        return await loop.run_in_executor(None, _schema)

    async def execute_query(self, soql: str) -> QueryResult:
        """
        Executes SOQL query against Salesforce.
        For CRUD, use JSON format: {"operation": "insert|update|delete|upsert",
                                    "object": "Account", "data": {...}}
        """
        import asyncio
        loop = asyncio.get_event_loop()
        start = time.time()

        # Check if it's a CRUD operation (JSON format)
        stripped = soql.strip()
        if stripped.startswith("{"):
            def _crud():
                sf = self._get_sf()
                op = json.loads(stripped)
                operation = op.get("operation", "").lower()
                obj_name = op.get("object", "")
                data = op.get("data", {})
                obj = getattr(sf, obj_name)
                if operation == "insert":
                    result = obj.create(data)
                    return ["id", "success"], [[result.get("id"), str(result.get("success"))]]
                elif operation == "update":
                    record_id = op.get("id") or data.get("Id")
                    result = obj.update(record_id, data)
                    return ["status_code"], [[str(result)]]
                elif operation == "delete":
                    record_id = op.get("id")
                    result = obj.delete(record_id)
                    return ["status_code"], [[str(result)]]
                else:
                    return ["error"], [[f"Unknown operation: {operation}"]]
            columns, rows = await loop.run_in_executor(None, _crud)
            duration_ms = (time.time() - start) * 1000
            return QueryResult(columns=columns, rows=rows, row_count=len(rows), duration_ms=duration_ms)

        # SOQL SELECT query
        def _query():
            sf = self._get_sf()
            result = sf.query_all(soql)
            records = result.get("records", [])
            return records
        records = await loop.run_in_executor(None, _query)
        duration_ms = (time.time() - start) * 1000

        if not records:
            return QueryResult(columns=[], rows=[], row_count=0, duration_ms=duration_ms)

        # Remove Salesforce metadata
        cleaned = [{k: v for k, v in r.items() if k != "attributes"} for r in records]
        columns = list(cleaned[0].keys())
        rows = [[str(r.get(c, "")) for c in columns] for r in cleaned]
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), duration_ms=duration_ms)

    def get_schema_prompt(self, tables) -> str:
        lines = ["Salesforce Objects (use SOQL for queries):"]
        for t in tables:
            cols = ", ".join(f"{c.name}({c.type})" for c in t.columns[:20])
            lines.append(f"Object: {t.name} | Fields: {cols}")
        lines.append('\nUse SOQL: SELECT Id, Name FROM Account WHERE ...')
        lines.append('For CRUD ops use JSON: {"operation": "insert", "object": "Account", "data": {...}}')
        return "\n".join(lines)
