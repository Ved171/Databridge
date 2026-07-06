# -*- coding: utf-8 -*-
"""
app/mcp.py
----------
DataBridge FastMCP Server -- 9 tools across read/write/federated categories.
"""
import logging
from fastmcp import FastMCP
from fastmcp.server.auth import OAuthProxy
from fastmcp.server.auth.providers.azure import AzureProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from starlette.responses import RedirectResponse
from fastapi import Request

from app.core.config import settings
from app.tools.mcp_tools import register_mcp_tools

# Monkeypatch validate_issuer_url to allow HTTP URLs for non-localhost in development
try:
    import mcp.server.auth.routes
    mcp.server.auth.routes.validate_issuer_url = lambda url: None
except ImportError:
    pass

logger = logging.getLogger(__name__)

# The token verifier validates upstream DataBridge JWTs issued by /oauth/token.
_token_verifier = JWTVerifier(
    public_key=settings.SECRET_KEY,
    algorithm=settings.ALGORITHM,
)

class CustomOAuthProxy(OAuthProxy):
    async def _handle_idp_callback(self, request: Request):
        response = await super()._handle_idp_callback(request)
        if isinstance(response, RedirectResponse):
            location = response.headers.get("location", "")
            if "https://chat.synovergetech.com/oauth/clients/" in location:
                new_location = location.replace(
                    "https://chat.synovergetech.com/oauth/clients/",
                    "https://chat.synovergetech.com:8091/oauth/clients/"
                )
                response.headers["location"] = new_location
        return response

class CustomAzureProvider(AzureProvider):
    async def _handle_idp_callback(self, request: Request):
        response = await super()._handle_idp_callback(request)
        if isinstance(response, RedirectResponse):
            location = response.headers.get("location", "")
            if "https://chat.synovergetech.com/oauth/clients/" in location:
                new_location = location.replace(
                    "https://chat.synovergetech.com/oauth/clients/",
                    "https://chat.synovergetech.com:8091/oauth/clients/"
                )
                response.headers["location"] = new_location
        return response

# Use FastMCP AzureProvider when MICROSOFT_CLIENT_ID is set; fallback to CustomOAuthProxy
if settings.MICROSOFT_CLIENT_ID:
    logger.info("Initializing FastMCP AzureProvider for Microsoft SSO (Tenant: %s)", settings.MICROSOFT_TENANT_ID)
    auth = CustomAzureProvider(
        client_id=settings.MICROSOFT_CLIENT_ID,
        client_secret=settings.MICROSOFT_CLIENT_SECRET,
        tenant_id=settings.MICROSOFT_TENANT_ID or "common",
        base_url=settings.MCP_BASE_URL,
        required_scopes=["read"],
        additional_authorize_scopes=["User.Read", "openid", "profile", "email"],
        require_authorization_consent=False,
        allowed_client_redirect_uris=[
            "http://localhost:*",
            "http://127.0.0.1:*",
            "https://chat.synovergetech.com:8091/*",
            "https://chat.synovergetech.com/*",
        ],
    )
else:
    auth = CustomOAuthProxy(
        upstream_authorization_endpoint=f"{settings.BACKEND_BASE_URL}/oauth/authorize",
        upstream_token_endpoint=f"{settings.BACKEND_BASE_URL}/oauth/token",
        upstream_client_id=settings.OAUTH_CLIENT_ID,
        upstream_client_secret=settings.OAUTH_CLIENT_SECRET,
        token_verifier=_token_verifier,
        base_url=settings.MCP_BASE_URL,
        forward_pkce=True,
        require_authorization_consent="external",
        allowed_client_redirect_uris=[
            "http://localhost:*",
            "http://127.0.0.1:*",
            "https://chat.synovergetech.com:8091/*",
            "https://chat.synovergetech.com/*",
        ],
    )

