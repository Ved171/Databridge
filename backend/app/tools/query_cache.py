"""
app/tools/query_cache.py
------------------------
Redis-backed TTL query cache with PyArrow IPC serialization.
"""
from __future__ import annotations

import io
import logging
import pickle
from typing import Any, List, Optional

import pyarrow as pa
import redis.asyncio as aioredis

from app.connectors.base import QueryResult
from app.core.config import settings
from app.tools.duckdb_engine import sql_fingerprint

logger = logging.getLogger(__name__)


class QueryCache:
    """
    Distributed Redis cache with PyArrow IPC serialization.
    Keys: "db_cache:{connector_id}:{sql_fingerprint}"
    """
    _TTL_SECONDS = 120
    _PREFIX = "db_cache"

    def __init__(self):
        self._redis = aioredis.from_url(settings.REDIS_URL)

    def _key(self, connector_id: str, sql: str) -> str:
        return f"{self._PREFIX}:{connector_id}:{sql_fingerprint(sql)}"

    async def get(self, connector_id: str, sql: str) -> Optional[Any]:
        try:
            k = self._key(connector_id, sql)
            raw = await self._redis.get(k)
            if not raw:
                return None

            meta_len = int.from_bytes(raw[:4], "little")
            meta = pickle.loads(raw[4:4+meta_len])

            if "is_dict" in meta:
                return meta["data"]

            qr = QueryResult(
                columns=meta["columns"],
                rows=meta["rows"],
                row_count=meta["row_count"],
                duration_ms=meta["duration_ms"]
            )

            arrow_data = raw[4+meta_len:]
            if arrow_data:
                with pa.ipc.open_stream(io.BytesIO(arrow_data)) as reader:
                    qr.pa_table = reader.read_all()

            return qr
        except Exception as e:
            logger.warning("Cache get failed: %s", e)
            return None

    async def set(self, connector_id: str, sql: str, data: Any, tables: List[str] = None) -> None:
        try:
            k = self._key(connector_id, sql)

            meta = {"tables": tables or []}
            arrow_bytes = b""

            if isinstance(data, dict):
                meta["is_dict"] = True
                meta["data"] = data
            elif isinstance(data, QueryResult):
                meta.update({
                    "columns": data.columns,
                    "rows": data.rows,
                    "row_count": data.row_count,
                    "duration_ms": data.duration_ms
                })
                if data.pa_table is not None:
                    sink = io.BytesIO()
                    with pa.ipc.new_stream(sink, data.pa_table.schema) as writer:
                        writer.write_table(data.pa_table)
                    arrow_bytes = sink.getvalue()

            meta_blob = pickle.dumps(meta)
            packet = len(meta_blob).to_bytes(4, "little") + meta_blob + arrow_bytes

            await self._redis.setex(k, self._TTL_SECONDS, packet)

            if tables:
                for t in tables:
                    t_key = f"{self._PREFIX}_tables:{connector_id}:{t}"
                    await self._redis.sadd(t_key, k)
                    await self._redis.expire(t_key, self._TTL_SECONDS)
        except Exception as e:
            logger.warning("Cache set failed: %s", e)

    async def invalidate(self, connector_id: str, table_name: Optional[str] = None) -> None:
        try:
            if table_name:
                t_key = f"{self._PREFIX}_tables:{connector_id}:{table_name}"
                keys = await self._redis.smembers(t_key)
                if keys:
                    await self._redis.delete(*keys)
                    await self._redis.delete(t_key)
            else:
                pattern = f"{self._PREFIX}:{connector_id}:*"
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
        except Exception as e:
            logger.warning("Cache invalidation failed: %s", e)


# Module-level singleton
query_cache = QueryCache()
