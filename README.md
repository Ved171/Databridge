# DataBridge v2 — Multi-DB NL Query Platform

DataBridge v2 is a next-generation, permission-based data accessibility platform. It acts as an enterprise-grade CData Connect AI-equivalent, enabling secure natural language queries, full CRUD operations, and cross-database federation across **11 database connector types**. 

With v2, intelligence is shifted directly to the AI agent via a centralized **FastMCP Server** (running on port 9000) that exposes **11 custom tools** and **2 resources**, complete with row-level security (RLS), smart schema pre-resolution, and tribal knowledge capture.

---

## Key Upgrades in v2

### 1. Client-Centric FastMCP Architecture
To maximize agent flexibility and reduce overhead, the backend intelligence (the local agent service `/chat` and `/chat/stream` endpoints) has been **deprecated and removed**. AI agents (such as Claude Desktop, Cursor, VS Code, or Gemini CLI) connect directly to the DataBridge FastMCP server, allowing the agent to orchestrate query generation, cross-database joins, and CRUD operations using native tools.

### 2. Semantic Accuracy Layer (CData-grade 98%+)
* **Blazing-Fast Token-Based Search**: Replaced slow external embedding API calls (which added ~500ms latency) with an inline token-based scoring and filtering mechanism (<5ms latency).
* **Smart Minification (Token Savings)**: Shrinks column and table definition JSONs by **65% to 75%** before passing them to the LLM by stripping boilerplate audit columns and formatting fields as compact `Name:type` or `Name:type:PK` strings.
* **Atlas Tribal Knowledge Capture**: The system preserves status definitions, gotchas, recommended filters, and soft-delete patterns. These are automatically merged into schemas fetched by the LLM, preventing hallucination.
* **Strict Join Rules**: Forces AI agents to join cross-database employee records using `EmployeeCode` (stable, shared business key) rather than database-specific surrogate keys (`EmployeeId`, `Id`).

### 3. Parallel Cross-DB Federation via DuckDB
Uses a persistent, high-performance DuckDB instance to execute extraction queries across multiple databases in parallel, then joins the result sets locally using DuckDB SQL syntax. Stable reference tables can be mirrored directly into DuckDB for instant joins.

---

## Core Features

### 1. Hierarchical Organization & User Management
* **Department Tree Hierarchy:** Organizes users into parent-child departments with soft-delete protections and role propagation.
* **Dynamic Role Levels:** Roles are structured as a tree with levels recalculated dynamically bottom-up. Leaf roles start at level 1; parent roles increment based on children levels.
* **Manager-Member Reporting:** Assigns direct managers to team members, complete with loop detection to prevent circular references and permission boundaries to prevent demoting users of equal/higher rank.
* **Role Audit History:** Keeps an audit trail of user role modifications and promotions using a dedicated history table.

### 2. Multi-DB Semantic Gateway
* **11 Database Drivers:** Seamless integration with SQL (Postgres, MySQL, SQLite, MSSQL, Oracle), Cloud (Snowflake), NoSQL (MongoDB, Elasticsearch, Redis), and SaaS (Salesforce, HTTP REST API) connectors.
* **FastMCP Server Integration:** Shuns slow backend chat agents to serve tools and resources directly to client-side AI agents (Cursor, Claude Desktop, etc.) on port `9000`.
* **Zero-Cost Semantic Resolver:** Substitutes expensive vector database searches with ultra-fast token scoring (<5ms) to filter relevant metadata.
* **Context Token Compressor:** Shrinks database schemas by 65–75% to optimize context-window usage and reduce LLM token overhead.
* **Atlas Tribal Knowledge Ingestion:** Automatically injects gotchas, soft-delete states, status mappings, and documentation (stored in `backend/app/atlas/`) directly into schemas parsed by the LLM.

