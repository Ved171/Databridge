import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus, Database, Trash2, RefreshCw, CheckCircle, XCircle,
  ChevronDown, ChevronUp, Eye, EyeOff, Loader2, Zap, Pencil, X, AlertCircle, AlertTriangle, Clock
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
  SQL:   'bg-accent-100 text-accent-700',
  Cloud: 'bg-sky-100 text-sky-700',
  NoSQL: 'bg-green-100 text-green-700',
  SaaS:  'bg-amber-100 text-amber-700',
}

const parseUTC = (dateStr: string | null | undefined): Date | null => {
  if (!dateStr) return null
  let normalized = dateStr
  if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !/-\d{2}:\d{2}$/.test(dateStr)) {
    normalized = dateStr + 'Z'
  }
  return new Date(normalized)
}

const getRemainingTime = (expiresAtStr: string) => {
  const expiresAt = parseUTC(expiresAtStr)
  if (!expiresAt) return 'Expired'
  const now = new Date()
  const diffMs = expiresAt.getTime() - now.getTime()
  if (diffMs <= 0) return 'Expired'
  
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 60) return `${diffMins}m remaining`
  
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) {
    const mins = diffMins % 60
    return `${diffHours}h ${mins}m remaining`
  }
  
  const diffDays = Math.floor(diffHours / 24)
  const hours = diffHours % 24
  return `${diffDays}d ${hours}h remaining`
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
  const [editTarget, setEditTarget] = useState<{ id: string; name: string; type: string; config: Record<string, string>; default_policy?: string; is_open_access?: boolean } | null>(null)
  const [editLoading, setEditLoading] = useState(false)
  const [showPolicyDialog, setShowPolicyDialog] = useState(false)
  const [selectedConnectorForPolicy, setSelectedConnectorForPolicy] = useState<any | null>(null)
  const { user: me } = useAuthStore()
  const myRole = me?.is_superadmin ? 'superadmin' : (me?.role || 'member')
  const isAdmin = myRole === 'admin' || myRole === 'superadmin'
  const isWsAdmin = myRole === 'workspace_admin'
  const canEdit = isAdmin || isWsAdmin  // members cannot edit
  const canDelete = isAdmin             // only admins can delete

  // SQLite upload specific state
  const [sqliteMode, setSqliteMode] = useState<'upload' | 'path'>('upload')
  const [sqliteFile, setSqliteFile] = useState<File | null>(null)
  const [editSqliteMode, setEditSqliteMode] = useState<'upload' | 'path'>('upload')
  const [editSqliteFile, setEditSqliteFile] = useState<File | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  })

  const { data: connectors = [], isLoading } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  const { data: myPerms = [] } = useQuery({
    queryKey: ['my-permissions'],
    queryFn: () => api.get('/api/permissions/my-permissions').then(r => r.data),
  })


  const createMutation = useMutation({
    mutationFn: (data: any) => {
      if (data instanceof FormData) {
        return api.post('/api/connectors/upload-sqlite', data, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
      }
      return api.post('/api/connectors/', data)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['connectors'] })
      setShowForm(false)
      resetForm()
      toast.success('Connector created')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Creation failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/connectors/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['connectors'] })
      toast.success('Connector deleted')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Delete failed'),
  })

  const updatePolicyMutation = useMutation({
    mutationFn: ({ id, policy }: { id: string; policy: 'allow_all' | 'deny_all' }) =>
      api.patch(`/api/connectors/${id}/policy`, { policy }),
    onSuccess: (res: any) => {
      qc.invalidateQueries({ queryKey: ['connectors'] })
      setShowPolicyDialog(false)
      setSelectedConnectorForPolicy(null)
      if (editTarget && editTarget.id === res.data.id) {
        setEditTarget(prev => prev ? { ...prev, default_policy: res.data.default_policy, is_open_access: res.data.is_open_access } : null)
      }
      toast.success('Policy updated')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Update failed'),
  })

  const openEditModal = async (c: any) => {
    setEditLoading(true)
    try {
      const res = await api.get(`/api/connectors/${c.id}/config`)
      setEditTarget({ id: c.id, name: c.name, type: c.type, config: res.data, default_policy: c.default_policy, is_open_access: c.is_open_access })
      if (c.type === 'sqlite') {
        const isUploaded = isUploadedPath(res.data.path || '')
        setEditSqliteMode(isUploaded ? 'upload' : 'path')
        setEditSqliteFile(null)
      }
    } catch {
      toast.error('Failed to load config')
    }
    setEditLoading(false)
  }

  const resetForm = () => {
    setForm({ name: '', type: 'postgres', config: {} })
    setSqliteMode('upload')
    setSqliteFile(null)
  }

  const selectedType = DB_TYPES.find(t => t.value === form.type)

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (form.type === 'sqlite' && sqliteMode === 'upload') {
      if (!sqliteFile) {
        toast.error('Please select a database file to upload')
        return
      }
      if (sqliteFile.size > 500 * 1024 * 1024) {
        toast.error('File size exceeds the 500MB limit. Use the Server File Path option.')
        return
      }
      const formData = new FormData()
      formData.append('name', form.name)
      formData.append('file', sqliteFile)
      createMutation.mutate(formData)
    } else {
      createMutation.mutate({ name: form.name, type: form.type, config: form.config })
    }
  }

  const handleUpdate = async () => {
    if (!editTarget) return
    setIsSaving(true)
    try {
      if (editTarget.type === 'sqlite' && editSqliteMode === 'upload') {
        if (editSqliteFile) {
          if (editSqliteFile.size > 500 * 1024 * 1024) {
            toast.error('File size exceeds the 500MB limit. Use the Server File Path option.')
            setIsSaving(false)
            return
          }
          const formData = new FormData()
          formData.append('file', editSqliteFile)
          await api.post(`/api/connectors/${editTarget.id}/upload-sqlite-file`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
          })
        }
        await api.patch(`/api/connectors/${editTarget.id}`, { name: editTarget.name })
      } else {
        await api.patch(`/api/connectors/${editTarget.id}`, {
          name: editTarget.name,
          config: editTarget.config
        })
      }
      toast.success('Connector updated')
      qc.invalidateQueries({ queryKey: ['connectors'] })
      setEditTarget(null)
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Update failed')
    } finally {
      setIsSaving(false)
    }
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

  const handleTogglePolicy = (connector: any) => {
    setSelectedConnectorForPolicy(connector)
    // Only show confirmation if switching TO allow_all
    if (connector.default_policy === 'deny_all') {
      setShowPolicyDialog(true)
    } else {
      // Switch to deny_all without confirmation
      updatePolicyMutation.mutate({ id: connector.id, policy: 'deny_all' })
    }
  }

  const confirmPolicyChange = () => {
    if (selectedConnectorForPolicy) {
      updatePolicyMutation.mutate({
        id: selectedConnectorForPolicy.id,
        policy: 'allow_all'
      })
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
          <h1 className="text-xl font-semibold text-text-primary">Database Connectors</h1>
          <p className="text-sm text-text-secondary mt-0.5">{connectors.length} connected - 14 supported types</p>
        </div>
        <button
          onClick={() => setShowForm(f => !f)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Connector
        </button>
      </div>

      {/* Add Connector Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm animate-fade-in" onClick={() => { setShowForm(false); resetForm() }} />
          <div className="relative bg-bg-card rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col overflow-hidden border border-border-default animate-scale-in">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-muted bg-bg-card flex-shrink-0">
              <div>
                <h3 className="text-lg font-semibold text-text-primary">New Connector</h3>
                <p className="text-xs text-text-secondary mt-0.5">Enter connection and authentication details</p>
              </div>
              <button className="p-1 rounded-md hover:bg-bg-surface" onClick={() => { setShowForm(false); resetForm() }}>
                <X className="w-5 h-5 text-text-muted" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="flex-1 flex flex-col overflow-hidden">
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-text-primary mb-1">Display Name</label>
                    <input
                      value={form.name}
                      onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                      placeholder="e.g. Production PostgreSQL"
                      required
                      className="input"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-text-primary mb-1">Database Type</label>
                    <select
                      value={form.type}
                      onChange={e => setForm(f => ({ ...f, type: e.target.value, config: {} }))}
                      className="input"
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
                  <div className="bg-bg-surface rounded-lg p-4 space-y-4">
                    <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
                      Connection Config
                      <span className={`ml-2 text-xs px-2 py-0.5 rounded-full font-medium ${CATEGORY_COLORS[selectedType.category]}`}>
                        {selectedType.category}
                      </span>
                    </p>

                    {selectedType.value === 'sqlite' ? (
                      <SqliteConnectorForm
                        sqliteMode={sqliteMode}
                        setSqliteMode={setSqliteMode}
                        sqliteFile={sqliteFile}
                        setSqliteFile={setSqliteFile}
                        sqlitePath={form.config.path || ''}
                        setSqlitePath={(p) => setForm(f => ({ ...f, config: { ...f.config, path: p } }))}
                      />
                    ) : (
                      selectedType.fieldGroups.map((group, gi) => (
                        <div key={gi}>
                          {group.title && (
                            <p className="form-section-label mt-1">{group.title}</p>
                          )}
                          <div className="grid grid-cols-2 gap-3">
                            {group.fields.map(field => (
                              <div key={field.key} className={field.fullWidth ? 'col-span-2' : ''}>
                                <label className="block text-xs font-medium text-text-primary mb-1">
                                  {field.label}
                                  {field.required && <span className="text-red-400 ml-0.5">*</span>}
                                </label>

                                {/* Select dropdown */}
                                {field.type === 'select' && field.options ? (
                                  <select
                                    value={form.config[field.key] || field.options[0]?.value || ''}
                                    onChange={e => setForm(f => ({ ...f, config: { ...f.config, [field.key]: e.target.value } }))}
                                    className="input"
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
                                      className="input font-mono text-xs"
                                    />
                                    {field.secret && (
                                      <button
                                        type="button"
                                        onClick={() => setShowSecrets(s => ({ ...s, [field.key]: !s[field.key] }))}
                                        className="absolute right-2 top-2 text-text-muted hover:text-text-secondary"
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
                                      className="input pr-8"
                                    />
                                    {field.secret && (
                                      <button
                                        type="button"
                                        onClick={() => setShowSecrets(s => ({ ...s, [field.key]: !s[field.key] }))}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
                                      >
                                        {showSecrets[field.key] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                      </button>
                                    )}
                                  </div>
                                )}

                                {field.helpText && (
                                  <p className="help-text">{field.helpText}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 px-6 py-4 border-t border-border-muted bg-bg-surface flex-shrink-0">
                <button type="button" onClick={() => { setShowForm(false); resetForm() }}
                  className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={createMutation.isPending}
                  className="btn-primary flex items-center gap-2 disabled:bg-text-muted">
                  {createMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Create Connector
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Connectors List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-text-muted" /></div>
      ) : connectors.length === 0 ? (
        <div className="text-center py-16 text-text-secondary">
          <Database className="w-10 h-10 mx-auto mb-3 text-text-muted" />
          <p className="font-medium">No connectors yet</p>
          <p className="text-sm mt-1">Add your first database connector to get started</p>
        </div>
      ) : (
        <div className="space-y-3">
          {connectors.map((c: any) => {
            const typeInfo = DB_TYPES.find(t => t.value === c.type)
            const categoryColor = CATEGORY_COLORS[typeInfo?.category || ''] || 'bg-bg-surface text-text-secondary'
            const testResult = testResults[c.id]
            const schemaResult = schemaStatus[c.id]
            const myPerm = myPerms.find((p: any) => p.connector_id === c.id)

            return (
              <div key={c.id} className="bg-bg-card border border-border-default rounded-xl overflow-hidden shadow-sm">
                <div className="flex items-center px-5 py-4 gap-4">
                  <div className="w-9 h-9 bg-accent-50 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Database className="w-5 h-5 text-accent-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-text-primary text-sm">{c.name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${categoryColor}`}>
                        {c.type}
                      </span>
                      {!c.is_active && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">inactive</span>
                      )}
                      {/* Policy badge */}
                      {c.is_open_access ? (
                        <span className="text-xs px-2.5 py-0.5 rounded-full bg-red-100 text-red-800 font-medium flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" /> Open Access
                        </span>
                      ) : (
                        <span className="text-xs px-2.5 py-0.5 rounded-full bg-green-100 text-green-800 font-medium flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" /> Closed
                        </span>
                      )}
                      {/* Expiration badge */}
                      {myPerm?.expires_at && (() => {
                        const parsedDate = parseUTC(myPerm.expires_at)
                        return (
                          <span
                            className="text-xs px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 font-semibold flex items-center gap-1 border border-amber-300 shadow-sm animate-pulse"
                            title={`Expires: ${parsedDate ? parsedDate.toLocaleString() : ''}`}
                          >
                            <Clock className="w-3 h-3 text-amber-600" />
                            {getRemainingTime(myPerm.expires_at)}
                            {parsedDate && ` (${parsedDate.toLocaleDateString()} ${parsedDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})`}
                          </span>
                        )
                      })()}
                    </div>
                    <p className="text-xs text-text-muted mt-0.5">
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
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 border border-border-default rounded-lg hover:bg-bg-surface text-text-secondary transition-colors"
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
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 border border-border-default rounded-lg hover:bg-bg-surface text-text-secondary transition-colors"
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
                        className="text-text-muted hover:text-accent-500 p-1 transition-colors"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
                      className="text-text-muted hover:text-text-secondary p-1"
                    >
                      {expandedId === c.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                    {canDelete && (
                      <button
                        onClick={() => {
                          setConfirmModal({
                            isOpen: true,
                            title: 'Delete Database Connector',
                            message: `Are you sure you want to delete the database connector "${c.name}"? This action is irreversible.`,
                            onConfirm: () => {
                              deleteMutation.mutate(c.id)
                              setConfirmModal(prev => ({ ...prev, isOpen: false }))
                            }
                          })
                        }}
                        className="text-text-muted hover:text-red-500 p-1 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded schema view */}
                {expandedId === c.id && c.schema_cached_at && (
                  <div className="border-t border-border-muted px-5 py-4 bg-bg-surface">
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
            <div className="relative bg-bg-card rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
              <div className="flex items-center justify-between px-6 py-4 border-b border-border-muted sticky top-0 bg-bg-card z-10">
                <div>
                  <h3 className="text-lg font-semibold text-text-primary">Edit Connector</h3>
                  <p className="text-sm text-text-secondary mt-0.5">{editTarget.type}</p>
                </div>
                <button className="p-1 rounded-md hover:bg-bg-surface" onClick={() => setEditTarget(null)}>
                  <X className="w-5 h-5 text-text-muted" />
                </button>
              </div>
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-xs font-medium text-text-primary mb-1">Display Name</label>
                  <input value={editTarget.name} onChange={e => setEditTarget(p => p ? { ...p, name: e.target.value } : p)}
                    className="input" />
                </div>
                {editTarget.type === 'sqlite' ? (
                  <SqliteConnectorForm
                    sqliteMode={editSqliteMode}
                    setSqliteMode={setEditSqliteMode}
                    sqliteFile={editSqliteFile}
                    setSqliteFile={setEditSqliteFile}
                    sqlitePath={editTarget.config.path || ''}
                    setSqlitePath={(newPath) => setEditTarget(prev => prev ? { ...prev, config: { ...prev.config, path: newPath } } : prev)}
                    isEdit={true}
                    existingPath={editTarget.config.path}
                  />
                ) : (
                  editType?.fieldGroups.map((group, gi) => (
                    <div key={gi}>
                      {group.title && <p className="form-section-label">{group.title}</p>}
                      <div className="grid grid-cols-2 gap-3">
                        {group.fields.map(field => (
                          <div key={field.key} className={field.fullWidth ? 'col-span-2' : ''}>
                            <label className="block text-xs font-medium text-text-primary mb-1">{field.label}</label>
                            {field.type === 'select' && field.options ? (
                              <select value={editTarget.config[field.key] || ''}
                                onChange={e => setEditTarget(p => p ? { ...p, config: { ...p.config, [field.key]: e.target.value } } : p)}
                                className="input">
                                {field.options.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                              </select>
                            ) : (
                              <div className="relative">
                                <input type={field.secret && !showSecrets[`edit_${field.key}`] ? 'password' : 'text'}
                                  value={editTarget.config[field.key] || ''}
                                  onChange={e => setEditTarget(p => p ? { ...p, config: { ...p.config, [field.key]: e.target.value } } : p)}
                                  className="input pr-8" />
                                {field.secret && (
                                  <button type="button" onClick={() => setShowSecrets(s => ({ ...s, [`edit_${field.key}`]: !s[`edit_${field.key}`] }))}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary">
                                    {showSecrets[`edit_${field.key}`] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                )}

                {/* Policy Toggle Section */}
                <div className="border-t border-border-default pt-4 mt-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="block text-xs font-medium text-text-primary mb-0.5">Default Access Policy</label>
                      <p className="text-xs text-text-secondary">
                        {editTarget.default_policy === 'deny_all'
                          ? 'Only explicitly granted users can access'
                          : 'All authenticated users can access (open)'}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleTogglePolicy(editTarget)}
                      disabled={updatePolicyMutation.isPending}
                      className={clsx(
                        'px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                        editTarget.default_policy === 'deny_all'
                          ? 'bg-green-100 text-green-800 hover:bg-green-200'
                          : 'bg-red-100 text-red-800 hover:bg-red-200',
                        updatePolicyMutation.isPending && 'opacity-50 cursor-not-allowed'
                      )}
                    >
                      {updatePolicyMutation.isPending ? 'Updating...' : (editTarget.default_policy === 'deny_all' ? 'Open Access' : 'Close Access')}
                    </button>
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border-muted bg-bg-surface sticky bottom-0">
                <button className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary" onClick={() => setEditTarget(null)}>Cancel</button>
                <button className="btn-primary flex items-center gap-2"
                  disabled={isSaving}
                  onClick={handleUpdate}>
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : null} Save Changes
                </button>
              </div>
            </div>
          </div>
        )
      })()}

      {/* Policy Change Confirmation Dialog */}
      {showPolicyDialog && selectedConnectorForPolicy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowPolicyDialog(false)} />
          <div className="relative bg-bg-card rounded-xl shadow-2xl w-full max-w-sm mx-4">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-muted">
              <h3 className="text-lg font-semibold text-text-primary">Open Access Warning</h3>
              <button className="p-1 rounded-md hover:bg-bg-surface" onClick={() => setShowPolicyDialog(false)}>
                <X className="w-5 h-5 text-text-muted" />
              </button>
            </div>
            <div className="px-6 py-4">
              <div className="flex items-start gap-3 mb-4">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-text-primary font-medium mb-1">Allow all authenticated users?</p>
                  <p className="text-sm text-text-secondary">
                    This will allow <strong>all authenticated users</strong> to query <strong>{selectedConnectorForPolicy.name}</strong> until explicit rules are added.
                  </p>
                </div>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border-muted bg-bg-surface">
              <button
                className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary font-medium"
                onClick={() => setShowPolicyDialog(false)}
              >
                Cancel
              </button>
              <button
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
                onClick={confirmPolicyChange}
                disabled={updatePolicyMutation.isPending}
              >
                {updatePolicyMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {updatePolicyMutation.isPending ? 'Updating...' : 'Confirm - Open Access'}
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-[2px] transition-all duration-300 animate-fade-in">
          <div className="bg-white rounded-lg shadow-xl border border-border-default max-w-sm w-full p-6 animate-scale-in">
            <div className="flex items-center gap-3 text-red-600 mb-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              <h3 className="text-base font-bold text-gray-900">{confirmModal.title}</h3>
            </div>
            <p className="text-xs text-text-secondary mb-5 leading-relaxed">
              {confirmModal.message}
            </p>
            <div className="flex justify-end gap-2.5">
              <button
                type="button"
                className="btn-secondary text-xs px-3.5 py-1.5"
                onClick={() => setConfirmModal(prev => ({ ...prev, isOpen: false }))}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger text-xs px-3.5 py-1.5"
                onClick={confirmModal.onConfirm}
              >
                Delete Connector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SchemaPreview({ connectorId }: { connectorId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['schema', connectorId],
    queryFn: () => api.get(`/api/connectors/${connectorId}/schema`).then(r => r.data),
  })

  if (isLoading) return <div className="flex items-center gap-2 text-xs text-text-muted"><Loader2 className="w-3 h-3 animate-spin" /> Loading schema...</div>
  if (!data?.tables?.length) return <p className="text-xs text-text-muted">No tables found</p>

  return (
    <div>
      <p className="text-xs font-semibold text-text-secondary mb-2">{data.tables.length} tables</p>
      <div className="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto">
        {data.tables.map((t: any) => (
          <div key={t.name} className="bg-bg-card border border-border-default rounded-lg p-2">
            <p className="text-xs font-semibold text-text-primary mb-1">
              {t.schema ? `${t.schema}.` : ''}{t.name}
              {t.row_count > 0 && <span className="text-text-muted font-normal ml-1">({t.row_count.toLocaleString()} rows)</span>}
            </p>
            <div className="space-y-0.5">
              {t.columns.slice(0, 6).map((c: any) => (
                <div key={c.name} className="flex items-center gap-1.5 text-xs">
                  {c.primary_key && <span className="text-yellow-500 text-xs font-mono font-bold">PK</span>}
                  <span className="text-text-primary">{c.name}</span>
                  <span className="text-text-muted text-xs">{c.type}</span>
                </div>
              ))}
              {t.columns.length > 6 && (
                <p className="text-xs text-text-muted">+{t.columns.length - 6} more</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

interface SqliteConnectorFormProps {
  sqliteMode: 'upload' | 'path'
  setSqliteMode: (mode: 'upload' | 'path') => void
  sqliteFile: File | null
  setSqliteFile: (file: File | null) => void
  sqlitePath: string
  setSqlitePath: (path: string) => void
  isEdit?: boolean
  existingPath?: string
}

const isUploadedPath = (path: string) => {
  if (!path) return false
  return path.startsWith('/data/sqlite/') || /^[a-f0-9]{12}_/.test(path.split('/').pop() || '')
}

const getSqliteFileName = (path: string) => {
  if (!path) return ''
  const parts = path.split('/')
  const lastPart = parts[parts.length - 1]
  const match = lastPart.match(/^[a-f0-9]{12}_(.+)$/)
  return match ? match[1] : lastPart
}

export function SqliteConnectorForm({
  sqliteMode,
  setSqliteMode,
  sqliteFile,
  setSqliteFile,
  sqlitePath,
  setSqlitePath,
  isEdit = false,
  existingPath = ''
}: SqliteConnectorFormProps) {
  const currentFileName = getSqliteFileName(existingPath)
  const isUploaded = isUploadedPath(existingPath)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSqliteFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSqliteFile(e.target.files[0])
    }
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const isTooLarge = sqliteFile ? sqliteFile.size > 500 * 1024 * 1024 : false

  return (
    <div className="space-y-4 col-span-2">
      <div className="flex items-center justify-between border-b border-border-default pb-2">
        <label className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono">
          SQLite Setup Method
        </label>
        <div className="flex bg-bg-surface rounded-lg p-0.5 text-xs font-medium">
          <button
            type="button"
            onClick={() => setSqliteMode('upload')}
            className={clsx(
              'px-3 py-1 rounded-md transition-all',
              sqliteMode === 'upload' ? 'bg-bg-card shadow-sm text-accent-600' : 'text-text-secondary hover:text-text-primary'
            )}
          >
            Upload File
          </button>
          <button
            type="button"
            onClick={() => setSqliteMode('path')}
            className={clsx(
              'px-3 py-1 rounded-md transition-all',
              sqliteMode === 'path' ? 'bg-bg-card shadow-sm text-accent-600' : 'text-text-secondary hover:text-text-primary'
            )}
          >
            Server File Path
          </button>
        </div>
      </div>

      {sqliteMode === 'upload' ? (
        <div className="space-y-3">
          {sqliteFile ? (
            <div className={clsx(
              "border rounded-xl p-4 flex items-center justify-between shadow-sm transition-all duration-200",
              isTooLarge ? "border-red-200 bg-red-50/50" : "border-emerald-200 bg-emerald-50/50"
            )}>
              <div className="flex items-center gap-3">
                <div className={clsx(
                  "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0",
                  isTooLarge ? "bg-red-100 text-red-600" : "bg-emerald-100 text-emerald-600"
                )}>
                  <Database className="w-5 h-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-text-primary truncate max-w-[220px]">{sqliteFile.name}</p>
                  <p className="text-xs text-text-secondary mt-0.5">{formatBytes(sqliteFile.size)}</p>
                </div>
              </div>
              
              <div className="flex items-center gap-2 flex-shrink-0">
                {isTooLarge ? (
                  <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-red-100 text-red-800">
                    Too Large (&gt;500MB)
                  </span>
                ) : (
                  <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 flex items-center gap-1">
                    <CheckCircle className="w-3 h-3" /> Ready
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => setSqliteFile(null)}
                  className="text-text-muted hover:text-text-secondary p-1 rounded-full hover:bg-bg-card transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          ) : isEdit && isUploaded && !sqliteFile ? (
            <div className="border border-accent-100 bg-accent-50 rounded-xl p-4 flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 bg-accent-100 text-accent-600 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Database className="w-5 h-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-text-primary truncate max-w-[220px]">{currentFileName}</p>
                  <p className="text-xs text-text-secondary mt-0.5">Currently stored database file</p>
                </div>
              </div>
              <label className="text-xs font-semibold text-accent-600 hover:text-accent-700 bg-bg-card border border-accent-200 px-3 py-1.5 rounded-lg cursor-pointer hover:shadow-sm transition-all flex-shrink-0">
                Replace File
                <input
                  type="file"
                  accept=".db,.sqlite,.sqlite3"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </label>
            </div>
          ) : (
            <div
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className="border-2 border-dashed border-border-strong rounded-xl p-6 text-center hover:border-accent-500 hover:bg-accent-50 transition-all cursor-pointer relative"
            >
              <input
                type="file"
                accept=".db,.sqlite,.sqlite3"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFileChange}
              />
              <div className="w-12 h-12 bg-bg-surface rounded-xl flex items-center justify-center mx-auto mb-3 border border-border-muted">
                <Plus className="w-6 h-6 text-text-muted" />
              </div>
              <p className="text-sm font-medium text-text-primary">
                Drag and drop your SQLite database here, or <span className="text-accent-600 font-semibold">browse</span>
              </p>
              <p className="text-xs text-text-muted mt-1">
                Accepts .db, .sqlite, .sqlite3 (Max size: 500MB)
              </p>
            </div>
          )}

          {isTooLarge && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800">File size exceeds limit</p>
                <p className="text-xs text-red-600 mt-1 leading-relaxed">
                  The file you selected is too large to be uploaded. Database uploads are capped at 500MB.
                  For larger files, we recommend copying the database to the server manually and using the
                  <strong> Server File Path</strong> option instead.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setSqliteMode('path');
                    setSqliteFile(null);
                  }}
                  className="mt-3 text-xs font-semibold text-red-700 hover:text-red-800 bg-bg-card border border-red-200 px-3 py-1.5 rounded-lg shadow-sm hover:shadow transition-all"
                >
                  Switch to Server File Path
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-1">
          <label className="block text-xs font-medium text-text-primary">
            Database File Path <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={sqlitePath}
            onChange={(e) => setSqlitePath(e.target.value)}
            placeholder="e.g. /data/sqlite/my_database.db"
            required
            className="input"
          />
          <p className="help-text font-sans">
            Provide the absolute path to the SQLite file accessible by the backend server.
          </p>
        </div>
      )}
    </div>
  )
}
