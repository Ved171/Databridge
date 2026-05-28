import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Shield, Plus, Trash2, ToggleLeft, ToggleRight, ChevronDown, ChevronUp, Lock, Pencil } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/auth'

export function PermissionsPage() {
  const qc = useQueryClient()
  const { user: me } = useAuthStore()
  const [selectedConnector, setSelectedConnector] = useState<string>('')
  const [showRLSForm, setShowRLSForm] = useState(false)
  const [editingRLSId, setEditingRLSId] = useState<string | null>(null)
  const [rlsForm, setRlsForm] = useState({
    name: '', table_name: '', filter_expr: '', filter_expr_nosql: '',
    applies_to_user_id: '', applies_to_role: '',
  })

  const { data: connectors = [] } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get('/api/users/').then(r => r.data),
  })

  const { data: permissions = [], refetch: refetchPerms } = useQuery({
    queryKey: ['permissions', selectedConnector],
    queryFn: () => api.get(`/api/permissions/connector/${selectedConnector}`).then(r => r.data),
    enabled: !!selectedConnector,
  })

  const { data: rlsPolicies = [], refetch: refetchRLS } = useQuery({
    queryKey: ['rls', selectedConnector],
    queryFn: () => api.get(`/api/permissions/connector/${selectedConnector}/rls`).then(r => r.data),
    enabled: !!selectedConnector,
  })

  const upsertPerm = useMutation({
    mutationFn: (data: any) => api.put(`/api/permissions/connector/${selectedConnector}`, data),
    onSuccess: () => { refetchPerms(); toast.success('Permission saved') },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const revokePerm = useMutation({
    mutationFn: (userId: string) =>
      api.delete(`/api/permissions/connector/${selectedConnector}/user/${userId}`),
    onSuccess: () => { refetchPerms(); toast.success('Access revoked') },
  })

  const createRLS = useMutation({
    mutationFn: (data: any) => api.post(`/api/permissions/connector/${selectedConnector}/rls`, data),
    onSuccess: () => {
      refetchRLS()
      toast.success('RLS policy created')
      setShowRLSForm(false)
      setRlsForm({ name: '', table_name: '', filter_expr: '', filter_expr_nosql: '', applies_to_user_id: '', applies_to_role: '' })
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const updateRLS = useMutation({
    mutationFn: (data: any) => api.put(`/api/permissions/connector/${selectedConnector}/rls/${editingRLSId}`, data),
    onSuccess: () => {
      refetchRLS()
      toast.success('RLS policy updated')
      setShowRLSForm(false)
      setEditingRLSId(null)
      setRlsForm({ name: '', table_name: '', filter_expr: '', filter_expr_nosql: '', applies_to_user_id: '', applies_to_role: '' })
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const toggleRLS = useMutation({
    mutationFn: (policyId: string) =>
      api.patch(`/api/permissions/connector/${selectedConnector}/rls/${policyId}/toggle`),
    onSuccess: () => refetchRLS(),
  })

  const deleteRLS = useMutation({
    mutationFn: (policyId: string) =>
      api.delete(`/api/permissions/connector/${selectedConnector}/rls/${policyId}`),
    onSuccess: () => { refetchRLS(); toast.success('Policy deleted') },
  })

  const activeConnector = connectors.find((c: any) => c.id === selectedConnector)
  const isNoSQL = activeConnector && ['mongodb', 'elasticsearch', 'redis', 'salesforce'].includes(activeConnector.type.toLowerCase())
  const isRedis = activeConnector && activeConnector.type.toLowerCase() === 'redis'

  // Build permission map: userId → {can_create, can_read, can_update, can_delete}
  const permMap: Record<string, any> = {}
  permissions.forEach((p: any) => { permMap[p.user_id] = p })

  const handleTickChange = (userId: string, field: string, value: boolean) => {
    const existing = permMap[userId] || { can_create: false, can_read: true, can_update: false, can_delete: false }
    upsertPerm.mutate({ user_id: userId, ...existing, [field]: value })
  }

  const CRUD_FIELDS = [
    { key: 'can_create', label: 'CREATE', color: 'text-green-600' },
    { key: 'can_read',   label: 'READ',   color: 'text-blue-600' },
    { key: 'can_update', label: 'UPDATE', color: 'text-yellow-600' },
    { key: 'can_delete', label: 'DELETE', color: 'text-red-600' },
  ]

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Permissions</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Control user access to each connector with per-operation permissions and row-level security
        </p>
      </div>

      {/* Connector Selector */}
      <div className="card p-5 mb-6">
        <label className="label">Select Connector</label>
        <select
          className="input max-w-sm"
          value={selectedConnector}
          onChange={e => setSelectedConnector(e.target.value)}
        >
          <option value="">- choose a connector -</option>
          {connectors.map((c: any) => (
            <option key={c.id} value={c.id}>{c.name} ({c.type})</option>
          ))}
        </select>
      </div>

      {selectedConnector && (
        <>
          {/* ── CRUD Permission Matrix ── */}
          <div className="card mb-6">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-brand-600" />
                <h2 className="font-semibold text-gray-900">User Permissions</h2>
              </div>
              <p className="text-xs text-gray-400">Tick boxes to grant per-user access</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-64">
                      User
                    </th>
                    {CRUD_FIELDS.map(f => (
                      <th key={f.key} className="text-center px-6 py-3 text-xs font-semibold uppercase tracking-wider">
                        <span className={f.color}>{f.label}</span>
                      </th>
                    ))}
                    <th className="px-6 py-3 w-20" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {users.map((u: any) => {
                    const perm = permMap[u.id]
                    const hasAccess = !!perm
                    const myRole = me?.is_superadmin ? 'superadmin' : (me?.role || 'member')
                    const targetRole = u.is_superadmin ? 'superadmin' : (u.role || 'member')
                    const RANK: Record<string, number> = { superadmin: 4, admin: 3, workspace_admin: 2, member: 1 }
                    const isProtected = (RANK[targetRole] || 1) >= (RANK[myRole] || 1)
                    const isSelf = u.id === me?.id
                    const isDisabled = isProtected && !isSelf

                    return (
                      <tr key={u.id} className={`${hasAccess ? '' : 'opacity-50'} ${isDisabled ? 'bg-gray-50' : ''}`}>
                        <td className="px-6 py-3">
                          <div className="flex items-center gap-2">
                            <div>
                              <p className="text-sm font-medium text-gray-900">{u.name}</p>
                              <p className="text-xs text-gray-400">{u.email}</p>
                            </div>
                            {isDisabled && (
                              <Lock className="w-3.5 h-3.5 text-gray-400" title="Protected - higher or equal role" />
                            )}
                            {u.is_superadmin && (
                              <span className="text-xs bg-brand-100 text-brand-700 px-1.5 py-0.5 rounded-full">Admin</span>
                            )}
                          </div>
                        </td>
                        {CRUD_FIELDS.map(f => (
                          <td key={f.key} className="px-6 py-3 text-center">
                            <input
                              type="checkbox"
                              className="w-4 h-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                              checked={perm?.[f.key] ?? false}
                              onChange={e => handleTickChange(u.id, f.key, e.target.checked)}
                              disabled={isDisabled}
                            />
                          </td>
                        ))}
                        <td className="px-6 py-3 text-center">
                          {hasAccess && !isDisabled && (
                            <button
                              className="text-xs text-red-500 hover:text-red-700"
                              onClick={() => revokePerm.mutate(u.id)}
                            >
                              Revoke
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="px-6 py-3 bg-gray-50 border-t border-gray-100">
              <p className="text-xs text-gray-400">
                Tip: Superadmins always have full access. Tick any cell to immediately grant that permission.
              </p>
            </div>
          </div>

          {/* ── RLS Policies ── */}
          <div className="card">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-gray-900">Row-Level Security Policies</h2>
                <p className="text-xs text-gray-400 mt-0.5">
                  Automatically inject WHERE filters into queries for specific users or roles
                </p>
              </div>
              <button
                className="btn-primary text-sm flex items-center gap-1"
                onClick={() => {
                  setEditingRLSId(null)
                  setRlsForm({ name: '', table_name: '', filter_expr: '', filter_expr_nosql: '', applies_to_user_id: '', applies_to_role: '' })
                  setShowRLSForm(true)
                }}
              >
                <Plus className="w-3.5 h-3.5" /> Add Policy
              </button>
            </div>

            {/* RLS Form */}
            {showRLSForm && (
              <div className="px-6 py-5 border-b border-gray-100 bg-blue-50">
                <h3 className="font-medium text-gray-900 mb-4">{editingRLSId ? 'Edit RLS Policy' : 'New RLS Policy'}</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">Policy Name</label>
                    <input className="input" placeholder="e.g. Employee Dept Filter"
                      value={rlsForm.name} onChange={e => setRlsForm({ ...rlsForm, name: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">Table Name</label>
                    <input className="input" placeholder="e.g. employees (or Redis key prefix)"
                      value={rlsForm.table_name} onChange={e => setRlsForm({ ...rlsForm, table_name: e.target.value })} />
                  </div>
                  {isNoSQL ? (
                    isRedis ? (
                      <div className="col-span-2">
                        <label className="label">Allowed Key Pattern (Redis SCAN Glob pattern)</label>
                        <input className="input font-mono text-sm"
                          placeholder="org:{user.id}:*"
                          value={rlsForm.filter_expr_nosql}
                          onChange={e => setRlsForm({ ...rlsForm, filter_expr_nosql: e.target.value })} />
                        <p className="text-xs text-gray-400 mt-1">
                          Restricts key access. Supports: <code className="bg-gray-100 px-1 rounded">{'{user.id}'}</code>{' '}
                          <code className="bg-gray-100 px-1 rounded">{'{user.email}'}</code>
                        </p>
                      </div>
                    ) : (
                      <div className="col-span-2">
                        <div className="flex justify-between items-center mb-1">
                          <label className="label mb-0">Filter Expression (JSON object)</label>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              className="text-xs text-brand-600 hover:text-brand-700 font-medium bg-brand-50 px-2 py-0.5 rounded border border-brand-100"
                              onClick={() => {
                                const template = activeConnector?.type?.toLowerCase() === 'mongodb' ?
                                  '{\n  "field": "org_id",\n  "op": "eq",\n  "value": "{user.id}"\n}' :
                                  activeConnector?.type?.toLowerCase() === 'elasticsearch' ?
                                  '{\n  "field": "tenant_id",\n  "op": "eq",\n  "value": "{user.id}"\n}' :
                                  '{\n  "field": "OwnerId",\n  "op": "eq",\n  "value": "{user.id}"\n}';
                                setRlsForm({ ...rlsForm, filter_expr_nosql: template });
                              }}
                            >
                              Insert {activeConnector?.type} Template
                            </button>
                            <button
                              type="button"
                              className="text-xs text-brand-600 hover:text-brand-700 font-medium bg-brand-50 px-2 py-0.5 rounded border border-brand-100"
                              onClick={() => {
                                const template = '{\n  "org_id": "{user.id}"\n}';
                                setRlsForm({ ...rlsForm, filter_expr_nosql: template });
                              }}
                            >
                              Insert Raw Query Template
                            </button>
                          </div>
                        </div>
                        <textarea className="input font-mono text-sm h-32"
                          placeholder={`{\n  "field": "org_id",\n  "op": "eq",\n  "value": "{user.id}"\n}`}
                          value={rlsForm.filter_expr_nosql}
                          onChange={e => setRlsForm({ ...rlsForm, filter_expr_nosql: e.target.value })} />
                        <p className="text-xs text-gray-400 mt-1">
                          Supports structured op/value format or raw query. Resolved placeholders: <code className="bg-gray-100 px-1 rounded">{'{user.id}'}</code>{' '}
                          <code className="bg-gray-100 px-1 rounded">{'{user.email}'}</code>
                        </p>
                      </div>
                    )
                  ) : (
                    <div className="col-span-2">
                      <label className="label">Filter Expression (SQL WHERE fragment)</label>
                      <input className="input font-mono text-sm"
                        placeholder="department_id = '{user.id}' OR manager_email = '{user.email}'"
                        value={rlsForm.filter_expr}
                        onChange={e => setRlsForm({ ...rlsForm, filter_expr: e.target.value })} />
                      <p className="text-xs text-gray-400 mt-1">
                        Supports: <code className="bg-gray-100 px-1 rounded">{'{user.id}'}</code>{' '}
                        <code className="bg-gray-100 px-1 rounded">{'{user.email}'}</code>
                      </p>
                    </div>
                  )}
                  <div>
                    <label className="label">Apply to User (optional)</label>
                    <select className="input"
                      value={rlsForm.applies_to_user_id}
                      onChange={e => setRlsForm({ ...rlsForm, applies_to_user_id: e.target.value })}>
                      <option value="">All users</option>
                      {users.map((u: any) => (
                        <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label">Apply to Role (optional)</label>
                    <select className="input"
                      value={rlsForm.applies_to_role}
                      onChange={e => setRlsForm({ ...rlsForm, applies_to_role: e.target.value })}>
                      <option value="">Any role</option>
                      <option value="member">Member</option>
                      <option value="viewer">Viewer</option>
                      <option value="workspace_admin">Workspace Admin</option>
                    </select>
                  </div>
                </div>
                <div className="flex gap-3 mt-4">
                  <button className="btn-primary text-sm" onClick={() => {
                    let filterExprNosql = null
                    if (isNoSQL) {
                      if (isRedis) {
                        filterExprNosql = { key_pattern: rlsForm.filter_expr_nosql }
                      } else {
                        try {
                          filterExprNosql = rlsForm.filter_expr_nosql ? JSON.parse(rlsForm.filter_expr_nosql) : null
                        } catch (err) {
                          toast.error('Invalid JSON in NoSQL Filter Expression')
                          return
                        }
                      }
                    }
                    const payload = {
                      name: rlsForm.name,
                      table_name: rlsForm.table_name,
                      filter_expr: isNoSQL ? null : rlsForm.filter_expr,
                      filter_expr_nosql: isNoSQL ? filterExprNosql : null,
                      applies_to_user_id: rlsForm.applies_to_user_id || null,
                      applies_to_role: rlsForm.applies_to_role || null,
                    }
                    if (editingRLSId) {
                      updateRLS.mutate(payload)
                    } else {
                      createRLS.mutate(payload)
                    }
                  }} disabled={createRLS.isPending || updateRLS.isPending}>
                    {(createRLS.isPending || updateRLS.isPending) ? 'Saving...' : (editingRLSId ? 'Update Policy' : 'Save Policy')}
                  </button>
                  <button className="btn-secondary text-sm" onClick={() => {
                    setShowRLSForm(false)
                    setEditingRLSId(null)
                  }}>Cancel</button>
                </div>
              </div>
            )}

            {/* RLS List */}
            <div className="divide-y divide-gray-50">
              {rlsPolicies.length === 0 ? (
                <p className="px-6 py-8 text-center text-gray-400 text-sm">
                  No RLS policies. Add one to restrict row visibility per user.
                </p>
              ) : rlsPolicies.map((p: any) => (
                <div key={p.id} className="px-6 py-4 flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="font-medium text-gray-900 text-sm">{p.name}</p>
                      <span className={`badge ${p.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {p.is_active ? 'active' : 'disabled'}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">
                      Table/Prefix: <span className="font-mono font-medium text-gray-700">{p.table_name}</span>
                    </p>
                    {p.filter_expr_nosql ? (
                      <pre className="text-xs font-mono text-gray-500 bg-gray-50 rounded px-2 py-1 mt-1 overflow-x-auto whitespace-pre-wrap max-h-32">
                        {JSON.stringify(p.filter_expr_nosql, null, 2)}
                      </pre>
                    ) : (
                      <p className="text-xs font-mono text-gray-500 bg-gray-50 rounded px-2 py-1 mt-1 truncate">
                        WHERE {p.filter_expr}
                      </p>
                    )}
                    {p.applies_to_user_id && (
                      <p className="text-xs text-gray-400 mt-1">-&gt; User: {p.applies_to_user_id}</p>
                    )}
                    {p.applies_to_role && (
                      <p className="text-xs text-gray-400 mt-1">-&gt; Role: {p.applies_to_role}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => {
                        setEditingRLSId(p.id)
                        setRlsForm({
                          name: p.name,
                          table_name: p.table_name,
                          filter_expr: p.filter_expr || '',
                          filter_expr_nosql: p.filter_expr_nosql
                            ? (isRedis ? (p.filter_expr_nosql.key_pattern || '') : JSON.stringify(p.filter_expr_nosql, null, 2))
                            : '',
                          applies_to_user_id: p.applies_to_user_id || '',
                          applies_to_role: p.applies_to_role || '',
                        })
                        setShowRLSForm(true)
                      }}
                      className="text-gray-400 hover:text-indigo-600 transition-colors"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => toggleRLS.mutate(p.id)}
                      className="text-gray-400 hover:text-brand-600 transition-colors"
                      title={p.is_active ? 'Disable' : 'Enable'}
                    >
                      {p.is_active
                        ? <ToggleRight className="w-5 h-5 text-brand-600" />
                        : <ToggleLeft className="w-5 h-5" />
                      }
                    </button>
                    <button
                      onClick={() => { if (confirm('Delete this policy?')) deleteRLS.mutate(p.id) }}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
