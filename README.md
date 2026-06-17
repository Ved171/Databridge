# 📊 DataBridge — Enterprise Multi-DB Natural Language Query & Governance Platform

DataBridge is an enterprise-grade, permission-aware data gateway (serving as a local, secure alternative to **CData Connect AI**). It enables AI agents to query, join, and update data across heterogeneous databases using natural language. The system shifts intelligence directly to the client's AI agent by exposing a high-performance **FastMCP Server** integrated with Row-Level Security (RLS), smart schema compression, and persistent DuckDB-driven cross-database federation.

---

## 🌟 Architecture Overview

```
                          ┌──────────────────────────────┐
                          │    AI Client / Agent         │
                          │   (Cursor, Claude Desktop)   │
                          └──────────────┬───────────────┘
                                         │ MCP Protocol (JSON-RPC + JWT Bearer)
                          ┌──────────────▼───────────────┐
                          │   FastMCP Server (Port 9000) │
                          └──────────────┬───────────────┘
                                         │ Internal API Auth check
             ┌───────────────────────────┼───────────────────────────┐
             │                           │                           │
 ┌───────────▼───────────┐   ┌───────────▼───────────┐   ┌───────────▼───────────┐
 │  FastAPI Admin / Web  │   │  Permission & Policy  │   │   Semantic Schema     │
 │    App (Port 8000)    │   │  Enforcement Engine   │   │  Resolver & Compressor│
 └───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘
             │                           │                           │
 ┌───────────▼───────────┐               │               ┌───────────▼───────────┐
 │ PostgreSQL Metadata  │◄──────────────┘               │  Atlas Tribal Schema  │
 │  (RBAC, Depts, RLS)   │                               │  (backend/app/atlas/) │
 └───────────────────────┘                               └───────────────────────┘
                                         │ SQL/NoSQL/SaaS Queries
                          ┌──────────────▼───────────────┐
                          │   Driver Abstraction Layer   │
                          │     (11 Database Types)      │
                          └──────────────┬───────────────┘
                                         │ Raw Result Sets
                          ┌──────────────▼───────────────┐
                          │ DuckDB Parallel Federation   │
                          └──────────────────────────────┘
```

In DataBridge, the legacy backend chat endpoints (`/chat` and `/chat/stream`) have been **deprecated and removed**. Client AI agents connect directly to the FastMCP server. The agent orchestrates schema discovery, query planning, and CRUD operations natively through client-side tools.

---

## 📁 Codebase Directory Structure

```
databridge-main/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (auth, users, connectors, permissions, rls, packages, roles, depts, dashboard)
│   │   ├── atlas/          # Rich JSON files representing semantic schemas and tribal knowledge metadata
│   │   ├── connectors/     # BaseConnector and 11 dialect-specific connection drivers (Postgres, MongoDB, Redis, etc.)
│   │   ├── core/           # Configuration, DB sessions, dependencies, security algorithms, and access packages
│   │   ├── models/         # SQLAlchemy schemas (User, Department, Role, Connector, RLSPolicy, AccessPackage, AuditEvent, etc.)
│   │   ├── schemas/        # Pydantic schemas for request validation and serialization
│   │   ├── services/       # Core services (Atlas builder, schema cache, token scoring search)
│   │   ├── tools/          # MCP tools definition (mcp_tools.py), DuckDB engine, and RLS query rewrites
│   │   ├── main.py         # Entry point for the FastAPI application (Port 8000)
│   │   └── mcp.py          # Entry point for the FastMCP Server (Port 9000)
│   ├── scripts/            # Database initialization, admin bootstrapping, role migrations, and atlas builder utilities
│   ├── alembic/            # SQLAlchemy database migration environment
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/     # Layouts, MultiSelect, SearchableTableSelectors
│   │   ├── pages/          # Admin UI tabs (MCP settings, Permissions Matrix, Access Packages, RLS manager, Org Trees, etc.)
│   │   ├── store/          # Frontend state management (Zustand)
│   │   └── main.tsx        # React entry point
│   ├── tailwind.config.js  # Styling guidelines
│   └── package.json        # Frontend dependencies
├── sync_schema.py          # Centralized compiler for compiling database schemas, minification, and FK resolutions
└── docker-compose.yml      # Multi-container orchestration (PostgreSQL, Redis, Backend, Frontend, MCP)
```

---

