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
  READ:   'bg-blue-100 text-blue-700',
  CREATE: 'bg-green-100 text-green-700',
  UPDATE: 'bg-orange-100 text-orange-700',
  DELETE: 'bg-red-100 text-red-700',
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
      databridge: {
        url: mcpUrl,
        headers: { Authorization: `Bearer ${token || 'YOUR_JWT_TOKEN'}` },
      },
    },
  }, null, 2)

  const cursorConfig = JSON.stringify({
    mcpServers: {
      "databridge-remote": {
        command: "npx",
        args: [
          "mcp-remote",
          mcpUrl,
          "--allow-http",
          "--header",
          `Authorization:Bearer ${token || 'YOUR_JWT_TOKEN'}`
        ]
      },
    },
  }, null, 2)

  const grouped = CATEGORY_ORDER.map(cat => ({
    category: cat,
    tools: MCP_TOOLS.filter(t => t.category === cat),
  }))

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">MCP Server</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Connect Claude, Cursor, Gemini CLI, or any MCP-compatible AI agent to DataBridge
        </p>
      </div>

      {/* Server Status */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-sm font-semibold text-gray-800">MCP Server Active</span>
          <span className="text-xs text-gray-400 ml-auto">Streamable HTTP Transport</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1 bg-gray-900 rounded-lg px-4 py-2.5 font-mono text-sm text-green-400">
            {mcpUrl}
          </div>
          <button
            onClick={() => copy(mcpUrl, 'url')}
            className="flex items-center gap-1.5 text-sm px-3 py-2.5 border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 transition-colors"
          >
            {copied === 'url' ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
            {copied === 'url' ? 'Copied!' : 'Copy'}
          </button>
        </div>
      </div>

      {/* Tools */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">{MCP_TOOLS.length} Available Tools</h2>
            <p className="text-xs text-gray-500 mt-0.5">Permission-enforced - RLS injection - Cross-DB federation via DuckDB</p>
          </div>
          <div className="flex items-center gap-2">
            {CATEGORY_ORDER.map(cat => (
              <span key={cat} className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600 font-medium">
                {cat} ({MCP_TOOLS.filter(t => t.category === cat).length})
              </span>
            ))}
          </div>
        </div>
        <div className="divide-y divide-gray-50">
          {grouped.map(({ category, tools }) => (
            <div key={category}>
              <div className="px-5 py-2 bg-gray-50">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{category}</span>
              </div>
              {tools.map(tool => {
                const Icon = tool.icon
                const colorMap: Record<string, string> = {
                  blue: 'bg-blue-50 text-blue-600', green: 'bg-green-50 text-green-600',
                  amber: 'bg-amber-50 text-amber-600', purple: 'bg-purple-50 text-purple-600',
                  orange: 'bg-orange-50 text-orange-600', red: 'bg-red-50 text-red-600',
                  teal: 'bg-teal-50 text-teal-600',
                }
                return (
                  <div key={tool.name} className="flex items-start gap-4 px-5 py-4 hover:bg-gray-50/50 transition-colors">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${colorMap[tool.color]}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="text-sm font-mono font-semibold text-gray-900">{tool.name}</code>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PERMISSION_COLORS[tool.permission]}`}>
                          {tool.permission}
                        </span>
                        {tool.badge && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">
                            {tool.badge}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-1 leading-relaxed">{tool.description}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Auth Token */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="w-4 h-4 text-gray-500" />
          <h2 className="text-sm font-semibold text-gray-800">Your JWT Token</h2>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          Include this in the Authorization header. CRUD permissions are automatically enforced per your access level.
        </p>
        <div className="relative">
          <div className="bg-gray-900 rounded-lg px-4 py-3 font-mono text-xs text-green-400 break-all pr-12 max-h-24 overflow-hidden">
            {token || 'Not logged in'}
          </div>
          <button
            onClick={() => copy(token || '', 'token')}
            className="absolute right-2 top-2 text-gray-400 hover:text-gray-200 p-1.5 bg-gray-800 rounded"
          >
            {copied === 'token' ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Client Configs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[
          { key: 'claude', label: 'Claude Desktop', config: claudeConfig, path: 'claude_desktop_config.json' },
          { key: 'cursor', label: 'Cursor / VS Code / Gemini CLI', config: cursorConfig, path: '.cursor/mcp.json' },
        ].map(({ key, label, config, path }) => (
          <div key={key} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-800">{label}</h2>
              <button
                onClick={() => copy(config, key)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 transition-colors"
              >
                {copied === key ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                {copied === key ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <p className="text-xs text-gray-400 mb-2">Add to <code className="bg-gray-100 px-1 py-0.5 rounded">{path}</code></p>
            <pre className="bg-gray-900 text-green-400 text-xs rounded-lg p-3 overflow-x-auto font-mono leading-relaxed max-h-48 overflow-y-auto">
              {config}
            </pre>
          </div>
        ))}
      </div>

      {/* Supported DBs */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">14 Supported Database Types</h3>
        <div className="flex flex-wrap gap-2">
          {[
            'PostgreSQL', 'MySQL', 'SQLite', 'SQL Server', 'Oracle',
            'Snowflake', 'Redshift', 'BigQuery', 'MongoDB',
            'Elasticsearch', 'Redis', 'Salesforce', 'REST API', 'Airtable'
          ].map(db => (
            <span key={db} className="text-xs bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-700">
              {db}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
