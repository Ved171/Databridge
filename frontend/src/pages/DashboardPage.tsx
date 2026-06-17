import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Database, Shield, Zap, Radio, AlertTriangle, ArrowRight,
  Server, Cloud, Globe, Search, HardDrive, ShieldCheck,
  Plug, Layers,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import { useAuthStore } from '../store/auth'

const DB_TYPE_ICONS: Record<string, React.ReactNode> = {
  postgres: <Database className="w-5 h-5 text-accent-500" />,
  mysql: <Database className="w-5 h-5 text-orange-500" />,
  mongodb: <Database className="w-5 h-5 text-green-500" />,
  snowflake: <Cloud className="w-5 h-5 text-sky-500" />,
  elasticsearch: <Search className="w-5 h-5 text-yellow-500" />,
  redis: <Zap className="w-5 h-5 text-red-500" />,
  sqlite: <HardDrive className="w-5 h-5 text-text-muted" />,
  mssql: <Server className="w-5 h-5 text-accent-600" />,
  oracle: <Database className="w-5 h-5 text-red-600" />,
  salesforce: <Cloud className="w-5 h-5 text-sky-500" />,
  rest_api: <Globe className="w-5 h-5 text-accent-500" />,
  default: <Database className="w-5 h-5 text-text-muted" />,
}

function MiniBarChart({ values }: { values: number[] }) {
  const max = Math.max(...values, 1)
  return (
    <div className="flex items-end gap-1 h-8">
      {values.map((v, i) => (
        <div
          key={i}
          className="flex-1 bg-accent-500/70 rounded-sm min-h-[4px]"
          style={{ height: `${Math.max((v / max) * 100, 8)}%` }}
        />
      ))}
    </div>
  )
}

function HealthChart({ healthy, warning, offline }: { healthy: number; warning: number; offline: number }) {
  const total = healthy + warning + offline
  const max = Math.max(healthy, warning, offline, 1)
  const items = [
    { label: 'Ready', count: healthy, color: 'bg-accent-500' },
    { label: 'Needs Schema', count: warning, color: 'bg-accent-500/40' },
    { label: 'Inactive', count: offline, color: 'bg-outline-variant' },
  ]
  return (
    <div className="flex items-end gap-6 h-44 pt-4">
      {items.map(item => (
        <div key={item.label} className="flex-1 flex flex-col items-center gap-1.5">
          <span className="text-[10px] font-mono text-text-muted">{item.count}</span>
          <div className="w-full flex justify-center h-32 items-end">
            <div
              className={`w-12 rounded-t-sm ${item.color}`}
              style={{ height: `${Math.max((item.count / max) * 100, item.count > 0 ? 8 : 0)}%`, minHeight: item.count > 0 ? 16 : 0 }}
            />
          </div>
          <span className="text-[10px] font-mono text-text-muted text-center">{item.label}</span>
        </div>
      ))}
      {total === 0 && (
        <div className="flex-1 flex items-center justify-center text-sm text-text-muted">
          No connectors to analyse
        </div>
      )}
    </div>
  )
}

