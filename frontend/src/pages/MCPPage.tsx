import { useState } from 'react'
import { useAuthStore } from '../store/auth'
import {
  Copy, Check, Shield, Zap, Globe, Database,
  Edit, Trash2, Plus, Search, Server, BookOpen,
  HardDrive, Layers
} from 'lucide-react'

const MCP_TOOLS = [
  {
    name: 'get_relevant_schema',
    category: 'Discovery',
    icon: Search,
    description: 'CALL THIS FIRST for every query. Uses fast token-based scoring (< 5ms) to pick only the databases and tables relevant to the user\'s question, with atlas tribal knowledge merged in.',
    permission: 'READ',
    color: 'blue',
  },
  {
    name: 'list_available_databases',
    category: 'Discovery',
    icon: Database,
    description: 'Lists all database connectors the user has READ access to. Returns IDs, names, types, query format hints, and schema cache status.',
    permission: 'READ',
    color: 'blue',
  },
  {
    name: 'get_global_schema_awareness',
    category: 'Discovery',
    icon: Globe,
    description: 'High-level overview of all databases grouped by schema/table. Use to discover where specific data lives without fetching every full schema.',
    permission: 'READ',
    color: 'blue',
  },
  {
    name: 'get_database_schema',
    category: 'Discovery',
    icon: Layers,
    description: 'Enriched schema with semantic type annotations and Atlas-enriched tribal knowledge. Optionally filter by schema_name or table_names.',
    permission: 'READ',
    color: 'blue',
  },
  {
    name: 'execute_query',
    category: 'Query',
    icon: Server,
    description: 'Execute raw SQL/NoSQL query. Supports SQL, MongoDB aggregation pipelines, Elasticsearch DSL, Redis commands, and SOQL.',
    permission: 'READ',
    color: 'green',
  },
  {
    name: 'execute_federated_query',
    category: 'Query',
    icon: Globe,
    description: 'Execute per-database extraction queries in parallel and join them using DuckDB. Supply the execution plan - no internal LLM involved.',
    permission: 'READ',
    color: 'purple',
    badge: 'Cross-DB',
  },
  {
    name: 'create_record',
    category: 'Write',
    icon: Plus,
    description: 'INSERT a new record into any table or collection. Works across SQL, MongoDB, Elasticsearch, Salesforce, and Redis.',
    permission: 'CREATE',
    color: 'green',
  },
  {
    name: 'update_record',
    category: 'Write',
    icon: Edit,
    description: 'UPDATE a record by ID. Specify id_field for the identifier column and pass updates as key-value pairs.',
    permission: 'UPDATE',
    color: 'orange',
  },
  {
    name: 'delete_record',
    category: 'Write',
    icon: Trash2,
    description: 'DELETE a record by ID. Irreversible operation - always confirm with user before calling.',
    permission: 'DELETE',
    color: 'red',
  },
  {
    name: 'record_discovery',
    category: 'Metadata',
    icon: BookOpen,
    description: 'Permanently record semantic discoveries (data gaps, gotchas, recommended aggregations) about a table into the catalog atlas.',
    permission: 'READ',
    color: 'teal',
  },
  {
    name: 'mirror_database_table',
    category: 'Metadata',
    icon: HardDrive,
    description: 'Mirror a full table into the persistent DuckDB instance for lightning-fast federation queries against core reference data.',
    permission: 'READ',
    color: 'teal',
  },
]

const PERMISSION_COLORS: Record<string, string> = {
  READ: 'bg-accent-50 text-accent-700 border border-accent-100',
  CREATE: 'bg-success-bg text-success border border-success-border',
  UPDATE: 'bg-warning-bg text-warning border border-warning-border',
  DELETE: 'bg-error-bg text-error border border-error-border',
}

const CATEGORY_ORDER = ['Discovery', 'Query', 'Write', 'Metadata']