### 3. Enterprise Access Control & Security
* **Granular CRUD Permission Matrix:** Restricts connector actions (create, read, update, delete) individually per user and connector.
* **Dynamic Row-Level Security (RLS):** Modifies incoming queries and filter parameters on the fly to enforce tenant isolation (e.g., matching database records against logged-in user and department criteria).
* **Reference Protection Guards:** Prevents accidental deletion of system-critical roles or departments, and blocks deleting active roles referenced in active workspace permission tables.

### 4. Resilient Database Migrations
* **Idempotent Database Migrations:** Migration scripts automatically check table/column status before execution, supporting smooth database builds from scratch on both SQLite and PostgreSQL.
* **Superadmin Bootstrapping:** CLI commands to register system roles and seed the initial Superadmin user safely.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Agent / Claude / Cursor               │
└──────────────────────────┬──────────────────────────────────┘
                           │ MCP Protocol (JSON-RPC)
┌──────────────────────────▼──────────────────────────────────┐
│               FastMCP Server (port 9000)                    │
│  11 Tools: get_relevant_schema, execute_query, etc.         │
│  2 Resources: schema://databridge/atlas/...                 │
└──────────┬──────────────────────────────────────────────────┘
           │ JWT auth + CRUD permission check
┌──────────▼──────────────────────────────────────────────────┐
│              Permission & Auth Layer                        │
│  ConnectorPermission: can_read/create/update/delete         │
│  RLSPolicy: Row-level filters automatically injected        │
└──────────┬──────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│              Semantic Schema Resolver                       │
│  • Token-overlap relevance ranking (<5ms, zero API cost)     │
│  • Compresses schemas for LLM injection (saves 65-75% tokens)│
│  • Merges tribal knowledge (gotchas, status IDs) into schema │
└──────────┬──────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│           Driver Abstraction Layer                          │
│  BaseConnector interface → 11 registered implementations    │
│  SQL: Postgres, MySQL, SQLite, MSSQL, Oracle, Snowflake     │
│  NoSQL: MongoDB, Elasticsearch, Redis                       │
│  SaaS: Salesforce, REST API                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 11 Supported Database Connectors

DataBridge v2 includes built-in drivers for the following storage engines:

| Category | Database Type | Driver / Connection Library |
| :--- | :--- | :--- |
| **SQL** | PostgreSQL | `asyncpg` |
| | MySQL / MariaDB | `aiomysql` |
| | SQLite | `aiosqlite` |
| | SQL Server (MSSQL) | `aioodbc` |
| | Oracle | `oracledb` |
| **Cloud** | Snowflake | `snowflake-connector-python` |
| **NoSQL** | MongoDB | `motor` |
| | Elasticsearch | `elasticsearch` |
| | Redis | `redis` |
| **SaaS** | Salesforce | `simple-salesforce` |
| | REST API | `httpx` |

---

## MCP Server Interface

The FastMCP server runs on port **9000** and uses **JWT tokens** for authorization.

### 11 Registered Tools

| Category | Tool Name | Permission | Description |
| :--- | :--- | :--- | :--- |
| **Discovery** | `get_relevant_schema` ★ | READ | **CALL THIS FIRST.** Filters schemas down to tables/columns relevant to the natural language question. Merges atlas tribal knowledge. |
| | `get_database_schema` | READ | Drill down to detailed column type/annotations for specific tables. |
| | `get_global_schema_awareness` | READ | High-level outline of all databases grouped by schema/table (reads from atlas first). |
| | `list_available_databases` | READ | Lists connectors the user has read permissions for. |
| **Query** | `execute_query` | READ | Run queries on a single database (supports SQL dialects, MongoDB pipelines, Elasticsearch DSL, Redis, and SOQL). |
| | `execute_federated_query` | READ | Run queries in parallel across databases and join them using DuckDB federation SQL. |
| **Write** | `create_record` | CREATE | INSERT a record into any table or collection. |
| | `update_record` | UPDATE | UPDATE a record by ID. |
| | `delete_record` | DELETE | DELETE a record by ID (irreversible, requires explicit user confirmation). |
| **Metadata**| `record_discovery` | READ | Write semantic discoveries (data gaps, soft-deletes, aggregation rules) to the atlas. |
| | `mirror_database_table` | READ | Mirror a stable lookup table to DuckDB for ultra-fast federation. |

