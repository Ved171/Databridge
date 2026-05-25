import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus, Database, Trash2, RefreshCw, CheckCircle, XCircle,
  ChevronDown, ChevronUp, Eye, EyeOff, Loader2, Zap, Pencil, X
} from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../lib/api'
import { useAuthStore } from '../store/auth'
import clsx from 'clsx'

// ─── Field definition for each input ────────────────────────────────────────
interface FieldDef {
  key: string
  label: string
  placeholder?: string
  required?: boolean
  secret?: boolean
  type?: 'text' | 'password' | 'textarea' | 'select'
  options?: { value: string; label: string }[]
  helpText?: string
  fullWidth?: boolean
}

// ─── Field group (rendered as a section in the form) ────────────────────────
interface FieldGroup {
  title?: string
  fields: FieldDef[]
}

// ─── DB type definition with dynamic field groups ───────────────────────────
interface DBTypeDef {
  value: string
  label: string
  category: 'SQL' | 'Cloud' | 'NoSQL' | 'SaaS'
  fieldGroups: FieldGroup[]
}

const DB_TYPES: DBTypeDef[] = [
  {
    value: 'postgres', label: 'PostgreSQL', category: 'SQL',
    fieldGroups: [{
      title: 'Connection',
      fields: [
        { key: 'host', label: 'Host', placeholder: 'localhost', required: true },
        { key: 'port', label: 'Port', placeholder: '5432' },
        { key: 'database', label: 'Database', placeholder: 'mydb', required: true },
      ],
    }, {
      title: 'Authentication',
      fields: [
        { key: 'user', label: 'Username', required: true },
        { key: 'password', label: 'Password', required: true, secret: true },
      ],
    }, {
      title: 'Security (optional)',
      fields: [
        { key: 'use_ssl', label: 'SSL Mode', type: 'select', options: [{ value: '', label: 'Off' }, { value: 'true', label: 'On (no verify)' }, { value: 'verify-ca', label: 'Verify CA' }], helpText: 'Enable for cloud-hosted databases (RDS, Supabase, etc.)' },
      ],
    }],
  },
  {
    value: 'mysql', label: 'MySQL / MariaDB', category: 'SQL',
    fieldGroups: [{
      title: 'Connection',
      fields: [
        { key: 'host', label: 'Host', placeholder: 'localhost', required: true },
        { key: 'port', label: 'Port', placeholder: '3306' },
        { key: 'database', label: 'Database', placeholder: 'mydb', required: true },
      ],
    }, {
      title: 'Authentication',
      fields: [
        { key: 'user', label: 'Username', required: true },
        { key: 'password', label: 'Password', required: true, secret: true },
      ],
    }, {
      title: 'Security (optional)',
      fields: [
        { key: 'use_ssl', label: 'Use SSL', type: 'select', options: [{ value: '', label: 'Off' }, { value: 'true', label: 'On' }], helpText: 'Enable for cloud MySQL (RDS, Azure, PlanetScale)' },
      ],
    }],
  },
  {
    value: 'sqlite', label: 'SQLite', category: 'SQL',
    fieldGroups: [{
      fields: [
        { key: 'path', label: 'Database File Path', placeholder: '/path/to/database.db', required: true, fullWidth: true },
      ],
    }],
  },
  {
    value: 'mssql', label: 'SQL Server', category: 'SQL',
    fieldGroups: [{
      title: 'Connection',
      fields: [
        { key: 'host', label: 'Host', placeholder: 'localhost', required: true },
        { key: 'port', label: 'Port', placeholder: '1433' },
        { key: 'database', label: 'Database', required: true },
      ],
    }, {
      title: 'Authentication',
      fields: [
        { key: 'user', label: 'Username', required: true },
        { key: 'password', label: 'Password', required: true, secret: true },
      ],
    }, {
      title: 'Security (optional)',
      fields: [
        { key: 'encrypt', label: 'Encrypt', type: 'select', options: [{ value: '', label: 'Off' }, { value: 'true', label: 'Yes' }], helpText: 'Required for Azure SQL and TLS-enabled servers' },
        { key: 'trust_server_certificate', label: 'Trust Server Certificate', type: 'select', options: [{ value: '', label: 'No' }, { value: 'true', label: 'Yes' }], helpText: 'Skip certificate validation (dev/self-signed certs)' },
      ],
    }],
  },
  {
    value: 'oracle', label: 'Oracle', category: 'SQL',
    fieldGroups: [{
      title: 'Connection',
      fields: [
        { key: 'host', label: 'Host', required: true },
        { key: 'port', label: 'Port', placeholder: '1521' },
        { key: 'service_name', label: 'Service Name', required: true },
      ],
    }, {
      title: 'Authentication',
      fields: [
        { key: 'user', label: 'Username', required: true },
        { key: 'password', label: 'Password', required: true, secret: true },
      ],
    }],
  },
  {
    value: 'snowflake', label: 'Snowflake', category: 'Cloud',
    fieldGroups: [{
      title: 'Account',
      fields: [
        { key: 'account', label: 'Account Identifier', placeholder: 'xy12345.us-east-1', required: true },
        { key: 'database', label: 'Database', required: true },
        { key: 'schema', label: 'Schema', placeholder: 'PUBLIC' },
      ],
    }, {
      title: 'Authentication',
      fields: [
        { key: 'user', label: 'Username', required: true },
        { key: 'password', label: 'Password', required: true, secret: true },
      ],
    }, {
      title: 'Compute',
      fields: [
        { key: 'warehouse', label: 'Warehouse', placeholder: 'COMPUTE_WH' },
        { key: 'role', label: 'Role', placeholder: 'PUBLIC' },
      ],
    }],
  },
  {
    value: 'redshift', label: 'Redshift', category: 'Cloud',
    fieldGroups: [{
      title: 'Connection',
      fields: [
        { key: 'host', label: 'Cluster Endpoint', required: true },
        { key: 'port', label: 'Port', placeholder: '5439' },
        { key: 'database', label: 'Database', required: true },
      ],
    }, {
      title: 'Authentication',
      fields: [
        { key: 'user', label: 'Username', required: true },
        { key: 'password', label: 'Password', required: true, secret: true },
      ],
    }],
  },
  {
    value: 'bigquery', label: 'BigQuery', category: 'Cloud',
    fieldGroups: [{
      fields: [
        { key: 'project_id', label: 'Project ID', required: true },
        { key: 'dataset', label: 'Dataset', required: true },
        { key: 'credentials_json', label: 'Service Account JSON', required: true, secret: true, type: 'textarea', fullWidth: true, helpText: 'Paste the full JSON key file contents' },
      ],
    }],
  },
  {
    value: 'mongodb', label: 'MongoDB', category: 'NoSQL',
    fieldGroups: [{
      title: 'Connection',
      fields: [
        { key: 'uri', label: 'Connection String (URI)', placeholder: 'mongodb+srv://user:pass@cluster.mongodb.net/mydb', required: true, secret: true, fullWidth: true, helpText: 'Full MongoDB connection string including credentials' },
        { key: 'database', label: 'Database Name', placeholder: 'mydb', required: true, helpText: 'Overrides the database in the URI if specified' },
      ],
    }, {
      title: 'Advanced (optional)',
      fields: [
        { key: 'authSource', label: 'Auth Source', placeholder: 'admin', helpText: 'Authentication database, defaults to admin' },
      ],
    }],
  },
  {
    value: 'elasticsearch', label: 'Elasticsearch', category: 'NoSQL',
    fieldGroups: [{
      title: 'Connection',
      fields: [
        { key: 'host', label: 'Host', placeholder: 'localhost', required: true },
        { key: 'port', label: 'Port', placeholder: '9200' },
        { key: 'use_ssl', label: 'Use SSL', type: 'select', options: [{ value: 'false', label: 'No' }, { value: 'true', label: 'Yes' }] },
        { key: 'index_pattern', label: 'Index Pattern', placeholder: 'logs-*', helpText: 'Glob pattern to discover indices' },
      ],
    }, {
      title: 'Authentication (optional)',
      fields: [
        { key: 'user', label: 'Username' },
        { key: 'password', label: 'Password', secret: true },
      ],
    }],
  },
  {
    value: 'redis', label: 'Redis', category: 'NoSQL',
    fieldGroups: [{
      fields: [
        { key: 'host', label: 'Host', placeholder: 'localhost', required: true },
        { key: 'port', label: 'Port', placeholder: '6379' },
        { key: 'password', label: 'Password', secret: true },
        { key: 'db', label: 'DB Index', placeholder: '0' },
      ],
    }],
  },
  {
    value: 'salesforce', label: 'Salesforce', category: 'SaaS',
    fieldGroups: [{
      title: 'Credentials',
      fields: [
        { key: 'username', label: 'Username', required: true },
        { key: 'password', label: 'Password', required: true, secret: true },
        { key: 'security_token', label: 'Security Token', required: true, secret: true },
        { key: 'domain', label: 'Domain', placeholder: 'login', type: 'select', options: [{ value: 'login', label: 'Production (login)' }, { value: 'test', label: 'Sandbox (test)' }] },
      ],
    }],
  },
  {
    value: 'rest_api', label: 'REST API', category: 'SaaS',
    fieldGroups: [{
      fields: [
        { key: 'base_url', label: 'Base URL', placeholder: 'https://api.example.com', required: true, fullWidth: true },
        { key: 'auth_type', label: 'Auth Type', type: 'select', options: [{ value: 'none', label: 'None' }, { value: 'bearer', label: 'Bearer Token' }, { value: 'basic', label: 'Basic Auth' }, { value: 'api_key', label: 'API Key' }] },
        { key: 'auth_value', label: 'Auth Value', secret: true, helpText: 'Token, key, or user:pass depending on auth type' },
      ],
    }],
  },
  {
    value: 'airtable', label: 'Airtable', category: 'SaaS',
    fieldGroups: [{
      fields: [
        { key: 'api_key', label: 'API Key / Personal Access Token', required: true, secret: true, fullWidth: true },
        { key: 'base_id', label: 'Base ID', placeholder: 'appXXXXXXXXXXXXXX', required: true },
      ],
    }],
  },
]