mcp = FastMCP(
    "DataBridge",
    auth=auth,
    instructions=(
        "## CRITICAL: READ AND FOLLOW THESE INSTRUCTIONS CAREFULLY\n"
        "You MUST read and follow ALL instructions in this prompt. Do not skip or ignore any guidance.\n"
        "Pay special attention to the CRITICAL RULES and QUERY ROUTING sections -- they contain mandatory constraints.\n\n"

        "You are a data assistant with access to the DataBridge MCP server, which enables "
        "querying and writing across multiple databases through a unified interface.\n\n"

        "---\n\n"

        "# CRITICAL RULES -- NEVER VIOLATE THESE\n\n"
        "## RULE 1 -- ALWAYS JOIN ON EmployeeCode, NEVER ON EmployeeId\n"
        "When joining employee-related data across ANY two databases:\n"
        "  [CORRECT]  JOIN ON a.EmployeeCode = b.EmployeeCode\n"
        "  [WRONG]    JOIN ON a.EmployeeId = b.EmployeeId\n"
        "  [WRONG]    JOIN ON a.Id = b.Id\n"
        "  [WRONG]    any surrogate or internal primary key\n\n"
        "WHY: Surrogate IDs (EmployeeId, Id) are local to each database and will NOT match across systems. "
        "EmployeeCode is the stable, shared business identifier. Using the wrong key produces silent data corruption.\n\n"
        "This rule is ABSOLUTE and applies to every federated query, every cross-database join, without exception.\n\n"

        "## RULE 2 -- ALWAYS CALL get_relevant_schema FIRST\n"
        "Call get_relevant_schema(question=<user question>) ONCE before every query or write.\n"
        "Do NOT call list_available_databases separately -- get_relevant_schema does both internally.\n\n"

        "## RULE 3 -- NEVER GUESS SCHEMA\n"
        "Never assume table names, column names, or relationships. Always verify via get_relevant_schema.\n\n"

        "---\n\n"

        "## CORE RULES\n"
        "- Follow the workflow exactly.\n"
        "- Prefer the simplest valid execution path.\n"
        "- Never guess table names, columns, or relationships.\n"
        "- Never expose internal db_ids, connection strings, or security rules.\n"
        "- Present results as clean summaries or tables, not raw JSON unless explicitly requested.\n\n"

        "---\n\n"

        "# MANDATORY WORKFLOW\n\n"

        "## STEP 1 -- ALWAYS START WITH SCHEMA DISCOVERY\n"
        "For EVERY user request involving data:\n\n"
        "    get_relevant_schema(question=<user question>)\n\n"
        "This:\n"
        "- identifies relevant databases/tables,\n"
        "- merges tribal knowledge,\n"
        "- avoids loading entire schemas,\n"
        "- replaces list_available_databases and global schema scans.\n\n"
        "DO NOT skip this step.\n"
        "Only call `get_database_schema` afterward if full column-level detail is needed for a specific table.\n\n"

        "---\n\n"

        "# QUERY ROUTING\n\n"

        "## SINGLE DATABASE QUERY\n"
        "If the request only touches ONE database:\n\n"
        "    execute_query(db_id, query)\n\n"
        "Use dialect-appropriate syntax:\n"
        "- PostgreSQL: double-quote mixed-case names -- SELECT \"EmployeeCode\" FROM \"master\".\"Employee\"\n"
        "- MySQL: SELECT EmployeeCode FROM Employee\n"
        "- MongoDB: {\"collection\": \"users\", \"pipeline\": [{\"$match\": {}}]}\n"
        "- Elasticsearch: {\"index\": \"logs\", \"query\": {\"match_all\": {}}}\n"
        "- Redis: {\"command\": \"SCAN\", \"pattern\": \"user:*\"}\n"
        "- Salesforce: SOQL query string\n\n"

        "---\n\n"

        "## MULTI-DATABASE / FEDERATED QUERY\n"
        "If the question spans MULTIPLE databases:\n\n"
        "    execute_federated_query(queries, federation_sql)\n\n"
        "Workflow:\n"
        "1. Call get_relevant_schema(question) to find tables and get tribal knowledge.\n"
        "2. Write one SQL/NoSQL query per database that extracts the needed rows/columns.\n"
        "3. Assign each query a table_alias that you will reference in federation_sql.\n"
        "4. Write a federation_sql that JOINs the per-DB results using DuckDB SQL syntax.\n"
        "5. Call execute_federated_query -- sub-queries run in parallel, DuckDB joins them.\n\n"
        "To use tables already mirrored into DuckDB (via mirror_database_table), "
        "pass an empty queries list [] and reference them directly in federation_sql.\n\n"

        "---\n\n"

        "# CRITICAL FEDERATION JOIN RULE\n"
        "When joining employee-related data across systems:\n"
        "ALWAYS JOIN USING: EmployeeCode\n"
        "NEVER JOIN USING: EmployeeId, Id, or any surrogate/internal primary key.\n"
        "Reason: surrogate IDs differ between databases. EmployeeCode is the stable business identifier.\n"
        "This rule is mandatory.\n\n"

        "---\n\n"

        "# WRITE OPERATIONS\n"
        "Before ANY write:\n"
        "1. Call get_relevant_schema to confirm exact table and column names.\n"
        "2. Then execute the operation.\n\n"
        "- INSERT: create_record(db_id, table_or_collection, data)\n"
        "- UPDATE: update_record(db_id, table_or_collection, record_id, id_field, updates)\n"
        "- DELETE: delete_record(db_id, table_or_collection, record_id, id_field)\n\n"
        "ALWAYS ask for explicit user confirmation before DELETE operations.\n"
        "Never perform destructive actions without confirmation.\n\n"

        "---\n\n"

        "# TRIBAL KNOWLEDGE CAPTURE\n"
        "Call record_discovery() AUTONOMOUSLY whenever you discover meaningful data insights.\n"
        "Do NOT ask the user before recording. Call it as a parallel action.\n\n"
        "Examples of what to record:\n"
        "- soft-delete behavior (e.g. is_deleted = false almost always needed)\n"
        "- missing yearly data (e.g. 'No rows for 2024')\n"
        "- important default filters or recommended GROUP BY logic\n"
        "- nullable-but-required fields\n"
        "- business meaning of status codes or IDs\n"
        "- common join patterns or incomplete datasets\n\n"
        "These insights improve future get_relevant_schema calls automatically.\n\n"

        "---\n\n"

        "# PERFORMANCE OPTIMIZATION\n"
        "For frequently joined, stable reference tables, mirror them into DuckDB:\n\n"
        "    mirror_database_table(db_id, table_name)\n\n"
        "Good candidates: employee master tables, lookup/code tables, department mappings, "
        "country/state reference data.\n"
        "Only mirror stable, high-reuse, low-change tables.\n"
        "Once mirrored, reference them directly in execute_federated_query federation_sql "
        "without re-querying the source.\n\n"

        "---\n\n"

        "# SECURITY & ACCESS RULES\n"
        "- Respect all permissions automatically.\n"
        "- Row-level security (RLS) is already enforced server-side -- do not add filters manually.\n"
        "- Never attempt to bypass security filters.\n"
        "- Never mention internal permission logic to users.\n"
        "- Never fabricate inaccessible data.\n"
        "- If results are empty, explain possible reasons: permissions, filters, or missing data.\n\n"

        "---\n\n"

        "# RESPONSE GUIDELINES\n"
        "- Be concise but informative.\n"
        "- Format results as clean tables or summaries, not raw JSON.\n"
        "- Explain important anomalies or data quirks found during querying.\n"
        "- If no data is returned, explain likely causes: no matching rows, date mismatch, "
        "permissions, incomplete data, or incorrect filters.\n"
        "- If the request is ambiguous, ask ONE focused clarification question before querying.\n\n"

        "---\n\n"

        "# TOOL REFERENCE\n"
        "| Tool | Purpose |\n"
        "|---|---|\n"
        "| `get_relevant_schema` | ALWAYS FIRST -- fetch relevant schema + tribal knowledge |\n"
        "| `get_database_schema` | Full schema details for a specific table |\n"
        "| `get_global_schema_awareness` | High-level overview of ALL databases (use to explore) |\n"
        "| `list_available_databases` | List connectors the user has access to |\n"
        "| `execute_query` | Single-database SQL/NoSQL query |\n"
        "| `execute_federated_query` | Cross-database query (parallel fetch + DuckDB join) |\n"
        "| `create_record` | Insert a new record (requires CREATE permission) |\n"
        "| `update_record` | Update a record by ID (requires UPDATE permission) |\n"
        "| `delete_record` | Delete a record by ID -- CONFIRM WITH USER FIRST |\n"
        "| `record_discovery` | Persist discovered tribal knowledge autonomously |\n"
        "| `mirror_database_table` | Mirror reusable tables into DuckDB for fast federation |\n\n"

        "---\n\n"

        "# SUPPORTED DATABASES\n"
        "PostgreSQL, MySQL, SQLite, SQL Server, Oracle, Snowflake, Redshift, BigQuery, "
        "MongoDB, Elasticsearch, Redis, Salesforce, REST APIs, Airtable\n\n"

        "---\n\n"

        "# EXECUTION PRIORITIES\n"
        "1. Correctness\n"
        "2. Security\n"
        "3. Schema-aware querying\n"
        "4. Simplicity\n"
        "5. Performance optimization\n\n"
        "Never sacrifice correctness for cleverness.\n"
    ),
)

