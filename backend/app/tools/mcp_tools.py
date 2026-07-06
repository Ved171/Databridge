"""
app/tools/mcp_tools.py

Registers ALL DataBridge tool functions as FastMCP tools.
"""
from __future__ import annotations

import json
import logging
import time
import hashlib
from typing import Optional, List
from pathlib import Path

from fastmcp import FastMCP, Context
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models import User
from app.tools.db_tools import (
    ToolContext,
    tool_list_available_databases,
    tool_get_database_schema,
    tool_get_global_schema_awareness,
    tool_execute_query,
    tool_create_record,
    tool_update_record,
    tool_delete_record,
    tool_execute_federated_query,
    tool_record_discovery,
    tool_mirror_table,
)

logger = logging.getLogger(__name__)


#  User auth cache 
_user_cache: dict = {}
_USER_CACHE_TTL = 60  # seconds


async def _resolve_user(token_or_access, db):
    """
    Decode JWT or extract claims from FastMCP AccessToken object,
    fetch user from DB, or auto-provision new Microsoft SSO user with default role.
    """
    import secrets
    from passlib.context import CryptContext
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    claims = getattr(token_or_access, "claims", None)
    email = None
    user_id = None

    if isinstance(claims, dict):
        email = claims.get("email") or claims.get("preferred_username") or claims.get("upn")
        user_id = claims.get("sub")
    
    if not user_id and not email:
        token_str = getattr(token_or_access, "token", str(token_or_access))
        try:
            payload = decode_token(token_str)
            user_id = payload.get("sub")
            email = payload.get("email")
        except Exception:
            pass

    user = None
    if user_id:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if not user and email:
        result = await db.execute(select(User).where(User.email == email.lower().strip()))
        user = result.scalar_one_or_none()

    # Auto-provision user if logging in via Azure AD / Microsoft for the first time
    if not user and email:
        ms_email = email.lower().strip()
        ms_name = ms_email.split("@")[0].capitalize()

        from app.models import Role
        role_res = await db.execute(select(Role).where(Role.slug == "member"))
        default_role = role_res.scalar_one_or_none()

        user = User(
            email=ms_email,
            name=ms_name,
            hashed_password=pwd_ctx.hash(secrets.token_urlsafe(32)),
            is_superadmin=False,
            role_id=default_role.id if default_role else None,
            department_id=None,  
            is_active=True,
            force_password_change=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("Auto-provisioned new Microsoft SSO user: %s (id=%s, role=member)", ms_email, user.id)

    return user


async def _get_accessible_connectors_with_schema(db, user) -> list[dict]:
    """Fetch all connectors user has read access to, including their cached schemas."""
    from app.models import Connector
    from app.core.deps import check_connector_permission, check_table_permission

    stmt = select(Connector).where(Connector.is_active == True)
    res = await db.execute(stmt)
    connectors = res.scalars().all()

    accessible = []
    for c in connectors:
        if await check_connector_permission(c.id, "read", user, db):
            tables = []
            if c.schema_cache and isinstance(c.schema_cache, dict):
                raw_tables = c.schema_cache.get("tables", [])
                cache = {}
                for t in raw_tables:
                    t_schema = t.get("schema")
                    t_name = t.get("name")
                    full_name = f"{t_schema}.{t_name}" if t_schema else t_name
                    if await check_table_permission(c.id, full_name, "read", user, db, _cache=cache):
                        tables.append(t)
            accessible.append({
                "id": c.id,
                "name": c.name,
                "type": str(c.type.value) if hasattr(c.type, "value") else str(c.type),
                "tables": tables,
            })
    return accessible


async def _build_ctx_and_run(mcp_ctx: Context, coro_factory):
    """Auth check + ToolContext builder shared across all tools."""
    try:
        from fastmcp.server.dependencies import get_access_token
        access_token = get_access_token()
        if not access_token:
            return "Error: Missing or invalid authentication. Please configure/login to OAuth."
    except Exception as e:
        logger.error("Authentication extraction failed: %s", e)
        return "Error: Unable to extract authentication token."
    try:
        async with AsyncSessionLocal() as db:
            try:
                user = await _resolve_user(access_token, db)
            except Exception as e:
                logger.error("Authentication check failed: %s", e)
                return "Error: Invalid or expired token."

            if not user or not user.is_active:
                return "Error: User not found or inactive."

            ctx = ToolContext(user=user, db=db)

            try:
                return await coro_factory(ctx)
            except Exception as e:
                logger.error("Tool execution failed: %s", e, exc_info=True)
                return f"Error executing tool: {e}"
    except Exception as e:
        logger.error("_build_ctx_and_run connection failed: %s", e)
        return f"Error: Database connection issue. Detail: {e}"


def register_mcp_tools(mcp: FastMCP) -> None:
    """Register all DataBridge tools and resources on the FastMCP instance."""

    #  RESOURCES 
    @mcp.resource("schema://databridge/atlas",
                  description="List all available connector atlases with metadata.")
    async def list_connector_atlases() -> str:
        from app.services.atlas_builder import get_atlas_builder
        builder = get_atlas_builder()
        atlases = builder.load_all_atlases()
        summary = [
            {
                "connector_id": meta.get("connector_id"),
                "connector_type": meta.get("connector_type"),
                "db_name": meta.get("db_name"),
                "table_count": meta.get("table_count"),
                "last_updated": meta.get("last_updated"),
            }
            for a in atlases.values()
            for meta in [a.get("metadata", {})]
        ]
        return json.dumps(summary, indent=2)

    @mcp.resource("schema://databridge/atlas/{connector_id}",
                  description="Full atlas for a specific connector -- enriched schema with tribal knowledge.")
    async def get_connector_atlas(connector_id: str) -> str:
        from app.services.atlas_builder import get_atlas_builder
        builder = get_atlas_builder()
        atlas = builder.load_connector_atlas_by_id(connector_id)
        if atlas is None:
            return json.dumps({"error": f"No atlas found for connector '{connector_id}'. Run create_atlases.py first."})
        return json.dumps(atlas, indent=2)

    #  READ: List Databases 
    @mcp.tool
    async def list_available_databases(ctx: Context) -> str:
        """
        Lists all database connectors the current user has READ access to.
        Returns IDs, names, types, query format hints, schema status, and atlas status.
        If the schema is not cached or you can't see the atlas just say these words 'Schema of the connector is not cached please click the refresh schema button on connectors page.'
        """
        return await _build_ctx_and_run(ctx, tool_list_available_databases)

    #  READ: Get Relevant Schema 
    @mcp.tool
    async def get_relevant_schema(ctx: Context, question: str) -> str:
        """
        CALL THIS FIRST for every query.

        Returns only the databases and tables relevant to the user's question,
        with atlas tribal knowledge (gotchas, learned filters) already merged in.
        Uses fast token-based scoring (no API calls, < 5ms).
        Typically returns 6-15 tables instead of the full 200+ table schema.

        Columns are returned in compact "Name:type" format (audit columns stripped)
        to minimize token usage. Use get_database_schema for full column detail.

        Args:
            question: The user's natural language question or task description.

        Returns:
            JSON list of relevant connectors with filtered, minified table schemas.
        """
        from app.services.schema_search import pick_cross_db_tables, minify_schema_response
        from app.services.schema_cache import get_or_fetch_connectors_schema

        async def _run(tool_ctx: ToolContext) -> str:
            async def fetch_dbs():
                return await _get_accessible_connectors_with_schema(tool_ctx.db, tool_ctx.user)

            dbs = await get_or_fetch_connectors_schema(str(tool_ctx.user.id), fetch_dbs)
            result = pick_cross_db_tables(question, dbs)
            result = minify_schema_response(result)
            return json.dumps(result, indent=2)

        return await _build_ctx_and_run(ctx, _run)

    #  READ: Get Schema 
    @mcp.tool
    async def get_database_schema(
        ctx: Context,
        db_id: str,
        schema_name: Optional[str] = None,
        table_names: Optional[List[str]] = None,
    ) -> str:
        """
        Retrieves the enriched schema for a specific database.
        Merges live column metadata with atlas tribal knowledge (gotchas, learned filters,
        summaries, aggregation patterns). Use after get_relevant_schema to drill into
        specific tables before writing a query.

        Args:
            db_id: Connector ID from list_available_databases.
            schema_name: Optional schema filter (e.g. 'public').
            table_names: Optional list of specific tables (e.g. ['master.Employee']).
        """
        async def _run(tool_ctx: ToolContext) -> str:
            return await tool_get_database_schema(tool_ctx, db_id, schema_name, table_names)
        return await _build_ctx_and_run(ctx, _run)

    #  READ: Global Awareness 
    @mcp.tool
    async def get_global_schema_awareness(ctx: Context) -> str:
        """
        High-level overview of ALL connected databases grouped by schema and tables.
        Tables with recorded tribal knowledge are marked with [INFO].
        Reads from atlas files first (fast), falls back to live schema cache.
        Use to discover where specific data lives without fetching every full schema.
        """
        return await _build_ctx_and_run(ctx, tool_get_global_schema_awareness)

    #  READ: Execute Raw Query 
    @mcp.tool
    async def execute_query(ctx: Context, db_id: str, query: str) -> str:
        """
        Executes a raw query against a single database. Returns results as JSON.
        - SQL databases: standard SQL
        - MongoDB: {"collection":"...","pipeline":[...]}
        - Elasticsearch: {"index":"...","query":{...}}
        - Redis: {"command":"SCAN","pattern":"prefix:*"}
        - Salesforce: SOQL string
        Permission enforced: SELECT->READ, INSERT->CREATE, UPDATE->UPDATE, DELETE->DELETE.
        """
        async def _run(tool_ctx: ToolContext) -> str:
            return await tool_execute_query(tool_ctx, db_id, query)
        return await _build_ctx_and_run(ctx, _run)

    #  FEDERATED: Execute Cross-Database Query 
    @mcp.tool
    async def execute_federated_query(
        ctx: Context,
        queries: List[dict],
        federation_sql: str,
    ) -> str:
        """
        Execute queries across multiple databases in parallel, then join the results
        using DuckDB federation SQL.

        Workflow:
          1. Call get_relevant_schema(question) to find tables and get tribal knowledge
          2. Write one SQL query per database that extracts the needed rows/columns
          3. Write a federation_sql that JOINs the per-DB results using DuckDB syntax
          4. Call this tool -- sub-queries run in parallel, DuckDB joins them

        Args:
            queries: List of {"db_id": "...", "query": "...", "table_alias": "..."}.
                     table_alias must match the alias used in federation_sql.
                     Pass an empty list [] to query only mirrored tables.
            federation_sql: DuckDB SQL referencing the table aliases from queries.

        Returns:
            JSON with federated_result (columns + rows) and per-DB execution metadata.
        """
        async def _run(tool_ctx: ToolContext) -> str:
            return await tool_execute_federated_query(tool_ctx, queries, federation_sql)
        return await _build_ctx_and_run(ctx, _run)

    #  CREATE: Insert Record 
    @mcp.tool
    async def create_record(
        ctx: Context,
        db_id: str,
        table_or_collection: str,
        data: dict,
    ) -> str:
        """
        Insert a new record into a table or collection.
        Requires CREATE permission on the connector.
        Works across SQL, MongoDB, Elasticsearch, Salesforce, Redis.
        data: dictionary of field_name -> value pairs.
        """
        async def _run(tool_ctx: ToolContext) -> str:
            return await tool_create_record(tool_ctx, db_id, table_or_collection, data)
        return await _build_ctx_and_run(ctx, _run)

    #  UPDATE: Update Record 
    @mcp.tool
    async def update_record(
        ctx: Context,
        db_id: str,
        table_or_collection: str,
        record_id: str,
        id_field: str,
        updates: dict,
    ) -> str:
        """
        Update an existing record by its ID. Requires UPDATE permission.
        record_id: the value of the identifier (e.g. "42")
        id_field: the column/field name holding the ID (e.g. "id", "_id")
        updates: dictionary of field_name -> new_value pairs.
        """
        async def _run(tool_ctx: ToolContext) -> str:
            return await tool_update_record(tool_ctx, db_id, table_or_collection, record_id, id_field, updates)
        return await _build_ctx_and_run(ctx, _run)

    #  DELETE: Delete Record 
    @mcp.tool
    async def delete_record(
        ctx: Context,
        db_id: str,
        table_or_collection: str,
        record_id: str,
        id_field: str = "id",
    ) -> str:
        """
        Delete a record by its ID. Requires DELETE permission.
         Irreversible. Always confirm with the user before calling.
        """
        async def _run(tool_ctx: ToolContext) -> str:
            return await tool_delete_record(tool_ctx, db_id, table_or_collection, record_id, id_field)
        return await _build_ctx_and_run(ctx, _run)

    #  METADATA: Record Discovery 
    @mcp.tool
    async def record_discovery(
        ctx: Context,
        table_name: str,
        summary: Optional[str] = None,
        gotcha: Optional[str] = None,
        aggregation: Optional[str] = None,
        learned_filter: Optional[str] = None,
    ) -> str:
        """
        Permanently record tribal knowledge about a table into the atlas.
        Writes to both the atlas file and the DB -- immediately visible in
        get_database_schema and get_relevant_schema on the next call.

        MANDATORY RULE: Call this automatically whenever you discover anything
        not obvious from the schema alone -- data gaps, soft-delete patterns,
        surprising nulls, status ID meanings, recommended filters, etc.
        Do NOT ask permission. Call autonomously as a parallel action.

        Args:
            table_name:     Full path e.g. 'Appraisal.pa.Appraisal' or 'master.Employee'.
            summary:        One-line business description of the table.
            gotcha:         A data quirk future queries must know, e.g. 'No rows for 2024'.
            aggregation:    A common aggregation pattern, e.g. 'GROUP BY PeriodYear, StatusID'.
            learned_filter: A WHERE clause that is almost always needed, e.g. 'is_deleted = false'.
        """
        async def _run(tool_ctx: ToolContext) -> str:
            return await tool_record_discovery(tool_ctx, table_name, summary, gotcha, aggregation, learned_filter)
        return await _build_ctx_and_run(ctx, _run)

    #  METADATA: Mirror Table 
    @mcp.tool
    async def mirror_database_table(
        ctx: Context,
        db_id: str,
        table_name: str,
    ) -> str:
        """
        Fetch a full table from a connector and mirror it into the persistent DuckDB instance.
        Use for core reference tables that don't change often (e.g. master.Employee, lookup tables).
        Once mirrored, the table alias can be used directly in execute_federated_query
        without providing a sub-query for it -- making repeated joins lightning-fast.
        """
        async def _run(tool_ctx: ToolContext) -> str:
            return await tool_mirror_table(tool_ctx, db_id, table_name)
        return await _build_ctx_and_run(ctx, _run)