const CATEGORY_COLORS: Record<string, string> = {
  SQL:   'bg-blue-100 text-blue-700',
  Cloud: 'bg-purple-100 text-purple-700',
  NoSQL: 'bg-green-100 text-green-700',
  SaaS:  'bg-orange-100 text-orange-700',
}

export function ConnectorsPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  const [form, setForm] = useState<{ name: string; type: string; config: Record<string, string> }>({
    name: '', type: 'postgres', config: {}
  })
  const [testResults, setTestResults] = useState<Record<string, 'ok' | 'fail' | 'loading'>>({})
  const [schemaStatus, setSchemaStatus] = useState<Record<string, 'loading' | 'ok' | 'fail'>>({})
  const [editTarget, setEditTarget] = useState<{ id: string; name: string; type: string; config: Record<string, string> } | null>(null)
  const [editLoading, setEditLoading] = useState(false)
  const { user: me } = useAuthStore()
  const myRole = me?.is_superadmin ? 'superadmin' : (me?.role || 'member')
  const isAdmin = myRole === 'admin' || myRole === 'superadmin'
  const isWsAdmin = myRole === 'workspace_admin'
  const canEdit = isAdmin || isWsAdmin  // members cannot edit
  const canDelete = isAdmin             // only admins can delete

  const { data: connectors = [], isLoading } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post('/api/connectors/', data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['connectors'] }); setShowForm(false); resetForm() },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/connectors/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connectors'] }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.patch(`/api/connectors/${id}`, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['connectors'] }); setEditTarget(null); toast.success('Connector updated') },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Update failed'),
  })

  const openEditModal = async (c: any) => {
    setEditLoading(true)
    try {
      const res = await api.get(`/api/connectors/${c.id}/config`)
      setEditTarget({ id: c.id, name: c.name, type: c.type, config: res.data })
    } catch {
      toast.error('Failed to load config')
    }
    setEditLoading(false)
  }

  const resetForm = () => setForm({ name: '', type: 'postgres', config: {} })

  const selectedType = DB_TYPES.find(t => t.value === form.type)

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({ name: form.name, type: form.type, config: form.config })
  }

  const testConnection = async (id: string) => {
    setTestResults(p => ({ ...p, [id]: 'loading' }))
    try {
      await api.post(`/api/connectors/${id}/test`)
      setTestResults(p => ({ ...p, [id]: 'ok' }))
    } catch {
      setTestResults(p => ({ ...p, [id]: 'fail' }))
    }
  }

  const refreshSchema = async (id: string) => {
    setSchemaStatus(p => ({ ...p, [id]: 'loading' }))
    try {
      await api.post(`/api/connectors/${id}/refresh-schema`)
      setSchemaStatus(p => ({ ...p, [id]: 'ok' }))
      qc.invalidateQueries({ queryKey: ['connectors'] })
    } catch {
      setSchemaStatus(p => ({ ...p, [id]: 'fail' }))
    }
  }

  const groupedTypes = DB_TYPES.reduce((acc, t) => {
    acc[t.category] = [...(acc[t.category] || []), t]
    return acc
  }, {} as Record<string, typeof DB_TYPES>)

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Database Connectors</h1>
          <p className="text-sm text-gray-500 mt-0.5">{connectors.length} connected - 14 supported types</p>
        </div>
        <button
          onClick={() => setShowForm(f => !f)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Connector
        </button>
      </div>

      {/* Add Connector Form */}
      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 shadow-sm">
          <h2 className="text-base font-semibold text-gray-800 mb-4">New Connector</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Display Name</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Production PostgreSQL"
                  required
                  className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Database Type</label>
                <select
                  value={form.type}
                  onChange={e => setForm(f => ({ ...f, type: e.target.value, config: {} }))}
                  className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {Object.entries(groupedTypes).map(([cat, types]) => (
                    <optgroup key={cat} label={cat}>
                      {types.map(t => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            </div>

            {/* Dynamic config fields — grouped by section */}
            {selectedType && (
              <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                  Connection Config
                  <span className={`ml-2 text-xs px-2 py-0.5 rounded-full font-medium ${CATEGORY_COLORS[selectedType.category]}`}>
                    {selectedType.category}
                  </span>
                </p>

                {selectedType.fieldGroups.map((group, gi) => (
                  <div key={gi}>
                    {group.title && (
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 mt-1">{group.title}</p>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                      {group.fields.map(field => (
                        <div key={field.key} className={field.fullWidth ? 'col-span-2' : ''}>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            {field.label}
                            {field.required && <span className="text-red-400 ml-0.5">*</span>}
                          </label>

                          {/* Select dropdown */}
                          {field.type === 'select' && field.options ? (
                            <select
                              value={form.config[field.key] || field.options[0]?.value || ''}
                              onChange={e => setForm(f => ({ ...f, config: { ...f.config, [field.key]: e.target.value } }))}
                              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                            >
                              {field.options.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                              ))}
                            </select>

                          /* Textarea */
                          ) : field.type === 'textarea' ? (
                            <div className="relative">
                              <textarea
                                value={form.config[field.key] || ''}
                                onChange={e => setForm(f => ({ ...f, config: { ...f.config, [field.key]: e.target.value } }))}
                                placeholder={field.placeholder || ''}
                                required={field.required}
                                rows={3}
                                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-xs"
                              />
                              {field.secret && (
                                <button
                                  type="button"
                                  onClick={() => setShowSecrets(s => ({ ...s, [field.key]: !s[field.key] }))}
                                  className="absolute right-2 top-2 text-gray-400 hover:text-gray-600"
                                >
                                  {showSecrets[field.key] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                </button>
                              )}
                            </div>

                          /* Default: text/password input */
                          ) : (
                            <div className="relative">
                              <input
                                type={field.secret && !showSecrets[field.key] ? 'password' : 'text'}
                                value={form.config[field.key] || ''}
                                onChange={e => setForm(f => ({ ...f, config: { ...f.config, [field.key]: e.target.value } }))}
                                placeholder={field.placeholder || ''}
                                required={field.required}
                                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              />
                              {field.secret && (
                                <button
                                  type="button"
                                  onClick={() => setShowSecrets(s => ({ ...s, [field.key]: !s[field.key] }))}
                                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                >
                                  {showSecrets[field.key] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                </button>
                              )}
                            </div>
                          )}

                          {field.helpText && (
                            <p className="text-xs text-gray-400 mt-0.5">{field.helpText}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => { setShowForm(false); resetForm() }}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors">
                Cancel
              </button>
              <button type="submit" disabled={createMutation.isPending}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                {createMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Create Connector
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Connectors List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>
      ) : connectors.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <Database className="w-10 h-10 mx-auto mb-3 text-gray-300" />
          <p className="font-medium">No connectors yet</p>
          <p className="text-sm mt-1">Add your first database connector to get started</p>
        </div>
      ) : (
        <div className="space-y-3">
          {connectors.map((c: any) => {
            const typeInfo = DB_TYPES.find(t => t.value === c.type)
            const categoryColor = CATEGORY_COLORS[typeInfo?.category || ''] || 'bg-gray-100 text-gray-600'
            const testResult = testResults[c.id]
            const schemaResult = schemaStatus[c.id]

            return (
              <div key={c.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
                <div className="flex items-center px-5 py-4 gap-4">
                  <div className="w-9 h-9 bg-indigo-50 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Database className="w-5 h-5 text-indigo-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 text-sm">{c.name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${categoryColor}`}>
                        {c.type}
                      </span>
                      {!c.is_active && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">inactive</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {c.schema_cached_at
                        ? `Schema cached ${new Date(c.schema_cached_at).toLocaleDateString()}`
                        : '[!] Schema not cached - run refresh to enable NL queries'}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => testConnection(c.id)}
                      disabled={testResult === 'loading'}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 transition-colors"
                    >
                      {testResult === 'loading' ? <Loader2 className="w-3 h-3 animate-spin" /> :
                       testResult === 'ok' ? <CheckCircle className="w-3 h-3 text-green-500" /> :
                       testResult === 'fail' ? <XCircle className="w-3 h-3 text-red-500" /> :
                       <Zap className="w-3 h-3" />}
                      Test
                    </button>
                    <button
                      onClick={() => refreshSchema(c.id)}
                      disabled={schemaResult === 'loading'}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 transition-colors"
                    >
                      {schemaResult === 'loading' ? <Loader2 className="w-3 h-3 animate-spin" /> :
                       schemaResult === 'ok' ? <CheckCircle className="w-3 h-3 text-green-500" /> :
                       schemaResult === 'fail' ? <XCircle className="w-3 h-3 text-red-500" /> :
                       <RefreshCw className="w-3 h-3" />}
                      Refresh Schema
                    </button>
                    {canEdit && (
                      <button
                        onClick={() => openEditModal(c)}
                        className="text-gray-400 hover:text-indigo-500 p-1 transition-colors"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
                      className="text-gray-400 hover:text-gray-600 p-1"
                    >
                      {expandedId === c.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                    {canDelete && (
                      <button
                        onClick={() => confirm(`Delete ${c.name}?`) && deleteMutation.mutate(c.id)}
                        className="text-gray-400 hover:text-red-500 p-1 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded schema view */}
                {expandedId === c.id && c.schema_cached_at && (
                  <div className="border-t border-gray-100 px-5 py-4 bg-gray-50">
                    <SchemaPreview connectorId={c.id} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
      {/* Edit Connector Modal */}
      {editTarget && (() => {
        const editType = DB_TYPES.find(t => t.value === editTarget.type)
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setEditTarget(null)} />
            <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 sticky top-0 bg-white z-10">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Edit Connector</h3>
                  <p className="text-sm text-gray-500 mt-0.5">{editTarget.type}</p>
                </div>
                <button className="p-1 rounded-md hover:bg-gray-100" onClick={() => setEditTarget(null)}>
                  <X className="w-5 h-5 text-gray-400" />
                </button>
              </div>
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Display Name</label>
                  <input value={editTarget.name} onChange={e => setEditTarget(p => p ? { ...p, name: e.target.value } : p)}
                    className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                </div>
                {editType?.fieldGroups.map((group, gi) => (
                  <div key={gi}>
                    {group.title && <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">{group.title}</p>}
                    <div className="grid grid-cols-2 gap-3">
                      {group.fields.map(field => (
                        <div key={field.key} className={field.fullWidth ? 'col-span-2' : ''}>
                          <label className="block text-xs font-medium text-gray-600 mb-1">{field.label}</label>
                          {field.type === 'select' && field.options ? (
                            <select value={editTarget.config[field.key] || ''}
                              onChange={e => setEditTarget(p => p ? { ...p, config: { ...p.config, [field.key]: e.target.value } } : p)}
                              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white">
                              {field.options.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                            </select>
                          ) : (
                            <div className="relative">
                              <input type={field.secret && !showSecrets[`edit_${field.key}`] ? 'password' : 'text'}
                                value={editTarget.config[field.key] || ''}
                                onChange={e => setEditTarget(p => p ? { ...p, config: { ...p.config, [field.key]: e.target.value } } : p)}
                                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                              {field.secret && (
                                <button type="button" onClick={() => setShowSecrets(s => ({ ...s, [`edit_${field.key}`]: !s[`edit_${field.key}`] }))}
                                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                                  {showSecrets[`edit_${field.key}`] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 sticky bottom-0">
                <button className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900" onClick={() => setEditTarget(null)}>Cancel</button>
                <button className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
                  disabled={updateMutation.isPending}
                  onClick={() => updateMutation.mutate({ id: editTarget.id, data: { name: editTarget.name, config: editTarget.config } })}>
                  {updateMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null} Save Changes
                </button>
              </div>
            </div>
          </div>
        )
      })()}
    </div>
  )
}

function SchemaPreview({ connectorId }: { connectorId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['schema', connectorId],
    queryFn: () => api.get(`/api/connectors/${connectorId}/schema`).then(r => r.data),
  })

  if (isLoading) return <div className="flex items-center gap-2 text-xs text-gray-400"><Loader2 className="w-3 h-3 animate-spin" /> Loading schema...</div>
  if (!data?.tables?.length) return <p className="text-xs text-gray-400">No tables found</p>

  return (
    <div>
      <p className="text-xs font-semibold text-gray-600 mb-2">{data.tables.length} tables</p>
      <div className="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto">
        {data.tables.map((t: any) => (
          <div key={t.name} className="bg-white border border-gray-200 rounded-lg p-2">
            <p className="text-xs font-semibold text-gray-700 mb-1">
              {t.schema ? `${t.schema}.` : ''}{t.name}
              {t.row_count > 0 && <span className="text-gray-400 font-normal ml-1">({t.row_count.toLocaleString()} rows)</span>}
            </p>
            <div className="space-y-0.5">
              {t.columns.slice(0, 6).map((c: any) => (
                <div key={c.name} className="flex items-center gap-1.5 text-xs">
                  {c.primary_key && <span className="text-yellow-500 text-xs font-mono font-bold">PK</span>}
                  <span className="text-gray-700">{c.name}</span>
                  <span className="text-gray-400 text-xs">{c.type}</span>
                </div>
              ))}
              {t.columns.length > 6 && (
                <p className="text-xs text-gray-400">+{t.columns.length - 6} more</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
