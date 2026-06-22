import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Shield, Plus, Trash2, Edit, X, AlertTriangle, RefreshCw, Check, Info, Lock, Eye, Calendar, User, UserCheck, Zap, Layers, Trash, CheckSquare
} from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/auth'
import { MultiSelect } from '../components/MultiSelect'
import { SearchableTableSelector } from '../components/SearchableTableSelector'

import { parseUTC } from '../lib/utils'

interface PackageConnectorRule {
  connector_id: string
  is_deny: boolean
  can_read: boolean
  can_create: boolean
  can_update: boolean
  can_delete: boolean
}

interface PackageTableRule {
  connector_id: string
  table_name: string
  is_deny: boolean
  can_read: boolean
  can_create: boolean
  can_update: boolean
  can_delete: boolean
}

interface PackageRLSFilter {
  connector_id: string
  table_name: string
  filter_expression: string
}

interface DeptAssignment {
  id: string
  department_id: string
  role_id: string | null
  valid_from: string | null
  expires_at: string | null
  revoked_at: string | null
  assigned_by: string
  assigned_at: string
}

interface RoleAssignment {
  id: string
  role_id: string
  valid_from: string | null
  expires_at: string | null
  revoked_at: string | null
  assigned_by: string
  assigned_at: string
}

interface AccessPackage {
  id: string
  name: string
  slug: string
  description: string | null
  color: string
  is_active: boolean
  connector_rules: PackageConnectorRule[]
  table_rules: PackageTableRule[]
  rls_filters: PackageRLSFilter[]
  dept_assignments: DeptAssignment[]
  role_assignments: RoleAssignment[]
  created_at: string
}

interface Connector {
  id: string
  name: string
  type: string
  num_tables?: number
}

interface Role {
  id: string
  name: string
}

interface Department {
  id: string
  name: string
}

interface UserData {
  id: string
  name: string
  email: string
}

interface EffectivePackage {
  package: {
    id: string
    name: string
    description: string | null
    color: string
    is_active: boolean
  }
  source_type: 'department' | 'role'
  source_name: string
  source_detail: string
}

const PRESET_COLORS = [
  { hex: '1E40AF', name: 'Deep Blue' },
  { hex: '047857', name: 'Emerald' },
  { hex: 'B45309', name: 'Amber' },
  { hex: 'BE185D', name: 'Rose' },
  { hex: '6D28D9', name: 'Royal Purple' },
  { hex: '0369A1', name: 'Sky Blue' },
  { hex: 'C2410C', name: 'Rust Orange' },
  { hex: '475569', name: 'Slate Gray' },
]

const PLACEHOLDERS = [
  { token: '{user.employee_code}', desc: "Employee code" },
  { token: '{user.name}', desc: "Name" },
  { token: '{user.email}', desc: "Email" },
]

interface PackagesPageProps {
  embedded?: boolean
}

