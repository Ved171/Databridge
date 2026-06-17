import React, { useState, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Shield, Plus, Trash2, Edit, X, AlertTriangle, Eye, RefreshCw, Check, Info, ChevronDown, ChevronUp, Layers
} from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/auth'
import { MultiSelect } from '../components/MultiSelect'
import { SearchableTableSelector } from '../components/SearchableTableSelector'

interface RLSFilter {
  id: string
  connector_id: string
  table_name: string
  filter_expression: string
  applies_to_role_id: string | null
  applies_to_dept_id: string | null
  applies_to_user_id: string | null
  is_active: boolean
  created_at: string
  is_package_rule?: boolean
}

interface Connector {
  id: string
  name: string
  type: string
}

interface Role {
  id: string
  name: string
  slug: string
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

interface RLSContext {
  user_id: string
  user_email: string
  user_employee_code: string | null
  managed_codes: string[]
  managed_user_ids: string[]
  managed_count: number
  is_manager: boolean
}

const PLACEHOLDERS = [
  { token: '{user.employee_code}', desc: "Employee code" },
  { token: '{user.name}', desc: "Name" },
  { token: '{user.email}', desc: "Email" },
]

interface RLSPageProps {
  embedded?: boolean
  connectorId?: string
}

export function RLSPage({ embedded = false, connectorId: externalConnectorId }: RLSPageProps = {}) {
  const qc = useQueryClient()
  const { user: me } = useAuthStore()

  // Expanded rows state
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({})
  const [selectedRlsIds, setSelectedRlsIds] = useState<string[]>([])

  // Modal State
  const [isOpen, setIsOpen] = useState(false)
  const [editingFilter, setEditingFilter] = useState<RLSFilter | null>(null)

  // Form Fields
  const [connectorId, setConnectorId] = useState('')
  const [searchParams] = useSearchParams()
  useEffect(() => {
    if (embedded && externalConnectorId) {
      setConnectorId(externalConnectorId)
      return
    }
    const preConnector = searchParams.get('connector')
    if (preConnector) setConnectorId(preConnector)
  }, [embedded, externalConnectorId, searchParams])
  const [selectedTables, setSelectedTables] = useState<string[]>([])
  const [targetType, setTargetType] = useState<'role' | 'dept' | 'user'>('role')
  const [appliesToRoleIds, setAppliesToRoleIds] = useState<string[]>([])
  const [appliesToDeptIds, setAppliesToDeptIds] = useState<string[]>([])
  const [appliesToUserId, setAppliesToUserId] = useState('')
  const [filterExpression, setFilterExpression] = useState('')
  const [isActive, setIsActive] = useState(true)

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

  // Textarea Ref for placeholder chip insertion
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Live Preview States
  const [previewUserId, setPreviewUserId] = useState('')
  const [previewResult, setPreviewResult] = useState<{
    input: string
    substituted: string
    context: Record<string, any>
  } | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)

  // Debug Context Panel States
  const [debugUserId, setDebugUserId] = useState('')
  const [debugContext, setDebugContext] = useState<RLSContext | null>(null)
  const [isDebugLoading, setIsDebugLoading] = useState(false)
  const [showDebugPanel, setShowDebugPanel] = useState(false)

  // Standard Hierarchy Modal state (GAP 2)
  const [showHierarchyModal, setShowHierarchyModal] = useState(false)
  const [hierarchyConnectorId, setHierarchyConnectorId] = useState('')
  const [hierarchyTable, setHierarchyTable] = useState<string[]>([])
  const [hierarchyIdentityColumn, setHierarchyIdentityColumn] = useState('')
  const [hierarchyBaseLevel, setHierarchyBaseLevel] = useState<number>(1)

  // Queries
  const { data: filters = [], isLoading: isFiltersLoading } = useQuery<RLSFilter[]>({
    queryKey: ['rlsFilters'],
    queryFn: () => api.get('/api/rls/filters/').then(r => r.data),
  })

  useEffect(() => {
    setSelectedRlsIds([])
  }, [connectorId, filters])