### 2 Registered Resources

* `schema://databridge/atlas`: Lists all available database connector atlases with last updated timestamps.
* `schema://databridge/atlas/{connector_id}`: Fetches the full detailed semantic atlas for a specific connector.

---

## Security: CRUD Matrix & Row-Level Security (RLS)

### 1. Connector-Level Permissions
Permissions are stored in the database per-user and per-connector:
```sql
connector_permissions(
  user_id, 
  connector_id,
  can_read,    -- Controls SELECT queries
  can_create,  -- Controls INSERTs
  can_update,  -- Controls UPDATEs
  can_delete   -- Controls DELETEs
)
```
Regular users can only view and interact with databases they have been granted explicit permissions for. Superadmins bypass all checks.

### 2. Row-Level Security (RLS) Injections
RLS policies define filter expressions (e.g. `org_id = {user.id}`) that are automatically appended to SQL WHERE clauses or NoSQL query objects.
```sql
-- User asks: "Select all customer accounts"
-- Raw generated query: SELECT * FROM accounts;
-- Executed query (with RLS): SELECT * FROM accounts WHERE org_id = 'usr-org-123';
```

---

## CLI Tools: Schema Sync & Optimization Compiler

The `sync_schema.py` script serves as the centralized compiler for compiling raw database schemas:
```bash
python sync_schema.py [--verify] [--input-dir DIR]
```
### What it does:
1. Parses raw schema text dumps and matches tables/views.
2. Integrates physical foreign key constraints from `physical_fks.json`.
3. Resolves cross-database relationship mapping using verified gotchas.
4. Outputs:
   * `databridge_schema_summary.json`: Detailed master schema with physical FK constraints.
   * `databridge_schema_summary_min.json`: Token-optimized minified JSON for direct LLM injection.
   * `databridge_schema_summary.md`: Human-readable Markdown database catalog.

---

## Dialect-Specific Semantic Date Resolution

The platform translates natural language date expressions (e.g. "this quarter", "last 30 days") into dialect-specific SQL snippets:

| Expression | PostgreSQL | MySQL | Snowflake | SQL Server |
| :--- | :--- | :--- | :--- | :--- |
| **"this quarter"** | `DATE_TRUNC('quarter', NOW())` | `MAKEDATE(YEAR(NOW()),1) + INTERVAL QUARTER(NOW())-1 QUARTER` | `DATE_TRUNC('QUARTER', CURRENT_DATE())` | `DATEADD(q, DATEDIFF(q, 0, GETDATE()), 0)` |
| **"last 30 days"** | `NOW() - INTERVAL '30 days'` | `DATE_SUB(NOW(), INTERVAL 30 DAY)` | `DATEADD('DAY', -30, CURRENT_TIMESTAMP())` | `DATEADD(day, -30, GETDATE())` |
| **"this month"** | `DATE_TRUNC('month', NOW())` | `DATE_FORMAT(NOW(), '%Y-%m-01')` | `DATE_TRUNC('MONTH', CURRENT_DATE())` | `DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0)` |

8 dialects are supported: PostgreSQL, MySQL, SQL Server, Snowflake, BigQuery, SQLite, Oracle, and Redshift.

---

## Running the Application

### 1. Configure the Environment
```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY and SECRET_KEY
```

### 2. Start Services with Docker
```bash
docker-compose up -d
```
* **Backend API**: `http://localhost:8000` (FastAPI docs at `/docs`)
* **Frontend UI**: `http://localhost:5173`
* **MCP Server**: `http://localhost:9000/mcp`

### 3. Connect a Client AI Agent (e.g. Claude Desktop)
Add the server configuration to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "databridge": {
      "url": "http://localhost:9000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_JWT_TOKEN"
      }
    }
  }
}
```
*(Copy your personal JWT token from the **MCP Server** tab in the DataBridge Web UI).*