## 🔒 Enterprise Security & Access Control

DataBridge implements a sophisticated, multi-tier security model designed to satisfy strict compliance requirements:

### 1. Hierarchical Access Management
* **Department Trees**: Users are structured in parent-child department hierarchies. Department deletions are protected by member propagation checks.
* **Dynamic Role Hierarchies**: Roles are structured in a tree with privilege levels recalculated dynamically bottom-up (leaf roles start at level 1; parent roles increment based on child role ranks).
* **Manager-Member Chains**: Assign direct reporting structures with cycle detection to prevent circular references, and enforcement guards to prevent manager demotions by users of equal or lower rank.

### 2. Granular Permissions Matrix
Access is evaluated at both the **Connector** and **Table** levels:
* **Connector-Level Permissions**: Grants or restricts CRUD operations (`can_create`, `can_read`, `can_update`, `can_delete`) per user, department, or role on a specific connector database.
* **Table-Level Permissions**: If table rules are defined on a connector, it defaults to a *deny-by-default* policy where users can only query explicitly whitelisted tables.

### 3. Dynamic Row-Level Security (RLS)
The gateway intercepts outgoing queries to inject security filters dynamically before they reach the database:
* **SQL Connectors**: Appends custom WHERE clause fragments (e.g., `org_id = '{user.id}'`).
* **NoSQL Connectors**: Injects structured JSON filters into MongoDB queries or Redis key pattern lookups.
* Supports contextual placeholders: `{user.id}`, `{user.email}`, `{user.name}`, and `{user.employee_code}`.

### 4. Time-Bound Access Packages
Access Packages allow administrators to bundle connector permissions, table permissions, and RLS filters into reusable packages.
* **Targeting**: Assignable to specific Roles, Departments, or combined Scoped Department + Role targets.
* **Lifespan Constraints**: Controlled by `valid_from` (start date), `expires_at` (expiration date), and manual `revoked_at` flags.

---

## 🔌 11 Supported Database Connectors

DataBridge integrates with 11 relational, NoSQL, and SaaS backends:

| Category | Database Type | Python Driver / Library |
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

## 🛠️ FastMCP Server Interface (Port 9000)

The FastMCP server accepts JSON-RPC requests authorized via JWT tokens passed in the `Authorization: Bearer <token>` header. It registers 11 tools and 2 resources:

### Registered Tools

#### Discovery Category
* **`get_relevant_schema(question)`** ★ **(CALL THIS FIRST)**: Compares the user's natural language question against cached metadata using token-based similarity search (<5ms latency). It returns only the schemas and tables required for the query, complete with merged gotchas and filters. Columns are minified to `Name:type` for context-window token efficiency.
* **`get_database_schema(db_id, schema_name, table_names)`**: Retrieves column-level detail and constraint rules for specific tables.
* **`get_global_schema_awareness()`**: Lists all databases, schemas, and tables to provide a high-level overview of where data resides.
* **`list_available_databases()`**: Returns all connectors the authorized user has read permissions for.

#### Query Category
* **`execute_query(db_id, query)`**: Runs a raw query against a single database (SQL query, MongoDB pipeline, ES query DSL, Redis commands, or SOQL). Enforces CRUD permissions and RLS filters.
* **`execute_federated_query(queries, federation_sql)`**: Executes extraction queries across multiple databases in parallel, then joins the result sets locally using DuckDB SQL.

#### Write Category
* **`create_record(db_id, table_or_collection, data)`**: Inserts a new record.
* **`update_record(db_id, table_or_collection, record_id, id_field, updates)`**: Updates an existing record.
* **`delete_record(db_id, table_or_collection, record_id, id_field)`**: Deletes a record. *(Requires explicit user confirmation before executing)*.

#### Metadata / Performance Category
* **`record_discovery(table_name, summary, gotcha, aggregation, learned_filter)`**: Autonomous tool for LLMs to save discovered tribal knowledge (data quirks, soft-delete behaviors, nullability gotchas) directly to the atlas.
* **`mirror_database_table(db_id, table_name)`**: Fetches a static reference table from a database and mirrors it into the persistent local DuckDB instance, enabling instant federated joins without querying the source again.

### Registered Resources
* **`schema://databridge/atlas`**: A catalog list of all connector atlases and update timestamps.
* **`schema://databridge/atlas/{connector_id}`**: Retrieves the detailed semantic atlas for a single connector.

