import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Building, Plus, Trash2, Edit, X, AlertTriangle } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/auth'

interface DepartmentData {
  id: string
  name: string
  slug: string
  color: string
  is_active: boolean
  is_system: boolean
  default_role_id: string | null
  parent_department_id: string | null
  member_count: number
}

interface RoleData {
  id: string
  name: string
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

interface DepartmentsPageProps {
  embedded?: boolean
}

export function DepartmentsPage({ embedded = false }: DepartmentsPageProps = {}) {
  const qc = useQueryClient()
  const { user } = useAuthStore()

  // Modal States
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [editingDept, setEditingDept] = useState<DepartmentData | null>(null)
  const [deletingDept, setDeletingDept] = useState<DepartmentData | null>(null)

  // Form States
  const [name, setName] = useState('')
  const [selectedColor, setSelectedColor] = useState('1E40AF')
  const [defaultRoleId, setDefaultRoleId] = useState<string>('')

  // Queries
  const { data: departments = [], isLoading, isError } = useQuery<DepartmentData[]>({
    queryKey: ['departments'],
    queryFn: () => api.get('/api/departments/').then(r => r.data),
  })

  const { data: roles = [] } = useQuery<RoleData[]>({
    queryKey: ['roles'],
    queryFn: () => api.get('/api/departments/roles').then(r => r.data),
    enabled: !!user?.is_superadmin,
  })

  // Mutations
  const createMutation = useMutation({
    mutationFn: (newDept: { name: string; color: string }) =>
      api.post('/api/departments/', newDept),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['departments'] })
      toast.success('Department created successfully')
      closeAddModal()
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to create department')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string; color: string; default_role_id: string | null; is_active: boolean } }) =>
      api.patch(`/api/departments/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['departments'] })
      toast.success('Department updated successfully')
      closeEditModal()
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to update department')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/departments/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['departments'] })
      toast.success('Department deleted successfully')
      setDeletingDept(null)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      if (typeof detail === 'object' && detail?.message) {
        toast.error(`${detail.message} (${detail.assigned_users} users assigned)`)
      } else {
        toast.error(detail || 'Failed to delete department')
      }
    },
  })

  // Security Check
  if (!user?.is_superadmin) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="max-w-md w-full text-center bg-white p-8 rounded-xl shadow-md border border-gray-100">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-500 text-sm">
            Only Super Administrators can manage department configurations.
          </p>
        </div>
      </div>
    )
  }

  // Modal Handlers
  const openAddModal = () => {
    setName('')
    setSelectedColor('1E40AF')
    setIsAddOpen(true)
  }

  const closeAddModal = () => {
    setIsAddOpen(false)
  }

  const openEditModal = (dept: DepartmentData) => {
    setEditingDept(dept)
    setName(dept.name)
    setSelectedColor(dept.color.replace('#', ''))
    setDefaultRoleId(dept.default_role_id || '')
  }

  const closeEditModal = () => {
    setEditingDept(null)
  }

  // Submit Handlers
  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    const randomColor = PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)].hex
    createMutation.mutate({
      name: name.trim(),
      color: randomColor,
    })
  }

  const handleUpdateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingDept || !name.trim()) return
    updateMutation.mutate({
      id: editingDept.id,
      data: {
        name: name.trim(),
        color: editingDept.color.replace('#', ''),
        default_role_id: defaultRoleId || null,
        is_active: editingDept.is_active,
      },
    })
  }

  const getBadgeStyle = (hexColor: string) => {
    const clean = hexColor.startsWith('#') ? hexColor : '#' + hexColor
    return {
      backgroundColor: clean + '15', // 8% opacity background
      color: clean,
      borderColor: clean + '30',
    }
  }

  return (
    <div className={embedded ? 'p-6' : 'p-8'}>
      {/* Header */}
      {embedded ? (
        <div className="flex justify-end mb-4">
          <button onClick={openAddModal} className="btn-primary py-2 px-4 flex items-center gap-2 text-sm">
            <Plus className="w-4 h-4" /> Add Department
          </button>
        </div>
      ) : (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Building className="w-6 h-6 text-gray-700" />
              Departments
            </h1>
            <p className="text-gray-500 mt-1 text-sm">Configure organization structure and default memberships</p>
          </div>
          <button
            onClick={openAddModal}
            className="btn-primary py-2 px-4 flex items-center gap-2 text-sm justify-center"
          >
            <Plus className="w-4 h-4" /> Add Department
          </button>
        </div>
      )}

      {/* Main Table */}
      {isLoading ? (
        <div className="text-center py-12 text-gray-400">Loading departments...</div>
      ) : isError ? (
        <div className="text-center py-12 text-red-500">Failed to load departments.</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Slug</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Members</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Active</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {departments.map((dept) => (
                <tr key={dept.id} className={dept.is_active ? '' : 'opacity-65'}>
                  <td className="px-6 py-4">
                    <span
                      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border"
                      style={getBadgeStyle(dept.color)}
                    >
                      {dept.name}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <code className="text-xs bg-gray-50 border border-gray-100 px-2 py-0.5 rounded text-gray-600 font-mono">
                      {dept.slug}
                    </code>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {dept.member_count} {dept.member_count === 1 ? 'member' : 'members'}
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() =>
                        updateMutation.mutate({
                          id: dept.id,
                          data: {
                            name: dept.name,
                            color: dept.color,
                            default_role_id: dept.default_role_id,
                            is_active: !dept.is_active,
                          },
                        })
                      }
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border cursor-pointer transition-colors ${
                        dept.is_active
                          ? 'bg-green-50 text-green-700 border-green-200 hover:bg-green-100'
                          : 'bg-gray-100 text-gray-500 border-gray-200 hover:bg-gray-200'
                      }`}
                    >
                      {dept.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={() => openEditModal(dept)}
                        className="p-1.5 rounded-lg border border-gray-100 text-gray-600 hover:bg-gray-50 transition-colors"
                        title="Edit Department"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeletingDept(dept)}
                        disabled={dept.member_count > 0}
                        className={`p-1.5 rounded-lg border transition-colors ${
                          dept.member_count > 0
                            ? 'border-gray-100 text-gray-300 cursor-not-allowed'
                            : 'border-red-100 text-red-600 hover:bg-red-50'
                        }`}
                        title={dept.member_count > 0 ? "Cannot delete department with members" : "Delete Department"}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Add Department Modal ────────────────────────────────────────── */}
      {isAddOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={closeAddModal} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h3 className="text-lg font-bold text-gray-900">Add Department</h3>
              <button onClick={closeAddModal} className="p-1 rounded-md hover:bg-gray-100 transition-colors">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <form onSubmit={handleCreateSubmit}>
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Department Name
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={e => setName(e.target.value)}
                    placeholder="e.g. Quality Assurance"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>


              </div>
              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
                <button type="button" onClick={closeAddModal} className="btn-secondary text-sm">
                  Cancel
                </button>
                <button type="submit" disabled={createMutation.isPending} className="btn-primary text-sm px-4">
                  {createMutation.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Edit Department Modal ───────────────────────────────────────── */}
      {editingDept && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={closeEditModal} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h3 className="text-lg font-bold text-gray-900">Edit Department</h3>
              <button onClick={closeEditModal} className="p-1 rounded-md hover:bg-gray-100 transition-colors">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <form onSubmit={handleUpdateSubmit}>
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Department Name
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={e => setName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>



                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Default Role for Members
                  </label>
                  <select
                    value={defaultRoleId}
                    onChange={e => setDefaultRoleId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">No Default Role (None)</option>
                    {roles.map(r => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
                <button type="button" onClick={closeEditModal} className="btn-secondary text-sm">
                  Cancel
                </button>
                <button type="submit" disabled={updateMutation.isPending} className="btn-primary text-sm px-4">
                  {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Delete Confirmation Modal ──────────────────────────────────── */}
      {deletingDept && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setDeletingDept(null)} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h3 className="text-lg font-bold text-gray-900">Delete Department</h3>
              <button onClick={() => setDeletingDept(null)} className="p-1 rounded-md hover:bg-gray-100 transition-colors">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <div className="px-6 py-5 flex items-start gap-4">
              <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">Delete "{deletingDept.name}"?</p>
                <p className="text-sm text-gray-500 mt-1.5">
                  Are you sure you want to delete this department? This action is permanent and cannot be undone.
                </p>
                
                {deletingDept.member_count > 0 ? (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 mt-4 text-xs text-red-700 font-medium">
                    This department currently has <span className="font-bold">{deletingDept.member_count}</span> assigned members. 
                    Deletion is blocked. Please reassign all members in the Users directory before trying again.
                  </div>
                ) : deletingDept.is_system ? (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 mt-4 text-xs text-red-700 font-medium">
                    This is a protected system department and cannot be deleted.
                  </div>
                ) : null}
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
              <button type="button" onClick={() => setDeletingDept(null)} className="btn-secondary text-sm">
                {deletingDept.member_count > 0 || deletingDept.is_system ? 'Close' : 'Cancel'}
              </button>
              {deletingDept.member_count === 0 && !deletingDept.is_system && (
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(deletingDept.id)}
                  disabled={deleteMutation.isPending}
                  className="bg-red-600 hover:bg-red-700 text-white rounded-lg px-4 py-2 font-medium text-sm transition-colors"
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