  const { data: connectors = [] } = useQuery<Connector[]>({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  const { data: schemaData } = useQuery({
    queryKey: ['connectorSchema', connectorId],
    queryFn: () => api.get(`/api/connectors/${connectorId}/schema`).then(r => r.data),
    enabled: !!connectorId,
  })
  const allConnectorTables = (schemaData?.tables || []).map((t: any) => t.schema ? `${t.schema}.${t.name}` : t.name)

  const { data: hierarchySchemaData } = useQuery({
    queryKey: ['connectorSchema', hierarchyConnectorId],
    queryFn: () => api.get(`/api/connectors/${hierarchyConnectorId}/schema`).then(r => r.data),
    enabled: !!hierarchyConnectorId,
  })
  const allHierarchyConnectorTables = (hierarchySchemaData?.tables || []).map((t: any) => t.schema ? `${t.schema}.${t.name}` : t.name)


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

  // GAP 4: RLS settings query + mutation (superadmin only)
  const { data: rlsSettings } = useQuery({
    queryKey: ['rlsSettings'],
    queryFn: () => api.get('/api/rls/settings/').then(r => r.data),
    enabled: !!me?.is_superadmin,
  })

  const toggleRlsEnabledMutation = useMutation({
    mutationFn: (enabled: boolean) => api.put('/api/rls/settings/', { rls_enabled: enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rlsSettings'] })
      qc.invalidateQueries({ queryKey: ['rlsFilters'] })
      toast.success('RLS setting updated')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to update RLS setting')
    },
  })

  // GAP 2: Standard hierarchy mutation
  const hierarchyMutation = useMutation({
    mutationFn: (data: { connector_id: string; table_name: string; identity_column: string; scope_level: number }) =>
      api.post('/api/rls/apply-standard-hierarchy/', data),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['rlsFilters'] })
      toast.success(`${res.data.created} standard hierarchy filters created`)
      setShowHierarchyModal(false)
    },
    onError: (err: any) => {
      if (err.response?.status === 409) {
        toast.error('Filters already exist for this table. Remove them first.')
      } else {
        toast.error(err.response?.data?.detail || 'Failed to apply standard hierarchy')
      }
    },
  })

