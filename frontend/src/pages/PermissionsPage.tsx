import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Shield, Plus, Trash2, ChevronDown, ChevronUp, Lock, Table, AlertTriangle, Bug, ChevronRight, ArrowRight, Users, Search, CheckCircle, XCircle, Zap, Database, Pencil, X, Clock } from 'lucide-react'
import api from '../lib/api'
import { parseUTC, toLocalDateTimeString } from '../lib/utils'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/auth'
import { SearchableTableSelector } from '../components/SearchableTableSelector'
import { MultiSelect } from '../components/MultiSelect'

// parseUTC and toLocalDateTimeString are now imported from ../lib/utils
export { parseUTC, toLocalDateTimeString } from '../lib/utils'

export interface PermissionsPageProps {
  embedded?: boolean
  section?: 'connector' | 'table'
  selectedConnectorId?: string
  hideDebug?: boolean
  debugOnly?: boolean
}

export function PermissionsPage({
  embedded = false,
  section = 'connector',
  selectedConnectorId,
  hideDebug = false,
  debugOnly = false,
}: PermissionsPageProps = {}) {
  const qc = useQueryClient()
  const { user: me } = useAuthStore()
  const [internalSelectedConnector, setInternalSelectedConnector] = useState<string>('')
  const selectedConnector = embedded ? (selectedConnectorId ?? '') : internalSelectedConnector
  const setSelectedConnector = embedded ? () => { } : setInternalSelectedConnector

  // Advanced UX Collapsible States
  // (showUserAdvanced state removed — was unused dead code)
  const [expandedConnectorDepts, setExpandedConnectorDepts] = useState<Record<string, boolean>>({})
  const [expandedConnectorRoles, setExpandedConnectorRoles] = useState<Record<string, boolean>>({})
  const [expandedTableDepts, setExpandedTableDepts] = useState<Record<string, boolean>>({})
  const [expandedTableRoles, setExpandedTableRoles] = useState<Record<string, boolean>>({})

  const [showTableForm, setShowTableForm] = useState(false)
  const [showConnectorGrantsForm, setShowConnectorGrantsForm] = useState(false)
  const [connectorGrantsForm, setConnectorGrantsForm] = useState<{
    departments: { department_id: string; role_id?: string; is_deny: boolean; can_read: boolean; can_create: boolean; can_update: boolean; can_delete: boolean; valid_from?: string; expires_at?: string; grant_reason?: string }[];
    roles: { role_id: string; is_deny: boolean; can_read: boolean; can_create: boolean; can_update: boolean; can_delete: boolean; valid_from?: string; expires_at?: string; grant_reason?: string }[];
  }>({
    departments: [],
    roles: [],
  })
  const [scheduleEditUser, setScheduleEditUser] = useState<any | null>(null)
  const [modalPerms, setModalPerms] = useState({
    can_read: true,
    can_create: false,
    can_update: false,
    can_delete: false,
    allow_share_access: false,
  })
  const [modalValidFrom, setModalValidFrom] = useState('')
  const [modalExpiresAt, setModalExpiresAt] = useState('')
  const [modalGrantReason, setModalGrantReason] = useState('')
  const [userSearchQuery, setUserSearchQuery] = useState('')
  const [filterDeptId, setFilterDeptId] = useState('')
  const [filterRoleId, setFilterRoleId] = useState('')

  const openScheduleEditModal = (u: any) => {
    const perm = permMap[u.id]
    const activePerm = perm && perm.is_active ? perm : null
    setScheduleEditUser(u)
    setModalPerms({
      can_read: activePerm ? activePerm.can_read : true,
      can_create: activePerm ? activePerm.can_create : false,
      can_update: activePerm ? activePerm.can_update : false,
      can_delete: activePerm ? activePerm.can_delete : false,
      allow_share_access: activePerm ? activePerm.allow_share_access : false,
    })
    setModalValidFrom(activePerm && activePerm.valid_from ? toLocalDateTimeString(parseUTC(activePerm.valid_from)) : '')
    setModalExpiresAt(activePerm && activePerm.expires_at ? toLocalDateTimeString(parseUTC(activePerm.expires_at)) : '')
    setModalGrantReason(activePerm && activePerm.grant_reason ? activePerm.grant_reason : '')
  }

  const closeScheduleEditModal = () => {
    setScheduleEditUser(null)
    setModalValidFrom('')
    setModalExpiresAt('')
    setModalGrantReason('')
  }
  const [showExpiringBanner, setShowExpiringBanner] = useState(true)
  const [highlightExpiring, setHighlightExpiring] = useState(false)
  const [selectedTableGrantTables, setSelectedTableGrantTables] = useState<string[]>([])
  const [selectedTableIds, setSelectedTableIds] = useState<string[]>([])

  useEffect(() => {
    setSelectedTableIds([])
  }, [selectedConnector])
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({})
  const [tableForm, setTableForm] = useState<{
    table_name: string;
    applies_to_user_id: string;
    departments: { department_id: string; role_id?: string; is_deny: boolean; can_read: boolean; can_create: boolean; can_update: boolean; can_delete: boolean }[];
    roles: { role_id: string; is_deny: boolean; can_read: boolean; can_create: boolean; can_update: boolean; can_delete: boolean }[];
    can_read: boolean;
    can_create: boolean;
    can_update: boolean;
    can_delete: boolean;
  }>({
    table_name: '',
    applies_to_user_id: '',
    departments: [],
    roles: [],
    can_read: true,
    can_create: false,
    can_update: false,
    can_delete: false,
  })

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


  const { data: connectors = [] } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get('/api/users/').then(r => r.data),
  })

  const { data: departments = [] } = useQuery<any[]>({
    queryKey: ['departments'],
    queryFn: () => api.get('/api/departments/').then(r => r.data),
  })

  const { data: roles = [] } = useQuery<any[]>({
    queryKey: ['roles'],
    queryFn: () => api.get('/api/roles/').then(r => r.data),
  })

  const { data: assignments = [] } = useQuery<any[]>({
    queryKey: ['managerAssignments'],
    queryFn: () => api.get('/api/users/manager-assignments').then(r => r.data),
  })

  const managersSet = useMemo(() => {
    return new Set<string>(assignments.map((a: any) => a.manager_user_id))
  }, [assignments])

  const { data: permissions = [], refetch: refetchPerms } = useQuery({
    queryKey: ['permissions', selectedConnector],
    queryFn: () => api.get(`/api/permissions/connector/${selectedConnector}`).then(r => r.data),
    enabled: !!selectedConnector,
  })

  const { data: tablePermissions = [], refetch: refetchTables } = useQuery({
    queryKey: ['tablePermissions', selectedConnector],
    queryFn: () => api.get(`/api/permissions/tables/?connector_id=${selectedConnector}`).then(r => r.data),
    enabled: !!selectedConnector,
  })

  const { data: connectorGrants = {}, refetch: refetchConnectorGrants } = useQuery({
    queryKey: ['connectorGrants', selectedConnector],
    queryFn: () => api.get(`/api/permissions/connector/${selectedConnector}/grants`).then(r => r.data),
    enabled: !!selectedConnector,
  })

  const { data: schemaData } = useQuery({
    queryKey: ['connectorSchema', selectedConnector],
    queryFn: () => api.get(`/api/connectors/${selectedConnector}/schema`).then(r => r.data),
    enabled: !!selectedConnector,
  })
  const allConnectorTables = (schemaData?.tables || []).map((t: any) => t.schema ? `${t.schema}.${t.name}` : t.name)

  const { data: expiringGrants = { user_grants: [], dept_grants: [], role_grants: [] }, refetch: refetchExpiring } = useQuery({
    queryKey: ['expiringGrants'],
    queryFn: () => api.get('/api/permissions/expiring?within_hours=24').then(r => r.data),
    enabled: me?.is_superadmin,
  })

  const invalidateAllAccess = () => {
    qc.invalidateQueries({ queryKey: ['permissions'] })
    qc.invalidateQueries({ queryKey: ['tablePermissions'] })
    qc.invalidateQueries({ queryKey: ['connectorGrants'] })
    qc.invalidateQueries({ queryKey: ['accessPackages'] })
  }

  const revokeUserPerm = useMutation({
    mutationFn: (permId: string) => api.post(`/api/permissions/connector/${permId}/revoke`),
    onSuccess: () => {
      invalidateAllAccess()
      refetchExpiring()
      toast.success('Access revoked')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to revoke'),
  })

  const revokeDeptPerm = useMutation({
    mutationFn: (junctionId: string) => api.post(`/api/permissions/connector/dept/${junctionId}/revoke`),
    onSuccess: () => {
      invalidateAllAccess()
      refetchExpiring()
      toast.success('Access revoked')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to revoke'),
  })

  const revokeRolePerm = useMutation({
    mutationFn: (junctionId: string) => api.post(`/api/permissions/connector/role/${junctionId}/revoke`),
    onSuccess: () => {
      invalidateAllAccess()
      refetchExpiring()
      toast.success('Access revoked')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to revoke'),
  })

  const expiringIds = new Set([
    ...(expiringGrants?.user_grants || []).map((g: any) => g.id),
    ...(expiringGrants?.dept_grants || []).map((g: any) => g.id),
    ...(expiringGrants?.role_grants || []).map((g: any) => g.id),
  ])
  const totalExpiring = expiringIds.size

  const handleBannerClick = () => {
    setHighlightExpiring(true)
    setTimeout(() => setHighlightExpiring(false), 4000)
    const firstExpiringId = [...expiringIds][0]
    if (firstExpiringId) {
      const el = document.getElementById(`grant-${firstExpiringId}`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }

  const renderExpiryStatus = (grant: any, onRevoke?: () => void) => {
    const now = new Date()
    const validFrom = grant.valid_from ? parseUTC(grant.valid_from) : null
    const expiresAt = grant.expires_at ? parseUTC(grant.expires_at) : null
    const revokedAt = grant.revoked_at ? parseUTC(grant.revoked_at) : null

    if (revokedAt) {
      return (
        <div className="flex flex-col items-start gap-1">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-700 border border-red-200">
            Revoked
          </span>
          <span className="text-[10px] text-gray-400">
            {revokedAt.toLocaleString()}
          </span>
        </div>
      )
    }

    if (expiresAt && now > expiresAt) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-700 border border-red-200">
          Expired
        </span>
      )
    }

    if (validFrom && now < validFrom) {
      return (
        <div className="flex flex-col items-start gap-1">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-accent-100 text-accent-700 border border-accent-200">
            Scheduled
          </span>
          <span className="text-[10px] text-gray-400 font-mono">
            Starts: {validFrom.toLocaleString()}
          </span>
        </div>
      )
    }

    return (
      <div className="flex flex-wrap items-center gap-2">
        {expiresAt ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-700 border border-amber-250 animate-pulse">
            Expires: {expiresAt.toLocaleDateString()} {expiresAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-100 text-gray-500 border border-gray-250">
            Permanent
          </span>
        )}
        {grant.grant_reason && (
          <span className="text-[10px] text-gray-400 italic truncate max-w-[150px]" title={grant.grant_reason}>
            "{grant.grant_reason}"
          </span>
        )}
        {onRevoke && !revokedAt && (!expiresAt || now <= expiresAt) && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              setConfirmModal({
                isOpen: true,
                title: 'Revoke Access Grant',
                message: 'Are you sure you want to revoke this access grant? This will immediately disable this access configuration.',
                onConfirm: () => {
                  onRevoke()
                  setConfirmModal(prev => ({ ...prev, isOpen: false }))
                }
              })
            }}
            className="text-[10px] font-semibold text-red-500 hover:text-red-700 hover:underline px-1.5 py-0.5 rounded hover:bg-red-50 transition-all border border-transparent hover:border-red-200"
          >
            Revoke
          </button>
        )}
      </div>
    )
  }



  const upsertPerm = useMutation({
    mutationFn: (data: any) => api.put(`/api/permissions/connector/${selectedConnector}`, data),
    onSuccess: () => {
      invalidateAllAccess()
      refetchExpiring()
      toast.success('Permission saved')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  // revokePerm mutation removed — was dead code, superseded by revokeUserPerm

  const createTablePerm = useMutation({
    mutationFn: async (data: any) => {
      const { table_names, ...rest } = data
      await Promise.all(table_names.map((tName: string) => {
        return api.post(`/api/permissions/tables/`, {
          ...rest,
          connector_id: selectedConnector,
          table_name: tName,
        })
      }))
    },
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Table permissions granted')
      setShowTableForm(false)
      setSelectedTableGrantTables([])
      setTableForm({
        table_name: '',
        applies_to_user_id: '',
        departments: [],
        roles: [],
        can_read: true,
        can_create: false,
        can_update: false,
        can_delete: false,
      })
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })


  const deleteTablePerm = useMutation({
    mutationFn: (permId: string) =>
      api.delete(`/api/permissions/tables/${permId}`),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Table permission revoked')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const bulkDeleteTablePerms = useMutation({
    mutationFn: (permIds: string[]) =>
      api.post('/api/permissions/tables/bulk-delete', { ids: permIds }),
    onSuccess: () => {
      invalidateAllAccess()
      setSelectedTableIds([])
      toast.success('Selected table permissions revoked')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to revoke permissions'),
  })

  const bulkUpdateConnectorGrants = useMutation({
    mutationFn: (data: any) =>
      api.post(`/api/permissions/connector/${selectedConnector}/grants/bulk`, data),
    onSuccess: () => {
      invalidateAllAccess()
      refetchExpiring()
      toast.success('Connector permissions updated')
      setShowConnectorGrantsForm(false)
      setConnectorGrantsForm({ departments: [], roles: [] })
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const deleteConnectorDeptGrant = useMutation({
    mutationFn: (deptId: string) =>
      api.delete(`/api/permissions/connector/${selectedConnector}/grants/departments/${deptId}`),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Department grant revoked')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const deleteConnectorRoleGrant = useMutation({
    mutationFn: (roleId: string) =>
      api.delete(`/api/permissions/connector/${selectedConnector}/grants/roles/${roleId}`),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Role grant revoked')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  // ─── Debug Access Panel State ───
  const [debugForm, setDebugForm] = useState({
    user_id: '',
    connector_id: '',
    operation: 'read',
  })
  const [debugSelectedTables, setDebugSelectedTables] = useState<string[]>([])
  const [debugResult, setDebugResult] = useState<any>(null)
  const [debugLoading, setDebugLoading] = useState(false)

  // Lazy load connector schema for the debug panel's selected connector
  const { data: debugSchemaData, isLoading: isLoadingDebugSchema } = useQuery({
    queryKey: ['connectorSchema', debugForm.connector_id],
    queryFn: () => api.get(`/api/connectors/${debugForm.connector_id}/schema`).then(r => r.data),
    enabled: !!debugForm.connector_id,
  })
  const debugConnectorTables = (debugSchemaData?.tables || []).map((t: any) => t.schema ? `${t.schema}.${t.name}` : t.name)

  const runDebug = useCallback(async () => {
    if (!debugForm.user_id || !debugForm.connector_id) {
      toast.error('Please select both a user and a connector')
      return
    }
    setDebugLoading(true)
    setDebugResult(null)
    try {
      const params = new URLSearchParams({
        user_id: debugForm.user_id,
        connector_id: debugForm.connector_id,
        operation: debugForm.operation,
      })
      if (debugSelectedTables.length > 0) {
        params.set('table_names', debugSelectedTables.join(','))
      }
      const { data } = await api.get(`/api/permissions/debug?${params.toString()}`)
      setDebugResult(data)
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Debug query failed')
    } finally {
      setDebugLoading(false)
    }
  }, [debugForm, debugSelectedTables])

  const handleAddDept = (deptId: string) => {
    if (!deptId) return
    if (tableForm.departments.some(d => d.department_id === deptId)) return
    setTableForm({
      ...tableForm,
      departments: [
        ...tableForm.departments,
        { department_id: deptId, is_deny: false, can_read: true, can_create: false, can_update: false, can_delete: false }
      ]
    })
  }

  const handleAddRole = (roleId: string) => {
    if (!roleId) return
    if (tableForm.roles.some(r => r.role_id === roleId)) return
    setTableForm({
      ...tableForm,
      roles: [
        ...tableForm.roles,
        { role_id: roleId, is_deny: false, can_read: true, can_create: false, can_update: false, can_delete: false }
      ]
    })
  }

  const handleAddConnectorDept = (deptId: string) => {
    if (!deptId) return
    if (connectorGrantsForm.departments.some(d => d.department_id === deptId)) return
    setConnectorGrantsForm({
      ...connectorGrantsForm,
      departments: [
        ...connectorGrantsForm.departments,
        { department_id: deptId, is_deny: false, can_read: true, can_create: false, can_update: false, can_delete: false, valid_from: '', expires_at: '', grant_reason: '' }
      ]
    })
  }

  const handleAddConnectorRole = (roleId: string) => {
    if (!roleId) return
    if (connectorGrantsForm.roles.some(r => r.role_id === roleId)) return
    setConnectorGrantsForm({
      ...connectorGrantsForm,
      roles: [
        ...connectorGrantsForm.roles,
        { role_id: roleId, is_deny: false, can_read: true, can_create: false, can_update: false, can_delete: false, valid_from: '', expires_at: '', grant_reason: '' }
      ]
    })
  }

  const toggleRowExpanded = (id: string) => {
    setExpandedRows(prev => ({ ...prev, [id]: !prev[id] }))
  }


  // Build permission map: userId → {can_create, can_read, can_update, can_delete}
  const permMap: Record<string, any> = {}
  permissions.forEach((p: any) => { permMap[p.user_id] = p })

  // Build a set of user IDs who have table-level access for this connector
  const tableAccessUserIds = useMemo(() => {
    const ids = new Set<string>()
    tablePermissions.forEach((tp: any) => {
      if (tp.applies_to_user_id) ids.add(tp.applies_to_user_id)
      // dept/role scoped table rules = anyone in that dept/role has limited access
      // mark as "scoped" separately
    })
    return ids
  }, [tablePermissions])

  // Build a set of user IDs who have scoped access via dept/role table rules
  const tableScopedAccessUserIds = useMemo(() => {
    const ids = new Set<string>()
    tablePermissions.forEach((tp: any) => {
      if (!tp.applies_to_user_id && (tp.departments?.length > 0 || tp.roles?.length > 0)) {
        // All users whose dept/role matches get scoped access
        users.forEach((u: any) => {
          const inDept = tp.departments?.some((d: any) => d.department_id === u.department_id && !d.is_deny && (!d.role_id || d.role_id === u.role_id))
          const inRole = tp.roles?.some((r: any) => r.role_id === u.role_id && !r.is_deny)
          if (inDept || inRole) ids.add(u.id)
        })
      }
    })
    return ids
  }, [tablePermissions, users])

  // Build a set of user IDs who have connector access via dept/role grants
  const connectorGrantUserIds = useMemo(() => {
    const ids = new Set<string>()
    const deptGrants = (connectorGrants as any)?.department_grants?.filter((g: any) => g.is_active && !g.is_deny) || []
    const roleGrants = (connectorGrants as any)?.role_grants?.filter((g: any) => g.is_active && !g.is_deny) || []
    users.forEach((u: any) => {
      const hasConnectorDept = deptGrants.some((g: any) => g.department_id === u.department_id && (!g.role_id || g.role_id === u.role_id))
      const hasConnectorRole = roleGrants.some((g: any) => g.role_id === u.role_id)
      if (hasConnectorDept || hasConnectorRole) ids.add(u.id)
    })
    return ids
  }, [connectorGrants, users])

  // Build a map of package grants by user ID
  const packageGrantsMap = useMemo(() => {
    const map: Record<string, any> = {}
    const grants = (connectorGrants as any)?.package_grants || []
    grants.forEach((g: any) => {
      map[g.user_id] = g
    })
    return map
  }, [connectorGrants])

  // Build a set of user IDs who have package access for this connector
  const hasPackageAccessUserIds = useMemo(() => {
    const ids = new Set<string>()
    const grants = (connectorGrants as any)?.package_grants || []
    grants.forEach((g: any) => {
      if (g.can_read || g.can_create || g.can_update || g.can_delete) {
        ids.add(g.user_id)
      }
    })
    return ids
  }, [connectorGrants])

  // Task 6: Debounce handleTickChange with 300ms delay
  const tickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handleTickChange = (userId: string, field: string, value: boolean) => {
    if (tickTimerRef.current) clearTimeout(tickTimerRef.current)
    tickTimerRef.current = setTimeout(() => {
      const perm = permMap[userId]
      const activePerm = perm && perm.is_active ? perm : null
      const existing = activePerm || { can_create: false, can_read: true, can_update: false, can_delete: false }
      upsertPerm.mutate({ user_id: userId, ...existing, [field]: value })
    }, 300)
  }

  // Task 2: Reset form states when selectedConnector changes
  useEffect(() => {
    setShowTableForm(false)
    setShowConnectorGrantsForm(false)
    setSelectedTableGrantTables([])
    setTableForm({
      table_name: '',
      applies_to_user_id: '',
      departments: [],
      roles: [],
      can_read: true,
      can_create: false,
      can_update: false,
      can_delete: false,
    })
    setConnectorGrantsForm({ departments: [], roles: [] })
    setUserSearchQuery('')
    setFilterDeptId('')
    setFilterRoleId('')
  }, [selectedConnector])

  const CRUD_FIELDS = [
    { key: 'can_create', label: 'CREATE', color: 'text-green-600' },
    { key: 'can_read', label: 'READ', color: 'text-accent-600' },
    { key: 'can_update', label: 'UPDATE', color: 'text-yellow-600' },
    { key: 'can_delete', label: 'DELETE', color: 'text-red-600' },
  ]

  const filteredUsers = users.filter((u: any) => {
    const query = userSearchQuery.toLowerCase().trim()
    if (query) {
      const match = u.name.toLowerCase().includes(query) || u.email.toLowerCase().includes(query)
      if (!match) return false
    }
    if (filterDeptId) {
      if (u.department_id !== filterDeptId) return false
    }
    if (filterRoleId) {
      if (u.role_id !== filterRoleId) return false
    }
    return true
  })

  const visibleConnectors = embedded
    ? connectors.filter((c: any) => c.id === selectedConnector)
    : connectors

  return (
    <div className={embedded ? 'p-0' : debugOnly ? 'p-0' : 'p-8'}>
      {!debugOnly && totalExpiring > 0 && showExpiringBanner && (
        <div className="mb-6 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-3 cursor-pointer" onClick={handleBannerClick}>
            <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center shadow-inner">
              <AlertTriangle className="w-5 h-5 text-amber-700" />
            </div>
            <div>
              <p className="text-sm font-semibold text-amber-800">Expiring Access Grants</p>
              <p className="text-xs text-amber-700">
                {totalExpiring} access grant{totalExpiring > 1 ? 's are' : ' is'} expiring within the next 24 hours. Click to view and highlight.
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowExpiringBanner(false)}
            className="text-amber-500 hover:text-amber-700 text-xs font-semibold px-2 py-1 hover:bg-amber-100/50 rounded-lg transition-all"
          >
            Dismiss
          </button>
        </div>
      )}

      {!debugOnly && !embedded && (
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-text-primary">Permissions</h1>
          <p className="text-text-secondary mt-1 text-sm">
            Control user access to each connector with per-operation permissions and row-level security
          </p>
        </div>
      )}

      {/* Connector Accordion List */}
      {!debugOnly && (
        <div className={embedded ? '' : 'space-y-4 mb-6'}>
          {visibleConnectors.map((c: any) => {
            const isExpanded = embedded || selectedConnector === c.id
            return (
              <div key={c.id} className={embedded ? '' : 'border border-border-default rounded-xl overflow-hidden shadow-sm bg-bg-card'}>
                {/* Accordion Header */}
                {!embedded && (
                  <button
                    type="button"
                    className={`w-full px-6 py-4 flex items-center justify-between text-left transition-colors border-b ${isExpanded ? 'bg-accent-50 border-accent-100 font-semibold' : 'bg-bg-card border-transparent hover:bg-bg-surface'
                      }`}
                    onClick={() => setSelectedConnector(isExpanded ? '' : c.id)}
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-accent-100 rounded-lg text-accent-700">
                        <Database className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-text-primary">{c.name}</h3>
                        <p className="text-xs text-text-secondary font-mono capitalize">{c.type}</p>
                      </div>
                    </div>
                    <div>
                      {isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-text-secondary" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-text-secondary" />
                      )}
                    </div>
                  </button>
                )}

                {/* Accordion Content */}
                {isExpanded && (
                  <div className={embedded ? 'p-4 space-y-6' : 'p-6 bg-bg-surface space-y-6'}>
                    {(!embedded || section === 'connector') && (
                      <>
                        {/* CRUD Permission Matrix */}
                        <div className="card mb-6">
                          <div className="px-6 py-4 border-b border-border-muted flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 bg-gray-50/50">
                            <div className="flex items-center gap-2 flex-shrink-0">
                              <Shield className="w-4 h-4 text-accent-600" />
                              <h2 className="font-semibold text-text-primary">User Permissions</h2>
                            </div>
                            <div className="flex flex-wrap items-center gap-2 w-full lg:w-auto lg:justify-end">
                              {/* Search */}
                              <div className="relative w-full sm:w-48 flex-shrink-0">
                                <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                                <input
                                  type="text"
                                  placeholder="Search users..."
                                  className="input pl-9 py-1.5 text-xs w-full bg-white border border-gray-200"
                                  value={userSearchQuery}
                                  onChange={e => setUserSearchQuery(e.target.value)}
                                />
                                {userSearchQuery && (
                                  <button
                                    type="button"
                                    onClick={() => setUserSearchQuery('')}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-655"
                                  >
                                    <X className="w-3.5 h-3.5" />
                                  </button>
                                )}
                              </div>

                              {/* Department Filter */}
                              <select
                                value={filterDeptId}
                                onChange={e => setFilterDeptId(e.target.value)}
                                className="input py-1.5 text-xs w-full sm:w-40 bg-white border border-gray-200"
                              >
                                <option value="">All Departments</option>
                                {departments.map(d => (
                                  <option key={d.id} value={d.id}>{d.name}</option>
                                ))}
                              </select>

                              {/* Role Filter */}
                              <select
                                value={filterRoleId}
                                onChange={e => setFilterRoleId(e.target.value)}
                                className="input py-1.5 text-xs w-full sm:w-40 bg-white border border-gray-200"
                              >
                                <option value="">All Roles</option>
                                {roles.map(r => (
                                  <option key={r.id} value={r.id}>{r.name}</option>
                                ))}
                              </select>
                            </div>
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
                                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                    Access Period
                                  </th>
                                  <th className="text-center px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-32">
                                    Team Access
                                  </th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-50">
                                {filteredUsers.length === 0 ? (
                                  <tr>
                                    <td colSpan={7} className="text-center py-8 text-gray-400 text-xs italic">
                                      {userSearchQuery ? 'No users found matching your search' : 'No users available'}
                                    </td>
                                  </tr>
                                ) : (
                                  filteredUsers.map((u: any) => {
                                    const perm = permMap[u.id]
                                    const activePerm = perm && perm.is_active ? perm : null
                                    const hasAccess = !!activePerm
                                    const hasTableAccess = tableAccessUserIds.has(u.id)
                                    const hasScopedAccess = tableScopedAccessUserIds.has(u.id)
                                    const hasConnectorGrantAccess = connectorGrantUserIds.has(u.id)
                                    const hasPackageAccess = hasPackageAccessUserIds.has(u.id)
                                    const hasAnyAccess = hasAccess || hasTableAccess || hasScopedAccess || hasConnectorGrantAccess || hasPackageAccess

                                    const pkgGrant = packageGrantsMap[u.id]

                                    const myRole = me?.is_superadmin ? 'superadmin' : (me?.role || 'member')
                                    const targetRole = u.is_superadmin ? 'superadmin' : (u.role || 'member')
                                    const RANK: Record<string, number> = { superadmin: 4, admin: 3, workspace_admin: 2, member: 1 }
                                    const isProtected = (RANK[targetRole] || 1) >= (RANK[myRole] || 1)
                                    const isSelf = u.id === me?.id
                                    const isDisabled = isProtected && !isSelf
                                    const isHighlighted = activePerm && highlightExpiring && expiringIds.has(activePerm.id)

                                    return (
                                      <tr
                                        key={u.id}
                                        id={activePerm ? `grant-${activePerm.id}` : undefined}
                                        className={`transition-all duration-300 ${hasAnyAccess && !activePerm
                                            ? 'border-l-2 border-amber-300'
                                            : hasAnyAccess
                                              ? ''
                                              : 'opacity-40'
                                          } ${isProtected && !isSelf ? 'bg-gray-50' : ''} ${isHighlighted ? 'ring-2 ring-amber-400 bg-amber-50/50' : ''}`}
                                      >
                                        <td className="px-6 py-3">
                                          <div className="flex items-center gap-2">
                                            <div>
                                              <p className="text-sm font-medium text-gray-900">
                                                {u.name}
                                              </p>
                                              <p className="text-xs text-gray-400">{u.email}</p>
                                            </div>
                                            {isProtected && !isSelf && (
                                              <span title="Protected - higher or equal role">
                                                <Lock className="w-3.5 h-3.5 text-gray-400" />
                                              </span>
                                            )}
                                            {u.is_superadmin && (
                                              <span className="text-xs bg-accent-100 text-accent-700 px-1.5 py-0.5 rounded-full font-semibold">Admin</span>
                                            )}
                                          </div>
                                        </td>
                                        {CRUD_FIELDS.map(f => {
                                          const hasPkgGrantForField = pkgGrant ? !!pkgGrant[f.key] : false;
                                          return (
                                            <td key={f.key} className="px-6 py-3 text-center">
                                              {hasPkgGrantForField ? (
                                                <div className="relative group flex items-center justify-center">
                                                  <input
                                                    type="checkbox"
                                                    className="w-4 h-4 rounded border-gray-350 text-indigo-600 focus:ring-indigo-550 cursor-help"
                                                    checked={true}
                                                    readOnly
                                                    disabled={true}
                                                  />
                                                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-50 hidden group-hover:block w-max max-w-[200px]">
                                                    <div className="bg-gray-900 text-white text-[10px] font-medium px-2 py-1 rounded shadow-lg leading-snug text-center">
                                                      Granted via Package:<br />{pkgGrant.package_names}
                                                      <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
                                                    </div>
                                                  </div>
                                                </div>
                                              ) : activePerm ? (
                                                <input
                                                  type="checkbox"
                                                  className="w-4 h-4 rounded border-gray-300 text-accent-600 focus:ring-accent-500 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                                                  checked={activePerm[f.key] ?? false}
                                                  onChange={e => handleTickChange(u.id, f.key, e.target.checked)}
                                                  disabled={isDisabled}
                                                />
                                              ) : hasAnyAccess ? (
                                                <div className="relative group flex items-center justify-center">
                                                  <span
                                                    className="inline-block w-4 h-4 rounded border-2 border-amber-300 bg-amber-50 cursor-help"
                                                  />
                                                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-50 hidden group-hover:block w-max max-w-[160px]">
                                                    <div className="bg-gray-900 text-white text-[10px] font-medium px-2 py-1 rounded shadow-lg leading-snug text-center">
                                                      Table-scoped only.<br />Not a full connector grant.
                                                      <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
                                                    </div>
                                                  </div>
                                                </div>
                                              ) : (
                                                <input
                                                  type="checkbox"
                                                  className="w-4 h-4 rounded border-gray-300 text-accent-600 focus:ring-accent-500 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                                                  checked={false}
                                                  onChange={e => handleTickChange(u.id, f.key, e.target.checked)}
                                                  disabled={isDisabled}
                                                />
                                              )}
                                            </td>
                                          );
                                        })}
                                        <td className="px-6 py-3 text-left">
                                          <div className="flex items-center justify-between gap-2">
                                            <div className="flex items-center gap-1.5 flex-wrap">
                                              {activePerm ? (
                                                renderExpiryStatus(activePerm, () => revokeUserPerm.mutate(activePerm.id))
                                              ) : hasAnyAccess ? null : (
                                                <span className="text-xs text-gray-400 italic">No direct grant</span>
                                              )}
                                              {!activePerm && hasTableAccess && (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                                  Table-scoped
                                                </span>
                                              )}
                                              {!activePerm && hasScopedAccess && (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-violet-50 text-violet-700 border border-violet-200">
                                                  Dept/Role scoped
                                                </span>
                                              )}
                                              {!activePerm && hasConnectorGrantAccess && (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                                  Connector grant
                                                </span>
                                              )}
                                              {!activePerm && hasPackageAccess && (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-750 border border-indigo-250">
                                                  Package: {pkgGrant?.package_names}
                                                </span>
                                              )}
                                            </div>
                                            {!isDisabled && (
                                              <button
                                                type="button"
                                                onClick={() => openScheduleEditModal(u)}
                                                className="text-accent-600 hover:text-accent-700 p-1 hover:bg-gray-100 rounded transition-colors flex-shrink-0"
                                                title={activePerm ? "Edit Schedule / Reason" : "Configure Temporary Access / Schedule"}
                                              >
                                                {activePerm ? (
                                                  <Pencil className="w-3.5 h-3.5" />
                                                ) : (
                                                  <Clock className="w-3.5 h-3.5 text-gray-400" />
                                                )}
                                              </button>
                                            )}
                                          </div>
                                        </td>
                                        <td className="px-6 py-3 text-center">
                                          {managersSet.has(u.id) ? (
                                            <input
                                              type="checkbox"
                                              className="w-4 h-4 rounded border-gray-300 text-accent-600 focus:ring-accent-500 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                                              checked={activePerm?.allow_share_access ?? false}
                                              onChange={e => handleTickChange(u.id, 'allow_share_access', e.target.checked)}
                                              disabled={isDisabled}
                                            />
                                          ) : (
                                            <span className="text-xs text-gray-400 font-mono">—</span>
                                          )}
                                        </td>
                                      </tr>
                                    )
                                  })
                                )}
                              </tbody>
                            </table>
                          </div>

                          <div className="px-6 py-3 bg-gray-50 border-t border-gray-100">
                            <p className="text-xs text-gray-400">
                              Amber squares = scoped access exists (table-level or dept/role). Ticking a box grants full connector-wide access for that operation.
                            </p>
                          </div>
                        </div>
                      </>
                    )}

                    {(!embedded || section === 'table') && (
                      <div className="card mb-6">
                        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <Table className="w-4 h-4 text-accent-600" />
                              <h2 className="font-semibold text-gray-900">Table-Level Access Control</h2>
                            </div>
                            <p className="text-xs text-gray-400 mt-0.5">
                              Grant or deny access to specific tables/collections within this database
                            </p>
                          </div>
                          <button
                            className="btn-primary text-sm flex items-center gap-1"
                            onClick={() => {
                              setShowTableForm(!showTableForm)
                            }}
                          >
                            <Plus className="w-3.5 h-3.5" /> Grant Table Access
                          </button>
                        </div>

                        {/* Default Deny Status Bar */}
                        {tablePermissions.length > 0 && (
                          <div className="bg-amber-50 border-b border-amber-100 px-6 py-3 flex items-start gap-2 text-amber-800 text-xs">
                            <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                            <div>
                              <span className="font-semibold">Connector-wide DEFAULT-DENY active:</span> Any non-superadmin users not explicitly granted table access below will be blocked from accessing tables in this connector.
                            </div>
                          </div>
                        )}

                        {/* Table Grant Form */}
                        {showTableForm && (
                          <div className="px-6 py-5 border-b border-gray-100 bg-gray-50">
                            <h3 className="font-medium text-gray-900 mb-4">Grant Table Permission</h3>
                            <div className="grid grid-cols-2 gap-4">
                              <div className="col-span-2">
                                <label className="label">Select Table(s) to Grant Access</label>
                                <SearchableTableSelector
                                  allTables={allConnectorTables}
                                  selectedTables={selectedTableGrantTables}
                                  onChange={setSelectedTableGrantTables}
                                />
                              </div>

                              {/* Departments Multi-Select & CRUD */}
                              <div className="col-span-2 border-t border-gray-200 pt-4 mt-2">
                                <h4 className="text-sm font-semibold text-gray-800 mb-2">Department Permissions</h4>
                                <div className="flex gap-2 mb-3">
                                  <select
                                    className="input max-w-xs text-sm bg-white"
                                    value=""
                                    onChange={e => handleAddDept(e.target.value)}
                                  >
                                    <option value="">- add department -</option>
                                    {departments
                                      .filter(d => !tableForm.departments.some(td => td.department_id === d.id))
                                      .map(d => (
                                        <option key={d.id} value={d.id}>{d.name}</option>
                                      ))
                                    }
                                  </select>
                                </div>

                                <div className="space-y-2">
                                  {tableForm.departments.map(td => {
                                    const dept = departments.find(d => d.id === td.department_id)
                                    const deptColor = dept?.color || '1E40AF'
                                    const cleanColor = deptColor.startsWith('#') ? deptColor : '#' + deptColor
                                    return (
                                      <div key={td.department_id} className="p-3 bg-white border border-gray-200 rounded-lg">
                                        <div className="flex flex-wrap items-center justify-between gap-4">
                                          <span
                                            className="px-2.5 py-1 rounded-full text-xs font-semibold border"
                                            style={{
                                              backgroundColor: cleanColor + '15',
                                              color: cleanColor,
                                              borderColor: cleanColor + '30',
                                            }}
                                          >
                                            {dept?.name || 'Unknown'}
                                          </span>

                                          <div className="flex items-center gap-6">
                                            <button
                                              type="button"
                                              onClick={() => setExpandedTableDepts(prev => ({ ...prev, [td.department_id]: !prev[td.department_id] }))}
                                              className="text-xs text-accent-600 hover:text-accent-700 font-semibold focus:outline-none"
                                            >
                                              {expandedTableDepts[td.department_id] ? 'Advanced ▲' : 'Advanced ▼'}
                                            </button>

                                            <div className="flex items-center gap-4 border-l border-gray-200 pl-4">
                                              {CRUD_FIELDS.map(f => (
                                                <label key={f.key} className="flex items-center gap-1 cursor-pointer text-xs">
                                                  <input
                                                    type="checkbox"
                                                    className="rounded border-gray-300 text-accent-600 focus:ring-accent-500"
                                                    checked={(td as any)[f.key]}
                                                    disabled={td.is_deny}
                                                    onChange={e => {
                                                      setTableForm({
                                                        ...tableForm,
                                                        departments: tableForm.departments.map(item =>
                                                          item.department_id === td.department_id ? { ...item, [f.key]: e.target.checked } : item
                                                        )
                                                      })
                                                    }}
                                                  />
                                                  {f.label.charAt(0)}
                                                </label>
                                              ))}
                                            </div>

                                            <button
                                              type="button"
                                              className="text-gray-400 hover:text-red-500 transition-colors"
                                              onClick={() => {
                                                setTableForm({
                                                  ...tableForm,
                                                  departments: tableForm.departments.filter(item => item.department_id !== td.department_id)
                                                })
                                              }}
                                            >
                                              <Trash2 className="w-4 h-4" />
                                            </button>
                                          </div>
                                        </div>
                                        {expandedTableDepts[td.department_id] && (
                                          <div className="mt-2 pt-2 border-t border-gray-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4 animate-fade-in">
                                            <label className="flex items-center gap-1.5 cursor-pointer text-xs font-semibold text-red-600">
                                              <input
                                                type="checkbox"
                                                className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                                                checked={td.is_deny}
                                                onChange={e => {
                                                  setTableForm({
                                                    ...tableForm,
                                                    departments: tableForm.departments.map(item =>
                                                      item.department_id === td.department_id ? { ...item, is_deny: e.target.checked } : item
                                                    )
                                                  })
                                                }}
                                              />
                                              DENY ACCESS (Overrides all allow rules)
                                            </label>

                                            <div className="flex items-center gap-2">
                                              <label className="text-xs font-medium text-gray-500">Scoped Role (Optional):</label>
                                              <select
                                                className="input text-xs py-1 px-2 h-auto bg-white border border-gray-250 rounded"
                                                value={(td as any).role_id || ''}
                                                onChange={e => {
                                                  setTableForm({
                                                    ...tableForm,
                                                    departments: tableForm.departments.map(item =>
                                                      item.department_id === td.department_id ? { ...item, role_id: e.target.value || undefined } : item
                                                    )
                                                  })
                                                }}
                                              >
                                                <option value="">- All Roles -</option>
                                                {roles.map(r => (
                                                  <option key={r.id} value={r.id}>{r.name}</option>
                                                ))}
                                              </select>
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    )
                                  })}
                                  {tableForm.departments.length === 0 && (
                                    <p className="text-xs text-gray-400 italic">No department permissions selected yet.</p>
                                  )}
                                </div>
                              </div>

                              {/* Roles Multi-Select & CRUD */}
                              <div className="col-span-2 border-t border-gray-200 pt-4 mt-2">
                                <h4 className="text-sm font-semibold text-gray-800 mb-2">Role Permissions</h4>
                                <div className="flex gap-2 mb-3">
                                  <select
                                    className="input max-w-xs text-sm bg-white"
                                    value=""
                                    onChange={e => handleAddRole(e.target.value)}
                                  >
                                    <option value="">- add role -</option>
                                    {roles
                                      .filter(r => !tableForm.roles.some(tr => tr.role_id === r.id))
                                      .map(r => (
                                        <option key={r.id} value={r.id}>{r.name}</option>
                                      ))
                                    }
                                  </select>
                                </div>

                                <div className="space-y-2">
                                  {tableForm.roles.map(tr => {
                                    const rObj = roles.find(r => r.id === tr.role_id)
                                    const roleColor = rObj?.color || '1E40AF'
                                    const cleanColor = roleColor.startsWith('#') ? roleColor : '#' + roleColor
                                    return (
                                      <div key={tr.role_id} className="p-3 bg-white border border-gray-200 rounded-lg">
                                        <div className="flex flex-wrap items-center justify-between gap-4">
                                          <span
                                            className="px-2.5 py-1 rounded-full text-xs font-semibold border"
                                            style={{
                                              backgroundColor: cleanColor + '15',
                                              color: cleanColor,
                                              borderColor: cleanColor + '30',
                                            }}
                                          >
                                            {rObj?.name || 'Unknown'}
                                          </span>

                                          <div className="flex items-center gap-6">
                                            <button
                                              type="button"
                                              onClick={() => setExpandedTableRoles(prev => ({ ...prev, [tr.role_id]: !prev[tr.role_id] }))}
                                              className="text-xs text-accent-600 hover:text-accent-700 font-semibold focus:outline-none"
                                            >
                                              {expandedTableRoles[tr.role_id] ? 'Advanced ▲' : 'Advanced ▼'}
                                            </button>

                                            <div className="flex items-center gap-4 border-l border-gray-200 pl-4">
                                              {CRUD_FIELDS.map(f => (
                                                <label key={f.key} className="flex items-center gap-1 cursor-pointer text-xs">
                                                  <input
                                                    type="checkbox"
                                                    className="rounded border-gray-300 text-accent-600 focus:ring-accent-500"
                                                    checked={(tr as any)[f.key]}
                                                    disabled={tr.is_deny}
                                                    onChange={e => {
                                                      setTableForm({
                                                        ...tableForm,
                                                        roles: tableForm.roles.map(item =>
                                                          item.role_id === tr.role_id ? { ...item, [f.key]: e.target.checked } : item
                                                        )
                                                      })
                                                    }}
                                                  />
                                                  {f.label.charAt(0)}
                                                </label>
                                              ))}
                                            </div>

                                            <button
                                              type="button"
                                              className="text-gray-400 hover:text-red-500 transition-colors"
                                              onClick={() => {
                                                setTableForm({
                                                  ...tableForm,
                                                  roles: tableForm.roles.filter(item => item.role_id !== tr.role_id)
                                                })
                                              }}
                                            >
                                              <Trash2 className="w-4 h-4" />
                                            </button>
                                          </div>
                                        </div>
                                        {expandedTableRoles[tr.role_id] && (
                                          <div className="mt-2 pt-2 border-t border-gray-100 flex items-center gap-4 animate-fade-in">
                                            <label className="flex items-center gap-1.5 cursor-pointer text-xs font-semibold text-red-600">
                                              <input
                                                type="checkbox"
                                                className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                                                checked={tr.is_deny}
                                                onChange={e => {
                                                  setTableForm({
                                                    ...tableForm,
                                                    roles: tableForm.roles.map(item =>
                                                      item.role_id === tr.role_id ? { ...item, is_deny: e.target.checked } : item
                                                    )
                                                  })
                                                }}
                                              />
                                              DENY ACCESS (Overrides all allow rules)
                                            </label>
                                          </div>
                                        )}
                                      </div>
                                    )
                                  })}
                                  {tableForm.roles.length === 0 && (
                                    <p className="text-xs text-gray-400 italic">No role permissions selected yet.</p>
                                  )}
                                </div>
                              </div>

                              {/* User override */}
                              <div className="col-span-2 border-t border-gray-200 pt-4 mt-2">
                                <h4 className="text-sm font-semibold text-gray-800 mb-2">User Override (Optional)</h4>
                                <div className="grid grid-cols-2 gap-4">
                                  <div>
                                    <label className="label text-xs">Select User</label>
                                    <select
                                      className="input text-sm bg-white"
                                      value={tableForm.applies_to_user_id}
                                      onChange={e => setTableForm({ ...tableForm, applies_to_user_id: e.target.value })}
                                    >
                                      <option value="">- no user override -</option>
                                      {users.map((u: any) => (
                                        <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                                      ))}
                                    </select>
                                  </div>
                                  {tableForm.applies_to_user_id && (
                                    <div>
                                      <label className="label text-xs">User Permissions</label>
                                      <div className="flex items-center gap-4 py-2.5">
                                        {CRUD_FIELDS.map(f => (
                                          <label key={f.key} className="flex items-center gap-1.5 cursor-pointer text-xs font-medium text-gray-700">
                                            <input
                                              type="checkbox"
                                              className="rounded border-gray-300 text-accent-600 focus:ring-accent-500"
                                              checked={(tableForm as any)[f.key]}
                                              onChange={e => setTableForm({ ...tableForm, [f.key]: e.target.checked })}
                                            />
                                            {f.label}
                                          </label>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>

                            <div className="flex gap-3 mt-6 border-t border-gray-200 pt-4">
                              <button
                                className="btn-primary text-sm px-4 py-2"
                                onClick={() => {
                                  if (selectedTableGrantTables.length === 0) {
                                    toast.error('Please select at least one table')
                                    return
                                  }
                                  createTablePerm.mutate({
                                    table_names: selectedTableGrantTables,
                                    applies_to_user_id: tableForm.applies_to_user_id || null,
                                    departments: tableForm.departments,
                                    roles: tableForm.roles,
                                    can_read: tableForm.can_read,
                                    can_create: tableForm.can_create,
                                    can_update: tableForm.can_update,
                                    can_delete: tableForm.can_delete,
                                  })
                                }}
                                disabled={createTablePerm.isPending}
                              >
                                {createTablePerm.isPending ? 'Saving...' : 'Grant Access'}
                              </button>
                              <button
                                className="btn-secondary text-sm px-4 py-2"
                                onClick={() => {
                                  setShowTableForm(false)
                                  setSelectedTableGrantTables([])
                                  setTableForm({
                                    table_name: '',
                                    applies_to_user_id: '',
                                    departments: [],
                                    roles: [],
                                    can_read: true,
                                    can_create: false,
                                    can_update: false,
                                    can_delete: false,
                                  })
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}

                        {/* Table Permissions List */}
                        {selectedTableIds.length > 0 && (
                          <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 flex items-center justify-between text-sm text-red-800 animate-fade-in">
                            <div className="flex items-center gap-2 font-medium">
                              <AlertTriangle className="w-4 h-4 text-red-650" />
                              <span>{selectedTableIds.length} table permission(s) selected</span>
                            </div>
                            <button
                              onClick={() => {
                                setConfirmModal({
                                  isOpen: true,
                                  title: 'Revoke Selected Table Access Rules',
                                  message: `Are you sure you want to revoke the selected ${selectedTableIds.length} table access rules? This action is irreversible.`,
                                  onConfirm: () => {
                                    bulkDeleteTablePerms.mutate(selectedTableIds)
                                    setConfirmModal(prev => ({ ...prev, isOpen: false }))
                                  }
                                })
                              }}
                              disabled={bulkDeleteTablePerms.isPending}
                              className="btn-danger py-1 px-3 text-xs font-semibold"
                            >
                              {bulkDeleteTablePerms.isPending ? 'Revoking...' : 'Revoke Selected'}
                            </button>
                          </div>
                        )}

                        <div className="overflow-x-auto">
                          {tablePermissions.length === 0 ? (
                            <p className="px-6 py-8 text-center text-gray-400 text-sm">
                              No table permissions configured. Access is default-allow (inherits connector-level permission).
                            </p>
                          ) : (
                            <table className="w-full">
                              <thead>
                                <tr className="bg-gray-50 border-b border-gray-100">
                                  <th className="w-10 px-6 py-3 text-left">
                                    <input
                                      type="checkbox"
                                      className="rounded border-gray-300 text-accent-600 focus:ring-accent-500 cursor-pointer"
                                      checked={
                                        tablePermissions.length > 0 &&
                                        tablePermissions.filter((tp: any) => !tp.is_package_rule).length > 0 &&
                                        tablePermissions.filter((tp: any) => !tp.is_package_rule).every((tp: any) => selectedTableIds.includes(tp.id))
                                      }
                                      onChange={(e) => {
                                        if (e.target.checked) {
                                          const deletableIds = tablePermissions
                                            .filter((tp: any) => !tp.is_package_rule)
                                            .map((tp: any) => tp.id)
                                          setSelectedTableIds(deletableIds)
                                        } else {
                                          setSelectedTableIds([])
                                        }
                                      }}
                                    />
                                  </th>
                                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                    Table Name
                                  </th>
                                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                    Applies To
                                  </th>
                                  <th className="text-center px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                                    Permissions Summary
                                  </th>
                                  <th className="px-6 py-3 w-20" />
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-50">
                                {tablePermissions.flatMap((tp: any) => {
                                  const userObj = users.find((u: any) => u.id === tp.applies_to_user_id)
                                  const isExpanded = expandedRows[tp.id]

                                  const userOps = []
                                  if (tp.can_read) userOps.push('R')
                                  if (tp.can_create) userOps.push('C')
                                  if (tp.can_update) userOps.push('U')
                                  if (tp.can_delete) userOps.push('D')

                                  const hasDeny = tp.departments?.some((d: any) => d.is_deny) || tp.roles?.some((r: any) => r.is_deny)
                                  const rowElement = (
                                    <tr key={tp.id} className="hover:bg-gray-50/40" style={hasDeny ? { borderLeft: '4px solid #EF4444' } : undefined}>
                                      <td className="w-10 px-6 py-3 text-left">
                                        {!tp.is_package_rule && (
                                          <input
                                            type="checkbox"
                                            className="rounded border-gray-300 text-accent-600 focus:ring-accent-500 cursor-pointer"
                                            checked={selectedTableIds.includes(tp.id)}
                                            onChange={(e) => {
                                              if (e.target.checked) {
                                                setSelectedTableIds(prev => [...prev, tp.id])
                                              } else {
                                                setSelectedTableIds(prev => prev.filter(id => id !== tp.id))
                                              }
                                            }}
                                          />
                                        )}
                                      </td>
                                      <td className="px-6 py-3 text-sm font-mono font-medium text-gray-900">
                                        <div className="flex items-center gap-2">
                                          <button
                                            onClick={() => toggleRowExpanded(tp.id)}
                                            className="p-1 hover:bg-gray-100 rounded text-gray-500 transition-colors"
                                          >
                                            {isExpanded ? (
                                              <ChevronUp className="w-4 h-4" />
                                            ) : (
                                              <ChevronDown className="w-4 h-4" />
                                            )}
                                          </button>
                                          {tp.table_name}
                                        </div>
                                      </td>
                                      <td className="px-6 py-3 text-sm">
                                        <div className="flex flex-wrap gap-1.5">
                                          {userObj && (
                                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200">
                                              User: {userObj.name}
                                            </span>
                                          )}
                                          {tp.departments?.map((d: any) => {
                                            const deptObj = departments.find((dept: any) => dept.id === d.department_id)
                                            const roleObj = d.role_id ? roles.find((r: any) => r.id === d.role_id) : null
                                            const displayName = roleObj ? `${deptObj?.name || 'Department'}: ${roleObj.name}` : (deptObj?.name || 'Department')
                                            const color = d.is_deny ? 'EF4444' : (deptObj?.color || '1E40AF')
                                            const clean = color.startsWith('#') ? color : '#' + color
                                            return (
                                              <span
                                                key={d.department_id}
                                                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border"
                                                style={{
                                                  backgroundColor: clean + '15',
                                                  color: clean,
                                                  borderColor: clean + '30',
                                                }}
                                              >
                                                {d.is_deny && 'DENY: '}
                                                {displayName}
                                              </span>
                                            )
                                          })}
                                          {tp.roles?.map((r: any) => {
                                            const roleObj = roles.find((role: any) => role.id === r.role_id)
                                            const color = r.is_deny ? 'EF4444' : (roleObj?.color || '1E40AF')
                                            const clean = color.startsWith('#') ? color : '#' + color
                                            return (
                                              <span
                                                key={r.role_id}
                                                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border"
                                                style={{
                                                  backgroundColor: clean + '15',
                                                  color: clean,
                                                  borderColor: clean + '30',
                                                }}
                                              >
                                                {r.is_deny && 'DENY: '}
                                                {roleObj?.name || 'Role'}
                                              </span>
                                            )
                                          })}
                                          {!userObj && (!tp.departments || tp.departments.length === 0) && (!tp.roles || tp.roles.length === 0) && (
                                            <span className="text-xs text-gray-400 italic">All Users</span>
                                          )}
                                        </div>
                                      </td>
                                      <td className="px-6 py-3 text-center text-xs text-gray-500">
                                        {userObj ? (
                                          <div className="flex justify-center gap-1">
                                            {userOps.map(op => (
                                              <span key={op} className="px-1.5 py-0.5 rounded bg-accent-50 text-accent-600 font-bold text-[9px]">{op}</span>
                                            ))}
                                          </div>
                                        ) : (
                                          <span>Dept/Role Rules ({(tp.departments?.length || 0) + (tp.roles?.length || 0)} targets)</span>
                                        )}
                                      </td>
                                      <td className="px-6 py-3 text-center">
                                        {tp.is_package_rule ? (
                                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-755 border border-indigo-200" title="This table rule is inherited from an Access Package. Manage it in the Access Packages section.">
                                            Via Package
                                          </span>
                                        ) : (
                                          <button
                                            onClick={() => {
                                              setConfirmModal({
                                                isOpen: true,
                                                title: 'Revoke Table Access Rule',
                                                message: `Are you sure you want to revoke the table access rule for "${tp.table_name}"?`,
                                                onConfirm: () => {
                                                  deleteTablePerm.mutate(tp.id)
                                                  setConfirmModal(prev => ({ ...prev, isOpen: false }))
                                                }
                                              })
                                            }}
                                            className="text-gray-400 hover:text-red-500 transition-colors"
                                          >
                                            <Trash2 className="w-4 h-4" />
                                          </button>
                                        )}
                                      </td>
                                    </tr>
                                  )

                                  if (!isExpanded) return [rowElement]

                                  const expansionElement = (
                                    <tr key={`${tp.id}-details`} className="bg-gray-50/50">
                                      <td colSpan={5} className="px-12 py-4 border-b border-gray-100">
                                        <div className="space-y-4 max-w-2xl">
                                          {tp.departments?.length > 0 && (
                                            <div>
                                              <h5 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">Department Breakdown</h5>
                                              <div className="space-y-1.5">
                                                {tp.departments.map((d: any) => {
                                                  const deptObj = departments.find((dept: any) => dept.id === d.department_id)
                                                  const active = []
                                                  if (d.can_read) active.push('READ')
                                                  if (d.can_create) active.push('CREATE')
                                                  if (d.can_update) active.push('UPDATE')
                                                  if (d.can_delete) active.push('DELETE')
                                                  return (
                                                    <div key={d.department_id} className="flex items-center justify-between bg-white px-3 py-2 rounded-lg border border-gray-150 shadow-sm text-xs">
                                                      <span className="font-semibold text-gray-800">
                                                        {(() => {
                                                          const roleObj = d.role_id ? roles.find((r: any) => r.id === d.role_id) : null
                                                          return roleObj ? `${deptObj?.name || 'Unknown Dept'} (Scoped to ${roleObj.name})` : (deptObj?.name || 'Unknown Dept')
                                                        })()}
                                                      </span>
                                                      <div className="flex items-center gap-4">
                                                        {d.is_deny ? (
                                                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 border border-red-200">DENY</span>
                                                        ) : (
                                                          <div className="flex gap-1.5">
                                                            {active.map(op => (
                                                              <span key={op} className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${op === 'READ' ? 'bg-accent-50 text-accent-600' :
                                                                op === 'CREATE' ? 'bg-green-50 text-green-600' :
                                                                  op === 'UPDATE' ? 'bg-yellow-50 text-yellow-600' :
                                                                    'bg-red-50 text-red-600'
                                                                }`}>{op}</span>
                                                            ))}
                                                            {active.length === 0 && <span className="text-gray-400 italic">No access</span>}
                                                          </div>
                                                        )}
                                                      </div>
                                                    </div>
                                                  )
                                                })}
                                              </div>
                                            </div>
                                          )}

                                          {tp.roles?.length > 0 && (
                                            <div>
                                              <h5 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">Role Breakdown</h5>
                                              <div className="space-y-1.5">
                                                {tp.roles.map((r: any) => {
                                                  const roleObj = roles.find((role: any) => role.id === r.role_id)
                                                  const active = []
                                                  if (r.can_read) active.push('READ')
                                                  if (r.can_create) active.push('CREATE')
                                                  if (r.can_update) active.push('UPDATE')
                                                  if (r.can_delete) active.push('DELETE')
                                                  return (
                                                    <div key={r.role_id} className="flex items-center justify-between bg-white px-3 py-2 rounded-lg border border-gray-150 shadow-sm text-xs">
                                                      <span className="font-semibold text-gray-800">{roleObj?.name || 'Unknown Role'}</span>
                                                      <div className="flex items-center gap-4">
                                                        {r.is_deny ? (
                                                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 border border-red-200">DENY</span>
                                                        ) : (
                                                          <div className="flex gap-1.5">
                                                            {active.map(op => (
                                                              <span key={op} className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${op === 'READ' ? 'bg-accent-50 text-accent-600' :
                                                                op === 'CREATE' ? 'bg-green-50 text-green-600' :
                                                                  op === 'UPDATE' ? 'bg-yellow-50 text-yellow-600' :
                                                                    'bg-red-50 text-red-600'
                                                                }`}>{op}</span>
                                                            ))}
                                                            {active.length === 0 && <span className="text-gray-400 italic">No access</span>}
                                                          </div>
                                                        )}
                                                      </div>
                                                    </div>
                                                  )
                                                })}
                                              </div>
                                            </div>
                                          )}

                                          {tp.applies_to_user_id && (
                                            <div>
                                              <h5 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">User Override Details</h5>
                                              <div className="flex items-center justify-between bg-white px-3 py-2 rounded-lg border border-gray-150 shadow-sm text-xs">
                                                <span className="font-semibold text-gray-800">{userObj?.name || 'Unknown User'}</span>
                                                <div className="flex gap-1.5">
                                                  {tp.can_read && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-accent-50 text-accent-600">READ</span>}
                                                  {tp.can_create && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-green-50 text-green-600">CREATE</span>}
                                                  {tp.can_update && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-yellow-50 text-yellow-600">UPDATE</span>}
                                                  {tp.can_delete && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-red-50 text-red-600">DELETE</span>}
                                                </div>
                                              </div>
                                            </div>
                                          )}
                                        </div>
                                      </td>
                                    </tr>
                                  )

                                  return [rowElement, expansionElement]
                                })}
                              </tbody>
                            </table>
                          )}
                        </div>
                      </div>
                    )}

                    {(!embedded || section === 'connector') && (
                      <div className="card mb-6">
                        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <Shield className="w-4 h-4 text-accent-600" />
                              <h2 className="font-semibold text-gray-900">Connector-Level Access Control</h2>
                            </div>
                            <p className="text-xs text-gray-600 mt-0.5">
                              Grant entire departments or roles connector-wide access in one rule
                            </p>
                          </div>
                          <button
                            className="btn-primary text-sm flex items-center gap-1"
                            onClick={() => setShowConnectorGrantsForm(!showConnectorGrantsForm)}
                          >
                            <Plus className="w-3.5 h-3.5" /> Grant Connector Access
                          </button>
                        </div>

                        {/* Connector Grants Form */}
                        {showConnectorGrantsForm && (
                          <div className="px-6 py-5 border-b border-gray-100 bg-gray-50">
                            <h3 className="font-medium text-gray-900 mb-4">Grant Connector Permission</h3>

                            {/* Departments Multi-Select & CRUD */}
                            <div className="mb-6 pb-4 border-b border-gray-200">
                              <h4 className="text-sm font-semibold text-gray-800 mb-2">Department Permissions</h4>
                              <div className="flex gap-2 mb-3">
                                <MultiSelect
                                  options={departments.map(d => ({ id: d.id, label: d.name }))}
                                  value={connectorGrantsForm.departments.map(d => d.department_id)}
                                  onChange={ids => {
                                    setConnectorGrantsForm({
                                      ...connectorGrantsForm,
                                      departments: ids.map(id => (
                                        connectorGrantsForm.departments.find(d => d.department_id === id) || {
                                          department_id: id,
                                          is_deny: false,
                                          can_read: true,
                                          can_create: false,
                                          can_update: false,
                                          can_delete: false,
                                          valid_from: '',
                                          expires_at: '',
                                          grant_reason: '',
                                        }
                                      ))
                                    })
                                  }}
                                  placeholder="+ Add departments"
                                  className="max-w-xs"
                                />
                              </div>

                              <div className="space-y-2">
                                {connectorGrantsForm.departments.map(cd => {
                                  const dept = departments.find(d => d.id === cd.department_id)
                                  const deptColor = dept?.color || '1E40AF'
                                  const cleanColor = deptColor.startsWith('#') ? deptColor : '#' + deptColor
                                  return (
                                    <div key={cd.department_id} className="p-3 bg-white border border-gray-200 rounded-lg space-y-3">
                                      <div className="flex flex-wrap items-center justify-between gap-4">
                                        <span
                                          className="px-2.5 py-1 rounded-full text-xs font-semibold border"
                                          style={{
                                            backgroundColor: cleanColor + '15',
                                            color: cleanColor,
                                            borderColor: cleanColor + '30',
                                          }}
                                        >
                                          {dept?.name || 'Unknown'}
                                        </span>

                                        <div className="flex items-center gap-6">
                                          <button
                                            type="button"
                                            onClick={() => setExpandedConnectorDepts(prev => ({ ...prev, [cd.department_id]: !prev[cd.department_id] }))}
                                            className="text-xs text-accent-600 hover:text-accent-700 font-semibold focus:outline-none"
                                          >
                                            {expandedConnectorDepts[cd.department_id] ? 'Advanced ▲' : 'Advanced ▼'}
                                          </button>

                                          <div className="flex items-center gap-4 border-l border-gray-200 pl-4">
                                            {CRUD_FIELDS.map(f => (
                                              <label key={f.key} className="flex items-center gap-1 cursor-pointer text-xs">
                                                <input
                                                  type="checkbox"
                                                  className="rounded border-gray-300 text-accent-600 focus:ring-accent-500"
                                                  checked={(cd as any)[f.key]}
                                                  disabled={cd.is_deny}
                                                  onChange={e => {
                                                    setConnectorGrantsForm({
                                                      ...connectorGrantsForm,
                                                      departments: connectorGrantsForm.departments.map(item =>
                                                        item.department_id === cd.department_id ? { ...item, [f.key]: e.target.checked } : item
                                                      )
                                                    })
                                                  }}
                                                />
                                                {f.label.charAt(0)}
                                              </label>
                                            ))}
                                          </div>

                                          <button
                                            type="button"
                                            className="text-gray-400 hover:text-red-500 transition-colors"
                                            onClick={() => {
                                              setConnectorGrantsForm({
                                                ...connectorGrantsForm,
                                                departments: connectorGrantsForm.departments.filter(item => item.department_id !== cd.department_id)
                                              })
                                            }}
                                          >
                                            <Trash2 className="w-4 h-4" />
                                          </button>
                                        </div>
                                      </div>

                                      {expandedConnectorDepts[cd.department_id] && (
                                        <div className="space-y-3 pt-2 border-t border-gray-100 animate-fade-in">
                                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                            <label className="flex items-center gap-1.5 cursor-pointer text-xs font-semibold text-red-600">
                                              <input
                                                type="checkbox"
                                                className="rounded border-gray-350 text-red-650 focus:ring-red-500"
                                                checked={cd.is_deny}
                                                onChange={e => {
                                                  setConnectorGrantsForm({
                                                    ...connectorGrantsForm,
                                                    departments: connectorGrantsForm.departments.map(item =>
                                                      item.department_id === cd.department_id ? { ...item, is_deny: e.target.checked } : item
                                                    )
                                                  })
                                                }}
                                              />
                                              DENY ACCESS (Overrides all allow rules)
                                            </label>
                                            <div className="flex items-center gap-2">
                                              <label className="text-xs font-medium text-gray-500">Scoped Role (Optional):</label>
                                              <select
                                                className="input text-xs py-1 px-2 h-auto bg-white border border-gray-250 rounded"
                                                value={cd.role_id || ''}
                                                onChange={e => {
                                                  setConnectorGrantsForm({
                                                    ...connectorGrantsForm,
                                                    departments: connectorGrantsForm.departments.map(item =>
                                                      item.department_id === cd.department_id ? { ...item, role_id: e.target.value || undefined } : item
                                                    )
                                                  })
                                                }}
                                              >
                                                <option value="">- All Roles -</option>
                                                {roles.map(r => (
                                                  <option key={r.id} value={r.id}>{r.name}</option>
                                                ))}
                                              </select>
                                            </div>
                                          </div>
                                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                            <div>
                                              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Valid From</label>
                                              <input
                                                type="datetime-local"
                                                className="input text-xs py-1 px-2 h-auto"
                                                value={cd.valid_from || ''}
                                                onChange={e => {
                                                  setConnectorGrantsForm({
                                                    ...connectorGrantsForm,
                                                    departments: connectorGrantsForm.departments.map(item =>
                                                      item.department_id === cd.department_id ? { ...item, valid_from: e.target.value } : item
                                                    )
                                                  })
                                                }}
                                              />
                                            </div>
                                            <div>
                                              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Expires At</label>
                                              <input
                                                type="datetime-local"
                                                className="input text-xs py-1 px-2 h-auto"
                                                value={cd.expires_at || ''}
                                                onChange={e => {
                                                  setConnectorGrantsForm({
                                                    ...connectorGrantsForm,
                                                    departments: connectorGrantsForm.departments.map(item =>
                                                      item.department_id === cd.department_id ? { ...item, expires_at: e.target.value } : item
                                                    )
                                                  })
                                                }}
                                              />
                                            </div>
                                            <div>
                                              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Grant Reason</label>
                                              <input
                                                type="text"
                                                placeholder="Audit note"
                                                className="input text-xs py-1 px-2 h-auto"
                                                value={cd.grant_reason || ''}
                                                onChange={e => {
                                                  setConnectorGrantsForm({
                                                    ...connectorGrantsForm,
                                                    departments: connectorGrantsForm.departments.map(item =>
                                                      item.department_id === cd.department_id ? { ...item, grant_reason: e.target.value } : item
                                                    )
                                                  })
                                                }}
                                              />
                                            </div>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  )
                                })}
                                {connectorGrantsForm.departments.length === 0 && (
                                  <p className="text-xs text-gray-400 italic">No department permissions selected yet.</p>
                                )}
                              </div>
                            </div>

                            {/* Roles Multi-Select & CRUD */}
                            <div className="mb-6">
                              <h4 className="text-sm font-semibold text-gray-800 mb-2">Role Permissions</h4>
                              <div className="flex gap-2 mb-3">
                                <MultiSelect
                                  options={roles.map(r => ({ id: r.id, label: r.name }))}
                                  value={connectorGrantsForm.roles.map(r => r.role_id)}
                                  onChange={ids => {
                                    setConnectorGrantsForm({
                                      ...connectorGrantsForm,
                                      roles: ids.map(id => (
                                        connectorGrantsForm.roles.find(r => r.role_id === id) || {
                                          role_id: id,
                                          is_deny: false,
                                          can_read: true,
                                          can_create: false,
                                          can_update: false,
                                          can_delete: false,
                                          valid_from: '',
                                          expires_at: '',
                                          grant_reason: '',
                                        }
                                      ))
                                    })
                                  }}
                                  placeholder="+ Add roles"
                                  className="max-w-xs"
                                />
                              </div>

                              <div className="space-y-2">
                                {connectorGrantsForm.roles.map(cr => {
                                  const rObj = roles.find(r => r.id === cr.role_id)
                                  const roleColor = rObj?.color || '1E40AF'
                                  const cleanColor = roleColor.startsWith('#') ? roleColor : '#' + roleColor
                                  return (
                                    <div key={cr.role_id} className="p-3 bg-white border border-gray-200 rounded-lg space-y-3">
                                      <div className="flex flex-wrap items-center justify-between gap-4">
                                        <span
                                          className="px-2.5 py-1 rounded-full text-xs font-semibold border"
                                          style={{
                                            backgroundColor: cleanColor + '15',
                                            color: cleanColor,
                                            borderColor: cleanColor + '30',
                                          }}
                                        >
                                          {rObj?.name || 'Unknown'}
                                        </span>

                                        <div className="flex items-center gap-6">
                                          <button
                                            type="button"
                                            onClick={() => setExpandedConnectorRoles(prev => ({ ...prev, [cr.role_id]: !prev[cr.role_id] }))}
                                            className="text-xs text-accent-600 hover:text-accent-700 font-semibold focus:outline-none"
                                          >
                                            {expandedConnectorRoles[cr.role_id] ? 'Advanced ▲' : 'Advanced ▼'}
                                          </button>

                                          <div className="flex items-center gap-4 border-l border-gray-200 pl-4">
                                            {CRUD_FIELDS.map(f => (
                                              <label key={f.key} className="flex items-center gap-1 cursor-pointer text-xs">
                                                <input
                                                  type="checkbox"
                                                  className="rounded border-gray-300 text-accent-600 focus:ring-accent-500"
                                                  checked={(cr as any)[f.key]}
                                                  disabled={cr.is_deny}
                                                  onChange={e => {
                                                    setConnectorGrantsForm({
                                                      ...connectorGrantsForm,
                                                      roles: connectorGrantsForm.roles.map(item =>
                                                        item.role_id === cr.role_id ? { ...item, [f.key]: e.target.checked } : item
                                                      )
                                                    })
                                                  }}
                                                />
                                                {f.label.charAt(0)}
                                              </label>
                                            ))}
                                          </div>

                                          <button
                                            type="button"
                                            className="text-gray-400 hover:text-red-500 transition-colors"
                                            onClick={() => {
                                              setConnectorGrantsForm({
                                                ...connectorGrantsForm,
                                                roles: connectorGrantsForm.roles.filter(item => item.role_id !== cr.role_id)
                                              })
                                            }}
                                          >
                                            <Trash2 className="w-4 h-4" />
                                          </button>
                                        </div>
                                      </div>

                                      {expandedConnectorRoles[cr.role_id] && (
                                        <div className="space-y-3 pt-2 border-t border-gray-100 animate-fade-in">
                                          <div className="flex items-center">
                                            <label className="flex items-center gap-1.5 cursor-pointer text-xs font-semibold text-red-600">
                                              <input
                                                type="checkbox"
                                                className="rounded border-gray-350 text-red-650 focus:ring-red-500"
                                                checked={cr.is_deny}
                                                onChange={e => {
                                                  setConnectorGrantsForm({
                                                    ...connectorGrantsForm,
                                                    roles: connectorGrantsForm.roles.map(item =>
                                                      item.role_id === cr.role_id ? { ...item, is_deny: e.target.checked } : item
                                                    )
                                                  })
                                                }}
                                              />
                                              DENY ACCESS (Overrides all allow rules)
                                            </label>
                                          </div>
                                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                            <div>
                                              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Valid From</label>
                                              <input
                                                type="datetime-local"
                                                className="input text-xs py-1 px-2 h-auto"
                                                value={cr.valid_from || ''}
                                                onChange={e => {
                                                  setConnectorGrantsForm({
                                                    ...connectorGrantsForm,
                                                    roles: connectorGrantsForm.roles.map(item =>
                                                      item.role_id === cr.role_id ? { ...item, valid_from: e.target.value } : item
                                                    )
                                                  })
                                                }}
                                              />
                                            </div>
                                            <div>
                                              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Expires At</label>
                                              <input
                                                type="datetime-local"
                                                className="input text-xs py-1 px-2 h-auto"
                                                value={cr.expires_at || ''}
                                                onChange={e => {
                                                  setConnectorGrantsForm({
                                                    ...connectorGrantsForm,
                                                    roles: connectorGrantsForm.roles.map(item =>
                                                      item.role_id === cr.role_id ? { ...item, expires_at: e.target.value } : item
                                                    )
                                                  })
                                                }}
                                              />
                                            </div>
                                            <div>
                                              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Grant Reason</label>
                                              <input
                                                type="text"
                                                placeholder="Audit note"
                                                className="input text-xs py-1 px-2 h-auto"
                                                value={cr.grant_reason || ''}
                                                onChange={e => {
                                                  setConnectorGrantsForm({
                                                    ...connectorGrantsForm,
                                                    roles: connectorGrantsForm.roles.map(item =>
                                                      item.role_id === cr.role_id ? { ...item, grant_reason: e.target.value } : item
                                                    )
                                                  })
                                                }}
                                              />
                                            </div>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  )
                                })}
                                {connectorGrantsForm.roles.length === 0 && (
                                  <p className="text-xs text-gray-400 italic">No role permissions selected yet.</p>
                                )}
                              </div>
                            </div>

                            <div className="flex gap-3 border-t border-gray-200 pt-4">
                              <button
                                className="btn-primary text-sm px-4 py-2"
                                onClick={() => {
                                  if (connectorGrantsForm.departments.length === 0 && connectorGrantsForm.roles.length === 0) {
                                    toast.error('Please select at least one department or role')
                                    return
                                  }
                                  const formattedDepartments = connectorGrantsForm.departments.map(d => ({
                                    ...d,
                                    valid_from: d.valid_from ? new Date(d.valid_from).toISOString() : null,
                                    expires_at: d.expires_at ? new Date(d.expires_at).toISOString() : null,
                                    grant_reason: d.grant_reason || null,
                                  }))
                                  const formattedRoles = connectorGrantsForm.roles.map(r => ({
                                    ...r,
                                    valid_from: r.valid_from ? new Date(r.valid_from).toISOString() : null,
                                    expires_at: r.expires_at ? new Date(r.expires_at).toISOString() : null,
                                    grant_reason: r.grant_reason || null,
                                  }))
                                  bulkUpdateConnectorGrants.mutate({
                                    departments: formattedDepartments,
                                    roles: formattedRoles,
                                  })
                                }}
                                disabled={bulkUpdateConnectorGrants.isPending}
                              >
                                {bulkUpdateConnectorGrants.isPending ? 'Saving...' : 'Save Permissions'}
                              </button>
                              <button
                                type="button"
                                className="btn-secondary text-sm px-4 py-2"
                                onClick={() => {
                                  setShowConnectorGrantsForm(false)
                                  setConnectorGrantsForm({ departments: [], roles: [] })
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}

                        {/* Connector Grants Display */}
                        {(connectorGrants?.department_grants?.length > 0 || connectorGrants?.role_grants?.length > 0) && (
                          <div className="px-6 py-5 space-y-6">
                            <h4 className="text-sm font-semibold text-gray-800 border-b border-gray-100 pb-2">Connector Access Grants</h4>

                            {connectorGrants?.department_grants?.length > 0 && (
                              <div className="space-y-3">
                                <p className="text-xs text-gray-400 font-bold tracking-wider">DEPARTMENTS</p>
                                <div className="space-y-2">
                                  {connectorGrants.department_grants.map((dg: any) => {
                                    const dept = departments.find(d => d.id === dg.department_id)
                                    const deptColor = dg.is_deny ? 'EF4444' : (dept?.color || '1E40AF')
                                    const cleanColor = deptColor.startsWith('#') ? deptColor : '#' + deptColor
                                    const perms = []
                                    if (dg.can_read) perms.push('R')
                                    if (dg.can_create) perms.push('C')
                                    if (dg.can_update) perms.push('U')
                                    if (dg.can_delete) perms.push('D')

                                    const isInactive = !dg.is_active || dg.revoked_at
                                    const isHighlighted = highlightExpiring && expiringIds.has(dg.id)

                                    return (
                                      <div
                                        key={dg.id}
                                        id={`grant-${dg.id}`}
                                        className={`flex flex-wrap items-center justify-between gap-4 p-3 bg-white border border-gray-200 rounded-lg shadow-sm transition-all duration-300 ${isInactive ? 'opacity-55 bg-gray-50' : ''
                                          } ${isHighlighted ? 'ring-2 ring-amber-400 bg-amber-50/50' : ''}`}
                                        style={dg.is_deny ? { borderLeft: '4px solid #EF4444' } : undefined}
                                      >
                                        <div className="flex items-center gap-3">
                                          <span
                                            className="px-2.5 py-1 rounded-full text-xs font-semibold border"
                                            style={{
                                              backgroundColor: cleanColor + '15',
                                              color: cleanColor,
                                              borderColor: cleanColor + '30',
                                            }}
                                          >
                                            {dg.is_deny ? 'DENY:' : ''} {(() => {
                                              const roleObj = dg.role_id ? roles.find((r: any) => r.id === dg.role_id) : null
                                              return roleObj ? `${dept?.name || 'Unknown Department'}: ${roleObj.name}` : (dept?.name || 'Unknown Department')
                                            })()}
                                          </span>

                                          {!dg.is_deny && (
                                            <div className="flex gap-1">
                                              {perms.map(p => (
                                                <span key={p} className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200">
                                                  {p}
                                                </span>
                                              ))}
                                            </div>
                                          )}
                                        </div>

                                        <div className="flex items-center gap-4">
                                          {renderExpiryStatus(dg, () => revokeDeptPerm.mutate(dg.id))}
                                        </div>
                                      </div>
                                    )
                                  })}
                                </div>
                              </div>
                            )}

                            {connectorGrants?.role_grants?.length > 0 && (
                              <div className="space-y-3">
                                <p className="text-xs text-gray-400 font-bold tracking-wider">ROLES</p>
                                <div className="space-y-2">
                                  {connectorGrants.role_grants.map((rg: any) => {
                                    const role = roles.find(r => r.id === rg.role_id)
                                    const roleColor = rg.is_deny ? 'EF4444' : (role?.color || '1E40AF')
                                    const cleanColor = roleColor.startsWith('#') ? roleColor : '#' + roleColor
                                    const perms = []
                                    if (rg.can_read) perms.push('R')
                                    if (rg.can_create) perms.push('C')
                                    if (rg.can_update) perms.push('U')
                                    if (rg.can_delete) perms.push('D')

                                    const isInactive = !rg.is_active || rg.revoked_at
                                    const isHighlighted = highlightExpiring && expiringIds.has(rg.id)

                                    return (
                                      <div
                                        key={rg.id}
                                        id={`grant-${rg.id}`}
                                        className={`flex flex-wrap items-center justify-between gap-4 p-3 bg-white border border-gray-200 rounded-lg shadow-sm transition-all duration-300 ${isInactive ? 'opacity-55 bg-gray-50' : ''
                                          } ${isHighlighted ? 'ring-2 ring-amber-400 bg-amber-50/50' : ''}`}
                                        style={rg.is_deny ? { borderLeft: '4px solid #EF4444' } : undefined}
                                      >
                                        <div className="flex items-center gap-3">
                                          <span
                                            className="px-2.5 py-1 rounded-full text-xs font-semibold border"
                                            style={{
                                              backgroundColor: cleanColor + '15',
                                              color: cleanColor,
                                              borderColor: cleanColor + '30',
                                            }}
                                          >
                                            {rg.is_deny ? 'DENY:' : ''} {role?.name || 'Unknown Role'}
                                          </span>

                                          {!rg.is_deny && (
                                            <div className="flex gap-1">
                                              {perms.map(p => (
                                                <span key={p} className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200">
                                                  {p}
                                                </span>
                                              ))}
                                            </div>
                                          )}
                                        </div>

                                        <div className="flex items-center gap-4">
                                          {renderExpiryStatus(rg, () => revokeRolePerm.mutate(rg.id))}
                                        </div>
                                      </div>
                                    )
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        )}

                        {(!connectorGrants?.department_grants?.length || connectorGrants.department_grants.length === 0) &&
                          (!connectorGrants?.role_grants?.length || connectorGrants.role_grants.length === 0) && !showConnectorGrantsForm && (
                            <div className="px-6 py-5 text-xs text-gray-400 italic text-center">
                              No connector-level grants. Click "Grant Connector Access" to add departments or roles.
                            </div>
                          )}
                      </div>
                    )}

                    {!embedded && (
                      <div className="card">
                        <div className="px-6 py-4 flex items-center justify-between">
                          <div>
                            <h2 className="font-semibold text-gray-900">Row-Level Security</h2>
                            <p className="text-xs text-gray-400 mt-0.5">
                              Restrict row visibility per user, role, or department
                            </p>
                          </div>
                          <Link
                            to={`/access?tab=rls&connector=${selectedConnector}`}
                            className="btn-secondary text-sm flex items-center gap-1.5"
                          >
                            Manage RLS <ArrowRight className="w-3.5 h-3.5" />
                          </Link>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Debug Access Panel (Superadmin Only) */}
      {me?.is_superadmin && !hideDebug && (debugOnly || !embedded) && (
        <div className="card mt-6 overflow-visible">
          <div className="px-6 py-4 border-b border-border-muted bg-accent-50 rounded-t-xl">
            <div className="flex items-center gap-2">
              <Bug className="w-4 h-4 text-accent-600" />
              <h2 className="font-semibold text-gray-900">Debug Access</h2>
              <span className="badge bg-accent-100 text-accent-700 text-[10px] font-bold uppercase tracking-wider">Superadmin</span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Trace exactly why a user has or does not have access — resolves full role &amp; department hierarchy chains
            </p>
          </div>

          <div className="px-6 py-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* User Picker */}
              <div>
                <label className="label">User</label>
                <select
                  id="debug-user-picker"
                  className="input text-sm"
                  value={debugForm.user_id}
                  onChange={e => setDebugForm({ ...debugForm, user_id: e.target.value })}
                >
                  <option value="">- select user -</option>
                  {users.map((u: any) => (
                    <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                  ))}
                </select>
              </div>

              {/* Connector Picker */}
              <div>
                <label className="label">Connector</label>
                <select
                  id="debug-connector-picker"
                  className="input text-sm"
                  value={debugForm.connector_id}
                  onChange={e => {
                    setDebugForm({ ...debugForm, connector_id: e.target.value })
                    setDebugSelectedTables([])
                  }}
                >
                  <option value="">- select connector -</option>
                  {connectors.map((c: any) => (
                    <option key={c.id} value={c.id}>{c.name} ({c.type})</option>
                  ))}
                </select>
              </div>

              {/* Table Name (optional) */}
              <div>
                <label className="label">Table Name(s) <span className="text-gray-400 font-normal">(optional)</span></label>
                <SearchableTableSelector
                  allTables={debugConnectorTables}
                  selectedTables={debugSelectedTables}
                  onChange={setDebugSelectedTables}
                  placeholder={
                    !debugForm.connector_id
                      ? 'Select connector first...'
                      : isLoadingDebugSchema
                        ? 'Loading tables...'
                        : 'Select tables (optional)...'
                  }
                />
              </div>

              {/* Operation Dropdown */}
              <div>
                <label className="label">Operation</label>
                <select
                  id="debug-operation-picker"
                  className="input text-sm"
                  value={debugForm.operation}
                  onChange={e => setDebugForm({ ...debugForm, operation: e.target.value })}
                >
                  <option value="read">Read</option>
                  <option value="create">Create</option>
                  <option value="update">Update</option>
                  <option value="delete">Delete</option>
                </select>
              </div>
            </div>

            <div className="mt-4 flex gap-3">
              <button
                id="debug-submit-btn"
                className="btn-primary text-sm flex items-center gap-2"
                onClick={runDebug}
                disabled={debugLoading}
              >
                <Zap className="w-3.5 h-3.5" />
                {debugLoading ? 'Resolving...' : 'Check Permission'}
              </button>
              {(debugResult || debugForm.user_id || debugForm.connector_id || debugSelectedTables.length > 0) && (
                <button
                  id="debug-clear-btn"
                  className="btn-secondary text-sm"
                  onClick={() => {
                    setDebugResult(null)
                    setDebugForm({
                      user_id: '',
                      connector_id: '',
                      operation: 'read',
                    })
                    setDebugSelectedTables([])
                  }}
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Debug Result */}
          {debugResult && (
            <div className="border-t border-gray-100">
              {/* Decision Badge */}
              {(() => {
                const tables = debugResult.table_names || []
                if (tables.length > 1 && debugResult.decisions) {
                  const allowedCount = Object.values(debugResult.decisions).filter(d => d === 'allow').length
                  const totalCount = tables.length
                  const isAllAllow = allowedCount === totalCount
                  const isAllDeny = allowedCount === 0

                  if (isAllAllow) {
                    return (
                      <div className="px-6 py-5 flex items-center gap-4 bg-gradient-to-r from-emerald-50 to-green-50">
                        <div className="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center shadow-sm">
                          <CheckCircle className="w-7 h-7 text-emerald-600" />
                        </div>
                        <div>
                          <p className="text-xl font-bold text-emerald-700 tracking-tight">ALLOW</p>
                          <p className="text-xs text-emerald-600">User has permission for <span className="font-semibold">{debugResult.operation}</span> on all {totalCount} selected tables</p>
                        </div>
                      </div>
                    )
                  } else if (isAllDeny) {
                    return (
                      <div className="px-6 py-5 flex items-center gap-4 bg-gradient-to-r from-red-50 to-rose-50">
                        <div className="w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center shadow-sm">
                          <XCircle className="w-7 h-7 text-red-600" />
                        </div>
                        <div>
                          <p className="text-xl font-bold text-red-700 tracking-tight">DENY</p>
                          <p className="text-xs text-red-600">User is denied permission for <span className="font-semibold">{debugResult.operation}</span> on all {totalCount} selected tables</p>
                        </div>
                      </div>
                    )
                  } else {
                    return (
                      <div className="px-6 py-5 flex items-center gap-4 bg-gradient-to-r from-amber-50 to-yellow-50">
                        <div className="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center shadow-sm">
                          <AlertTriangle className="w-7 h-7 text-amber-600" />
                        </div>
                        <div>
                          <p className="text-xl font-bold text-amber-700 tracking-tight">MIXED</p>
                          <p className="text-xs text-amber-600">User has mixed permissions: <span className="font-semibold text-emerald-600">{allowedCount} allowed</span>, <span className="font-semibold text-red-600">{totalCount - allowedCount} denied</span></p>
                        </div>
                      </div>
                    )
                  }
                }

                // Default single table or connector check
                const isAllow = debugResult.decision === 'allow'
                const subject = tables.length === 1 ? `table "${tables[0]}"` : 'connector'
                return (
                  <div className={`px-6 py-5 flex items-center gap-4 ${isAllow
                    ? 'bg-gradient-to-r from-emerald-50 to-green-50'
                    : 'bg-gradient-to-r from-red-50 to-rose-50'
                    }`}>
                    {isAllow ? (
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center shadow-sm">
                          <CheckCircle className="w-7 h-7 text-emerald-600" />
                        </div>
                        <div>
                          <p className="text-xl font-bold text-emerald-700 tracking-tight">ALLOW</p>
                          <p className="text-xs text-emerald-600">User has permission for <span className="font-semibold">{debugResult.operation}</span> on {subject}</p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center shadow-sm">
                          <XCircle className="w-7 h-7 text-red-600" />
                        </div>
                        <div>
                          <p className="text-xl font-bold text-red-700 tracking-tight">DENY</p>
                          <p className="text-xs text-red-600">User does not have permission for <span className="font-semibold">{debugResult.operation}</span> on {subject}</p>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })()}

              {/* Individual Table Decisions (only for multi-table check) */}
              {debugResult.decisions && Object.keys(debugResult.decisions).length > 1 && (
                <div className="px-6 py-4 bg-gray-50 border-b border-gray-100">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Individual Table Permissions</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {Object.entries(debugResult.decisions).map(([tbl, dec]) => (
                      <div key={tbl} className="flex items-center justify-between p-2.5 bg-white border border-gray-200 rounded-lg shadow-sm">
                        <span className="font-mono text-xs text-gray-800 truncate pr-2" title={tbl}>{tbl}</span>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold ${dec === 'allow' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                          }`}>
                          {dec === 'allow' ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                          {dec === 'allow' ? 'ALLOW' : 'DENY'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Hierarchy Details */}
              <div className="px-6 py-5 grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Role Chain */}
                <div>
                  <div className="flex items-center gap-1.5 mb-3">
                    <Shield className="w-3.5 h-3.5 text-accent-500" />
                    <p className="text-xs font-semibold text-gray-700 uppercase tracking-wider">Role Chain</p>
                  </div>
                  {debugResult.role_chain.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-y-2 gap-x-1.5">
                      {debugResult.role_chain.map((r: any, idx: number) => (
                        <span key={r.id} className="flex items-center gap-1">
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold border ${idx === 0
                            ? 'bg-accent-100 text-accent-700 border-accent-200'
                            : 'bg-gray-100 text-gray-600 border-gray-200'
                            }`}>
                            {r.name}
                            <span className="ml-1 text-[10px] font-normal opacity-60">L{r.level}</span>
                          </span>
                          {idx < debugResult.role_chain.length - 1 && (
                            <ChevronRight className="w-3 h-3 text-gray-300 flex-shrink-0" />
                          )}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-400 italic">No role assigned</p>
                  )}
                </div>

                {/* Department Chain */}
                <div>
                  <div className="flex items-center gap-1.5 mb-3">
                    <Users className="w-3.5 h-3.5 text-amber-500" />
                    <p className="text-xs font-semibold text-gray-700 uppercase tracking-wider">Department Chain</p>
                  </div>
                  {debugResult.dept_chain.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-y-2 gap-x-1.5">
                      {debugResult.dept_chain.map((d: any, idx: number) => (
                        <span key={d.id} className="flex items-center gap-1">
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold border ${idx === 0
                            ? 'bg-amber-100 text-amber-800 border-amber-200'
                            : 'bg-gray-100 text-gray-600 border-gray-200'
                            }`}>
                            {d.name}
                          </span>
                          {idx < debugResult.dept_chain.length - 1 && (
                            <ChevronRight className="w-3 h-3 text-gray-300 flex-shrink-0" />
                          )}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-400 italic">No department assigned</p>
                  )}
                </div>

                {/* Managed Users Count */}
                <div>
                  <div className="flex items-center gap-1.5 mb-3">
                    <Users className="w-3.5 h-3.5 text-teal-500" />
                    <p className="text-xs font-semibold text-gray-700 uppercase tracking-wider">Managed Users</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-10 h-10 rounded-lg bg-teal-50 border border-teal-100 flex items-center justify-center">
                      <span className="text-lg font-bold text-teal-700">{debugResult.managed_user_count}</span>
                    </div>
                    <p className="text-xs text-gray-500">
                      {debugResult.managed_user_count === 0
                        ? 'No direct or indirect reports'
                        : `direct & indirect report${debugResult.managed_user_count > 1 ? 's' : ''}`
                      }
                    </p>
                  </div>
                </div>
              </div>


            </div>
          )}
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
                Revoke Access
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Direct Access Schedule & Reason Modal ──────────────────────── */}
      {scheduleEditUser && (() => {
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm animate-fade-in" onClick={closeScheduleEditModal} />
            <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100 flex flex-col max-h-[90vh] animate-scale-in">
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0 bg-gray-50/50">
                <div>
                  <h3 className="text-lg font-bold text-gray-900">Direct Access Settings</h3>
                  <p className="text-xs text-gray-500 mt-0.5">Configure override permissions for <span className="font-semibold text-gray-700">{scheduleEditUser.name}</span></p>
                </div>
                <button onClick={closeScheduleEditModal} className="p-1 rounded-md hover:bg-gray-105 transition-colors ml-2 text-gray-400">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {/* CRUD Checkboxes */}
                <div>
                  <label className="label text-xs">Direct Permissions</label>
                  <div className="flex items-center justify-between bg-gray-50 border border-gray-200/50 rounded-lg p-3">
                    {CRUD_FIELDS.map(f => (
                      <label key={f.key} className="flex items-center gap-1.5 cursor-pointer text-xs font-semibold text-gray-750">
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-accent-600 focus:ring-accent-500"
                          checked={modalPerms[f.key as keyof typeof modalPerms]}
                          onChange={e => setModalPerms(prev => ({ ...prev, [f.key]: e.target.checked }))}
                        />
                        {f.label}
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="label text-xs">Valid From (Optional)</label>
                  <input
                    type="datetime-local"
                    className="input text-sm"
                    value={modalValidFrom}
                    onChange={e => setModalValidFrom(e.target.value)}
                  />
                </div>

                <div>
                  <label className="label text-xs">Expires At (Optional)</label>
                  <input
                    type="datetime-local"
                    className="input text-sm"
                    value={modalExpiresAt}
                    onChange={e => setModalExpiresAt(e.target.value)}
                  />
                </div>

                <div>
                  <label className="label text-xs">Grant Reason (Optional)</label>
                  <input
                    type="text"
                    className="input text-sm"
                    placeholder="e.g. Temporary contractor support"
                    value={modalGrantReason}
                    onChange={e => setModalGrantReason(e.target.value)}
                  />
                </div>

                {managersSet.has(scheduleEditUser.id) && (
                  <div className="pt-2">
                    <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-gray-750">
                      <input
                        type="checkbox"
                        className="rounded border-gray-300 text-accent-600 focus:ring-accent-500"
                        checked={modalPerms.allow_share_access}
                        onChange={e => setModalPerms(prev => ({ ...prev, allow_share_access: e.target.checked }))}
                      />
                      Allow Team Sharing Access
                    </label>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 flex-shrink-0">
                <button type="button" onClick={closeScheduleEditModal} className="btn-secondary text-sm">
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => {
                    upsertPerm.mutate({
                      user_id: scheduleEditUser.id,
                      can_read: modalPerms.can_read,
                      can_create: modalPerms.can_create,
                      can_update: modalPerms.can_update,
                      can_delete: modalPerms.can_delete,
                      allow_share_access: modalPerms.allow_share_access,
                      valid_from: modalValidFrom ? new Date(modalValidFrom).toISOString() : null,
                      expires_at: modalExpiresAt ? new Date(modalExpiresAt).toISOString() : null,
                      grant_reason: modalGrantReason || null,
                    })
                    closeScheduleEditModal()
                  }}
                  disabled={upsertPerm.isPending}
                  className="btn-primary text-sm font-semibold"
                >
                  {upsertPerm.isPending ? 'Saving...' : 'Save Settings'}
                </button>
              </div>
            </div>
          </div>
        )
      })()}
    </div>
  )
}