export function PackagesPage({ embedded = false }: PackagesPageProps = {}) {
  const qc = useQueryClient()
  const { user: me } = useAuthStore()

  // Navigation / View State
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [activeTab, setActiveTab] = useState<'rules' | 'assignments' | 'rls'>('rules')
  const [packageStatusView, setPackageStatusView] = useState<'active' | 'inactive'>('active')

  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    confirmText: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    confirmText: 'Confirm',
    onConfirm: () => {},
  })

  // Rule Wizard State
  const [wizardStep, setWizardStep] = useState<number | null>(null)
  const [wizardType, setWizardType] = useState<'connector' | 'table' | 'rls'>('connector')
  const [wizardConnectorId, setWizardConnectorId] = useState('')
  const [wizardConnectorIds, setWizardConnectorIds] = useState<string[]>([])
  const [wizardConnectorAccess, setWizardConnectorAccess] = useState<Record<string, PackageConnectorRule>>({})
  const [wizardTableName, setWizardTableName] = useState('')
  const [wizardTableNames, setWizardTableNames] = useState<string[]>([])
  const [wizardIsDeny, setWizardIsDeny] = useState(false)
  const [wizardCanRead, setWizardCanRead] = useState(true)
  const [wizardCanCreate, setWizardCanCreate] = useState(false)
  const [wizardCanUpdate, setWizardCanUpdate] = useState(false)
  const [wizardCanDelete, setWizardCanDelete] = useState(false)
  const [wizardFilterExpr, setWizardFilterExpr] = useState('')

  const getColumnsForTable = (tableName: string) => {
    if (!schemaData?.tables || !tableName) return []
    const foundTable = schemaData.tables.find((t: any) => {
      const fullTName = t.schema ? `${t.schema}.${t.name}` : t.name
      return fullTName === tableName || t.name === tableName
    })
    return foundTable?.columns || []
  }

  const handleWizardPlaceholderClick = (token: string) => {
    const firstSelectedTable = wizardTableNames[0] || wizardTableName
    const tableColumns = firstSelectedTable ? getColumnsForTable(firstSelectedTable) : []

    const findMatchingColumn = (possibleNames: string[]) => {
      return tableColumns.find((col: any) => 
        possibleNames.some(name => col.name.toLowerCase() === name.toLowerCase() || col.name.toLowerCase().includes(name.toLowerCase()))
      )?.name
    }

    let expressionToInsert = ''
    if (token === '{user.employee_code}') {
      const colName = findMatchingColumn(['employee_code', 'emp_code', 'employee_id', 'emp_id', 'employee_no', 'emp_no', 'code']) || 'employee_code'
      expressionToInsert = `${colName} = '${token}'`
    } else if (token === '{user.name}') {
      const colName = findMatchingColumn(['name', 'full_name', 'username', 'user_name', 'display_name', 'first_name', 'last_name']) || 'name'
      expressionToInsert = `${colName} = '${token}'`
    } else if (token === '{user.email}') {
      const colName = findMatchingColumn(['email', 'email_address', 'usr_email', 'user_email', 'mail']) || 'email'
      expressionToInsert = `${colName} = '${token}'`
    } else {
      expressionToInsert = token
    }

    let prefix = ''
    if (wizardFilterExpr.trim().length > 0) {
      prefix = ' AND '
    }
    setWizardFilterExpr(prev => prev + prefix + expressionToInsert)
  }

  // Package Form Fields
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState('1E40AF')
  const [connectorRules, setConnectorRules] = useState<PackageConnectorRule[]>([])
  const [tableRules, setTableRules] = useState<PackageTableRule[]>([])
  const [rlsFilters, setRlsFilters] = useState<PackageRLSFilter[]>([])

  // Live RLS Filter Preview state inside Edit Modal
  const [previewUserId, setPreviewUserId] = useState('')
  const [previewResults, setPreviewResults] = useState<Record<number, string>>({})
  const [previewErrors, setPreviewErrors] = useState<Record<number, string>>({})
  const [previewLoading, setPreviewLoading] = useState<Record<number, boolean>>({})

  // Assignment fields
  const [assignMode, setAssignMode] = useState<'department' | 'role' | 'dept_role'>('dept_role')
  const [assignDeptIds, setAssignDeptIds] = useState<string[]>([])
  const [assignRoleIds, setAssignRoleIds] = useState<string[]>([])
  const [assignComboDeptId, setAssignComboDeptId] = useState('')
  const [assignComboRoleId, setAssignComboRoleId] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const [isAssigning, setIsAssigning] = useState(false)

  // Debug Panel states
  const [debugUserId, setDebugUserId] = useState('')
  const [effectivePackages, setEffectivePackages] = useState<EffectivePackage[]>([])
  const [isDebugLoading, setIsDebugLoading] = useState(false)

  // Queries
  const { data: packages = [], isLoading: isPackagesLoading } = useQuery<AccessPackage[]>({
    queryKey: ['accessPackages'],
    queryFn: () => api.get('/api/packages/').then(r => r.data),
  })

  const { data: connectors = [] } = useQuery<Connector[]>({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  const { data: schemaData, isFetching: isSchemaLoading } = useQuery({
    queryKey: ['connectorSchema', wizardConnectorId],
    queryFn: () => api.get(`/api/connectors/${wizardConnectorId}/schema`).then(r => r.data),
    enabled: !!wizardConnectorId,
  })

  const { data: roles = [] } = useQuery<Role[]>({
    queryKey: ['roles'],
    queryFn: () => api.get('/api/roles/').then(r => r.data),
  })

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ['departments'],
    queryFn: () => api.get('/api/departments/').then(r => r.data),
  })

  const { data: users = [] } = useQuery<UserData[]>({
    queryKey: ['users'],
    queryFn: () => api.get('/api/users/').then(r => r.data),
  })

  const invalidateAllAccess = () => {
    qc.invalidateQueries({ queryKey: ['permissions'] })
    qc.invalidateQueries({ queryKey: ['tablePermissions'] })
    qc.invalidateQueries({ queryKey: ['connectorGrants'] })
    qc.invalidateQueries({ queryKey: ['accessPackages'] })
  }

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: any) => api.post('/api/packages/', data),
    onSuccess: (res) => {
      invalidateAllAccess()
      toast.success('Access package created successfully')
      setSelectedPackageId(res.data.id)
      setIsCreating(false)
      setIsEditing(false)
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to create package')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.patch(`/api/packages/${id}`, data),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Access package updated successfully')
      setIsEditing(false)
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to update package')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/packages/${id}`),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Access package deleted')
      setSelectedPackageId(null)
      setIsEditing(false)
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to delete package')
    },
  })

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.patch(`/api/packages/${id}`, { is_active }),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Package status updated')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to update status')
    },
  })

  // Task 4: Wrap toggle in confirmModal
  const handleToggleActive = (pkg: AccessPackage) => {
    const newState = !pkg.is_active
    setConfirmModal({
      isOpen: true,
      title: newState ? 'Activate Package' : 'Deactivate Package',
      message: newState
        ? `Are you sure you want to activate "${pkg.name}"? All assigned departments and roles will immediately gain the configured access.`
        : `Are you sure you want to deactivate "${pkg.name}"? All departments and roles will lose access provided by this package.`,
      confirmText: newState ? 'Activate' : 'Deactivate',
      onConfirm: () => {
        toggleActiveMutation.mutate({ id: pkg.id, is_active: newState })
        setConfirmModal(prev => ({ ...prev, isOpen: false }))
      },
    })
  }

  const assignMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.post(`/api/packages/${id}/assign`, data),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Package assigned successfully')
      setAssignDeptIds([])
      setAssignRoleIds([])
      setAssignComboDeptId('')
      setAssignComboRoleId('')
      setValidFrom('')
      setExpiresAt('')
      setIsAssigning(false)
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to assign package')
    },
  })

  const revokeAssignmentMutation = useMutation({
    mutationFn: ({ packageId, assignmentId }: { packageId: string; assignmentId: string }) =>
      api.post(`/api/packages/${packageId}/revoke/assignment/${assignmentId}`),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Assignment revoked')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to revoke assignment')
    },
  })

  const revokeDeptMutation = useMutation({
    mutationFn: ({ packageId, deptId }: { packageId: string; deptId: string }) =>
      api.post(`/api/packages/${packageId}/revoke/dept/${deptId}`),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Department assignment revoked')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to revoke assignment')
    },
  })

  const revokeRoleMutation = useMutation({
    mutationFn: ({ packageId, roleId }: { packageId: string; roleId: string }) =>
      api.post(`/api/packages/${packageId}/revoke/role/${roleId}`),
    onSuccess: () => {
      invalidateAllAccess()
      toast.success('Role assignment revoked')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to revoke assignment')
    },
  })

  // Helpers
  const selectedPackage = packages.find(p => p.id === selectedPackageId)
  const availableConnectorOptions = connectors
    .filter(c => !connectorRules.some(r => r.connector_id === c.id))
    .map(c => ({ id: c.id, label: `${c.name} (${c.type})` }))
  const ruleConnectorOptions = connectorRules.map(r => {
    const connector = connectors.find(c => c.id === r.connector_id)
    return {
      id: r.connector_id,
      label: connector ? `${connector.name} (${connector.type})` : r.connector_id,
    }
  })
  const wizardTableOptions = (schemaData?.tables || []).map((t: any) => (
    t.schema ? `${t.schema}.${t.name}` : t.name
  ))

  const defaultConnectorRule = (connectorId: string): PackageConnectorRule => ({
    connector_id: connectorId,
    is_deny: false,
    can_read: true,
    can_create: false,
    can_update: false,
    can_delete: false,
  })

  const setWizardConnectorSelection = (ids: string[]) => {
    setWizardConnectorIds(ids)
    setWizardConnectorAccess(prev => ids.reduce<Record<string, PackageConnectorRule>>((next, id) => {
      next[id] = prev[id] || defaultConnectorRule(id)
      return next
    }, {}))
  }

  const updateWizardConnectorAccess = (connectorId: string, fields: Partial<PackageConnectorRule>) => {
    setWizardConnectorAccess(prev => ({
      ...prev,
      [connectorId]: {
        ...(prev[connectorId] || defaultConnectorRule(connectorId)),
        ...fields,
      },
    }))
  }

  const handleStartCreate = () => {
    setName('')
    setDescription('')
    setColor('1E40AF')
    setConnectorRules([])
    setTableRules([])
    setRlsFilters([])
    setPackageStatusView('active')
    setIsCreating(true)
    setIsEditing(false)
    setSelectedPackageId(null)
  }

  const handleStartEdit = () => {
    if (!selectedPackage) return
    setName(selectedPackage.name)
    setDescription(selectedPackage.description || '')
    setColor(selectedPackage.color)
    setConnectorRules([...selectedPackage.connector_rules])
    setTableRules([...selectedPackage.table_rules])
    setRlsFilters([...selectedPackage.rls_filters])
    setPreviewResults({})
    setPreviewErrors({})
    setIsAssigning(false)
    setIsEditing(true)
    setIsCreating(false)
  }

  const handleSavePackage = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      toast.error('Please enter a package name')
      return
    }

    const payload = {
      name: name.trim(),
      description: description.trim() || null,
      color,
      connector_rules: connectorRules,
      table_rules: tableRules,
      rls_filters: rlsFilters,
    }

    if (isCreating) {
      createMutation.mutate(payload)
    } else if (selectedPackageId) {
      updateMutation.mutate({ id: selectedPackageId, data: payload })
    }
  }

  // Connector Rule Form Helpers
  const addConnectorRule = () => {
    const unaddedConnector = connectors.find(c => !connectorRules.some(r => r.connector_id === c.id))
    if (!unaddedConnector) {
      toast.error('All connectors already have rules defined')
      return
    }
    setConnectorRules([
      ...connectorRules,
      {
        connector_id: unaddedConnector.id,
        is_deny: false,
        can_read: true,
        can_create: false,
        can_update: false,
        can_delete: false,
      }
    ])
  }

  const updateConnectorRule = (index: number, fields: Partial<PackageConnectorRule>) => {
    const next = [...connectorRules]
    next[index] = { ...next[index], ...fields }
    setConnectorRules(next)
  }

  const removeConnectorRule = (index: number) => {
    setConnectorRules(connectorRules.filter((_, i) => i !== index))
  }

  // Table Rule Form Helpers
  const addTableRule = () => {
    if (connectors.length === 0) return
    setTableRules([
      ...tableRules,
      {
        connector_id: connectors[0].id,
        table_name: '',
        is_deny: false,
        can_read: true,
        can_create: false,
        can_update: false,
        can_delete: false,
      }
    ])
  }

  const updateTableRule = (index: number, fields: Partial<PackageTableRule>) => {
    const next = [...tableRules]
    next[index] = { ...next[index], ...fields }
    setTableRules(next)
  }

  const removeTableRule = (index: number) => {
    setTableRules(tableRules.filter((_, i) => i !== index))
  }

  // RLS Filter Form Helpers
  const addRlsFilter = () => {
    if (connectors.length === 0) return
    setRlsFilters([
      ...rlsFilters,
      {
        connector_id: connectors[0].id,
        table_name: '',
        filter_expression: '',
      }
    ])
  }

  const updateRlsFilter = (index: number, fields: Partial<PackageRLSFilter>) => {
    const next = [...rlsFilters]
    next[index] = { ...next[index], ...fields }
    setRlsFilters(next)
  }

  const removeRlsFilter = (index: number) => {
    setRlsFilters(rlsFilters.filter((_, i) => i !== index))
  }

  // RLS Filter Chips Insertion
  const handleInsertPlaceholder = (filterIndex: number, token: string) => {
    const filter = rlsFilters[filterIndex]
    const nextExpr = filter.filter_expression + token
    updateRlsFilter(filterIndex, { filter_expression: nextExpr })
  }

  // Live RLS Preview Call
  const handlePreviewRLS = async (filterIndex: number, expr: string) => {
    if (!previewUserId) {
      toast.error('Select a preview user first')
      return
    }
    if (!expr.trim()) {
      toast.error('Filter expression is empty')
      return
    }

    setPreviewLoading(prev => ({ ...prev, [filterIndex]: true }))
    setPreviewResults(prev => {
      const copy = { ...prev }
      delete copy[filterIndex]
      return copy
    })
    setPreviewErrors(prev => {
      const copy = { ...prev }
      delete copy[filterIndex]
      return copy
    })

    try {
      const res = await api.get('/api/rls/preview', {
        params: {
          user_id: previewUserId,
          filter_expression: expr
        }
      })
      setPreviewResults(prev => ({ ...prev, [filterIndex]: res.data.substituted }))
    } catch (err: any) {
      setPreviewErrors(prev => ({ ...prev, [filterIndex]: err.response?.data?.detail || 'Preview generation failed' }))
    } finally {
      setPreviewLoading(prev => ({ ...prev, [filterIndex]: false }))
    }
  }

  // Assignment trigger
  const handleAssign = () => {
    if (!selectedPackageId) return

    if (assignMode === 'dept_role') {
      if (!assignComboDeptId || !assignComboRoleId) {
        toast.error('Please select both a Department and a Role')
        return
      }
      assignMutation.mutate({
        id: selectedPackageId,
        data: {
          department_ids: [],
          role_ids: [],
          dept_role_assignments: [{ department_id: assignComboDeptId, role_id: assignComboRoleId }],
          valid_from: validFrom ? new Date(validFrom).toISOString() : null,
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : null
        }
      })
    } else if (assignMode === 'department') {
      if (assignDeptIds.length === 0) {
        toast.error('Please choose at least one Department')
        return
      }
      assignMutation.mutate({
        id: selectedPackageId,
        data: {
          department_ids: assignDeptIds,
          role_ids: [],
          dept_role_assignments: [],
          valid_from: validFrom ? new Date(validFrom).toISOString() : null,
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : null
        }
      })
    } else {
      if (assignRoleIds.length === 0) {
        toast.error('Please choose at least one Role')
        return
      }
      assignMutation.mutate({
        id: selectedPackageId,
        data: {
          department_ids: [],
          role_ids: assignRoleIds,
          dept_role_assignments: [],
          valid_from: validFrom ? new Date(validFrom).toISOString() : null,
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : null
        }
      })
    }
  }

  // Load Debug Effective Packages
  const handleLoadEffectivePackages = async () => {
    if (!debugUserId) {
      toast.error('Select a user to run analysis')
      return
    }
    setIsDebugLoading(true)
    setEffectivePackages([])

    try {
      const res = await api.get(`/api/packages/user/${debugUserId}/active`)
      setEffectivePackages(res.data)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load user active packages')
    } finally {
      setIsDebugLoading(false)
    }
  }

  const getConnectorName = (id: string) => connectors.find(c => c.id === id)?.name || id
  const getRoleName = (id: string) => roles.find(r => r.id === id)?.name || id
  const getDeptName = (id: string) => departments.find(d => d.id === id)?.name || id

  const getPackageTablesCount = (pkg: any) => {
    let count = pkg.table_rules.length
    for (const cr of pkg.connector_rules) {
      if (!cr.is_deny && cr.can_read) {
        const hasTableRules = pkg.table_rules.some((tr: any) => tr.connector_id === cr.connector_id)
        if (!hasTableRules) {
          const connector = connectors.find(c => c.id === cr.connector_id)
          if (connector) {
            count += (connector.num_tables || 0)
          }
        }
      }
    }
    return count
  }

  const getBadgeStyle = (hexColor: string) => {
    const clean = hexColor.startsWith('#') ? hexColor : '#' + hexColor
    return {
      backgroundColor: clean + '12',
      color: clean,
      borderColor: clean + '25',
    }
  }

  // Active status checker (client-side visualization)
  const isAssignmentActive = (a: any) => {
    if (a.revoked_at) return false
    const now = new Date()
    const validFrom = a.valid_from ? parseUTC(a.valid_from) : null
    const expiresAt = a.expires_at ? parseUTC(a.expires_at) : null
    if (validFrom && validFrom > now) return false
    if (expiresAt && expiresAt < now) return false
    return true
  }

  const activePackages = packages.filter(pkg => pkg.is_active)
  const inactivePackages = packages.filter(pkg => !pkg.is_active)
  const visiblePackages = packageStatusView === 'active' ? activePackages : inactivePackages
  const isInactiveView = packageStatusView === 'inactive'

  return (
    <div className={embedded ? 'p-4 space-y-6' : 'p-8 max-w-7xl mx-auto space-y-8'}>
      {/* Header */}
      {embedded ? (
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-text-muted">Reusable access bundles for departments and roles</p>
          {!isEditing && !isCreating && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setSelectedPackageId(null)
                  setPackageStatusView(isInactiveView ? 'active' : 'inactive')
                }}
                className="btn-secondary text-sm py-2 px-4"
              >
                {isInactiveView ? `Active Packages (${activePackages.length})` : `Inactive Packages (${inactivePackages.length})`}
              </button>
              <button onClick={handleStartCreate} className="btn-primary text-sm flex items-center gap-2 py-2 px-4">
                <Plus className="w-4 h-4" /> Create Package
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight flex items-center gap-3">
              <Layers className="w-8 h-8 text-brand-600" />
              Access Packages & Bundles
            </h1>
            <p className="text-gray-500 mt-1 text-sm max-w-xl">
              Group connectors, tables, and row-level security policies into reusable access packages. Assign them to departments or roles dynamically.
            </p>
          </div>
          {!isEditing && !isCreating && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setSelectedPackageId(null)
                  setPackageStatusView(isInactiveView ? 'active' : 'inactive')
                }}
                className="btn-secondary py-2.5 px-4 text-sm justify-center"
              >
                {isInactiveView ? `Active Packages (${activePackages.length})` : `Inactive Packages (${inactivePackages.length})`}
              </button>
              <button onClick={handleStartCreate} className="btn-primary py-2.5 px-5 flex items-center gap-2 text-sm justify-center shadow-lg">
                <Plus className="w-4 h-4" /> Create Package
              </button>
            </div>
          )}
        </div>
      )}

      {/* Main Layout Split */}
      {isCreating || isEditing ? (
        /* ─── CREATE / EDIT FORM VIEW ─── */
        <form onSubmit={handleSavePackage} className="bg-white rounded-2xl border border-gray-250/80 shadow-md p-8 space-y-8 animate-fade-in">
          <div className="flex items-center justify-between border-b border-gray-100 pb-5">
            <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              {isCreating ? <Plus className="w-5 h-5 text-brand-600" /> : <Edit className="w-5 h-5 text-brand-650" />}
              {isCreating ? 'Create Access Package' : `Edit Access Package: ${name}`}
            </h2>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => {
                  setIsCreating(false)
                  setIsEditing(false)
                }}
                className="btn-secondary py-2 px-4 text-sm"
              >
                Cancel
              </button>
              <button type="submit" className="btn-primary py-2 px-5 text-sm shadow-md font-semibold">
                Save Package
              </button>
            </div>
          </div>

          {/* Basic Package Metadata */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            <div className="md:col-span-6 space-y-1.5">
              <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider">Package Name</label>
              <input
                type="text"
                required
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Finance Auditing Package"
                className="w-full px-3.5 py-2.5 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none"
              />
            </div>
            
            <div className="md:col-span-4 space-y-1.5">
              <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider">Badge Color</label>
              <div className="flex flex-wrap gap-2.5 items-center mt-1">
                {PRESET_COLORS.map(c => (
                  <button
                    key={c.hex}
                    type="button"
                    onClick={() => setColor(c.hex)}
                    className={`w-6 h-6 rounded-full border-2 transition-all ${
                      color === c.hex ? 'scale-110 shadow-md border-black' : 'border-transparent'
                    }`}
                    style={{ backgroundColor: '#' + c.hex }}
                    title={c.name}
                  />
                ))}
              </div>
            </div>

            <div className="md:col-span-12 space-y-1.5">
              <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider">Description</label>
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                rows={2}
                placeholder="Describe who needs this package and what data access it provides."
                className="w-full px-3.5 py-2.5 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none"
              />
            </div>
          </div>
          <hr className="border-gray-100" />

          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-gray-900">Configure Access Rules</h3>
              <p className="text-xs text-gray-500 mt-0.5 font-normal">Define connector permissions, table exclusions, and RLS policies for this package.</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setWizardType('connector')
                setWizardConnectorId('')          // reset before anything else
                setWizardTableName('')
                setWizardTableNames([])
                setWizardIsDeny(false)
                setWizardCanRead(true)
                setWizardCanCreate(false)
                setWizardCanUpdate(false)
                setWizardCanDelete(false)
                setWizardFilterExpr('')
                const firstAvailableConnectorId = availableConnectorOptions[0]?.id || ''
                setWizardConnectorSelection(firstAvailableConnectorId ? [firstAvailableConnectorId] : [])
                setWizardStep(1)
              }}
              className="btn-primary py-2 px-4 flex items-center gap-1.5 text-xs font-semibold shadow"
            >
              <Plus className="w-4 h-4" /> Add Rule
            </button>
          </div>

          {/* CONNECTOR RULES */}
          <div className="space-y-4">
            <div>
              <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider">Connector-Level Rules</h4>
              <p className="text-[11px] text-gray-400">Grants/denies complete access to entire databases or warehouses.</p>
            </div>
            {connectorRules.length === 0 ? (
              <div className="text-center py-6 border border-dashed border-gray-200 rounded-xl text-gray-400 text-xs">
                No connector-level rules defined yet.
              </div>
            ) : (
              <div className="space-y-3">
                {connectorRules.map((r, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-4 bg-gray-50 p-4 rounded-xl border border-gray-150 relative">
                    <div className="w-56 text-xs font-semibold text-gray-800">
                      {getConnectorName(r.connector_id)}
                    </div>
                    <div className="flex items-center gap-4">
                      {r.is_deny ? (
                        <span className="text-xs font-bold text-red-650 uppercase">Deny Access</span>
                      ) : (
                        <div className="flex items-center gap-3 pl-3 border-l border-gray-250 font-mono text-[10px]">
                          {r.can_read && <span className="bg-green-50 text-green-700 px-1.5 py-0.5 rounded">R</span>}
                          {r.can_create && <span className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">C</span>}
                          {r.can_update && <span className="bg-orange-50 text-orange-700 px-1.5 py-0.5 rounded">U</span>}
                          {r.can_delete && <span className="bg-red-50 text-red-700 px-1.5 py-0.5 rounded">D</span>}
                        </div>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeConnectorRule(i)}
                      className="ml-auto p-1.5 text-gray-400 hover:text-red-600 rounded-md hover:bg-red-50 transition-colors"
                    >
                      <Trash className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <hr className="border-gray-100" />

          {/* TABLE RULES LIST */}
          <div className="space-y-4">
            <div>
              <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider">Table-Level Rules</h4>
              <p className="text-[11px] text-gray-400">Grants/denies specific access to table names within connectors.</p>
            </div>
            {tableRules.length === 0 ? (
              <div className="text-center py-6 border border-dashed border-gray-200 rounded-xl text-gray-400 text-xs">
                No table-level rules defined yet.
              </div>
            ) : (
              <div className="space-y-3">
                {tableRules.map((r, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-4 bg-gray-55 p-4 rounded-xl border border-gray-150">
                    <div className="text-xs font-semibold text-gray-800">
                      {getConnectorName(r.connector_id)} <span className="text-gray-400 mx-1">/</span> <code className="font-mono text-xs">{r.table_name}</code>
                    </div>
                    <div className="flex items-center gap-4">
                      {r.is_deny ? (
                        <span className="text-xs font-bold text-red-650 uppercase">Deny Access</span>
                      ) : (
                        <div className="flex items-center gap-3 pl-3 border-l border-gray-250 font-mono text-[10px]">
                          {r.can_read && <span className="bg-green-50 text-green-700 px-1.5 py-0.5 rounded">R</span>}
                          {r.can_create && <span className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">C</span>}
                          {r.can_update && <span className="bg-orange-50 text-orange-700 px-1.5 py-0.5 rounded">U</span>}
                          {r.can_delete && <span className="bg-red-50 text-red-700 px-1.5 py-0.5 rounded">D</span>}
                        </div>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeTableRule(i)}
                      className="ml-auto p-1.5 text-gray-400 hover:text-red-605 rounded-md hover:bg-red-50 transition-colors"
                    >
                      <Trash className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <hr className="border-gray-100" />

          {/* RLS FILTERS LIST */}
          <div className="space-y-4">
            <div>
              <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider">Row-Level Security Filters</h4>
              <p className="text-[11px] text-gray-400">Binds database filters containing placeholder strings to enforce visibility scoping.</p>
            </div>
            {rlsFilters.length === 0 ? (
              <div className="text-center py-6 border border-dashed border-gray-200 rounded-xl text-gray-400 text-xs">
                No RLS filters configured for this package.
              </div>
            ) : (
              <div className="space-y-4">
                {rlsFilters.map((f, idx) => (
                  <div key={idx} className="bg-gray-55 p-4 rounded-xl border border-gray-150 space-y-2 relative">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-semibold text-gray-800">
                        {getConnectorName(f.connector_id)} <span className="text-gray-400 mx-1">|</span> <code className="font-mono text-xs">{f.table_name}</code>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeRlsFilter(idx)}
                        className="p-1.5 text-gray-400 hover:text-red-600 rounded-md hover:bg-red-50 transition-colors"
                      >
                        <Trash className="w-4 h-4" />
                      </button>
                    </div>
                    <pre className="bg-gray-900 text-green-400 p-2.5 rounded font-mono text-xs whitespace-pre-wrap overflow-x-auto shadow-inner">
                      {f.filter_expression}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Disabled old section */}
          {false && (
            <>
          <hr className="border-gray-100" />

          {/* CONNECTOR RULES */}
          <div className="space-y-4">
            <div>
              <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider">Table-Level Rules</h4>
              <p className="text-[11px] text-gray-400">Grants/denies specific access to table names within connectors.</p>
            </div>
          </div>
          </>
          )}

        </form>
      ) : (
        /* ─── MAIN MASTER VIEW (CARDS LIST) ─── */
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
          
          {/* Left Side: Package Cards List (8 cols or 12) */}
          <div className={me?.is_superadmin ? "xl:col-span-8 space-y-6" : "xl:col-span-12 space-y-6"}>
            {isPackagesLoading ? (
              <div className="text-center py-20 text-gray-400">
                <RefreshCw className="w-10 h-10 animate-spin mx-auto mb-3 text-gray-300" />
                <p className="text-sm font-medium">Loading access packages...</p>
              </div>
            ) : visiblePackages.length === 0 ? (
              <div className="text-center bg-white rounded-2xl border border-gray-200 py-16 px-4">
                <Layers className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-bold text-gray-900">
                  {isInactiveView ? 'No Inactive Packages' : 'No Active Access Packages'}
                </h3>
                <p className="text-sm text-gray-500 mt-2 max-w-md mx-auto">
                  {isInactiveView
                    ? 'Deleted or deactivated packages will appear here.'
                    : 'Access packages let you bundle queries, table permissions, and RLS rules, and assign them in bulk. Get started by creating your first package.'}
                </p>
                {isInactiveView ? (
                  <button
                    type="button"
                    onClick={() => setPackageStatusView('active')}
                    className="btn-secondary py-2 px-5 mt-5 inline-flex items-center gap-2 text-sm"
                  >
                    View Active Packages
                  </button>
                ) : (
                  <button onClick={handleStartCreate} className="btn-primary py-2 px-5 mt-5 inline-flex items-center gap-2 text-sm">
                    <Plus className="w-4 h-4" /> Create Package
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {visiblePackages.map(pkg => (
                  <div
                    key={pkg.id}
                    onClick={() => setSelectedPackageId(pkg.id)}
                    className={`cursor-pointer bg-white rounded-2xl border transition-all p-5 flex flex-col justify-between space-y-4 hover:shadow-md ${
                      selectedPackageId === pkg.id ? 'border-brand-500 ring-2 ring-brand-500/10' : 'border-gray-200/80'
                    }`}
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span
                          className="px-3 py-1 rounded-full text-xs font-bold border"
                          style={getBadgeStyle(pkg.color)}
                        >
                          {pkg.name}
                        </span>
                        
                        {/* Active Switch */}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleToggleActive(pkg)
                          }}
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            pkg.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-150 text-gray-600'
                          }`}
                        >
                          {pkg.is_active ? 'Active' : 'Reactivate'}
                        </button>
                      </div>
                      
                      <p className="text-sm font-semibold text-gray-900 tracking-tight">{pkg.slug}</p>
                      <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed">{pkg.description || 'No description provided.'}</p>
                    </div>

                    <div className="border-t border-gray-100 pt-3.5 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-gray-400 font-medium">
                      <span>Connectors: <strong>{pkg.connector_rules.length}</strong></span>
                      <span>Tables: <strong>{getPackageTablesCount(pkg)}</strong></span>
                      <span>RLS Filters: <strong>{pkg.rls_filters.length}</strong></span>
                      <span>Assignments: <strong>{pkg.dept_assignments.filter(a => isAssignmentActive(a)).length + pkg.role_assignments.filter(a => isAssignmentActive(a)).length}</strong></span>
                    </div>
                  </div>
                ))}
                {false && selectedPackage && (
                    <></>
                )}
              </div>
            )}
          </div>

          {/* Right Side: Superadmin User Analysis panel */}
          {me?.is_superadmin && (
            <div className="xl:col-span-4 space-y-6">
              <div className="bg-white rounded-2xl border border-gray-200/80 shadow-sm p-6 space-y-5">
                <div>
                  <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                    <UserCheck className="w-4.5 h-4.5 text-brand-650" />
                    Effective Packages Resolver
                  </h2>
                  <p className="text-xs text-gray-500 mt-1">
                    Select any user to inspect all access packages resolving to them through role and department inheritance.
                  </p>
                </div>

                <div className="space-y-3">
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Select User
                  </label>
                  <div className="flex gap-2">
                    <select
                      value={debugUserId}
                      onChange={e => setDebugUserId(e.target.value)}
                      className="flex-1 min-w-0 px-3 py-2 border border-gray-250 rounded-lg text-sm bg-white focus:outline-none"
                    >
                      <option value="">-- Choose User --</option>
                      {users.filter((u: any) => !u.is_superadmin).map(u => (
                        <option key={u.id} value={u.id}>
                          {u.name} ({u.email})
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={handleLoadEffectivePackages}
                      disabled={!debugUserId || isDebugLoading}
                      className="btn-primary px-3.5 flex items-center justify-center flex-shrink-0"
                      title="Load Active Packages"
                    >
                      <RefreshCw className={`w-4 h-4 ${isDebugLoading ? 'animate-spin' : ''}`} />
                    </button>
                  </div>
                </div>

                {effectivePackages.length > 0 ? (
                  <div className="space-y-3 border-t border-gray-150 pt-4 animate-fade-in">
                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Active User Packages</p>
                    <div className="space-y-2.5 max-h-96 overflow-y-auto">
                      {effectivePackages.map((ep, idx) => (
                        <div key={idx} className="bg-gray-50 border border-gray-200 p-3 rounded-xl space-y-1 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-gray-900">{ep.package.name}</span>
                            <span
                              className="w-2.5 h-2.5 rounded-full"
                              style={{ backgroundColor: '#' + ep.package.color }}
                            />
                          </div>
                          <p className="text-[11px] text-gray-500 leading-tight">
                            via {ep.source_detail}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : debugUserId && !isDebugLoading && (
                  <div className="text-center py-6 text-xs text-gray-400 border-t border-gray-150 pt-4">
                    No active packages resolved for this user.
                  </div>
                )}
              </div>
            </div>
          )}

        </div>
      )}

      {/* Access Package Detail Drawer */}
      {selectedPackage && !isCreating && !isEditing && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/45 backdrop-blur-sm animate-fade-in" onClick={() => setSelectedPackageId(null)} />
          {/* Drawer Body */}
          <div className="relative w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col transition-all duration-300 transform translate-x-0 overflow-hidden">
            {/* Header */}
            <div className="px-6 py-5 border-b border-gray-150 flex items-center justify-between bg-gray-50/50">
              <div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold border" style={getBadgeStyle(selectedPackage.color)}>
                  {selectedPackage.name}
                </span>
                <p className="text-[11px] text-gray-505 mt-1">Slug: <span className="font-mono">{selectedPackage.slug}</span> | Created {new Date(selectedPackage.created_at).toLocaleDateString()}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    handleToggleActive(selectedPackage)
                  }}
                  className="btn-secondary py-1.5 px-3 flex items-center gap-1.5 text-xs font-semibold shadow-sm"
                >
                  {selectedPackage.is_active ? 'Deactivate' : 'Reactivate'}
                </button>
                <button
                  onClick={handleStartEdit}
                  className="btn-secondary py-1.5 px-3 flex items-center gap-1.5 text-xs font-semibold shadow-sm"
                >
                  <Edit className="w-3.5 h-3.5" /> Edit
                </button>
                {selectedPackage.is_active && (
                  <button
                    onClick={() => {
                      setConfirmModal({
                        isOpen: true,
                        title: 'Delete Access Package',
                        message: `Are you sure you want to soft-delete package "${selectedPackage.name}"? It will move to Inactive Packages.`,
                        confirmText: 'Delete Package',
                        onConfirm: () => {
                          deleteMutation.mutate(selectedPackage.id)
                          setConfirmModal(prev => ({ ...prev, isOpen: false }))
                        }
                      })
                    }}
                    className="bg-red-50 hover:bg-red-100 border border-red-200 text-red-650 rounded-lg py-1.5 px-3 flex items-center gap-1.5 text-xs font-semibold"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </button>
                )}
                <button onClick={() => setSelectedPackageId(null)} className="p-1 hover:bg-gray-100 rounded text-gray-550 ml-2">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-100 px-6 bg-gray-50/20">
              {(['rules', 'assignments', 'rls'] as const).map(tab => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={`px-5 py-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-all -mb-px ${
                    activeTab === tab
                      ? 'border-brand-600 text-brand-650 font-extrabold'
                      : 'border-transparent text-gray-500 hover:text-gray-800'
                  }`}
                >
                  {tab === 'rules' ? 'Rules' : tab === 'assignments' ? 'Assignments' : 'RLS Filters'}
                </button>
              ))}
            </div>

            {/* Content Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {activeTab === 'rules' && (
                <div className="space-y-6">
                  {/* Connector Rules */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-gray-505 uppercase tracking-wider">Connector Rules</h4>
                    {selectedPackage.connector_rules.length === 0 ? (
                      <p className="text-xs text-gray-400 italic">No connector-level rules defined.</p>
                    ) : (
                      <div className="space-y-2">
                        {selectedPackage.connector_rules.map((cr, idx) => (
                          <div key={idx} className="bg-gray-50 border border-gray-150 rounded-xl p-3 flex justify-between items-center text-xs animate-fade-in">
                            <span className="font-semibold text-gray-900">{getConnectorName(cr.connector_id)}</span>
                            {cr.is_deny ? (
                              <span className="text-[10px] font-bold uppercase text-red-655 bg-red-50 border border-red-205 px-2 py-0.5 rounded">DENY</span>
                            ) : (
                              <div className="flex gap-1.5 font-mono text-[10px]">
                                {cr.can_read && <span className="bg-green-55 text-green-700 px-1.5 py-0.5 rounded">R</span>}
                                {cr.can_create && <span className="bg-blue-55 text-blue-700 px-1.5 py-0.5 rounded">C</span>}
                                {cr.can_update && <span className="bg-orange-55 text-orange-700 px-1.5 py-0.5 rounded">U</span>}
                                {cr.can_delete && <span className="bg-red-55 text-red-700 px-1.5 py-0.5 rounded">D</span>}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Table Rules */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-gray-505 uppercase tracking-wider">Table Rules</h4>
                    {selectedPackage.table_rules.length === 0 ? (
                      <p className="text-xs text-gray-400 italic">No table-level rules defined.</p>
                    ) : (
                      <div className="space-y-2">
                        {selectedPackage.table_rules.map((tr, idx) => (
                          <div key={idx} className="bg-gray-50 border border-gray-155 rounded-xl p-3 flex justify-between items-center text-xs animate-fade-in">
                            <div>
                              <span className="font-bold text-gray-505">{getConnectorName(tr.connector_id)}</span>
                              <span className="text-gray-400 mx-1.5">/</span>
                              <span className="font-mono text-gray-905">{tr.table_name}</span>
                            </div>
                            {tr.is_deny ? (
                              <span className="text-[10px] font-bold uppercase text-red-655 bg-red-50 border border-red-205 px-2 py-0.5 rounded">DENY</span>
                            ) : (
                              <div className="flex gap-1.5 font-mono text-[10px]">
                                {tr.can_read && <span className="bg-green-55 text-green-700 px-1.5 py-0.5 rounded">R</span>}
                                {tr.can_create && <span className="bg-blue-55 text-blue-700 px-1.5 py-0.5 rounded">C</span>}
                                {tr.can_update && <span className="bg-orange-55 text-orange-700 px-1.5 py-0.5 rounded">U</span>}
                                {tr.can_delete && <span className="bg-red-55 text-red-700 px-1.5 py-0.5 rounded">D</span>}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'rls' && (
                <div className="space-y-2 animate-fade-in">
                  <h4 className="text-xs font-bold text-gray-505 uppercase tracking-wider">Row-Level Security Policies</h4>
                  {selectedPackage.rls_filters.length === 0 ? (
                    <p className="text-xs text-gray-400 italic">No RLS filters defined inside this package.</p>
                  ) : (
                    <div className="space-y-3">
                      {selectedPackage.rls_filters.map((f, idx) => (
                        <div key={idx} className="bg-gray-50 border border-gray-150 rounded-xl p-4 space-y-2 text-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-gray-605">{getConnectorName(f.connector_id)}</span>
                            <span className="text-gray-300">|</span>
                            <span className="font-mono text-gray-900 font-semibold">{f.table_name}</span>
                          </div>
                          <pre className="bg-gray-905 text-green-405 p-3 rounded-lg text-xs font-mono whitespace-pre-wrap leading-relaxed shadow-inner">
                            {f.filter_expression}
                          </pre>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'assignments' && (
                <div className="space-y-5 animate-fade-in">
                  <div className="flex justify-between items-center">
                    <div>
                      <h4 className="text-xs font-bold text-gray-505 uppercase tracking-wider">Package Assignments</h4>
                      <p className="text-[11px] text-gray-400 mt-0.5">Configure time-bound validity windows and assign this package.</p>
                    </div>
                    {!isAssigning ? (
                      <button onClick={() => setIsAssigning(true)} className="btn-secondary py-1.5 px-3 flex items-center gap-1 text-xs font-semibold shadow-sm">
                        <Plus className="w-3.5 h-3.5" /> Assign Package
                      </button>
                    ) : (
                      <button onClick={() => setIsAssigning(false)} className="text-xs font-semibold text-gray-550 hover:text-gray-800">
                        Hide Form
                      </button>
                    )}
                  </div>

                  {isAssigning && (
                    <div className="bg-gray-50 border border-gray-150 p-5 rounded-xl space-y-4 animate-fade-in">
                      {/* Assignment Mode Selector */}
                      <div className="space-y-2">
                        <label className="block text-xs font-semibold text-gray-505 uppercase tracking-wider">Assignment Mode</label>
                        <div className="flex rounded-lg border border-gray-200 overflow-hidden bg-white">
                          {([
                            { key: 'dept_role' as const, label: 'Dept + Role', desc: 'Recommended' },
                            { key: 'department' as const, label: 'By Department', desc: 'All roles' },
                            { key: 'role' as const, label: 'By Role', desc: 'All depts' },
                          ]).map(mode => (
                            <button
                              key={mode.key}
                              type="button"
                              onClick={() => setAssignMode(mode.key)}
                              className={`flex-1 px-3 py-2.5 text-center transition-all ${
                                assignMode === mode.key
                                  ? 'bg-brand-600 text-white font-bold shadow-inner'
                                  : 'text-gray-600 hover:bg-gray-50 font-medium'
                              }`}
                            >
                              <p className="text-xs font-semibold leading-tight">{mode.label}</p>
                              <p className={`text-[9px] mt-0.5 ${assignMode === mode.key ? 'text-brand-100' : 'text-gray-400'}`}>{mode.desc}</p>
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="grid grid-cols-1 gap-4">
                        {assignMode === 'dept_role' && (
                          <>
                            {/* Dept + Role combo pickers */}
                            <div className="grid grid-cols-2 gap-3">
                              <div className="space-y-1.5">
                                <label className="block text-xs font-semibold text-gray-505 uppercase tracking-wider">Department</label>
                                <select
                                  value={assignComboDeptId}
                                  onChange={e => setAssignComboDeptId(e.target.value)}
                                  className="w-full px-3 py-2 border border-gray-250 rounded-lg text-xs bg-white focus:outline-none focus:border-brand-500"
                                >
                                  <option value="">-- Select Department --</option>
                                  {departments.map(d => (
                                    <option key={d.id} value={d.id}>{d.name}</option>
                                  ))}
                                </select>
                              </div>
                              <div className="space-y-1.5">
                                <label className="block text-xs font-semibold text-gray-505 uppercase tracking-wider">Role</label>
                                <select
                                  value={assignComboRoleId}
                                  onChange={e => setAssignComboRoleId(e.target.value)}
                                  className="w-full px-3 py-2 border border-gray-250 rounded-lg text-xs bg-white focus:outline-none focus:border-brand-500"
                                >
                                  <option value="">-- Select Role --</option>
                                  {roles.filter(r => r.slug !== 'superadmin' && r.slug !== 'super_admin').map(r => (
                                    <option key={r.id} value={r.id}>{r.name}</option>
                                  ))}
                                </select>
                              </div>
                            </div>
                            {assignComboDeptId && assignComboRoleId && (
                              <div className="flex items-center gap-2 text-xs bg-brand-50/50 border border-brand-200 rounded-lg p-2.5">
                                <Shield className="w-3.5 h-3.5 text-brand-600 flex-shrink-0" />
                                <span className="text-brand-700 font-medium">
                                  Only <strong>{roles.find(r => r.id === assignComboRoleId)?.name}</strong> members in <strong>{departments.find(d => d.id === assignComboDeptId)?.name}</strong> will get this package.
                                </span>
                              </div>
                            )}
                          </>
                        )}

                        {assignMode === 'department' && (
                          <div className="space-y-2">
                            <label className="block text-xs font-semibold text-gray-505 uppercase tracking-wider">Target Departments</label>
                            <div className="bg-white border border-gray-200 rounded-lg p-3 max-h-40 overflow-y-auto space-y-2">
                              {departments.map(d => (
                                <label key={d.id} className="flex items-center gap-2 text-xs font-medium cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={assignDeptIds.includes(d.id)}
                                    onChange={e => {
                                      if (e.target.checked) setAssignDeptIds([...assignDeptIds, d.id])
                                      else setAssignDeptIds(assignDeptIds.filter(id => id !== d.id))
                                    }}
                                    className="rounded text-brand-600 focus:ring-brand-500 border-gray-300"
                                  />
                                  {d.name}
                                </label>
                              ))}
                            </div>
                          </div>
                        )}

                        {assignMode === 'role' && (
                          <div className="space-y-2">
                            <label className="block text-xs font-semibold text-gray-505 uppercase tracking-wider">Target Roles</label>
                            <div className="bg-white border border-gray-200 rounded-lg p-3 max-h-40 overflow-y-auto space-y-2">
                              {roles.filter(r => r.slug !== 'superadmin' && r.slug !== 'super_admin').map(r => (
                                <label key={r.id} className="flex items-center gap-2 text-xs font-medium cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={assignRoleIds.includes(r.id)}
                                    onChange={e => {
                                      if (e.target.checked) setAssignRoleIds([...assignRoleIds, r.id])
                                      else setAssignRoleIds(assignRoleIds.filter(id => id !== r.id))
                                    }}
                                    className="rounded text-brand-600 focus:ring-brand-500 border-gray-300"
                                  />
                                  {r.name}
                                </label>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Time pickers */}
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <label className="block text-xs font-semibold text-gray-505 uppercase tracking-wider">Valid From (Optional)</label>
                            <input
                              type="datetime-local"
                              value={validFrom}
                              onChange={e => setValidFrom(e.target.value)}
                              className="w-full px-3 py-2 border border-gray-250 rounded-lg text-xs bg-white focus:outline-none"
                            />
                          </div>

                          <div className="space-y-2">
                            <label className="block text-xs font-semibold text-gray-505 uppercase tracking-wider">Expires At (Optional)</label>
                            <input
                              type="datetime-local"
                              value={expiresAt}
                              onChange={e => setExpiresAt(e.target.value)}
                              className="w-full px-3 py-2 border border-gray-250 rounded-lg text-xs bg-white focus:outline-none"
                            />
                          </div>
                        </div>
                      </div>

                      <div className="flex justify-end gap-3 pt-2">
                        <button type="button" onClick={() => setIsAssigning(false)} className="btn-secondary text-xs py-1.5 px-3">
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={handleAssign}
                          disabled={assignMutation.isPending}
                          className="btn-primary text-xs py-1.5 px-4 shadow-sm"
                        >
                          {assignMutation.isPending ? 'Assigning...' : 'Save Assignment'}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Active List of Assignments */}
                  {selectedPackage.dept_assignments.length === 0 && selectedPackage.role_assignments.length === 0 ? (
                    <p className="text-xs text-gray-400 italic">This package is not currently assigned to any departments or roles.</p>
                  ) : (
                    <div className="space-y-2">
                      {selectedPackage.dept_assignments.map(a => {
                        const active = isAssignmentActive(a)
                        const expiresAt = parseUTC(a.expires_at)
                        const hasRoleScope = !!a.role_id
                        return (
                          <div key={a.id} className={`flex justify-between items-center p-3 border rounded-xl text-xs ${active ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-155 text-gray-400 opacity-60'}`}>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-purple-705 bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
                                Dept: {getDeptName(a.department_id)}
                              </span>
                              {hasRoleScope && (
                                <span className="font-bold text-blue-705 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                                  + Role: {getRoleName(a.role_id!)}
                                </span>
                              )}
                              {expiresAt && (
                                <span className="text-[9px] text-gray-400 flex items-center gap-1">
                                  <Calendar className="w-3 h-3" />
                                  Expires {expiresAt.toLocaleString()}
                                </span>
                              )}
                              {!active && a.revoked_at && <span className="text-red-500 font-semibold text-[10px]">[REVOKED]</span>}
                              {!active && !a.revoked_at && expiresAt && expiresAt < new Date() && <span className="text-red-500 font-semibold text-[10px]">[EXPIRED]</span>}
                            </div>
                            {active && (
                              <button
                                onClick={() => {
                                  const label = hasRoleScope
                                    ? `${getDeptName(a.department_id)} + ${getRoleName(a.role_id!)}`
                                    : getDeptName(a.department_id)
                                  setConfirmModal({
                                    isOpen: true,
                                    title: 'Revoke Assignment',
                                    message: `Are you sure you want to revoke the assignment for "${label}"?`,
                                    confirmText: 'Revoke',
                                    onConfirm: () => {
                                      revokeAssignmentMutation.mutate({ packageId: selectedPackage.id, assignmentId: a.id })
                                      setConfirmModal(prev => ({ ...prev, isOpen: false }))
                                    }
                                  })
                                }}
                                className="text-red-500 hover:text-red-750 font-semibold"
                              >
                                Revoke
                              </button>
                            )}
                          </div>
                        )
                      })}

                      {selectedPackage.role_assignments.map(a => {
                        const active = isAssignmentActive(a)
                        const expiresAt = parseUTC(a.expires_at)
                        return (
                          <div key={a.id} className={`flex justify-between items-center p-3 border rounded-xl text-xs ${active ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-155 text-gray-400 opacity-60'}`}>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-blue-705 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                                Role: {getRoleName(a.role_id)}
                              </span>
                              {expiresAt && (
                                <span className="text-[9px] text-gray-400 flex items-center gap-1">
                                  <Calendar className="w-3 h-3" />
                                  Expires {expiresAt.toLocaleString()}
                                </span>
                              )}
                              {!active && a.revoked_at && <span className="text-red-500 font-semibold text-[10px]">[REVOKED]</span>}
                              {!active && !a.revoked_at && expiresAt && expiresAt < new Date() && <span className="text-red-500 font-semibold text-[10px]">[EXPIRED]</span>}
                            </div>
                            {active && (
                              <button
                                onClick={() => {
                                  setConfirmModal({
                                    isOpen: true,
                                    title: 'Revoke Role Assignment',
                                    message: `Are you sure you want to revoke the role assignment for "${getRoleName(a.role_id)}"?`,
                                    confirmText: 'Revoke',
                                    onConfirm: () => {
                                      revokeAssignmentMutation.mutate({ packageId: selectedPackage.id, assignmentId: a.id })
                                      setConfirmModal(prev => ({ ...prev, isOpen: false }))
                                    }
                                  })
                                }}
                                className="text-red-500 hover:text-red-750 font-semibold"
                              >
                                Revoke
                              </button>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 3-Step Add Rule Wizard */}
      {wizardStep !== null && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setWizardStep(null)} />
          <div className="relative bg-white rounded-2xl border border-gray-100 shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 space-y-6 animate-fade-in">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="font-bold text-gray-900">Add Rule (Step {wizardStep} of 3)</h3>
              <button type="button" onClick={() => setWizardStep(null)} className="p-1 hover:bg-gray-100 rounded text-gray-550">
                <X className="w-5 h-5" />
              </button>
            </div>

            {wizardStep === 1 && (
              <div className="space-y-4">
                <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Step 1: Pick Rule Type</p>
                <div className="grid grid-cols-1 gap-2">
                  {(['connector', 'table', 'rls'] as const).map(t => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setWizardType(t)}
                      className={`flex items-center justify-between p-3.5 border rounded-xl text-left transition-all ${
                        wizardType === t
                          ? 'border-brand-600 bg-brand-50/40 text-brand-700 font-bold ring-2 ring-brand-500/10'
                          : 'border-gray-200 hover:bg-gray-50 text-gray-700'
                      }`}
                    >
                      <div>
                        <p className="text-sm font-semibold capitalize">
                          {t === 'rls' ? 'Row-Level Security (RLS) Filter' : `${t}-Level Rule`}
                        </p>
                        <p className="text-xs text-gray-400 font-normal mt-0.5">
                          {t === 'connector' && 'Grant/deny access to an entire database or warehouse.'}
                          {t === 'table' && 'Grant/deny access to a specific table name.'}
                          {t === 'rls' && 'Bind database visibility constraints using user placeholders.'}
                        </p>
                      </div>
                      <Check className={`w-4 h-4 text-brand-600 ${wizardType === t ? 'opacity-100' : 'opacity-0'}`} />
                    </button>
                  ))}
                </div>
                <div className="flex justify-end gap-2 border-t border-gray-100 pt-4">
                  <button type="button" onClick={() => setWizardStep(null)} className="btn-secondary text-xs py-1.5 px-3">Cancel</button>
                  <button
                    type="button"
                    onClick={() => {
                      if (wizardType === 'connector') {
                        const firstAvailableConnectorId = availableConnectorOptions[0]?.id || ''
                        if (wizardConnectorIds.length === 0 && firstAvailableConnectorId) {
                          setWizardConnectorSelection([firstAvailableConnectorId])
                        }
                      } else {
                        if (ruleConnectorOptions.length === 0) {
                          toast.error('Add a connector-level rule before adding table or RLS access.')
                          return
                        }
                        const targetConnectorId = ruleConnectorOptions[0].id
                        setWizardConnectorId(targetConnectorId)
                        setWizardTableName('')
                        setWizardTableNames([])
                        // Use setTimeout(0) to ensure wizardConnectorId state is set before step 2 renders
                        setTimeout(() => setWizardStep(2), 0)
                        return
                      }
                      setWizardTableName('')
                      setWizardTableNames([])
                      setWizardStep(2)
                    }}
                    className="btn-primary text-xs py-1.5 px-4"
                  >
                    Next &rarr;
                  </button>
                </div>
              </div>
            )}

            {wizardStep === 2 && (
              <div className="space-y-4">
                <p className="text-xs text-gray-550 font-semibold uppercase tracking-wider">Step 2: Pick Connector{wizardType !== 'connector' && ' & Table'}</p>
                <div className="space-y-4">
                  {wizardType === 'connector' ? (
                    <div>
                      <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Select Connectors</label>
                      <MultiSelect
                        options={availableConnectorOptions}
                        value={wizardConnectorIds}
                        onChange={setWizardConnectorSelection}
                        placeholder={availableConnectorOptions.length === 0 ? 'All connectors already have rules' : 'Select connectors...'}
                      />
                      {availableConnectorOptions.length === 0 && (
                        <p className="text-xs text-amber-600 mt-2">Every connector already has a connector-level rule in this package draft.</p>
                      )}
                    </div>
                  ) : (
                    <div>
                      <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Select Connector</label>
                      <select
                        value={wizardConnectorId}
                        onChange={e => {
                          setWizardConnectorId(e.target.value)
                          setWizardTableName('')
                          setWizardTableNames([])
                        }}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none"
                      >
                        {ruleConnectorOptions.map(c => (
                          <option key={c.id} value={c.id}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                      {ruleConnectorOptions.length === 0 && (
                        <p className="text-xs text-amber-600 mt-2">Add connector-level rules first. Table and RLS rules can only target those connectors.</p>
                      )}
                    </div>
                  )}

                  {(wizardType === 'table' || wizardType === 'rls') && (
                    <div>
                      <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Table Names</label>
                      <SearchableTableSelector
                        allTables={wizardTableOptions}
                        selectedTables={wizardTableNames}
                        onChange={tables => {
                          setWizardTableNames(tables)
                          setWizardTableName(tables[0] || '')
                        }}
                        placeholder="Select table(s)..."
                        isLoading={isSchemaLoading}
                        inlineDropdown
                      />
                      {wizardConnectorId && !isSchemaLoading && wizardTableOptions.length === 0 && (
                        <p className="text-xs text-amber-600 mt-2">No schema tables are available for this connector yet.</p>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex justify-between gap-2 border-t border-gray-100 pt-4">
                  <button type="button" onClick={() => setWizardStep(1)} className="btn-secondary text-xs py-1.5 px-3">&larr; Back</button>
                  <button
                    type="button"
                    onClick={() => {
                      if (wizardType === 'connector' && wizardConnectorIds.length === 0) {
                        toast.error('Please select at least one connector')
                        return
                      }
                      if ((wizardType === 'table' || wizardType === 'rls') && !wizardConnectorId) {
                        toast.error('Add a connector-level rule before adding table or RLS access.')
                        return
                      }
                      if ((wizardType === 'table' || wizardType === 'rls') && isSchemaLoading) {
                        toast.error('Tables are still loading. Please wait a moment.')
                        return
                      }
                      if ((wizardType === 'table' || wizardType === 'rls') && wizardTableNames.length === 0) {
                        toast.error('Please select at least one table')
                        return
                      }
                      setWizardStep(3)
                    }}
                    className="btn-primary text-xs py-1.5 px-4"
                  >
                    Next &rarr;
                  </button>
                </div>
              </div>
            )}

            {wizardStep === 3 && (
              <div className="space-y-4">
                <p className="text-xs text-gray-550 font-semibold uppercase tracking-wider">Step 3: Set Rule Access Details</p>
                
                {wizardType === 'rls' ? (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Filter Expression</label>
                      <textarea
                        required
                        rows={3}
                        value={wizardFilterExpr}
                        onChange={e => setWizardFilterExpr(e.target.value)}
                        placeholder="e.g. employee_code = '{user.employee_code}'"
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:outline-none bg-white"
                      />
                      <div className="flex flex-wrap gap-1 mt-2">
                        {PLACEHOLDERS.map(p => (
                          <button
                            key={p.token}
                            type="button"
                            onClick={() => handleWizardPlaceholderClick(p.token)}
                            className="px-2 py-0.5 bg-gray-150 hover:bg-brand-50 border border-gray-200 rounded text-[10px] font-mono text-brand-600 font-semibold transition-colors"
                            title={p.desc}
                          >
                            {p.token}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : wizardType === 'connector' ? (
                  <div className="space-y-3">
                    {wizardConnectorIds.map(connectorId => {
                      const access = wizardConnectorAccess[connectorId] || defaultConnectorRule(connectorId)
                      return (
                        <div key={connectorId} className="rounded-xl border border-gray-150 bg-gray-55 p-3 space-y-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-bold text-gray-900">{getConnectorName(connectorId)}</p>
                              <p className="text-[11px] text-gray-500">Set permissions for this connector.</p>
                            </div>
                            <label className="flex items-center gap-1.5 cursor-pointer shrink-0">
                              <input
                                type="checkbox"
                                checked={access.is_deny}
                                onChange={e => updateWizardConnectorAccess(connectorId, { is_deny: e.target.checked })}
                                className="rounded text-red-650 focus:ring-red-500 border-gray-300"
                              />
                              <span className="text-xs font-bold text-red-655 uppercase">Deny</span>
                            </label>
                          </div>

                          {!access.is_deny && (
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                              {(['read', 'create', 'update', 'delete'] as const).map(op => {
                                const field = `can_${op}` as 'can_read' | 'can_create' | 'can_update' | 'can_delete'
                                return (
                                  <label key={op} className="flex items-center gap-1.5 cursor-pointer text-xs capitalize p-2 border border-gray-150 rounded-lg bg-white">
                                    <input
                                      type="checkbox"
                                      checked={access[field]}
                                      onChange={e => updateWizardConnectorAccess(connectorId, { [field]: e.target.checked } as Partial<PackageConnectorRule>)}
                                      className="rounded text-brand-600 focus:ring-brand-500 border-gray-300"
                                    />
                                    {op}
                                  </label>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="space-y-4">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={wizardIsDeny}
                        onChange={e => setWizardIsDeny(e.target.checked)}
                        className="rounded text-red-650 focus:ring-red-500 border-gray-300"
                      />
                      <span className="text-xs font-bold text-red-655 uppercase">Deny Access</span>
                    </label>

                    {!wizardIsDeny && (
                      <div className="space-y-2">
                        <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Permissions</label>
                        <div className="grid grid-cols-2 gap-2">
                          {(['read', 'create', 'update', 'delete'] as const).map(op => {
                            const val = op === 'read' ? wizardCanRead : op === 'create' ? wizardCanCreate : op === 'update' ? wizardCanUpdate : wizardCanDelete
                            const setter = op === 'read' ? setWizardCanRead : op === 'create' ? setWizardCanCreate : op === 'update' ? setWizardCanUpdate : setWizardCanDelete
                            return (
                              <label key={op} className="flex items-center gap-1.5 cursor-pointer text-xs capitalize p-2 border border-gray-150 rounded-lg bg-gray-55">
                                <input
                                  type="checkbox"
                                  checked={val}
                                  onChange={e => setter(e.target.checked)}
                                  className="rounded text-brand-600 focus:ring-brand-500 border-gray-300"
                                />
                                {op}
                              </label>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex justify-between gap-2 border-t border-gray-100 pt-4">
                  <button type="button" onClick={() => setWizardStep(2)} className="btn-secondary text-xs py-1.5 px-3">&larr; Back</button>
                  <button
                    type="button"
                    onClick={() => {
                      if (wizardType === 'connector') {
                        if (wizardConnectorIds.length === 0) {
                          toast.error('Please select at least one connector')
                          return
                        }
                        const duplicateConnector = wizardConnectorIds.find(id => connectorRules.some(r => r.connector_id === id))
                        if (duplicateConnector) {
                          toast.error(`A rule for ${getConnectorName(duplicateConnector)} is already defined.`)
                          return
                        }
                        setConnectorRules([
                          ...connectorRules,
                          ...wizardConnectorIds.map(id => wizardConnectorAccess[id] || defaultConnectorRule(id))
                        ])
                      } else if (wizardType === 'table') {
                        setTableRules([
                          ...tableRules,
                          ...wizardTableNames.map(tableName => ({
                            connector_id: wizardConnectorId,
                            table_name: tableName,
                            is_deny: wizardIsDeny,
                            can_read: wizardCanRead,
                            can_create: wizardCanCreate,
                            can_update: wizardCanUpdate,
                            can_delete: wizardCanDelete,
                          }))
                        ])
                      } else if (wizardType === 'rls') {
                        if (wizardTableNames.length === 0) {
                          toast.error('Please select at least one table')
                          return
                        }
                        if (!wizardFilterExpr.trim()) {
                          toast.error('Please enter a filter expression')
                          return
                        }
                        setRlsFilters([
                          ...rlsFilters,
                          ...wizardTableNames.map(tableName => ({
                            connector_id: wizardConnectorId,
                            table_name: tableName,
                            filter_expression: wizardFilterExpr.trim(),
                          }))
                        ])
                      }
                      setWizardStep(null)
                      toast.success('Rule added to package draft')
                    }}
                    className="btn-primary text-xs py-1.5 px-4 font-semibold shadow-sm"
                  >
                    Add Rule &rarr;
                  </button>
                </div>
              </div>
            )}
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
                {confirmModal.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
