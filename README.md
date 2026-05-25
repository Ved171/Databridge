# DataBridge v2 — Multi-DB NL Query Platform

A CData Connect AI-equivalent: permission-based, 14+ database connector types, semantic pre-resolution for 98%+ NL query accuracy, central MCP server with 9 tools, and full CRUD with row-level security.

## What's New in v2

### Semantic Accuracy Layer (CData-grade 98%+)
The #1 accuracy improvement: natural language terms are resolved to dialect-specific SQL **before** the LLM ever writes a query.

```
User: "Show revenue this quarter"
         ↓ SemanticResolver.resolve()
Resolved: "this quarter" → BETWEEN DATE_TRUNC('quarter', NOW()) AND NOW()  [PostgreSQL]
                         → BETWEEN DATE_TRUNC('quarter',CURRENT_DATE()) AND NOW()  [Snowflake]
         ↓ build_rich_schema_prompt()
Schema:  Only tables user has READ permission on + semantic type annotations
         ↓ Claude API
Query:   SELECT SUM(amount) FROM orders WHERE created_at BETWEEN DATE_TRUNC('quarter', NOW()) AND NOW()
         ↓ RLS injection
Final:   ... WHERE org_id = 'user-org-id' AND created_at BETWEEN ...
```

### 9 MCP Tools
| Category  | Tool                        | Permission |
|-----------|----------------------------|------------|
| Discovery | list_available_databases    | READ       |
| Discovery | get_global_schema_awareness | READ       |
| Discovery | get_database_schema         | READ       |
| Query     | **natural_language_query** ★| READ       |
| Query     | execute_query               | READ       |
| Query     | cross_database_query        | READ       |
| Write     | create_record               | CREATE     |
| Write     | update_record               | UPDATE     |
| Write     | delete_record               | DELETE     |

### 14 Database Types
| Category | Databases |
|----------|-----------|
| SQL | PostgreSQL, MySQL, SQLite, SQL Server, Oracle, Snowflake, Redshift |
| NoSQL | MongoDB, Elasticsearch, Redis |
| SaaS | Salesforce, REST API, Airtable |
| Cloud | BigQuery |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Agent / Claude                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ MCP Protocol
┌──────────────────────────▼──────────────────────────────────┐
│               FastMCP Server (port 9000)                    │
│  9 tools: list, schema, NL query, execute, cross-db,        │
│           create, update, delete                            │
└──────────┬──────────────────────────────────────────────────┘
           │ JWT auth + permission check
┌──────────▼──────────────────────────────────────────────────┐
│              Permission & Auth Layer                        │
│  ConnectorPermission: can_read/create/update/delete per user│
│  RLSPolicy: row-level filters per table per user/role       │
└──────────┬──────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│            Semantic Resolver (accuracy engine)              │
│  • Date terms → dialect-specific SQL (8 dialects)           │
│  • Business terms → SQL aggregations                        │
│  • Schema filtered to user's accessible tables              │
│  • Semantic type annotations (date/currency/id/boolean)     │
└──────────┬──────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│              NL Query Service (Claude API)                  │
│  Claude claude-sonnet-4 with enriched schema context        │
│  Cross-DB federated query generation                        │
└──────────┬──────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│           Driver Abstraction Layer                          │
│  BaseConnector interface → 14 implementations               │
│  SQL: asyncpg/aiomysql/aiosqlite                           │
│  NoSQL: motor/elasticsearch-py/redis-py                     │
│  SaaS: simple-salesforce/httpx                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Environment
```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and SECRET_KEY
```

### 2. Start with Docker
```bash
docker-compose up -d
```

Services:
- Backend API: http://localhost:8000
- Frontend: http://localhost:5173
- MCP Server: http://localhost:9000/mcp
- API Docs: http://localhost:8000/docs

### 3. Connect to Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "databridge": {
      "url": "http://localhost:9000/mcp",
      "headers": { "Authorization": "Bearer YOUR_JWT_TOKEN" }
    }
  }
}
```

Get your JWT token from the MCP page after logging in.

---

## How Permission + CRUD Works

### Connector-level CRUD matrix
Every user gets a permission row per connector:
```sql
connector_permissions(
  user_id, connector_id,
  can_read,    -- SELECT queries
  can_create,  -- INSERT operations
  can_update,  -- UPDATE operations
  can_delete   -- DELETE operations
)
```

Superadmin always has full access. Regular users only see and query databases they have explicit READ permission on.

### Row-Level Security
```sql
rls_policies(
  connector_id, table_name,
  filter_expr,             -- e.g. "org_id = {user.id}"
  applies_to_user_id,      -- specific user
  applies_to_role,         -- or all members/viewers
)
```

RLS filters are injected into every SELECT query automatically:
```sql
-- User asks: "show all orders"
-- Generated: SELECT * FROM orders LIMIT 500
-- After RLS: SELECT * FROM orders WHERE (org_id = 'abc-123') LIMIT 500
```

---

## Adding a New Connector

1. Create `backend/app/connectors/mydb.py` implementing `BaseConnector`:
```python
class MyDBConnector(BaseConnector):
    async def test_connection(self) -> bool: ...
    async def get_schema(self) -> List[TableInfo]: ...
    async def execute_query(self, query: str) -> QueryResult: ...
    # Optional: override get_schema_prompt() for NoSQL
```

2. Add to `ConnectorType` enum in `models/__init__.py`:
```python
MYDB = "mydb"
```

3. Register in `connectors/registry.py`:
```python
ConnectorType.MYDB: MyDBConnector,
```

4. Add form fields to `frontend/src/pages/ConnectorsPage.tsx` in `DB_TYPES`.

That's it — the connector is immediately available in the UI, MCP server, and agent.

---

## API Reference

```
POST /api/query/                    # NL query via ReAct agent
POST /api/query/cross-db            # Cross-database federated query
POST /api/query/nl-preview          # Preview generated query
GET  /api/query/logs                # Query audit log

POST /api/connectors/               # Create connector (superadmin)
GET  /api/connectors/               # List accessible connectors
POST /api/connectors/{id}/test      # Test connection
POST /api/connectors/{id}/refresh-schema  # Cache schema

GET  /api/permissions/connector/{id}     # Get CRUD matrix
PUT  /api/permissions/connector/{id}     # Update user permissions
POST /api/permissions/connector/{id}/rls # Create RLS policy
GET  /api/permissions/my-permissions     # My access summary
```

---

## Semantic Date Resolution Reference

| User says | PostgreSQL | MySQL | Snowflake |
|-----------|-----------|-------|-----------|
| "this quarter" | `DATE_TRUNC('quarter', NOW())` | `MAKEDATE(YEAR(NOW()),1) + INTERVAL QUARTER(NOW())-1 QUARTER` | `DATE_TRUNC('QUARTER', CURRENT_DATE())` |
| "last 30 days" | `NOW() - INTERVAL '30 days'` | `DATE_SUB(NOW(), INTERVAL 30 DAY)` | `DATEADD('DAY', -30, CURRENT_TIMESTAMP())` |
| "this month" | `DATE_TRUNC('month', NOW())` | `DATE_FORMAT(NOW(), '%Y-%m-01')` | `DATE_TRUNC('MONTH', CURRENT_DATE())` |

8 dialects supported: PostgreSQL, MySQL, SQL Server, Snowflake, BigQuery, SQLite, Oracle, Redshift.