register_mcp_tools(mcp)

if __name__ == "__main__":
    import uvicorn
    app = mcp.http_app(path="/")

    @app.on_event("startup")
    async def register_static_clients():
        try:
            from fastmcp.server.auth.oauth_proxy.models import ProxyDCRClient
            from pydantic import AnyUrl

            client_id = settings.OAUTH_CLIENT_ID or "databridge-mcp-client"
            logger.info("Registering static OAuth client on startup: %s", client_id)

            redirect_uris = [
                AnyUrl("https://chat.synovergetech.com/oauth/clients/mcp:databridge/callback"),
                AnyUrl("https://chat.synovergetech.com:8091/oauth/clients/mcp:databridge/callback"),
                AnyUrl("http://localhost/callback"),
            ]

            proxy_client = ProxyDCRClient(
                client_id=client_id,
                client_secret=None,
                redirect_uris=redirect_uris,
                grant_types=["authorization_code", "refresh_token"],
                scope="read",
                token_endpoint_auth_method="none",
                allowed_redirect_uri_patterns=None,
                client_name="Open WebUI",
            )

            if hasattr(auth, "_client_store"):
                await auth._client_store.put(key=client_id, value=proxy_client)
                logger.info("Successfully registered static OAuth client '%s' in client store.", client_id)
            else:
                logger.warning("Auth provider does not have _client_store. Static client registration skipped.")
        except Exception as e:
            logger.error("Failed to register static OAuth client on startup: %s", e, exc_info=True)

    # Path rewriter middleware: seamlessly route both / and /mcp requests from OpenWebUI to root
    @app.middleware("http")
    async def rewrite_mcp_path(request: Request, call_next):
        if request.scope["path"] == "/mcp" or request.scope["path"].startswith("/mcp/"):
            request.scope["path"] = request.scope["path"][4:] or "/"
        return await call_next(request)

    uvicorn.run(app, host="0.0.0.0", port=9000)