export function DashboardPage() {
  const user = useAuthStore(s => s.user)

  const { data: dashboardSummary } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => api.get('/api/dashboard/summary').then(r => r.data),
  })

  const { data: connectors = [] } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  const { data: myPerms = [] } = useQuery({
    queryKey: ['my-permissions'],
    queryFn: () => api.get('/api/permissions/my-permissions').then(r => r.data),
  })

  const visibleConnectors = dashboardSummary?.access?.accessible_connectors ?? connectors
  const mcpToolCount = dashboardSummary?.mcp?.tool_count ?? 0
  const mcpResourceCount = dashboardSummary?.mcp?.resource_count ?? 0

  const stats = useMemo(() => {
    const activeConnectors = connectors.filter((c: any) => c.is_active)
    const cachedConnectors = connectors.filter((c: any) => c.schema_cached_at)
    const readyConnectors = connectors.filter((c: any) => c.is_active && c.schema_cached_at)
    const needsSchema = connectors.filter((c: any) => c.is_active && !c.schema_cached_at)
    const inactive = connectors.filter((c: any) => !c.is_active)
    const summaryConnectors = dashboardSummary?.connectors
    const summaryAccess = dashboardSummary?.access

    const activeConnectorCount = summaryConnectors?.active ?? activeConnectors.length
    const cachedConnectorCount = summaryConnectors?.schema_cached ?? cachedConnectors.length
    const readyConnectorCount = summaryConnectors?.ready ?? readyConnectors.length
    const needsSchemaCount = summaryConnectors?.needs_schema ?? needsSchema.length
    const inactiveConnectorCount = summaryConnectors?.inactive ?? inactive.length

    const schemaReadiness = summaryConnectors?.schema_readiness_pct ?? (connectors.length > 0
      ? (cachedConnectors.length / connectors.length) * 100
      : null)

    const permCoverage = summaryAccess?.coverage_pct ?? (connectors.length > 0
      ? Math.round((myPerms.length / connectors.length) * 100)
      : null)

    const healthSource = visibleConnectors.length > 0 ? visibleConnectors : connectors
    const connectorHealthBars = healthSource.slice(0, 8).map((c: any) => {
      if (c.is_active && c.schema_cached_at) return 3
      if (c.is_active) return 2
      return 1
    })

    const typeCounts: Record<string, number> = {}
    connectors.forEach((c: any) => {
      typeCounts[c.type] = (typeCounts[c.type] || 0) + 1
    })
    const typeDistribution = summaryConnectors?.type_distribution ?? (
      Object.entries(typeCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([type, count]) => ({
          type,
          count,
          pct: connectors.length > 0 ? Math.round((count / connectors.length) * 100) : 0,
        }))
    )

    const readPerms = summaryAccess?.read ?? myPerms.filter((p: any) => p.can_read).length
    const writePerms = summaryAccess?.write ?? myPerms.filter((p: any) => p.can_create || p.can_update || p.can_delete).length

    return {
      activeConnectorCount,
      cachedConnectorCount,
      readyConnectorCount,
      needsSchemaCount,
      inactiveConnectorCount,
      schemaReadiness,
      permCoverage,
      connectorHealthBars,
      typeDistribution,
      readPerms,
      writePerms,
    }
  }, [connectors, myPerms, dashboardSummary, visibleConnectors])

  const roleBadge = user?.is_superadmin || user?.role === 'superadmin' || user?.role === 'super_admin'
    ? 'Super Admin'
    : user?.role === 'admin'
      ? 'Admin'
      : user?.role === 'workspace_admin'
        ? 'Workspace Admin'
        : 'Member'

  return (
    <div className="px-4 md:px-8 py-6 md:py-8 max-w-content mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="headline-xl">System Overview</h1>
        <p className="text-sm text-text-muted mt-1">
          Welcome back, {user?.name || 'User'} - {roleBadge} - {stats.activeConnectorCount} active connector{stats.activeConnectorCount !== 1 ? 's' : ''} - Query via MCP
        </p>
      </div>

      {/* 3 summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1 — Schema Readiness */}
        <div className="card p-4 hover:border-accent-500/30 transition-colors">
          <p className="label-sm text-text-muted">Schema Readiness</p>
          <div className="flex items-end justify-between mt-2">
            <p className="font-headline text-3xl font-extrabold text-on-surface">
              {stats.schemaReadiness !== null ? `${Math.round(stats.schemaReadiness)}%` : '—'}
            </p>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${stats.cachedConnectorCount === stats.activeConnectorCount && stats.activeConnectorCount > 0
                ? 'bg-success-bg text-success border-success-border'
                : 'bg-warning-bg text-warning border-warning-border'
              }`}>
              {stats.cachedConnectorCount}/{stats.activeConnectorCount} cached
            </span>
          </div>
          <div className="progress-track mt-3">
            <div className="progress-fill" style={{ width: `${stats.schemaReadiness ?? 0}%` }} />
          </div>
          <p className="text-xs text-text-muted mt-2">
            Schemas power MCP discovery tools
          </p>
        </div>

        {/* Card 2 — Active Connectors */}
        <div className="card p-4 hover:border-accent-500/30 transition-colors">
          <p className="label-sm text-text-muted">Active Connectors</p>
          <div className="flex items-end justify-between mt-2">
            <p className="font-headline text-3xl font-extrabold text-on-surface">
              {stats.activeConnectorCount}
            </p>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${stats.readyConnectorCount === stats.activeConnectorCount && stats.activeConnectorCount > 0
                ? 'bg-success-bg text-success border-success-border'
                : 'bg-warning-bg text-warning border-warning-border'
              }`}>
              <Radio className="w-3 h-3" />
              {stats.readyConnectorCount} MCP-ready
            </span>
          </div>
          <div className="mt-3">
            <MiniBarChart values={stats.connectorHealthBars.length > 0 ? stats.connectorHealthBars : [0]} />
          </div>
          <p className="text-xs text-text-muted mt-2">Per-connector health status</p>
        </div>

        {/* Card 3 — MCP Gateway (highlighted) */}
        <div className="bg-accent-500 rounded-card p-4 text-white relative overflow-hidden hover:opacity-95 transition-opacity">
          <div className="flex items-start justify-between">
            <p className="label-sm text-white/70">MCP Gateway</p>
            <Plug className="w-4 h-4 text-white/60" />
          </div>
          <p className="font-headline text-3xl font-extrabold mt-2">{mcpToolCount}</p>
          <p className="text-xs text-white/60 font-mono uppercase tracking-wider mt-0.5">
            Tools Available{mcpResourceCount > 0 ? ` - ${mcpResourceCount} resources` : ''}
          </p>
          <p className="text-xs text-white/70 mt-2 truncate">
            {stats.permCoverage !== null ? `${stats.permCoverage}% connector access` : 'Secure data access'}
            {stats.readPerms > 0 && ` - ${stats.readPerms} read / ${stats.writePerms} write`}
          </p>
          <Link
            to="/mcp"
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-white bg-white/15 hover:bg-white/25 px-3 py-1.5 rounded transition-colors"
          >
            Set up MCP <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>

      {/* Analytics row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Connector health */}
        <div className="lg:col-span-8 card p-5 hover:border-accent-500/30 transition-colors">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-on-surface">Connector Health</h2>
            <div className="flex items-center gap-4 text-xs text-text-muted">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent-500" /> Ready
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent-500/40" /> Needs Schema
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-outline-variant" /> Inactive
              </span>
            </div>
          </div>
          <HealthChart
            healthy={stats.readyConnectorCount}
            warning={stats.needsSchemaCount}
            offline={stats.inactiveConnectorCount}
          />
        </div>

        {/* Connector type distribution */}
        <div className="lg:col-span-4 card p-5 hover:border-accent-500/30 transition-colors flex flex-col">
          <h2 className="text-sm font-semibold text-on-surface mb-5">Connector Types</h2>
          {stats.typeDistribution.length === 0 ? (
            <p className="text-sm text-text-muted flex-1">No connectors configured.</p>
          ) : (
            <div className="space-y-4 flex-1">
              {stats.typeDistribution.slice(0, 5).map(({ type, pct }: { type: string; pct: number }, i: number) => (
                <div key={type}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-on-surface capitalize">{type.replace('_', ' ')}</span>
                    <span className="text-sm font-medium text-on-surface">{pct}%</span>
                  </div>
                  <div className="progress-track h-2">
                    <div
                      className="h-full rounded-full bg-accent-500"
                      style={{ width: `${pct}%`, opacity: 1 - i * 0.15 }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
          {stats.activeConnectorCount > 0 && (
            <div className="mt-5 p-3 bg-surface-container-low rounded border border-border-default">
              <p className="text-xs text-text-muted leading-relaxed">
                {stats.readyConnectorCount} of {stats.activeConnectorCount} active connector{stats.activeConnectorCount !== 1 ? 's are' : ' is'} ready for MCP queries.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Link to="/mcp" className="card p-4 flex items-center gap-3 hover:border-accent-500/30 transition-colors group border-accent-500/20">
          <div className="w-10 h-10 bg-accent-50 rounded flex items-center justify-center group-hover:bg-accent-100 transition-colors">
            <Zap className="w-5 h-5 text-accent-500" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-on-surface">MCP Integration</p>
            <p className="text-xs text-text-muted">{mcpToolCount} tools - Connect your AI client</p>
          </div>
          <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-accent-500 transition-colors" />
        </Link>
        <Link to="/connectors" className="card p-4 flex items-center gap-3 hover:border-accent-500/30 transition-colors group">
          <div className="w-10 h-10 bg-accent-50 rounded flex items-center justify-center group-hover:bg-accent-100 transition-colors">
            <Database className="w-5 h-5 text-accent-500" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-on-surface">Manage Connectors</p>
            <p className="text-xs text-text-muted">{stats.activeConnectorCount} active</p>
          </div>
          <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-accent-500 transition-colors" />
        </Link>
      </div>

      {/* Connected databases */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border-default flex items-center justify-between">
          <h2 className="text-sm font-semibold text-on-surface">Connected Databases</h2>
          <Link to="/connectors" className="text-xs text-accent-500 hover:opacity-80 font-medium transition-opacity">
            View all →
          </Link>
        </div>
        {visibleConnectors.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <Database className="w-8 h-8 text-text-muted mx-auto mb-2" />
            <p className="text-sm text-text-secondary">No readable databases available</p>
            <Link to="/connectors" className="text-xs text-accent-500 hover:opacity-80 mt-1 inline-block">
              Manage connector access -&gt;
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-border-muted">
            {visibleConnectors.slice(0, 6).map((c: any) => (
              <div key={c.id} className="flex items-center gap-3 px-5 py-3 hover:bg-surface-container-low transition-colors">
                <span className="flex items-center justify-center w-8 h-8 rounded bg-surface-container-low border border-border-default">
                  {DB_TYPE_ICONS[c.type] || DB_TYPE_ICONS.default}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-on-surface truncate">{c.name}</p>
                  <p className="text-xs text-text-muted">{c.type}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  {c.schema_cached_at ? (
                    <span className="badge-success">Cached</span>
                  ) : (
                    <span className="badge-warning flex items-center gap-1">
                      <AlertTriangle className="w-2.5 h-2.5" /> No schema
                    </span>
                  )}
                  <span className={`w-2 h-2 rounded-full ${c.is_active ? 'bg-success' : 'bg-text-muted'}`} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Access overview */}
      {visibleConnectors.length > 0 && (
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-accent-500" />
            <h2 className="text-sm font-semibold text-on-surface">Your Access</h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {visibleConnectors.map((p: any) => (
              <div key={p.id || p.connector_id} className="bg-surface-container-low rounded px-3 py-2.5">
                <p className="text-sm font-medium text-on-surface truncate">{p.name || p.connector_name}</p>
                <div className="flex items-center gap-1 mt-1 flex-wrap">
                  {p.can_read && <span className="text-xs bg-accent-50 text-accent-600 px-1.5 py-0.5 rounded font-mono">R</span>}
                  {p.can_create && <span className="text-xs bg-success-bg text-success px-1.5 py-0.5 rounded font-mono">C</span>}
                  {p.can_update && <span className="text-xs bg-warning-bg text-warning px-1.5 py-0.5 rounded font-mono">U</span>}
                  {p.can_delete && <span className="text-xs bg-error-bg text-error px-1.5 py-0.5 rounded font-mono">D</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MCP workflow */}
      <div className="card p-5">
        <h3 className="text-sm font-semibold text-on-surface mb-3 flex items-center gap-2">
          <Plug className="w-4 h-4 text-accent-500" />
          How Data Access Works via MCP
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {[
            { title: 'Connect MCP Client', desc: 'Link Cursor, Claude Desktop, or any MCP-compatible AI agent to the DataBridge gateway.', icon: <Plug className="w-5 h-5 text-accent-500" /> },
            { title: 'Schema Discovery', desc: 'AI calls get_relevant_schema to discover only the tables and columns you can access.', icon: <Search className="w-5 h-5 text-accent-500" /> },
            { title: 'Permission Check', desc: 'Every tool call is scoped to your role, connector permissions, and row-level security rules.', icon: <ShieldCheck className="w-5 h-5 text-success" /> },
            { title: 'Execute via Tools', desc: 'Queries run through execute_query or execute_federated_query — no in-app chat required.', icon: <Layers className="w-5 h-5 text-warning" /> },
          ].map(({ title, desc, icon }) => (
            <div key={title} className="bg-surface-container-low border border-border-default rounded p-3.5">
              <div className="flex items-center gap-2 mb-1.5">
                {icon}
                <span className="text-xs font-semibold text-on-surface">{title}</span>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
