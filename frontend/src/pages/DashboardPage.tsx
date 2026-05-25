import { useQuery } from '@tanstack/react-query'
import { Database, MessageSquare, Shield, Zap, Clock, CheckCircle, AlertTriangle, ArrowRight, Server, Cloud, Globe, Search, Lock, HardDrive } from 'lucide-react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import { useAuthStore } from '../store/auth'

const DB_TYPE_ICONS: Record<string, React.ReactNode> = {
  postgres: <Database className="w-5 h-5 text-blue-500" />,
  mysql: <Database className="w-5 h-5 text-orange-500" />,
  mongodb: <Database className="w-5 h-5 text-green-500" />,
  snowflake: <Cloud className="w-5 h-5 text-sky-500" />,
  elasticsearch: <Search className="w-5 h-5 text-yellow-500" />,
  redis: <Zap className="w-5 h-5 text-red-500" />,
  sqlite: <HardDrive className="w-5 h-5 text-gray-500" />,
  mssql: <Server className="w-5 h-5 text-blue-600" />,
  oracle: <Database className="w-5 h-5 text-red-600" />,
  salesforce: <Cloud className="w-5 h-5 text-blue-400" />,
  rest_api: <Globe className="w-5 h-5 text-indigo-500" />,
  default: <Database className="w-5 h-5 text-gray-400" />,
}

