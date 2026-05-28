import time
import json
from typing import Any, Dict, List

from app.connectors.base import BaseConnector, ColumnInfo, TableInfo, QueryResult


class MongoDBConnector(BaseConnector):
    """
    Connector for MongoDB.
    'Tables' = collections. 'Columns' = inferred from sampled documents.
    SQL queries are translated to MongoDB aggregation pipelines via LLM.
    """

    def _get_client(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        import urllib.parse
        cfg = self.config
        
        uri = cfg.get("uri")
        database = cfg.get("database")
        
        if not uri:
            host = cfg.get("host")
            port = cfg.get("port", 27017)
            user = cfg.get("user")
            password = cfg.get("password")
            auth_source = cfg.get("authSource") or cfg.get("auth_source")
            
            # Default to 'admin' for authSource if user is provided but no source is specified.
            if user and not auth_source:
                auth_source = "admin"
            
            if user:
                encoded_user = urllib.parse.quote_plus(user)
                encoded_pass = urllib.parse.quote_plus(password) if password else ""
                base_uri = f"mongodb://{encoded_user}:{encoded_pass}@{host}:{port}/{database or ''}"
                
                params = []
                if auth_source:
                    params.append(f"authSource={auth_source}")
                
                if params:
                    uri = f"{base_uri}?{'&'.join(params)}"
                else:
                    uri = base_uri
            else:
                uri = f"mongodb://{host}:{port}/{database or ''}"
        
        # If database is still not provided in cfg, try to extract from URI
        if not database:
            try:
                parsed_uri = urllib.parse.urlparse(uri)
                # Path is usually /database
                path = parsed_uri.path.strip("/")
                if path:
                    database = path
            except:
                pass
        
        # Fallback to 'test'
        database = database or "test"
        
        return AsyncIOMotorClient(uri), database

    async def test_connection(self) -> bool:
        client, db_name = self._get_client()
        await client[db_name].list_collection_names()
        client.close()
        return True

    async def get_schema(self) -> List[TableInfo]:
        client, db_name = self._get_client()
        print(f"DEBUG: Connecting to MongoDB. Target db_name='{db_name}'")
        try:
            # List all available databases
            all_dbs = await client.list_database_names()
            print(f"DEBUG: All available databases: {all_dbs}")
            
            db = client[db_name]
            collection_names = await db.list_collection_names()
            print(f"DEBUG: Found collections in '{db_name}': {collection_names}")
            tables = []

            for coll_name in collection_names:
                # Sample 20 docs to infer schema
                cursor = db[coll_name].find({}, limit=20)
                docs = await cursor.to_list(length=20)

                # Infer columns from union of all doc keys
                all_keys: Dict[str, set] = {}
                for doc in docs:
                    for k, v in doc.items():
                        if k not in all_keys:
                            all_keys[k] = set()
                        all_keys[k].add(type(v).__name__)

                columns = [
                    ColumnInfo(
                        name=k,
                        type="|".join(types),
                        nullable=True,
                        primary_key=(k == "_id"),
                    )
                    for k, types in all_keys.items()
                ]

                count = await db[coll_name].count_documents({})
                tables.append(TableInfo(name=coll_name, columns=columns, row_count=count))

            return tables
        finally:
            client.close()

    async def execute_query(self, sql: str) -> QueryResult:
        """
        For MongoDB, the LLM generates a JSON aggregation pipeline instead of SQL.
        The pipeline is expected as: {"collection": "...", "pipeline": [...]}
        Or for write operations:
        - {"collection": "...", "operation": "insertOne", "document": {...}}
        - {"collection": "...", "operation": "updateOne", "filter": {...}, "update": {...}}
        - {"collection": "...", "operation": "deleteOne", "filter": {...}}
        """
        client, db_name = self._get_client()
        try:
            start = time.time()
            parsed = json.loads(sql)
            collection = parsed["collection"]
            db = client[db_name]

            operation = parsed.get("operation")
            if operation == "insertOne":
                doc = parsed.get("document", {})
                result = await db[collection].insert_one(doc)
                duration_ms = (time.time() - start) * 1000
                return QueryResult(
                    columns=["inserted_id"],
                    rows=[[str(result.inserted_id)]],
                    row_count=1,
                    duration_ms=duration_ms
                )
            elif operation == "updateOne":
                filter_obj = parsed.get("filter", {})
                update_obj = parsed.get("update", {})
                result = await db[collection].update_one(filter_obj, update_obj)
                duration_ms = (time.time() - start) * 1000
                return QueryResult(
                    columns=["matched_count", "modified_count"],
                    rows=[[str(result.matched_count), str(result.modified_count)]],
                    row_count=1,
                    duration_ms=duration_ms
                )
            elif operation == "deleteOne":
                filter_obj = parsed.get("filter", {})
                result = await db[collection].delete_one(filter_obj)
                duration_ms = (time.time() - start) * 1000
                return QueryResult(
                    columns=["deleted_count"],
                    rows=[[str(result.deleted_count)]],
                    row_count=1,
                    duration_ms=duration_ms
                )

            pipeline = parsed["pipeline"]
            cursor = db[collection].aggregate(pipeline)
            docs = await cursor.to_list(length=1000)
            duration_ms = (time.time() - start) * 1000

            if not docs:
                return QueryResult(columns=[], rows=[], row_count=0, duration_ms=duration_ms)

            # Flatten docs
            columns = list(docs[0].keys())
            rows = [[str(doc.get(c, "")) for c in columns] for doc in docs]

            return QueryResult(columns=columns, rows=rows, row_count=len(rows), duration_ms=duration_ms)
        finally:
            client.close()

    def get_schema_prompt(self, tables):
        """Override for MongoDB -- prompt LLM to output aggregation pipeline JSON."""
        lines = ["MongoDB Collections (output as JSON aggregation pipeline):"]
        for table in tables:
            cols = ", ".join(f"{c.name}({c.type})" for c in table.columns)
            lines.append(f"Collection: {table.name} | Fields: {cols}")
        lines.append('\nRespond with JSON: {"collection": "...", "pipeline": [...]}')
        return "\n".join(lines)