  // Mutations
  const createMutation = useMutation({
    mutationFn: async (data: {
      connector_id: string
      tables: string[]
      filter_expression: string
      applies_to_role_ids: string[]
      applies_to_dept_ids: string[]
      applies_to_user_id: string | null
    }) => {
      const calls: Promise<any>[] = []
      // Fan out: one call per (table × role), one call per (table × dept), or one per (table × user)
      for (const table of data.tables) {
        if (data.applies_to_role_ids.length > 0) {
          for (const roleId of data.applies_to_role_ids) {
            calls.push(api.post('/api/rls/filters/', {
              connector_id: data.connector_id,
              table_name: table,
              filter_expression: data.filter_expression,
              applies_to_role_id: roleId,
              applies_to_dept_id: null,
              applies_to_user_id: null,
            }))
          }
        }
        if (data.applies_to_dept_ids.length > 0) {
          for (const deptId of data.applies_to_dept_ids) {
            calls.push(api.post('/api/rls/filters/', {
              connector_id: data.connector_id,
              table_name: table,
              filter_expression: data.filter_expression,
              applies_to_role_id: null,
              applies_to_dept_id: deptId,
              applies_to_user_id: null,
            }))
          }
        }
        if (data.applies_to_user_id) {
          calls.push(api.post('/api/rls/filters/', {
            connector_id: data.connector_id,
            table_name: table,
            filter_expression: data.filter_expression,
            applies_to_role_id: null,
            applies_to_dept_id: null,
            applies_to_user_id: data.applies_to_user_id,
          }))
        }
      }
      return Promise.all(calls)
    },
    onSuccess: (results) => {
      qc.invalidateQueries({ queryKey: ['rlsFilters'] })
      toast.success(`${results.length} RLS filter${results.length > 1 ? 's' : ''} created successfully`)
      closeModal()
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to create filter')
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: any }) => {
      const firstRole = data.applies_to_role_ids && data.applies_to_role_ids.length > 0 ? data.applies_to_role_ids[0] : null
      const firstDept = data.applies_to_dept_ids && data.applies_to_dept_ids.length > 0 ? data.applies_to_dept_ids[0] : null
      
      const updatePayload = {
        connector_id: data.connector_id,
        table_name: data.table_name,
        filter_expression: data.filter_expression,
        applies_to_role_id: firstRole,
        applies_to_dept_id: firstDept,
        applies_to_user_id: data.applies_to_user_id,
        is_active: data.is_active,
      }
      
      const calls = [api.patch(`/api/rls/filters/${id}`, updatePayload)]
      
      if (data.applies_to_role_ids && data.applies_to_role_ids.length > 1) {
        for (let i = 1; i < data.applies_to_role_ids.length; i++) {
          calls.push(api.post('/api/rls/filters/', {
            connector_id: data.connector_id,
            table_name: data.table_name,
            filter_expression: data.filter_expression,
            applies_to_role_id: data.applies_to_role_ids[i],
            applies_to_dept_id: null,
            applies_to_user_id: null,
          }))
        }
      }
      
      if (data.applies_to_dept_ids && data.applies_to_dept_ids.length > 1) {
        for (let i = 1; i < data.applies_to_dept_ids.length; i++) {
          calls.push(api.post('/api/rls/filters/', {
            connector_id: data.connector_id,
            table_name: data.table_name,
            filter_expression: data.filter_expression,
            applies_to_role_id: null,
            applies_to_dept_id: data.applies_to_dept_ids[i],
            applies_to_user_id: null,
          }))
        }
      }
      
      return Promise.all(calls)
    },
    onSuccess: (results) => {
      qc.invalidateQueries({ queryKey: ['rlsFilters'] })
      toast.success(`${results.length} RLS filter${results.length > 1 ? 's' : ''} updated successfully`)
      closeModal()
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to update filter')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/rls/filters/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rlsFilters'] })
      toast.success('RLS filter deleted successfully')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to delete filter')
    },
  })

  const bulkDeleteRlsFilters = useMutation({
    mutationFn: (filterIds: string[]) =>
      api.post('/api/rls/filters/bulk-delete', { ids: filterIds }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rlsFilters'] })
      setSelectedRlsIds([])
      toast.success('Selected RLS filters deleted successfully')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to delete filters')
    },
  })

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.patch(`/api/rls/filters/${id}`, { is_active }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rlsFilters'] })
      toast.success('Filter status updated')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to toggle status')
    },
  })

  // Modal Helpers
  const openCreateModal = () => {
    setEditingFilter(null)
    setConnectorId((embedded && externalConnectorId) ? externalConnectorId : connectors[0]?.id || '')
    setSelectedTables([])
    setTargetType('role')
    setAppliesToRoleIds([])
    setAppliesToDeptIds([])
    setAppliesToUserId('')
    setFilterExpression('')
    setIsActive(true)
    setPreviewResult(null)
    setPreviewError(null)
    setIsOpen(true)
  }

  const openEditModal = (filter: RLSFilter) => {
    setEditingFilter(filter)
    setConnectorId(filter.connector_id)
    setSelectedTables([filter.table_name])
    setIsActive(filter.is_active)
    setFilterExpression(filter.filter_expression)
    setPreviewResult(null)
    setPreviewError(null)

    if (filter.applies_to_role_id) {
      setTargetType('role')
      setAppliesToRoleIds([filter.applies_to_role_id])
      setAppliesToDeptIds([])
      setAppliesToUserId(users[0]?.id || '')
    } else if (filter.applies_to_dept_id) {
      setTargetType('dept')
      setAppliesToRoleIds([])
      setAppliesToDeptIds([filter.applies_to_dept_id])
      setAppliesToUserId(users[0]?.id || '')
    } else {
      setTargetType('user')
      setAppliesToRoleIds([])
      setAppliesToDeptIds([])
      setAppliesToUserId(filter.applies_to_user_id || '')
    }

    const siblings = filters.filter(
      f => f.id !== filter.id &&
           f.connector_id === filter.connector_id &&
           f.table_name === filter.table_name &&
           f.filter_expression === filter.filter_expression
    )
    if (siblings.length > 0) {
      toast(`Editing this filter only. ${siblings.length} related filter${siblings.length > 1 ? 's' : ''} with the same expression exist for this table.`, {
        icon: 'ℹ️',
        duration: 5000,
      })
    }

    setIsOpen(true)
  }

  const closeModal = () => {
    setIsOpen(false)
    setEditingFilter(null)
  }

  // Helper to resolve columns for the selected table
  const getColumnsForTable = (tableName: string) => {
    if (!schemaData?.tables || !tableName) return []
    const foundTable = schemaData.tables.find((t: any) => {
      const fullTName = t.schema ? `${t.schema}.${t.name}` : t.name
      return fullTName === tableName || t.name === tableName
    })
    return foundTable?.columns || []
  }

  // Chip Insertion Handler - Smart Expression Builder
  const handleChipClick = (token: string) => {
    const tableColumns = selectedTables.length > 0 ? getColumnsForTable(selectedTables[0]) : []

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

    if (!textareaRef.current) return
    const textarea = textareaRef.current
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const text = textarea.value
    const before = text.substring(0, start)
    const after = text.substring(end, text.length)

    // Prepend ' AND ' if there's already content and we're appending at the end
    let prefix = ''
    if (text.trim().length > 0 && start === text.length) {
      prefix = ' AND '
    }

    const insertVal = prefix + expressionToInsert
    const newText = before + insertVal + after
    setFilterExpression(newText)

    setTimeout(() => {
      textarea.focus()
      textarea.selectionStart = textarea.selectionEnd = start + insertVal.length
    }, 0)
  }

  // Live Preview Trigger
  const handleRunPreview = async () => {
    if (!previewUserId) {
      toast.error('Please select a preview user first')
      return
    }
    if (!filterExpression.trim()) {
      toast.error('Please enter a filter expression')
      return
    }

    setIsPreviewLoading(true)
    setPreviewResult(null)
    setPreviewError(null)

    try {
      const res = await api.get('/api/rls/preview', {
        params: {
          user_id: previewUserId,
          filter_expression: filterExpression
        }
      })
      setPreviewResult(res.data)
    } catch (err: any) {
      setPreviewError(err.response?.data?.detail || 'Failed to generate preview')
    } finally {
      setIsPreviewLoading(false)
    }
  }

  // Load Debug Context
  const handleLoadDebugContext = async () => {
    if (!debugUserId) {
      toast.error('Please select a user to load context')
      return
    }

    setIsDebugLoading(true)
    setDebugContext(null)

    try {
      const res = await api.get(`/api/rls/context/${debugUserId}`)
      setDebugContext(res.data)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load debug context')
    } finally {
      setIsDebugLoading(false)
    }
  }

  // Submit Handler
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (selectedTables.length === 0) {
      toast.error('Please select at least one table')
      return
    }

    if (!filterExpression.trim()) {
      toast.error('Filter expression cannot be empty')
      return
    }

    if (targetType === 'role' && appliesToRoleIds.length === 0) {
      toast.error('Please select at least one role')
      return
    }
    if (targetType === 'dept' && appliesToDeptIds.length === 0) {
      toast.error('Please select at least one department')
      return
    }
    if (targetType === 'user' && !appliesToUserId) {
      toast.error('Please select a user')
      return
    }

    if (editingFilter) {
      const payload: any = {
        connector_id: connectorId,
        table_name: selectedTables[0],
        filter_expression: filterExpression.trim(),
        applies_to_role_ids: targetType === 'role' ? appliesToRoleIds : [],
        applies_to_dept_ids: targetType === 'dept' ? appliesToDeptIds : [],
        applies_to_user_id: targetType === 'user' ? appliesToUserId : null,
        is_active: isActive,
      }
      updateMutation.mutate({
        id: editingFilter.id,
        data: payload
      })
    } else {
      createMutation.mutate({
        connector_id: connectorId,
        tables: selectedTables,
        filter_expression: filterExpression.trim(),
        applies_to_role_ids: targetType === 'role' ? appliesToRoleIds : [],
        applies_to_dept_ids: targetType === 'dept' ? appliesToDeptIds : [],
        applies_to_user_id: targetType === 'user' ? appliesToUserId : null,
      })
    }
  }

  const toggleRow = (id: string) => {
    setExpandedRows(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const activeConnectorId = embedded ? externalConnectorId : connectorId
  const displayedFilters = embedded && activeConnectorId
    ? filters.filter(f => f.connector_id === activeConnectorId)
    : filters

  // Helper displays
  const getConnectorName = (id: string) => connectors.find(c => c.id === id)?.name || id
  const getRoleName = (id: string) => roles.find(r => r.id === id)?.name || id
  const getDeptName = (id: string) => departments.find(d => d.id === id)?.name || id
  const getUserName = (id: string) => {
    const u = users.find(usr => usr.id === id)
    return u ? `${u.name} (${u.email})` : id
  }

  return (
    <div className={embedded ? 'p-4 space-y-4' : 'p-8 space-y-8 max-w-7xl mx-auto'}>
      {/* Header */}
      {embedded ? (
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-text-muted">Row-level security filters for this connector</p>
          <button onClick={openCreateModal} className="btn-primary text-sm flex items-center gap-2 py-2 px-4">
            <Plus className="w-4 h-4" /> Add Filter
          </button>
        </div>
      ) : (
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight flex items-center gap-3">
              <Shield className="w-8 h-8 text-brand-600" />
              Manager-Scoped Row-Level Security (RLS)
            </h1>
            <p className="text-gray-500 mt-1.5 text-sm max-w-2xl">
              Injects dynamic constraints into user SELECT queries based on department and role hierarchy, filtering results to reports automatically.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* GAP 4: RLS Active toggle (superadmin only) */}
            {me?.is_superadmin && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg">
                <span className="text-xs font-semibold text-gray-600">RLS Active</span>
                <button
                  type="button"
                  onClick={() => {
                    const currentlyEnabled = rlsSettings?.rls_enabled !== false
                    if (currentlyEnabled) {
                      setConfirmModal({
                        isOpen: true,
                        title: 'Disable RLS',
                        message: 'Disabling RLS means all users will see all data. Are you sure?',
                        onConfirm: () => {
                          toggleRlsEnabledMutation.mutate(false)
                          setConfirmModal(prev => ({ ...prev, isOpen: false }))
                        },
                      })
                    } else {
                      toggleRlsEnabledMutation.mutate(true)
                    }
                  }}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    rlsSettings?.rls_enabled !== false ? 'bg-green-500' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                      rlsSettings?.rls_enabled !== false ? 'translate-x-4.5' : 'translate-x-0.5'
                    }`}
                  />
                </button>
              </div>
            )}
            {me?.is_superadmin && (
              <button
                onClick={() => setShowDebugPanel(!showDebugPanel)}
                className="btn-secondary py-2.5 px-4 flex items-center gap-2 text-sm justify-center font-semibold"
              >
                Debug {showDebugPanel ? '▴' : '▾'}
              </button>
            )}
            {/* GAP 2: Apply Standard Hierarchy button */}
            <button
              onClick={() => {
                setHierarchyConnectorId(connectors[0]?.id || '')
                setHierarchyTable([])
                setHierarchyIdentityColumn('')
                setHierarchyBaseLevel(1)
                setShowHierarchyModal(true)
              }}
              className="btn-secondary py-2.5 px-4 flex items-center gap-2 text-sm justify-center font-semibold"
            >
              <Layers className="w-4 h-4" /> Quick Hierarchy Setup
            </button>
            <button
              onClick={openCreateModal}
              className="btn-primary py-2.5 px-5 flex items-center gap-2 text-sm justify-center shadow-lg hover:shadow-brand-200 transition-all font-semibold"
            >
              <Plus className="w-4 h-4" /> Add RLS Filter
            </button>
          </div>
        </div>
      )}

      {/* Main Grid: Filters List + Debug Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left Side: Table of Filters (8 columns if superadmin debug panel shown, otherwise 12) */}
        <div className={me?.is_superadmin && showDebugPanel ? "lg:col-span-8 space-y-6" : "lg:col-span-12 space-y-6"}>
          <div className="bg-white rounded-2xl border border-gray-200/80 shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
              <h2 className="text-base font-bold text-gray-900">Active RLS Filter Policies</h2>
              <span className="text-xs bg-gray-100 text-gray-600 px-2.5 py-1 rounded-full font-semibold">
                {displayedFilters.length} {displayedFilters.length === 1 ? 'Filter' : 'Filters'} Total
              </span>
            </div>

            {selectedRlsIds.length > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 mx-6 mt-4 flex items-center justify-between text-sm text-red-800 animate-fade-in">
                <div className="flex items-center gap-2 font-medium">
                  <AlertTriangle className="w-4 h-4 text-red-650" />
                  <span>{selectedRlsIds.length} RLS filter(s) selected</span>
                </div>
                <button
                  onClick={() => {
                    setConfirmModal({
                      isOpen: true,
                      title: 'Delete Selected RLS Filters',
                      message: `Are you sure you want to delete the selected ${selectedRlsIds.length} RLS filters? This action is irreversible.`,
                      onConfirm: () => {
                        bulkDeleteRlsFilters.mutate(selectedRlsIds)
                        setConfirmModal(prev => ({ ...prev, isOpen: false }))
                      }
                    })
                  }}
                  disabled={bulkDeleteRlsFilters.isPending}
                  className="btn-danger py-1 px-3 text-xs font-semibold"
                >
                  {bulkDeleteRlsFilters.isPending ? 'Deleting...' : 'Delete Selected'}
                </button>
              </div>
            )}

            {isFiltersLoading ? (
              <div className="text-center py-16 text-gray-400">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-gray-300" />
                <p className="text-sm">Loading security filters...</p>
              </div>
            ) : displayedFilters.length === 0 ? (
              <div className="text-center py-16 px-4">
                <Shield className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <h3 className="text-sm font-semibold text-gray-900">No RLS filters configured</h3>
                <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
                  Managers and employees currently run queries without automated manager hierarchy filters. Add a filter to start enforcing constraints.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-gray-100 text-[11px] font-bold text-gray-500 uppercase tracking-wider bg-gray-50/75">
                      <th className="py-3.5 px-6 w-10">
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-accent-600 focus:ring-accent-500 cursor-pointer"
                          checked={
                            displayedFilters.length > 0 &&
                            displayedFilters.filter(f => !f.is_package_rule).length > 0 &&
                            displayedFilters.filter(f => !f.is_package_rule).every(f => selectedRlsIds.includes(f.id))
                          }
                          onChange={(e) => {
                            if (e.target.checked) {
                              const deletableIds = displayedFilters
                                .filter(f => !f.is_package_rule)
                                .map(f => f.id)
                              setSelectedRlsIds(deletableIds)
                            } else {
                              setSelectedRlsIds([])
                            }
                          }}
                        />
                      </th>
                      <th className="py-3.5 px-6">Connector</th>
                      <th className="py-3.5 px-4">Table</th>
                      <th className="py-3.5 px-4">Applies To</th>
                      <th className="py-3.5 px-4">Status</th>
                      <th className="py-3.5 px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 text-sm">
                    {displayedFilters.map(f => {
                      const isExpanded = !!expandedRows[f.id]
                      return (
                        <React.Fragment key={f.id}>
                          <tr className="hover:bg-gray-50/50 transition-colors">
                            <td className="py-4 px-6 w-10">
                              {!f.is_package_rule && (
                                <input
                                  type="checkbox"
                                  className="rounded border-gray-300 text-accent-600 focus:ring-accent-500 cursor-pointer"
                                  checked={selectedRlsIds.includes(f.id)}
                                  onChange={(e) => {
                                    if (e.target.checked) {
                                      setSelectedRlsIds(prev => [...prev, f.id])
                                    } else {
                                      setSelectedRlsIds(prev => prev.filter(id => id !== f.id))
                                    }
                                  }}
                                />
                              )}
                            </td>
                            <td className="py-4 px-6 font-semibold text-gray-900">
                              <button
                                onClick={() => toggleRow(f.id)}
                                className="flex items-center gap-2 text-left hover:text-brand-600 transition-colors"
                              >
                                {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                                {getConnectorName(f.connector_id)}
                              </button>
                            </td>
                            <td className="py-4 px-4 text-gray-600 font-mono text-xs">{f.table_name}</td>
                            <td className="py-4 px-4">
                              {f.applies_to_role_id && (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-150">
                                  Role: {getRoleName(f.applies_to_role_id)}
                                </span>
                              )}
                              {f.applies_to_dept_id && (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-150">
                                  Dept: {getDeptName(f.applies_to_dept_id)}
                                </span>
                              )}
                              {f.applies_to_user_id && (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-150">
                                  User: {getUserName(f.applies_to_user_id)}
                                </span>
                              )}
                            </td>
                            <td className="py-4 px-4">
                              {f.is_package_rule ? (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-green-100 text-green-800 border border-green-200">
                                  Active
                                </span>
                              ) : (
                                <button
                                  onClick={() => toggleActiveMutation.mutate({ id: f.id, is_active: !f.is_active })}
                                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold transition-all ${
                                    f.is_active
                                      ? 'bg-green-100 text-green-800 hover:bg-green-200'
                                      : 'bg-gray-150 text-gray-650 hover:bg-gray-200'
                                  }`}
                                >
                                  {f.is_active ? 'Active' : 'Inactive'}
                                </button>
                              )}
                            </td>
                            <td className="py-4 px-6 text-right">
                              {f.is_package_rule ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-755 border border-indigo-200" title="This RLS filter is inherited from an Access Package. Manage it in the Access Packages section.">
                                  Via Package
                                </span>
                              ) : (
                                <div className="flex items-center justify-end gap-2">
                                  <button
                                    onClick={() => openEditModal(f)}
                                    className="p-1 rounded text-gray-500 hover:bg-gray-150 hover:text-gray-900 transition-colors"
                                    title="Edit RLS Filter"
                                  >
                                    <Edit className="w-4 h-4" />
                                  </button>
                                  <button
                                    onClick={() => {
                                      setConfirmModal({
                                        isOpen: true,
                                        title: 'Delete RLS Filter',
                                        message: 'Are you sure you want to delete this RLS filter? This action is irreversible.',
                                        onConfirm: () => {
                                          deleteMutation.mutate(f.id)
                                          setConfirmModal(prev => ({ ...prev, isOpen: false }))
                                        }
                                      })
                                    }}
                                    className="p-1 rounded text-red-500 hover:bg-red-50 hover:text-red-750 transition-colors"
                                    title="Delete RLS Filter"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr className="bg-gray-50/40">
                              <td colSpan={6} className="py-4 px-8 border-b border-gray-150">
                                <div className="space-y-3">
                                  <div>
                                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Filter Expression</p>
                                    <pre className="bg-gray-900 text-gray-100 p-3.5 rounded-lg text-xs font-mono whitespace-pre-wrap shadow-inner overflow-x-auto">
                                      {f.filter_expression}
                                    </pre>
                                  </div>
                                  <div className="flex items-center justify-between text-xs text-gray-400">
                                    <span>Filter ID: <code className="font-mono text-[10px]">{f.id}</code></span>
                                    <span>Created At: {new Date(f.created_at).toLocaleString()}</span>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: RLS Context Debugger (superadmin only) */}
        {me?.is_superadmin && showDebugPanel && (
          <div className="lg:col-span-4 space-y-6">
            <div className="bg-white rounded-2xl border border-gray-200/80 shadow-sm p-6 space-y-5">
              <div>
                <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                  <Eye className="w-4.5 h-4.5 text-brand-650" />
                  RLS Context Debugger
                </h2>
                <p className="text-xs text-gray-500 mt-1">
                  Load a user to inspect resolved manager placeholders before writing filter expressions.
                </p>
              </div>

              <div className="space-y-3">
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Target User
                </label>
                <div className="flex gap-2">
                  <select
                    value={debugUserId}
                    onChange={e => setDebugUserId(e.target.value)}
                    className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">-- Choose User --</option>
                    {users.map(u => (
                      <option key={u.id} value={u.id}>
                        {u.name} ({u.email})
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={handleLoadDebugContext}
                    disabled={!debugUserId || isDebugLoading}
                    className="btn-primary px-3.5 flex items-center justify-center"
                    title="Load Context"
                  >
                    <RefreshCw className={`w-4 h-4 ${isDebugLoading ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>

              {debugContext && (
                <div className="space-y-4 border-t border-gray-100 pt-4 animate-fade-in">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-gray-500">Is Manager:</span>
                    <span className={`px-2 py-0.5 rounded font-bold ${debugContext.is_manager ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                      {debugContext.is_manager ? 'True' : 'False'}
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Resolved Placeholders</p>
                    <div className="bg-gray-900 text-gray-100 p-4 rounded-xl space-y-3 text-xs font-mono shadow-inner max-h-96 overflow-y-auto">
                      <div>
                        <span className="text-gray-400 font-semibold">{`{user.id}`}</span>
                        <p className="text-green-400 break-all mt-0.5">{debugContext.user_id}</p>
                      </div>
                      <div>
                        <span className="text-gray-400 font-semibold">{`{user.email}`}</span>
                        <p className="text-green-400 break-all mt-0.5">{debugContext.user_email}</p>
                      </div>
                      <div>
                        <span className="text-gray-400 font-semibold">{`{user.employee_code}`}</span>
                        <p className="text-green-400 break-all mt-0.5">{debugContext.user_employee_code || "NULL"}</p>
                      </div>
                      <div>
                        <span className="text-gray-400 font-semibold">{`{manager.managed_codes}`}</span>
                        <p className="text-green-400 break-all mt-0.5">{debugContext.managed_codes.join(',') || 'empty'}</p>
                      </div>
                      <div>
                        <span className="text-gray-400 font-semibold">{`{manager.managed_codes_quoted}`}</span>
                        <p className="text-green-400 break-all mt-0.5">
                          {debugContext.managed_codes.map(c => `'${c}'`).join(',') || 'empty'}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-400 font-semibold">{`{manager.managed_count}`}</span>
                        <p className="text-green-400 mt-0.5">{debugContext.managed_count}</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Add / Edit Filter Modal ────────────────────────────────────── */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={closeModal} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden border border-gray-100 flex flex-col max-h-[90vh]">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0">
              <h3 className="text-lg font-bold text-gray-900">
                {editingFilter ? 'Edit Row-Level Security Filter' : 'Create Row-Level Security Filter'}
              </h3>
              <button onClick={closeModal} className="p-1 rounded-md hover:bg-gray-100 transition-colors">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            {/* Modal Scrollable Body */}
            <form id="rls-policy-form" onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-5">
              
              {/* Connector Selection */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Select Connector
                  </label>
                  <select
                    required
                    value={connectorId}
                    onChange={e => setConnectorId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  >
                    {connectors.map(c => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.type})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Target Table Name */}
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Target Table Name
                  </label>
                  <SearchableTableSelector
                    allTables={allConnectorTables}
                    selectedTables={selectedTables}
                    onChange={setSelectedTables}
                    singleSelect={editingFilter !== null}
                    placeholder="Select table(s)..."
                  />
                </div>
              </div>

              {/* Target Type Picker */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Applies To (Target Scope)
                </label>
                <div className="grid grid-cols-3 gap-2 p-1 bg-gray-100 rounded-lg">
                  {(['role', 'dept', 'user'] as const).map(type => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setTargetType(type)}
                      className={`py-1.5 text-xs font-bold rounded-md capitalize transition-all ${
                        targetType === type ? 'bg-white shadow text-brand-650' : 'text-gray-500 hover:text-gray-800'
                      }`}
                    >
                      {type === 'dept' ? 'Department' : type}
                    </button>
                  ))}
                </div>
              </div>

              {/* Target Scope Specific Dropdowns */}
              {targetType === 'role' && (
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Select Role
                  </label>
                  <MultiSelect
                    options={roles.map(r => ({ id: r.id, label: r.name }))}
                    value={appliesToRoleIds}
                    onChange={setAppliesToRoleIds}
                    placeholder="Select role(s)..."
                  />
                </div>
              )}

              {targetType === 'dept' && (
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Select Department
                  </label>
                  <MultiSelect
                    options={departments.map(d => ({ id: d.id, label: d.name }))}
                    value={appliesToDeptIds}
                    onChange={setAppliesToDeptIds}
                    placeholder="Select department(s)..."
                  />
                </div>
              )}

              {targetType === 'user' && (
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Select User
                  </label>
                  <select
                    required
                    value={appliesToUserId}
                    onChange={e => setAppliesToUserId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  >
                    {users.map(u => (
                      <option key={u.id} value={u.id}>
                        {u.name} ({u.email})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Filter Expression Textarea */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Filter Expression
                </label>
                <textarea
                  ref={textareaRef}
                  required
                  rows={4}
                  value={filterExpression}
                  onChange={e => setFilterExpression(e.target.value)}
                  placeholder="e.g. employee_code = '{user.employee_code}'"
                  className="w-full px-3.5 py-2.5 border border-gray-200 rounded-lg text-sm font-mono focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 bg-gray-50/20"
                />
                {/* Placeholder chips inline */}
                <div className="mt-2 space-y-1.5">
                  <p className="text-[11px] font-semibold text-gray-500">
                    Available User Placeholders (click to insert):
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {PLACEHOLDERS.map(p => (
                      <button
                        key={p.token}
                        type="button"
                        onClick={() => handleChipClick(p.token)}
                        className="font-mono text-xs px-2.5 py-1 rounded bg-white hover:bg-brand-50 border border-gray-200 text-gray-700 hover:text-brand-700 hover:border-brand-300 shadow-sm transition-all duration-150"
                        title={p.desc}
                      >
                        {p.token}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Live Preview Component (inline below placeholders) */}
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <label className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Live Filter Preview
                  </label>
                  <div className="flex gap-2 flex-1 sm:justify-end">
                    <select
                      value={previewUserId}
                      onChange={e => setPreviewUserId(e.target.value)}
                      className="px-2.5 py-1.5 border border-gray-200 rounded-lg text-xs bg-white focus:border-brand-500 focus:outline-none max-w-xs"
                    >
                      <option value="">-- Select Preview User --</option>
                      {users.map(u => (
                        <option key={u.id} value={u.id}>
                          {u.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={handleRunPreview}
                      disabled={!previewUserId || isPreviewLoading}
                      className="btn-primary text-xs px-3.5 py-1.5 flex items-center gap-1.5"
                    >
                      {isPreviewLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : 'Preview'}
                    </button>
                  </div>
                </div>

                {/* Preview Result Content (Diff style) */}
                <div className="min-h-[80px] bg-white border border-gray-150 rounded-lg p-3 text-xs overflow-y-auto">
                  {previewResult ? (
                    <div className="space-y-3 animate-fade-in font-mono text-[11px]">
                      <div>
                        <div className="text-red-650 bg-red-50 px-2.5 py-1.5 rounded border border-red-200 mb-2 whitespace-pre-wrap">
                          <span className="font-bold text-red-700 mr-1">-</span> {previewResult.input || '(empty)'}
                        </div>
                        <div className="text-green-650 bg-green-50 px-2.5 py-1.5 rounded border border-green-200 whitespace-pre-wrap">
                          <span className="font-bold text-green-700 mr-1">+</span> {previewResult.substituted}
                        </div>
                      </div>
                    </div>
                  ) : previewError ? (
                    <div className="text-red-650 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="font-bold">Substitution Error</p>
                        <p className="text-[11px] mt-0.5 leading-relaxed">{previewError}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="text-gray-400 text-center py-2 text-[11px]">
                      Select a user and hit Preview to test placeholder expansion.
                    </div>
                  )}
                </div>
              </div>

              {/* Active Checkbox (Edit only) */}
              {editingFilter && (
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="isActive"
                    checked={isActive}
                    onChange={e => setIsActive(e.target.checked)}
                    className="rounded text-brand-600 focus:ring-brand-500 border-gray-300"
                  />
                  <label htmlFor="isActive" className="text-sm font-medium text-gray-700">
                    Enable Filter Policy
                  </label>
                </div>
              )}
            </form>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 flex-shrink-0">
              <button type="button" onClick={closeModal} className="btn-secondary text-sm">
                Cancel
              </button>
              <button
                type="submit"
                form="rls-policy-form"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="btn-primary text-sm px-5"
              >
                {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save Policy'}
              </button>
            </div>

          </div>
        </div>
      )}
      {confirmModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-[2px] transition-all duration-300 animate-fade-in">
          <div className="bg-white rounded-lg shadow-xl border border-border-default max-w-sm w-full p-6 animate-scale-in">
            <div className="flex items-center gap-3 text-red-655 mb-3">
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
                Delete Filter
              </button>
            </div>
          </div>
        </div>
      )}

      {/* GAP 2: Standard Hierarchy Modal */}
      {showHierarchyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowHierarchyModal(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <Layers className="w-5 h-5 text-brand-600" />
                Quick Hierarchy Setup
              </h3>
              <button onClick={() => setShowHierarchyModal(false)} className="p-1 rounded-md hover:bg-gray-100 transition-colors">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-xs text-gray-500 leading-relaxed">
                Automatically sets up level-aware RLS query filters for roles at or above the base level on the selected table.
              </p>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Connector</label>
                <select
                  value={hierarchyConnectorId}
                  onChange={e => { setHierarchyConnectorId(e.target.value); setHierarchyTable([]) }}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  {connectors.map(c => (
                    <option key={c.id} value={c.id}>{c.name} ({c.type})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Table</label>
                <SearchableTableSelector
                  allTables={allHierarchyConnectorTables}
                  selectedTables={hierarchyTable}
                  onChange={setHierarchyTable}
                  singleSelect={true}
                  placeholder="Select a table..."
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Identity Column</label>
                <input
                  type="text"
                  value={hierarchyIdentityColumn}
                  onChange={e => setHierarchyIdentityColumn(e.target.value)}
                  placeholder="e.g. employee_code"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Base role level</label>
                <input
                  type="number"
                  value={hierarchyBaseLevel}
                  onChange={e => setHierarchyBaseLevel(parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                <span className="text-[10px] text-gray-400 mt-1 block">
                  Roles at this level see only their own records. Higher levels see their team's records too.
                </span>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
              <button type="button" onClick={() => setShowHierarchyModal(false)} className="btn-secondary text-sm">Cancel</button>
              <button
                type="button"
                disabled={!hierarchyConnectorId || hierarchyTable.length === 0 || !hierarchyIdentityColumn.trim() || hierarchyMutation.isPending}
                onClick={() => {
                  hierarchyMutation.mutate({
                    connector_id: hierarchyConnectorId,
                    table_name: hierarchyTable[0],
                    identity_column: hierarchyIdentityColumn.trim(),
                    scope_level: hierarchyBaseLevel,
                  })
                }}
                className="btn-primary text-sm px-5"
              >
                {hierarchyMutation.isPending ? 'Applying...' : 'Apply Hierarchy'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
