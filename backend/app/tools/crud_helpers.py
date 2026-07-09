"""
app/tools/crud_helpers.py
-------------------------
Create / Update / Delete record helpers extracted from db_tools.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.connectors.base import QueryResult
from app.core.deps import check_connector_permission
from app.models import Connector
from app.tools.db_tools import (
    ToolContext,
    _get_active_connector,
    _get_rls_policies,
    _build_user_context,
    _execute_on_connector,
    _safe_val,
)
from app.tools.query_cache import query_cache as _cache

logger = logging.getLogger(__name__)


async def tool_create_record(
    ctx: ToolContext,
    db_id: str,
    table_or_collection: str,
    data: dict,
) -> str:
    connector = await _get_active_connector(ctx, db_id)
    if not connector:
        return f"Error: Database '{db_id}' not found."
    if not await check_connector_permission(str(connector.id), "create", ctx.user, ctx.db):
        return f"Error: Permission denied -- no CREATE access on '{connector.name}'."

    from app.core.deps import check_table_permission
    if not await check_table_permission(str(connector.id), table_or_collection, "create", ctx.user, ctx.db):
        return f"Error: Permission denied -- no 'CREATE' access on table/collection '{table_or_collection}'."

    db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()

    try:
        if db_type == "mongodb":
            query = json.dumps({"collection": table_or_collection, "operation": "insertOne", "document": data})
        elif db_type == "elasticsearch":
            query = json.dumps({"index": table_or_collection, "operation": "index", "document": data})
        elif db_type == "salesforce":
            query = json.dumps({"operation": "insert", "object": table_or_collection, "data": data})
        elif db_type == "redis":
            key = data.get("key") or f"{table_or_collection}:{data.get('id', 'new')}"
            query = json.dumps({"command": "SET", "args": [key, json.dumps(data)]})
        else:
            cols = ", ".join(data.keys())
            vals = ", ".join(_safe_val(v) for v in data.values())
            query = f"INSERT INTO {table_or_collection} ({cols}) VALUES ({vals}) RETURNING *"

        if query.strip().startswith("{"):
            rls_policies = await _get_rls_policies(ctx, db_id)
            if rls_policies:
                user_ctx = _build_user_context(ctx.user)
                from app.tools.nosql_rls import apply_rls_nosql
                query = apply_rls_nosql(query, db_type, rls_policies, user_ctx)
                try:
                    q_obj = json.loads(query)
                    if isinstance(q_obj, dict) and "error" in q_obj:
                        return f"Error: Permission denied -- {q_obj['error']}"
                except Exception:
                    pass

        result = await _execute_on_connector(connector, query)
        result["operation"] = "create"
        result["table"] = table_or_collection
        await _cache.invalidate(db_id, table_name=table_or_collection)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Error creating record in '{connector.name}'.{table_or_collection}: {str(e)}"


async def tool_update_record(
    ctx: ToolContext,
    db_id: str,
    table_or_collection: str,
    record_id: str,
    id_field: str,
    updates: dict,
) -> str:
    connector = await _get_active_connector(ctx, db_id)
    if not connector:
        return f"Error: Database '{db_id}' not found."
    if not await check_connector_permission(str(connector.id), "update", ctx.user, ctx.db):
        return f"Error: Permission denied -- no UPDATE access on '{connector.name}'."

    from app.core.deps import check_table_permission
    if not await check_table_permission(str(connector.id), table_or_collection, "update", ctx.user, ctx.db):
        return f"Error: Permission denied -- no 'UPDATE' access on table/collection '{table_or_collection}'."

    db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()

    try:
        if db_type == "mongodb":
            query = json.dumps({"collection": table_or_collection, "operation": "updateOne", "filter": {id_field: record_id}, "update": {"$set": updates}})
        elif db_type == "salesforce":
            query = json.dumps({"operation": "update", "object": table_or_collection, "id": record_id, "data": updates})
        elif db_type == "redis":
            query = json.dumps({"command": "SET", "args": [record_id, json.dumps(updates)]})
        else:
            set_clause = ", ".join(f"{k} = {_safe_val(v)}" for k, v in updates.items())
            id_val = _safe_val(record_id)
            query = f"UPDATE {table_or_collection} SET {set_clause} WHERE {id_field} = {id_val}"

        if query.strip().startswith("{"):
            rls_policies = await _get_rls_policies(ctx, db_id)
            if rls_policies:
                user_ctx = _build_user_context(ctx.user)
                from app.tools.nosql_rls import apply_rls_nosql
                query = apply_rls_nosql(query, db_type, rls_policies, user_ctx)
                try:
                    q_obj = json.loads(query)
                    if isinstance(q_obj, dict) and "error" in q_obj:
                        return f"Error: Permission denied -- {q_obj['error']}"
                except Exception:
                    pass

        result = await _execute_on_connector(connector, query)
        result["operation"] = "update"
        result["table"] = table_or_collection
        result["record_id"] = record_id
        await _cache.invalidate(db_id, table_name=table_or_collection)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Error updating record in '{connector.name}'.{table_or_collection}: {str(e)}"


async def tool_delete_record(
    ctx: ToolContext,
    db_id: str,
    table_or_collection: str,
    record_id: str,
    id_field: str = "id",
) -> str:
    connector = await _get_active_connector(ctx, db_id)
    if not connector:
        return f"Error: Database '{db_id}' not found."
    if not await check_connector_permission(str(connector.id), "delete", ctx.user, ctx.db):
        return f"Error: Permission denied -- no DELETE access on '{connector.name}'."

    from app.core.deps import check_table_permission
    if not await check_table_permission(str(connector.id), table_or_collection, "delete", ctx.user, ctx.db):
        return f"Error: Permission denied -- no 'DELETE' access on table/collection '{table_or_collection}'."

    db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()

    try:
        if db_type == "mongodb":
            query = json.dumps({"collection": table_or_collection, "operation": "deleteOne", "filter": {id_field: record_id}})
        elif db_type == "salesforce":
            query = json.dumps({"operation": "delete", "object": table_or_collection, "id": record_id})
        elif db_type == "redis":
            query = json.dumps({"command": "DEL", "args": [record_id]})
        else:
            id_val = _safe_val(record_id)
            query = f"DELETE FROM {table_or_collection} WHERE {id_field} = {id_val}"

        if query.strip().startswith("{"):
            rls_policies = await _get_rls_policies(ctx, db_id)
            if rls_policies:
                user_ctx = _build_user_context(ctx.user)
                from app.tools.nosql_rls import apply_rls_nosql
                query = apply_rls_nosql(query, db_type, rls_policies, user_ctx)
                try:
                    q_obj = json.loads(query)
                    if isinstance(q_obj, dict) and "error" in q_obj:
                        return f"Error: Permission denied -- {q_obj['error']}"
                except Exception:
                    pass

        result = await _execute_on_connector(connector, query)
        result["operation"] = "delete"
        result["table"] = table_or_collection
        result["record_id"] = record_id
        await _cache.invalidate(db_id, table_name=table_or_collection)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Error deleting record from '{connector.name}'.{table_or_collection}: {str(e)}"