---

## ⚙️ Schema Compilation & Minification

The database schemas utilized by LLM agents are optimized using `sync_schema.py`:
```bash
python sync_schema.py [--verify] [--input-dir DIR]
```
### Compiler Workflow:
1. **Raw Parser**: Parses schema text files and groups tables by schema.
2. **Boilerplate Stripper**: Shrinks schema context by **65% to 75%** by stripping boilerplate/audit columns (such as `CreatedBy`, `UpdatedDate`, `ConcurrencyKey`) and compacting types.
3. **Physical Constraints Mapper**: Maps foreign key relationships extracted directly from database engines (`sys.foreign_keys` for MSSQL and `pg_constraint` for Postgres) using the `physical_fks.json` mapping.
4. **Tribal Knowledge Binder**: Resolves cross-database relationships using only verified gotchas starting with `"Verified cross-db relationship: Joins with..."` written by AI agents via `record_discovery`.
5. **Output Generation**: Outputs:
   - `databridge_schema_summary.json`: Detailed master schema with physical FK constraints.
   - `databridge_schema_summary_min.json`: Token-optimized JSON for direct LLM injection.
   - `databridge_schema_summary.md`: Human-readable Markdown database catalog.

---

## 📅 Dialect-Specific Date Translation

DataBridge translates natural language date filters into dialect-appropriate syntax across 8 dialects (PostgreSQL, MySQL, SQL Server, Snowflake, BigQuery, SQLite, Oracle, Redshift).

* **"this quarter"**
  - PostgreSQL: `DATE_TRUNC('quarter', NOW())`
  - SQL Server: `DATEADD(q, DATEDIFF(q, 0, GETDATE()), 0)`
  - Snowflake: `DATE_TRUNC('QUARTER', CURRENT_DATE())`
* **"last 30 days"**
  - PostgreSQL: `NOW() - INTERVAL '30 days'`
  - MySQL: `DATE_SUB(NOW(), INTERVAL 30 DAY)`
  - SQL Server: `DATEADD(day, -30, GETDATE())`

---

## 🚀 Getting Started

### 1. Configure the Environment
Create a `.env` file in the root directory:
```bash
cp .env.example .env
```
Ensure you configure the following variables:
* `SECRET_KEY`: Long secret key for signing JWT authorization tokens.
* `ENCRYPTION_KEY`: 32-character key for AES encryption of connector credentials.
* `DATABASE_URL`: Connection string for DataBridge internal metadata store.
* `REDIS_URL`: Connection string for background caching.
* `LLM_PROVIDER`: Specify `anthropic`, `openai`, or `litellm`.
* `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`: API keys for the respective model.

### 2. Start Services via Docker Compose
Run the multi-container configuration in the background:
```bash
docker-compose up -d --build
```
This launches:
* **Admin Web UI**: `http://localhost:5173`
* **FastAPI Backend**: `http://localhost:8000` (FastAPI docs at `/docs`)
* **FastMCP Server**: `http://localhost:9000`
* **PostgreSQL & Redis** infrastructure.

### 3. Bootstrap & Seeding (First-time setup)
If running manually, or to configure the database for development:
```bash
# Apply migrations to database
cd backend
alembic upgrade head

# Seed roles and bootstrap Superadmin user
export SUPERADMIN_EMAIL="admin@databridge.com"
export SUPERADMIN_PASSWORD="superadmin-secure-password"
python scripts/bootstrap_superadmin.py

# Enforce role levels and seed metadata
python scripts/migrate_role_id.py

# Auto-generate semantic schemas and atlas templates
python scripts/create_atlases.py
python scripts/build_atlas.py
```

### 4. Connect a Client AI Agent (e.g. Claude Desktop)
Add the DataBridge FastMCP server details to your local `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "databridge": {
      "command": "python",
      "args": ["-m", "app.mcp"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://databridge:databridge_secret@localhost:5431/databridge",
        "REDIS_URL": "redis://localhost:6379",
        "SECRET_KEY": "your-jwt-signing-secret-key",
        "ENCRYPTION_KEY": "your-aes-encryption-key-32-chars"
      }
    }
  }
}
```
Alternatively, if querying using SSE (Server-Sent Events) HTTP transport:
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
*(Copy your personal JWT token from the **MCP Settings** page in the DataBridge Web UI).*
