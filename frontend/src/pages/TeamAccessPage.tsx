import { useState, useMemo, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Users, Shield, Table, Trash2, Check, AlertCircle, AlertTriangle, ShieldAlert,
  ChevronDown, Database, Plus, CheckCircle, Loader2, ArrowRight
} from 'lucide-react'
import api from '../lib/api'
import { useAuthStore } from '../store/auth'
import { MultiSelect } from '../components/MultiSelect'
import toast from 'react-hot-toast'
import clsx from 'clsx'

interface DirectReport {
  user_id: string
  full_name: string
  email: string
  connector_permission: {
    can_read: boolean
    can_create: boolean
    can_update: boolean
    can_delete: boolean
    granted_by_caller: boolean
  } | null
  table_permissions: Array<{
    table_name: string
    can_read: boolean
    can_create: boolean
    can_update: boolean
    can_delete: boolean
    granted_by_caller: boolean
  }>
}

export function TeamAccessPage() {
  const { connectorId = '' } = useParams<{ connectorId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { user: me } = useAuthStore()

  const [selectedReportId, setSelectedReportId] = useState<string>('')
  const [selectedTablesToDelete, setSelectedTablesToDelete] = useState<string[]>([])

  useEffect(() => {
    setSelectedTablesToDelete([])
  }, [selectedReportId, connectorId])
  
  // Table grant form state
  const [targetTables, setTargetTables] = useState<string[]>([])
  const [tablePerms, setTablePerms] = useState({
    can_read: true,
    can_create: false,
    can_update: false,
    can_delete: false,
  })

  // Connector Grant form state (temp state when editing)
  const [connectorForm, setConnectorForm] = useState({
    can_read: true,
    can_create: false,
    can_update: false,
    can_delete: false,
  })

  // Custom confirmation modal state
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => { },
  })

  // Get connectors to match names and list sharing options
  const { data: connectors = [] } = useQuery<any[]>({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  // Filter connectors to only those where user has allow_share_access
  const shareAccessConnectors = useMemo(() => {
    const ids = new Set(me?.share_access_connector_ids || [])
    return connectors.filter(c => ids.has(c.id))
  }, [connectors, me?.share_access_connector_ids])

  const activeConnector = useMemo(() => {
    return connectors.find(c => c.id === connectorId)
  }, [connectors, connectorId])

  // Get caller's own permissions for this connector to enforce limits
  const { data: myPermissions = [] } = useQuery<any[]>({
    queryKey: ['my-permissions'],
    queryFn: () => api.get('/api/permissions/my-permissions').then(r => r.data),
  })

  const myConnectorPerm = useMemo(() => {
    return myPermissions.find(p => p.connector_id === connectorId)
  }, [myPermissions, connectorId])

  // Get list of direct reports and their permissions for this connector
  const { data: reports = [], isLoading: isReportsLoading, refetch: refetchReports } = useQuery<DirectReport[]>({
    queryKey: ['scoped-admin-reports', connectorId],
    queryFn: () => api.get(`/api/connectors/${connectorId}/scoped-admin/reports/`).then(r => r.data),
    enabled: !!connectorId,
  })

  // Get connector schema tables to populate table selector
  const { data: schemaData } = useQuery({
    queryKey: ['connectorSchema', connectorId],
    queryFn: () => api.get(`/api/connectors/${connectorId}/schema`).then(r => r.data),
    enabled: !!connectorId,
  })

  const availableTables = useMemo(() => {
    if (!schemaData?.tables) return []
    return schemaData.tables.map((t: any) => t.schema ? `${t.schema}.${t.name}` : t.name)
  }, [schemaData])

  const tableOptions = useMemo(() => {
    return availableTables.map((t: string) => ({ id: t, label: t }))
  }, [availableTables])

  const selectedReport = useMemo(() => {
    return reports.find(r => r.user_id === selectedReportId)
  }, [reports, selectedReportId])

  // Synchronize connector access form when selecting a report
  useMemo(() => {
    if (selectedReport) {
      if (selectedReport.connector_permission) {
        setConnectorForm({
          can_read: selectedReport.connector_permission.can_read,
          can_create: selectedReport.connector_permission.can_create,
          can_update: selectedReport.connector_permission.can_update,
          can_delete: selectedReport.connector_permission.can_delete,
        })
      } else {
        setConnectorForm({
          can_read: true,
          can_create: false,
          can_update: false,
          can_delete: false,
        })
      }
    }
  }, [selectedReport])

  // Mutations
  const grantConnectorAccess = useMutation({
    mutationFn: (payload: any) =>
      api.post(`/api/connectors/${connectorId}/scoped-admin/connector-access/`, payload),
    onSuccess: () => {
      refetchReports()
      toast.success('Connector permissions updated')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to update connector permissions')
    }
  })

  const revokeConnectorAccess = useMutation({
    mutationFn: (targetUserId: string) =>
      api.delete(`/api/connectors/${connectorId}/scoped-admin/connector-access/${targetUserId}/`),
    onSuccess: () => {
      refetchReports()
      toast.success('Connector permissions revoked')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to revoke connector permissions')
    }
  })

  const grantTableAccess = useMutation({
    mutationFn: async (payload: { target_user_id: string; table_names: string[]; can_read: boolean; can_create: boolean; can_update: boolean; can_delete: boolean }) => {
      const { table_names, ...rest } = payload
      await Promise.all(table_names.map(tName =>
        api.post(`/api/connectors/${connectorId}/scoped-admin/table-access/`, {
          ...rest,
          table_name: tName,
        })
      ))
    },
    onSuccess: () => {
      refetchReports()
      setTargetTables([])
      setTablePerms({
        can_read: true,
        can_create: false,
        can_update: false,
        can_delete: false,
      })
      toast.success('Table permissions granted')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to grant table permissions')
    }
  })

  const revokeTableAccess = useMutation({
    mutationFn: ({ targetUserId, tableName }: { targetUserId: string; tableName: string }) =>
      api.delete(`/api/connectors/${connectorId}/scoped-admin/table-access/${targetUserId}/`, {
        data: { table_name: tableName }
      }),
    onSuccess: () => {
      refetchReports()
      toast.success('Table permission revoked')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to revoke table permission')
    }
  })

  const bulkRevokeTableAccess = useMutation({
    mutationFn: (tableNames: string[]) =>
      api.post(`/api/connectors/${connectorId}/scoped-admin/table-access/${selectedReportId}/bulk-revoke`, { table_names: tableNames }),
    onSuccess: () => {
      refetchReports()
      setSelectedTablesToDelete([])
      toast.success('Selected table permissions revoked')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to revoke permissions')
    }
  })

  const handleConnectorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextId = e.target.value
    if (nextId) {
      navigate(`/connectors/${nextId}/team-access`)
      setSelectedReportId('')
    }
  }

  // Permission checks helper
  const canGrantFlag = (flag: 'can_read' | 'can_create' | 'can_update' | 'can_delete') => {
    if (me?.is_superadmin) return true
    return !!myConnectorPerm?.[flag]
  }

  return (
    <div className="h-full flex flex-col bg-bg-surface">
      {/* Header Panel */}
      <div className="px-6 py-5 flex-shrink-0 border-b border-border-default bg-bg-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="headline-lg flex items-center gap-2">
            <Users className="w-6 h-6 text-accent-500" />
            Team Share Access Manager
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Grant direct user-level access to your reports for shared connectors.
          </p>
        </div>

        {/* Connector Picker */}
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Select Shared Connector:</label>
          <div className="relative">
            <select
              value={connectorId}
              onChange={handleConnectorChange}
              className="appearance-none input py-2 pl-4 pr-10 bg-bg-surface border border-border-default rounded-lg text-sm font-medium focus:ring-2 focus:ring-accent-500 focus:border-accent-500"
            >
              {shareAccessConnectors.map(c => (
                <option key={c.id} value={c.id}>{c.name} ({c.type})</option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-text-secondary absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Main Content Split */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        
        {/* Left Panel: Direct Reports */}
        <div className="w-80 border-r border-border-default bg-bg-card flex flex-col flex-shrink-0">
          <div className="p-4 border-b border-border-muted bg-gray-50/50">
            <h2 className="text-xs font-bold text-text-secondary uppercase tracking-wider">Direct Reports</h2>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-border-muted">
            {isReportsLoading ? (
              <div className="flex flex-col items-center justify-center h-48 gap-2 text-text-secondary text-sm">
                <Loader2 className="w-6 h-6 animate-spin text-accent-500" />
                Loading direct reports...
              </div>
            ) : reports.length === 0 ? (
              <div className="p-6 text-center text-text-secondary text-xs italic">
                No active direct reports found.
              </div>
            ) : (
              reports.map(r => {
                const hasAccess = !!r.connector_permission
                return (
                  <button
                    key={r.user_id}
                    onClick={() => setSelectedReportId(r.user_id)}
                    className={clsx(
                      "w-full px-5 py-4 text-left transition-all hover:bg-gray-50 flex items-center justify-between",
                      selectedReportId === r.user_id ? "bg-accent-50/50 border-l-4 border-accent-500" : "border-l-4 border-transparent"
                    )}
                  >
                    <div>
                      <p className="font-semibold text-text-primary text-sm">{r.full_name}</p>
                      <p className="text-xs text-text-secondary mt-0.5">{r.email}</p>
                      <div className="flex gap-1.5 mt-2 flex-wrap">
                        {hasAccess ? (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-green-50 text-green-700 border border-green-200">
                            <Check className="w-2.5 h-2.5" /> Connector Access
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-150 text-gray-500 border border-gray-200">
                            No access
                          </span>
                        )}
                        {r.table_permissions.length > 0 && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-250">
                            {r.table_permissions.length} table rule{r.table_permissions.length > 1 ? 's' : ''}
                          </span>
                        )}
                      </div>
                    </div>
                    <ArrowRight className={clsx("w-4 h-4 transition-transform", selectedReportId === r.user_id ? "text-accent-500 translate-x-1" : "text-gray-300")} />
                  </button>
                )
              })
            )}
          </div>
        </div>

        {/* Right Panel: Selected Report Details & Permissions */}
        <div className="flex-1 flex flex-col min-w-0 bg-bg-surface overflow-y-auto">
          {!selectedReport ? (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center text-text-secondary">
              <div className="w-16 h-16 rounded-2xl bg-accent-50 flex items-center justify-center text-accent-500 mb-4 shadow-sm border border-accent-100">
                <Users className="w-8 h-8" />
              </div>
              <h3 className="font-bold text-text-primary text-base">Select a Team Member</h3>
              <p className="text-sm text-text-secondary mt-1 max-w-sm">
                Choose a direct report from the list on the left to configure their access rights.
              </p>
            </div>
          ) : (
            <div className="p-6 space-y-6 max-w-4xl">
              
              {/* Selected User Info Header Card */}
              <div className="bg-bg-card border border-border-default rounded-xl p-5 shadow-sm flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-text-primary">{selectedReport.full_name}</h2>
                  <p className="text-sm text-text-secondary mt-0.5">{selectedReport.email}</p>
                </div>
                <div className="text-right">
                  <span className="text-xs bg-gray-100 border border-gray-200 text-gray-655 px-2.5 py-1 rounded-full font-semibold font-mono">
                    Direct Report
                  </span>
                </div>
              </div>

              {/* Section 1: Connector Access */}
              <div className="bg-bg-card border border-border-default rounded-xl overflow-hidden shadow-sm">
                <div className="px-6 py-4 border-b border-border-muted flex items-center justify-between bg-gray-50/50">
                  <div className="flex items-center gap-2">
                    <Shield className="w-5 h-5 text-accent-500" />
                    <h3 className="font-bold text-text-primary">1. Connector-Level Access</h3>
                  </div>
                  {selectedReport.connector_permission?.granted_by_caller === false && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-250" title="This user's connector permission was granted at a higher level (e.g. by a superadmin) and cannot be modified or revoked by you.">
                      <ShieldAlert className="w-3.5 h-3.5" /> High-Level Managed
                    </span>
                  )}
                </div>

                <div className="p-6 space-y-6">
                  {/* Warning if higher level grant */}
                  {selectedReport.connector_permission && !selectedReport.connector_permission.granted_by_caller && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3 text-xs text-amber-800">
                      <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
                      <div>
                        <span className="font-bold">Managed at a higher level:</span> This report's connector-level permission record was granted by another manager or administrator. You do not have ownership of this permission record and cannot edit or revoke it.
                      </div>
                    </div>
                  )}

                  {/* Warning if manager lacks permissions */}
                  {!me?.is_superadmin && (
                    <div className="bg-gray-50 border border-border-default rounded-lg px-4 py-3 flex gap-2.5 text-xs text-text-secondary">
                      <AlertCircle className="w-4 h-4 text-text-secondary mt-0.5 flex-shrink-0" />
                      <div>
                        You can only grant permissions that you currently hold. Toggles for operations you lack (
                        <span className="font-semibold text-text-primary">
                          {['can_read', 'can_create', 'can_update', 'can_delete']
                            .filter(f => !canGrantFlag(f as any))
                            .map(f => f.replace('can_', '').toUpperCase())
                            .join(', ') || 'none'}
                        </span>
                        ) are disabled.
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    {(['can_read', 'can_create', 'can_update', 'can_delete'] as const).map(flag => {
                      const labelMap = { can_read: 'READ', can_create: 'CREATE', can_update: 'UPDATE', can_delete: 'DELETE' }
                      const hasOwnership = !selectedReport.connector_permission || selectedReport.connector_permission.granted_by_caller
                      const allowedByCallerScope = canGrantFlag(flag)
                      const isEditable = hasOwnership && allowedByCallerScope

                      return (
                        <label
                          key={flag}
                          className={clsx(
                            "flex items-center justify-between p-4 border rounded-xl cursor-pointer select-none transition-all",
                            connectorForm[flag]
                              ? "bg-accent-50/30 border-accent-500/30 text-accent-700 shadow-inner-sm"
                              : "border-border-default bg-bg-surface hover:bg-gray-50",
                            !isEditable && "opacity-50 cursor-not-allowed"
                          )}
                        >
                          <div>
                            <p className="font-bold text-xs uppercase tracking-wider">{labelMap[flag]}</p>
                            <p className="text-[10px] text-text-secondary mt-0.5">
                              {!allowedByCallerScope ? 'Not in your scope' : 'Allowed'}
                            </p>
                          </div>
                          <input
                            type="checkbox"
                            className="w-4.5 h-4.5 rounded border-gray-300 text-accent-600 focus:ring-accent-500"
                            checked={connectorForm[flag]}
                            onChange={e => {
                              if (isEditable) {
                                setConnectorForm({ ...connectorForm, [flag]: e.target.checked })
                              }
                            }}
                            disabled={!isEditable}
                          />
                        </label>
                      )
                    })}
                  </div>

                  <div className="flex items-center justify-between border-t border-border-muted pt-5">
                    {selectedReport.connector_permission?.granted_by_caller && (
                      <button
                        type="button"
                        onClick={() => {
                          setConfirmModal({
                            isOpen: true,
                            title: 'Revoke Connector Access',
                            message: 'Are you sure you want to revoke this connector access? This will also delete any table permissions you granted for this user.',
                            onConfirm: () => {
                              revokeConnectorAccess.mutate(selectedReport.user_id)
                              setConfirmModal(prev => ({ ...prev, isOpen: false }))
                            }
                          })
                        }}
                        disabled={revokeConnectorAccess.isPending}
                        className="btn-danger flex items-center gap-1.5 text-xs py-2 px-4"
                      >
                        <Trash2 className="w-4 h-4" />
                        Revoke Connector Access
                      </button>
                    )}
                    <div className="flex-1" />
                    {(!selectedReport.connector_permission || selectedReport.connector_permission.granted_by_caller) && (
                      <button
                        type="button"
                        onClick={() => {
                          grantConnectorAccess.mutate({
                            target_user_id: selectedReport.user_id,
                            ...connectorForm
                          })
                        }}
                        disabled={grantConnectorAccess.isPending}
                        className="btn-primary flex items-center gap-1.5 text-xs py-2 px-4 shadow-sm"
                      >
                        <CheckCircle className="w-4 h-4" />
                        {grantConnectorAccess.isPending ? 'Saving...' : selectedReport.connector_permission ? 'Update Access' : 'Grant Access'}
                      </button>
                    )}
                  </div>

                </div>
              </div>

              {/* Section 2: Table Access */}
              <div className="bg-bg-card border border-border-default rounded-xl overflow-hidden shadow-sm">
                <div className="px-6 py-4 border-b border-border-muted flex items-center justify-between bg-gray-50/50">
                  <div className="flex items-center gap-2">
                    <Table className="w-5 h-5 text-accent-500" />
                    <h3 className="font-bold text-text-primary">2. Table-Level Permissions</h3>
                  </div>
                </div>

                <div className="p-6 space-y-6">
                  {/* Grant Table Access Form */}
                  <div className="p-5 border border-border-default rounded-xl bg-gray-50/50 space-y-4">
                    <h4 className="font-bold text-text-primary text-xs uppercase tracking-wider">Grant Table Access Rule</h4>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Table Picker */}
                      <div>
                        <label className="label text-xs">Select Table(s) to Grant Access</label>
                        <MultiSelect
                          options={tableOptions}
                          value={targetTables}
                          onChange={setTargetTables}
                          placeholder="Select tables..."
                          className="bg-white"
                        />
                      </div>

                      {/* CRUD checkboxes */}
                      <div>
                        <label className="label text-xs">Table CRUD Scope</label>
                        <div className="flex flex-wrap items-center gap-4 bg-white border border-border-default rounded-lg px-4 py-2 h-[38px]">
                          {(['can_read', 'can_create', 'can_update', 'can_delete'] as const).map(flag => {
                            const isEditable = canGrantFlag(flag)
                            const labelMap = { can_read: 'R', can_create: 'C', can_update: 'U', can_delete: 'D' }
                            return (
                              <label key={flag} className={clsx("flex items-center gap-1 text-xs font-semibold cursor-pointer", !isEditable && "opacity-40 cursor-not-allowed")}>
                                <input
                                  type="checkbox"
                                  className="rounded border-gray-300 text-accent-600 focus:ring-accent-500"
                                  checked={tablePerms[flag]}
                                  onChange={e => isEditable && setTablePerms({ ...tablePerms, [flag]: e.target.checked })}
                                  disabled={!isEditable}
                                />
                                {labelMap[flag]}
                              </label>
                            )
                          })}
                        </div>
                      </div>
                    </div>

                    <div className="flex justify-end pt-2">
                      <button
                        type="button"
                        onClick={() => {
                          if (targetTables.length === 0) {
                            toast.error('Please select at least one table to grant permission.')
                            return
                          }
                          grantTableAccess.mutate({
                            target_user_id: selectedReport.user_id,
                            table_names: targetTables,
                            ...tablePerms
                          })
                        }}
                        disabled={grantTableAccess.isPending}
                        className="btn-primary flex items-center gap-1 text-xs py-2 px-4 shadow-sm"
                      >
                        <Plus className="w-4 h-4" />
                        {grantTableAccess.isPending ? 'Granting...' : 'Grant Table Permission'}
                      </button>
                    </div>
                  </div>

                  {/* Current Table Access List */}
                  <div className="space-y-3">
                    <h4 className="font-bold text-text-secondary text-xs uppercase tracking-wider">Current Table Rules for this User</h4>
                    
                    {selectedTablesToDelete.length > 0 && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center justify-between text-sm text-red-800 animate-fade-in">
                        <div className="flex items-center gap-2 font-medium">
                          <AlertTriangle className="w-4 h-4 text-red-650" />
                          <span>{selectedTablesToDelete.length} table rule(s) selected</span>
                        </div>
                        <button
                          onClick={() => {
                            setConfirmModal({
                              isOpen: true,
                              title: 'Revoke Selected Table Access Rules',
                              message: `Are you sure you want to revoke the selected ${selectedTablesToDelete.length} table access rules?`,
                              onConfirm: () => {
                                bulkRevokeTableAccess.mutate(selectedTablesToDelete)
                                setConfirmModal(prev => ({ ...prev, isOpen: false }))
                              }
                            })
                          }}
                          disabled={bulkRevokeTableAccess.isPending}
                          className="btn-danger py-1 px-3 text-xs font-semibold"
                        >
                          {bulkRevokeTableAccess.isPending ? 'Revoking...' : 'Revoke Selected'}
                        </button>
                      </div>
                    )}

                    {selectedReport.table_permissions.length === 0 ? (
                      <p className="text-xs text-text-secondary italic p-4 text-center border border-dashed border-border-default rounded-lg">
                        No custom table-level rules granted to this report.
                      </p>
                    ) : (
                      <div className="overflow-x-auto border border-border-default rounded-lg">
                        <table className="w-full text-left border-collapse">
                          <thead>
                            <tr className="bg-gray-50 border-b border-border-muted text-xs font-semibold text-text-secondary">
                              <th className="w-10 px-4 py-3 text-left">
                                <input
                                  type="checkbox"
                                  className="rounded border-gray-300 text-accent-600 focus:ring-accent-500 cursor-pointer"
                                  checked={
                                    selectedReport.table_permissions.length > 0 &&
                                    selectedReport.table_permissions.filter(tp => tp.granted_by_caller).length > 0 &&
                                    selectedReport.table_permissions.filter(tp => tp.granted_by_caller).every(tp => selectedTablesToDelete.includes(tp.table_name))
                                  }
                                  onChange={e => {
                                    if (e.target.checked) {
                                      const deletableNames = selectedReport.table_permissions
                                        .filter(tp => tp.granted_by_caller)
                                        .map(tp => tp.table_name)
                                      setSelectedTablesToDelete(deletableNames)
                                    } else {
                                      setSelectedTablesToDelete([])
                                    }
                                  }}
                                />
                              </th>
                              <th className="px-4 py-3">Table Name</th>
                              <th className="px-4 py-3 text-center w-24">READ</th>
                              <th className="px-4 py-3 text-center w-24">CREATE</th>
                              <th className="px-4 py-3 text-center w-24">UPDATE</th>
                              <th className="px-4 py-3 text-center w-24">DELETE</th>
                              <th className="px-4 py-3 text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border-muted text-sm text-text-primary">
                            {selectedReport.table_permissions.map(tp => (
                              <tr key={tp.table_name} className="hover:bg-gray-50/50">
                                <td className="w-10 px-4 py-3 text-left">
                                  {tp.granted_by_caller && (
                                    <input
                                      type="checkbox"
                                      className="rounded border-gray-300 text-accent-600 focus:ring-accent-500 cursor-pointer"
                                      checked={selectedTablesToDelete.includes(tp.table_name)}
                                      onChange={e => {
                                        if (e.target.checked) {
                                          setSelectedTablesToDelete(prev => [...prev, tp.table_name])
                                        } else {
                                          setSelectedTablesToDelete(prev => prev.filter(name => name !== tp.table_name))
                                        }
                                      }}
                                    />
                                  )}
                                </td>
                                <td className="px-4 py-3 font-mono text-xs">{tp.table_name}</td>
                                <td className="px-4 py-3 text-center">
                                  {tp.can_read ? <Check className="w-4 h-4 text-green-600 mx-auto" /> : <span className="text-gray-300">—</span>}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  {tp.can_create ? <Check className="w-4 h-4 text-green-600 mx-auto" /> : <span className="text-gray-300">—</span>}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  {tp.can_update ? <Check className="w-4 h-4 text-green-600 mx-auto" /> : <span className="text-gray-300">—</span>}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  {tp.can_delete ? <Check className="w-4 h-4 text-green-600 mx-auto" /> : <span className="text-gray-300">—</span>}
                                </td>
                                <td className="px-4 py-3 text-right">
                                  {tp.granted_by_caller ? (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setConfirmModal({
                                          isOpen: true,
                                          title: 'Revoke Table Access',
                                          message: `Are you sure you want to revoke permission for table "${tp.table_name}"?`,
                                          onConfirm: () => {
                                            revokeTableAccess.mutate({
                                              targetUserId: selectedReport.user_id,
                                              tableName: tp.table_name
                                            })
                                            setConfirmModal(prev => ({ ...prev, isOpen: false }))
                                          }
                                        })
                                      }}
                                      disabled={revokeTableAccess.isPending}
                                      className="text-red-500 hover:text-red-700 p-1 hover:bg-red-50 rounded"
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                  ) : (
                                    <span className="text-[10px] text-text-secondary bg-gray-100 border border-gray-200 px-2 py-0.5 rounded font-semibold" title="Granted by another administrator.">
                                      High-Level
                                    </span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                </div>
              </div>

            </div>
          )}
        </div>

      </div>

      {/* Custom Confirmation Modal */}
      {confirmModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-[2px] transition-all duration-300 animate-fade-in">
          <div className="bg-white rounded-lg shadow-xl border border-border-default max-w-sm w-full p-6 animate-scale-in text-on-surface">
            <div className="flex items-center gap-3 text-red-600 mb-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-600" />
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
                Confirm Revocation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