export function DashboardPage() {
  const user = useAuthStore(s => s.user)

  const { data: connectors = [] } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  const { data: logs = [] } = useQuery({
    queryKey: ['query-logs'],
    queryFn: () => api.get('/api/query/logs?limit=10').then(r => r.data),
  })

  const { data: myPerms = [] } = useQuery({
    queryKey: ['my-permissions'],
    queryFn: () => api.get('/api/permissions/my-permissions').then(r => r.data),
  })

  const successLogs = logs.filter((l: any) => l.status === 'success')
  const errorLogs = logs.filter((l: any) => l.status === 'error')
  const cachedConnectors = connectors.filter((c: any) => c.schema_cached_at)
  const roleBadge = user?.role === 'super_admin' ? 'Super Admin' : user?.role === 'admin' ? 'Admin' : user?.role === 'workspace_admin' ? 'Workspace Admin' : 'Member'

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Welcome */}
      <div className="bg-gradient-to-br from-indigo-600 via-purple-600 to-indigo-700 rounded-2xl p-6 text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-semibold">Welcome back, {user?.name || 'User'}</h1>
            <span className="text-xs bg-white/20 rounded-full px-2.5 py-0.5 font-medium">{roleBadge}</span>
          </div>
          <p className="text-indigo-200 text-sm">
            DataBridge - AI-powered multi-database query platform
          </p>
          <div className="flex items-center gap-3 mt-4 flex-wrap">
            <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-2 text-sm">
              <Database className="w-4 h-4" />
              <span className="font-medium">{connectors.length}</span>
              <span className="text-indigo-200 text-xs">databases</span>
            </div>
            <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-2 text-sm">
              <CheckCircle className="w-4 h-4" />
              <span className="font-medium">{cachedConnectors.length}</span>
              <span className="text-indigo-200 text-xs">schemas cached</span>
            </div>
            {/* <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-2 text-sm">
              <MessageSquare className="w-4 h-4" />
              <span className="font-medium">{logs.length}</span>
              <span className="text-indigo-200 text-xs">recent queries</span>
            </div> */}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* <Link to="/query" className="group flex items-center gap-3 bg-white border border-gray-200 rounded-xl p-4 shadow-sm hover:border-indigo-300 hover:shadow-md transition-all">
          <div className="w-10 h-10 bg-indigo-50 rounded-lg flex items-center justify-center group-hover:bg-indigo-100 transition-colors">
            <MessageSquare className="w-5 h-5 text-indigo-600" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-900">Ask a Question</p>
            <p className="text-xs text-gray-400">Natural language query</p>
          </div>
          <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-indigo-500 transition-colors" />
        </Link> */}
        <Link to="/connectors" className="group flex items-center gap-3 bg-white border border-gray-200 rounded-xl p-4 shadow-sm hover:border-indigo-300 hover:shadow-md transition-all">
          <div className="w-10 h-10 bg-green-50 rounded-lg flex items-center justify-center group-hover:bg-green-100 transition-colors">
            <Database className="w-5 h-5 text-green-600" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-900">Manage Connectors</p>
            <p className="text-xs text-gray-400">{connectors.length} connected</p>
          </div>
          <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-green-500 transition-colors" />
        </Link>
        <Link to="/mcp" className="group flex items-center gap-3 bg-white border border-gray-200 rounded-xl p-4 shadow-sm hover:border-indigo-300 hover:shadow-md transition-all">
          <div className="w-10 h-10 bg-purple-50 rounded-lg flex items-center justify-center group-hover:bg-purple-100 transition-colors">
            <Zap className="w-5 h-5 text-purple-600" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-900">MCP Integration</p>
            <p className="text-xs text-gray-400">11 tools available</p>
          </div>
          <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-purple-500 transition-colors" />
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {/* Connected databases */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-800">Connected Databases</h2>
            <Link to="/connectors" className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">
              View all &rarr;
            </Link>
          </div>
          {connectors.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <Database className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No databases connected yet</p>
              <Link to="/connectors" className="text-xs text-indigo-600 hover:underline mt-1 inline-block">
                Add your first connector &rarr;
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-gray-50">
              {connectors.slice(0, 6).map((c: any) => (
                <div key={c.id} className="flex items-center gap-3 px-5 py-3 hover:bg-gray-50/50 transition-colors">
                  <span className="flex items-center justify-center w-8 h-8 rounded-md bg-gray-50 border border-gray-100">{DB_TYPE_ICONS[c.type] || DB_TYPE_ICONS.default}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{c.name}</p>
                    <p className="text-xs text-gray-400">{c.type}</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {c.schema_cached_at ? (
                      <span className="text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">Cached</span>
                    ) : (
                      <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full flex items-center gap-1">
                        <AlertTriangle className="w-2.5 h-2.5" /> No schema
                      </span>
                    )}
                    <span className={`w-2 h-2 rounded-full ${c.is_active ? 'bg-green-400' : 'bg-gray-300'}`} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent queries */}
        {/* <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-800">Recent Queries</h2>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-green-600">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400" /> {successLogs.length} ok
              </span>
              <span className="flex items-center gap-1 text-red-500">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400" /> {errorLogs.length} errors
              </span>
            </div>
          </div>
          {logs.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <MessageSquare className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No queries yet</p>
              <Link to="/query" className="text-xs text-indigo-600 hover:underline mt-1 inline-block">
                Try asking a question &rarr;
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-gray-50">
              {logs.slice(0, 6).map((log: any) => (
                <div key={log.id} className="px-5 py-3 hover:bg-gray-50/50 transition-colors">
                  <div className="flex items-start gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${log.status === 'success' ? 'bg-green-400' : 'bg-red-400'
                      }`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-700 truncate">{log.natural_language}</p>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-xs text-gray-400 flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" />
                          {log.duration_ms ? `${Math.round(parseFloat(log.duration_ms))}ms` : '-'}
                        </span>
                        <span className="text-xs text-gray-300">{new Date(log.executed_at).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div> */}
      </div>

      {/* Access overview */}
      {myPerms.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-indigo-600" />
            <h2 className="text-sm font-semibold text-gray-800">Your Access</h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {myPerms.map((p: any) => (
              <div key={p.connector_id} className="bg-gray-50 rounded-lg px-3 py-2.5">
                <p className="text-sm font-medium text-gray-800 truncate">{p.connector_name}</p>
                <div className="flex items-center gap-1 mt-1 flex-wrap">
                  {p.can_read && <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">R</span>}
                  {p.can_create && <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">C</span>}
                  {p.can_update && <span className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">U</span>}
                  {p.can_delete && <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">D</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Architecture */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-500" />
          How DataBridge Processes Queries
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {[
            { step: '1', title: 'Schema Discovery', desc: 'Semantic type annotations and tribal knowledge enrich the schema context', icon: <Search className="w-5 h-5 text-indigo-500" /> },
            { step: '2', title: 'Permission Check', desc: 'Only tables/columns the user can access are sent to the AI model', icon: <Shield className="w-5 h-5 text-green-500" /> },
            { step: '3', title: 'Query Generation', desc: 'AI generates dialect-specific SQL/NoSQL with pre-resolved date terms', icon: <Zap className="w-5 h-5 text-amber-500" /> },
            { step: '4', title: 'RLS Injection', desc: 'Row-level security filters injected before execution. Results returned.', icon: <Lock className="w-5 h-5 text-red-500" /> },
          ].map(({ step, title, desc, icon }) => (
            <div key={step} className="bg-white border border-gray-200 rounded-lg p-3.5">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-base">{icon}</span>
                <span className="text-xs font-semibold text-gray-700">{title}</span>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