export function MCPPage() {
  const token = useAuthStore(s => s.token)
  const [copied, setCopied] = useState('')

  const mcpUrl = `${window.location.protocol}//${window.location.hostname}:9000/mcp`

  const copy = (text: string, key: string) => {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text)
    } else {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      textArea.style.top = "-999999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        document.execCommand('copy');
      } catch (err) {
        console.error('Fallback: Oops, unable to copy', err);
      }
      document.body.removeChild(textArea);
    }
    setCopied(key)
    setTimeout(() => setCopied(''), 2000)
  }

  const claudeConfig = JSON.stringify({
    mcpServers: {
      "databridge": {
        command: "cmd",
        args: [
          "/c",
          "npx",
          "mcp-remote",
          "http://localhost:9000/mcp",
          "--allow-http",
          "--header",
          `Authorization:Bearer ${token || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhY2FiYTAzOS0xMmQxLTQyNDktYTJhMS0yZGZlZDYyMGE1ZmEiLCJleHAiOjE3ODA5OTgxNDN9.FbuTua2qrbfEeood58tLVyYaHmMTC7rf0XE-hypE8EA'}`
        ]
      }
    }
  }, null, 2)

  const cursorConfig = JSON.stringify({
    mcpServers: {
      "databridge": {
        command: "npx",
        args: [
          "mcp-remote",
          "http://localhost:9000/mcp",
          "--allow-http",
          "--header",
          `Authorization:Bearer ${token || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhYzAyZDQzMi01ZThiLTRjZTMtOGI0Ny1hMmRmYWQ4YTVhYzQiLCJ0b2tlbl92ZXJzaW9uIjoxLCJleHAiOjE3ODE1ODA5MjF9.PkVCWbWGCW-lvD9zyae3XmdBeS0gpm4eg8w2Fu03n58'}`
        ]
      }
    }
  }, null, 2)

  const grouped = CATEGORY_ORDER.map(cat => ({
    category: cat,
    tools: MCP_TOOLS.filter(t => t.category === cat),
  }))

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="headline-lg mb-1 flex items-center gap-2 text-on-surface">
          <Server className="w-6 h-6 text-on-surface-variant" />
          MCP Server Configuration
        </h1>
        <p className="text-sm text-text-muted">
          Connect Claude Desktop, Cursor, Gemini CLI, or any MCP-compatible AI agent directly to DataBridge
        </p>
      </div>

      {/* Server Status */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-success animate-pulse" />
          <span className="text-sm font-semibold text-on-surface">MCP Server Active</span>
          <span className="text-xs text-text-muted ml-auto font-mono">Streamable HTTP Transport</span>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 bg-surface-container-low border border-border-default rounded-lg px-4 py-3 font-mono text-sm text-on-surface select-all break-all flex items-center">
            {mcpUrl}
          </div>
          <button
            onClick={() => copy(mcpUrl, 'url')}
            className="flex items-center justify-center gap-2 text-sm px-4 py-3 border border-border-default rounded hover:bg-surface-container-low text-on-surface font-semibold transition-colors bg-white flex-shrink-0"
          >
            {copied === 'url' ? <Check className="w-4 h-4 text-success" /> : <Copy className="w-4 h-4 text-text-muted" />}
            {copied === 'url' ? 'Copied!' : 'Copy Server URL'}
          </button>
        </div>
      </div>

      {/* Tools */}
      <div className="card overflow-hidden">
        <div className="px-6 py-5 border-b border-border-default flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface-container-lowest">
          <div>
            <h2 className="text-base font-bold text-on-surface">{MCP_TOOLS.length} Available Tools</h2>
            <p className="text-xs text-text-muted mt-0.5">Permission-enforced • Row-Level Security • Cross-DB federation via DuckDB</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {CATEGORY_ORDER.map(cat => (
              <span key={cat} className="text-[11px] px-2.5 py-1 rounded bg-surface-container text-on-surface-variant font-medium border border-border-default uppercase tracking-wider font-mono">
                {cat} ({MCP_TOOLS.filter(t => t.category === cat).length})
              </span>
            ))}
          </div>
        </div>
        <div className="divide-y divide-border-default">
          {grouped.map(({ category, tools }) => (
            <div key={category}>
              <div className="px-6 py-2 bg-surface-container-low border-b border-border-default">
                <span className="text-[10px] font-bold text-text-muted uppercase tracking-widest font-mono">{category}</span>
              </div>
              <div className="divide-y divide-border-muted">
                {tools.map(tool => {
                  const Icon = tool.icon
                  const colorMap: Record<string, string> = {
                    blue: 'bg-accent-50 text-accent-700 border border-accent-100',
                    green: 'bg-success-bg text-success border border-success-border',
                    amber: 'bg-warning-bg text-warning border border-warning-border',
                    purple: 'bg-accent-100 text-accent-900 border border-accent-200',
                    orange: 'bg-warning-bg text-warning border border-warning-border',
                    red: 'bg-error-bg text-error border border-error-border',
                    teal: 'bg-accent-50 text-accent-600 border border-accent-100',
                  }
                  return (
                    <div key={tool.name} className="flex items-start gap-4 px-6 py-5 hover:bg-surface-container-low/40 transition-colors">
                      <div className={`w-9 h-9 rounded flex items-center justify-center flex-shrink-0 ${colorMap[tool.color]}`}>
                        <Icon className="w-4.5 h-4.5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <code className="text-sm font-mono font-bold text-on-surface">{tool.name}</code>
                          <span className={`text-[10px] px-2.5 py-0.5 rounded font-bold tracking-wider font-mono uppercase ${PERMISSION_COLORS[tool.permission]}`}>
                            {tool.permission}
                          </span>
                          {tool.badge && (
                            <span className="text-[10px] px-2.5 py-0.5 rounded bg-accent-100 text-accent-700 border border-accent-200 font-bold tracking-wider font-mono uppercase">
                              {tool.badge}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-text-secondary mt-1.5 leading-relaxed">{tool.description}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Auth Token */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-on-surface-variant" />
          <h2 className="text-base font-bold text-on-surface">Your Authentication JWT Token</h2>
        </div>
        <p className="text-xs text-text-muted">
          Include this token in your MCP headers. Database CRUD permissions and row-level security constraints will be automatically enforced matching your active workspace role.
        </p>
        <div className="relative">
          <div className="bg-[#1A1916] border border-outline/30 rounded-lg px-4 py-4.5 font-mono text-xs text-[#efeeea] break-all pr-14 max-h-36 overflow-y-auto leading-relaxed shadow-inner select-all">
            {token || 'Not logged in'}
          </div>
          <button
            onClick={() => copy(token || '', 'token')}
            className="absolute right-3 top-3 text-text-muted hover:text-white p-2 bg-surface-container-highest/10 hover:bg-surface-container-highest/20 rounded border border-outline/20 transition-all"
            title="Copy Auth Token"
          >
            {copied === 'token' ? <Check className="w-4 h-4 text-success" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Client Configs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[
          { key: 'claude', label: 'Claude Desktop Config', config: claudeConfig, path: 'claude_desktop_config.json' },
          { key: 'cursor', label: 'Cursor / VS Code Config', config: cursorConfig, path: '.cursor/mcp.json' },
        ].map(({ key, label, config, path }) => (
          <div key={key} className="card p-6 flex flex-col justify-between space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-sm font-bold text-on-surface">{label}</h2>
                <p className="text-[11px] text-text-muted mt-1">
                  Add to <code className="bg-surface-container-low px-1.5 py-0.5 rounded border border-border-default font-mono text-[10px]">{path}</code>
                </p>
              </div>
              <button
                onClick={() => copy(config, key)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 border border-border-default rounded hover:bg-surface-container-low text-on-surface font-semibold bg-white transition-colors flex-shrink-0"
              >
                {copied === key ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5 text-text-muted" />}
                {copied === key ? 'Copied!' : 'Copy JSON'}
              </button>
            </div>
            <pre className="bg-[#1A1916] border border-outline/30 text-[#efeeea] text-xs rounded-lg p-4 overflow-x-auto font-mono leading-relaxed max-h-56 overflow-y-auto shadow-inner">
              {config}
            </pre>
          </div>
        ))}
      </div>

      {/* Supported DBs */}
      <div className="bg-surface-container-low border border-border-default rounded-card p-6">
        <h3 className="text-sm font-bold text-on-surface mb-3.5 uppercase tracking-wider font-mono">14 Supported Database Types</h3>
        <div className="flex flex-wrap gap-2">
          {[
            'PostgreSQL', 'MySQL', 'SQLite', 'SQL Server', 'Oracle',
            'Snowflake', 'Redshift', 'BigQuery', 'MongoDB',
            'Elasticsearch', 'Redis', 'Salesforce', 'REST API', 'Airtable'
          ].map(db => (
            <span key={db} className="text-xs bg-white border border-border-default rounded px-3 py-2 text-on-surface font-medium hover:bg-surface-container-low transition-colors shadow-sm">
              {db}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
