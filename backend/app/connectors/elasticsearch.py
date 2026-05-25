"""
app/connectors/elasticsearch.py -- Elasticsearch connector
Config: {"host": "localhost", "port": 9200, "user": "", "password": "", "use_ssl": false, "index_pattern": "*"}
"""
import time
import json
from typing import List, Dict, Any
from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class ElasticsearchConnector(BaseConnector):

    def _get_client(self):
        from elasticsearch import AsyncElasticsearch
        cfg = self.config
        host = f"{'https' if cfg.get('use_ssl') else 'http'}://{cfg.get('host', 'localhost')}:{cfg.get('port', 9200)}"
        kwargs: Dict[str, Any] = {}
        if cfg.get("user") and cfg.get("password"):
            kwargs["http_auth"] = (cfg["user"], cfg["password"])
        if cfg.get("api_key"):
            kwargs["api_key"] = cfg["api_key"]
        return AsyncElasticsearch([host], **kwargs)

    async def test_connection(self) -> bool:
        es = self._get_client()
        try:
            await es.info()
            return True
        finally:
            await es.close()

    async def get_schema(self) -> List[TableInfo]:
        es = self._get_client()
        try:
            pattern = self.config.get("index_pattern", "*")
            mappings = await es.indices.get_mapping(index=pattern)
            tables = []
            for index_name, mapping in mappings.items():
                if index_name.startswith("."):  # skip system indices
                    continue
                props = mapping.get("mappings", {}).get("properties", {})
                columns = [
                    ColumnInfo(
                        name=field,
                        type=info.get("type", "object"),
                        nullable=True,
                        primary_key=(field == "_id")
                    )
                    for field, info in props.items()
                ]
                # Add _id always
                if not any(c.name == "_id" for c in columns):
                    columns.insert(0, ColumnInfo(name="_id", type="keyword", nullable=False, primary_key=True))

                tables.append(TableInfo(name=index_name, columns=columns))
            return tables
        finally:
            await es.close()

    async def execute_query(self, query_json: str) -> QueryResult:
        """
        query_json: JSON string with Elasticsearch DSL:
        {"index": "my_index", "query": {...}, "size": 100, "sort": [...]}
        or {"index": "my_index", "aggs": {...}}
        """
        es = self._get_client()
        try:
            start = time.time()
            q = json.loads(query_json)
            index = q.pop("index", "_all")
            body = q

            response = await es.search(index=index, body=body)
            duration_ms = (time.time() - start) * 1000

            # Handle aggregations
            if "aggregations" in response or "aggs" in response:
                aggs = response.get("aggregations", response.get("aggs", {}))
                rows = []
                for key, val in aggs.items():
                    if "buckets" in val:
                        for bucket in val["buckets"]:
                            rows.append(bucket)
                if rows:
                    columns = list(rows[0].keys())
                    data = [[str(r.get(c, "")) for c in columns] for r in rows]
                    return QueryResult(columns=columns, rows=data, row_count=len(data), duration_ms=duration_ms)

            # Regular hits
            hits = response.get("hits", {}).get("hits", [])
            if not hits:
                return QueryResult(columns=[], rows=[], row_count=0, duration_ms=duration_ms)

            # Flatten _source + _id
            docs = [{"_id": h["_id"], **h.get("_source", {})} for h in hits]
            columns = list(docs[0].keys())
            data = [[str(doc.get(c, "")) for c in columns] for doc in docs]
            return QueryResult(columns=columns, rows=data, row_count=len(data), duration_ms=duration_ms)
        finally:
            await es.close()

    def get_schema_prompt(self, tables) -> str:
        lines = ["Elasticsearch Indices (output as JSON DSL query):"]
        for t in tables:
            cols = ", ".join(f"{c.name}({c.type})" for c in t.columns)
            lines.append(f"Index: {t.name} | Fields: {cols}")
        lines.append('\nRespond with JSON: {"index": "...", "query": {...}, "size": 100}')
        lines.append('For aggregations: {"index": "...", "aggs": {...}, "size": 0}')
        return "\n".join(lines)
