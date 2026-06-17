import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Shield, Plus, Trash2, Edit, X, AlertTriangle, Lock, ChevronRight, UserPlus, UserCheck } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/auth'

interface RoleNodeData {
  id: string
  name: string
  level: number
  member_count: number
  color: string
  is_system: boolean
  is_active: boolean
  parent_role_id?: string | null
  children: RoleNodeData[]
}

interface UserData {
  id: string
  email: string
  name: string
  role: string
  is_superadmin?: boolean
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

interface RolesPageProps {
  embedded?: boolean
}

export function RolesPage({ embedded = false }: RolesPageProps = {}) {
  const qc = useQueryClient()
  const { user: me } = useAuthStore()

  // Modal states
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [editingRole, setEditingRole] = useState<RoleNodeData | null>(null)
  const [deletingRole, setDeletingRole] = useState<RoleNodeData | null>(null)

  // Form states
  const [name, setName] = useState('')
  const [level, setLevel] = useState(1)
  const [selectedColor, setSelectedColor] = useState('1E40AF')
  const [parentRoleId, setParentRoleId] = useState<string>('')

  // Manager Assignment form states
  const [memberUserId, setMemberUserId] = useState('')
  const [managerUserId, setManagerUserId] = useState('')

  // Queries
  const { data: roleTree = [], isLoading: isTreeLoading } = useQuery<RoleNodeData[]>({
    queryKey: ['roleTree'],
    queryFn: () => api.get('/api/roles/tree').then(r => r.data),
  })

  // Flat roles list for dropdowns
  const { data: flatRoles = [] } = useQuery<any[]>({
    queryKey: ['flatRoles'],
    queryFn: () => api.get('/api/roles/').then(r => r.data),
  })

  const { data: users = [] } = useQuery<UserData[]>({
    queryKey: ['users'],
    queryFn: () => api.get('/api/users/').then(r => r.data),
  })

  // Mutations
  const createMutation = useMutation({
    mutationFn: (newRole: { name: string; level: number; color: string; parent_role_id: string | null }) =>
      api.post('/api/roles/', newRole),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['roleTree'] })
      qc.invalidateQueries({ queryKey: ['flatRoles'] })
      toast.success('Role created successfully')
      closeAddModal()
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to create role')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string; level: number; color: string; parent_role_id: string | null } }) =>
      api.patch(`/api/roles/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['roleTree'] })
      qc.invalidateQueries({ queryKey: ['flatRoles'] })
      toast.success('Role updated successfully')
      closeEditModal()
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to update role')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/roles/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['roleTree'] })
      qc.invalidateQueries({ queryKey: ['flatRoles'] })
      toast.success('Role soft-deleted successfully')
      setDeletingRole(null)
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to delete role')
    },
  })

  const assignManagerMutation = useMutation({
    mutationFn: ({ memberId, managerId }: { memberId: string; managerId: string | null }) =>
      api.put(`/api/roles/users/${memberId}/manager`, { manager_id: managerId }),
    onSuccess: () => {
      toast.success('Manager assigned successfully')
      setMemberUserId('')
      setManagerUserId('')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to assign manager')
    },
  })

  // Security Check
  if (!me?.is_superadmin) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="max-w-md w-full text-center bg-white p-8 rounded-xl shadow-md border border-gray-100">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-500 text-sm">
            Only Super Administrators can configure roles and manager relations.
          </p>
        </div>
      </div>
    )
  }

  // Modal Helpers
  const openAddModal = () => {
    setName('')
    setLevel(1)
    setSelectedColor('1E40AF')
    setParentRoleId('')
    setIsAddOpen(true)
  }

  const closeAddModal = () => {
    setIsAddOpen(false)
  }

  const openEditModal = (role: RoleNodeData) => {
    setEditingRole(role)
    setName(role.name)
    setLevel(role.level)
    setSelectedColor(role.color.replace('#', ''))
    setParentRoleId(role.parent_role_id || '')
  }

  const closeEditModal = () => {
    setEditingRole(null)
  }

  // Submit Handlers
  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    const randomColor = PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)].hex
    createMutation.mutate({
      name: name.trim(),
      level: 1, // Auto-calculated bottom-up in backend
      color: randomColor,
      parent_role_id: parentRoleId || null,
    })
  }

  const handleUpdateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingRole || !name.trim()) return
    updateMutation.mutate({
      id: editingRole.id,
      data: {
        name: name.trim(),
        level: 1, // Auto-calculated bottom-up in backend
        color: editingRole.color.replace('#', ''),
        parent_role_id: parentRoleId || null,
      },
    })
  }

  const handleAssignManager = (e: React.FormEvent) => {
    e.preventDefault()
    if (!memberUserId) return
    assignManagerMutation.mutate({
      memberId: memberUserId,
      managerId: managerUserId || null,
    })
  }

  const getBadgeStyle = (hexColor: string) => {
    const clean = hexColor.startsWith('#') ? hexColor : '#' + hexColor
    return {
      backgroundColor: clean + '15',
      color: clean,
      borderColor: clean + '30',
    }
  }

  // Recursive Tree Node Renderer
  const renderRoleNode = (node: RoleNodeData) => {
    return (
      <div key={node.id} className="mt-4">
        {/* Card */}
        <div className="flex items-center justify-between p-4 bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center gap-3">
            <span
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border"
              style={getBadgeStyle(node.color)}
            >
              {node.name}
            </span>
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-medium">
              Lvl {node.level}
            </span>
            {node.is_system && (
              <span className="text-gray-400" title="System Protected Role">
                <Lock className="w-3.5 h-3.5" />
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-4">
            <span className="text-xs text-gray-400">
              {node.member_count} {node.member_count === 1 ? 'user' : 'users'}
            </span>
            
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => openEditModal(node)}
                disabled={node.is_system}
                className={`p-1 rounded-lg border transition-colors ${
                  node.is_system
                    ? 'border-gray-50 text-gray-300 cursor-not-allowed'
                    : 'border-gray-100 text-gray-600 hover:bg-gray-50'
                }`}
                title={node.is_system ? 'System roles cannot be modified' : 'Edit Role'}
              >
                <Edit className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setDeletingRole(node)}
                disabled={node.is_system || node.member_count > 0}
                className={`p-1 rounded-lg border transition-colors ${
                  node.is_system || node.member_count > 0
                    ? 'border-gray-50 text-gray-300 cursor-not-allowed'
                    : 'border-red-100 text-red-600 hover:bg-red-50'
                }`}
                title={
                  node.is_system
                    ? 'System roles cannot be deleted'
                    : node.member_count > 0
                    ? 'Cannot delete role with assigned users'
                    : 'Delete Role'
                }
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Children Indented */}
        {node.children && node.children.length > 0 && (
          <div className="pl-6 border-l border-gray-150 ml-6 space-y-2">
            {node.children.map(child => renderRoleNode(child))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={embedded ? 'p-6' : 'p-8'}>
      {/* Header */}
      {embedded ? (
        <div className="flex justify-end mb-4">
          <button onClick={openAddModal} className="btn-primary py-2 px-4 flex items-center gap-2 text-sm">
            <Plus className="w-4 h-4" /> Add Role
          </button>
        </div>
      ) : (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Shield className="w-6 h-6 text-gray-700" />
              Roles & Access Levels
            </h1>
            <p className="text-gray-500 mt-1 text-sm">Configure hierarchical roles and manager assignments</p>
          </div>
          <button
            onClick={openAddModal}
            className="btn-primary py-2 px-4 flex items-center gap-2 text-sm justify-center"
          >
            <Plus className="w-4 h-4" /> Add Role
          </button>
        </div>
      )}

      {/* Main Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Side: Tree View (60%) */}
        <div className="lg:col-span-7">
          <div className="bg-gray-50 p-6 rounded-2xl border border-gray-100 min-h-[500px]">
            <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wider mb-2">Role Hierarchy Tree</h2>
            {isTreeLoading ? (
              <div className="text-center py-12 text-gray-400 text-sm">Loading hierarchy tree...</div>
            ) : roleTree.length === 0 ? (
              <div className="text-center py-12 text-gray-400 text-sm">No roles configured.</div>
            ) : (
              <div className="divide-y divide-transparent">
                {roleTree.map(rootNode => renderRoleNode(rootNode))}
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Manager Assignment Panel (40%) */}
        <div className="lg:col-span-5 space-y-6">
          <div className="card p-6 border border-gray-100">
            <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wider mb-4 flex items-center gap-1.5">
              <UserPlus className="w-4 h-4 text-brand-600" />
              Manager Assignment
            </h2>
            
            <form onSubmit={handleAssignManager} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Select Member / Employee
                </label>
                <select
                  required
                  value={memberUserId}
                  onChange={e => setMemberUserId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value="">-- Choose User --</option>
                  {users.map(u => (
                    <option key={u.id} value={u.id}>
                      {u.name} ({u.email})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Select Manager
                </label>
                <select
                  value={managerUserId}
                  onChange={e => setManagerUserId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value="">No Manager (Clear / None)</option>
                  {users
                    .filter(u => u.id !== memberUserId && (u.role?.toLowerCase() === 'manager' || u.role?.toLowerCase() === 'superadmin' || u.is_superadmin)) // Cannot assign self as manager, and must have manager or superadmin role
                    .map(u => (
                      <option key={u.id} value={u.id}>
                        {u.name} ({u.email})
                      </option>
                    ))}
                </select>
              </div>

              <button
                type="submit"
                disabled={!memberUserId || assignManagerMutation.isPending}
                className="btn-primary w-full py-2 flex items-center justify-center gap-2 text-sm mt-2"
              >
                <UserCheck className="w-4 h-4" />
                {assignManagerMutation.isPending ? 'Saving...' : 'Save Assignment'}
              </button>
            </form>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-5 text-sm text-blue-800 space-y-2">
            <h3 className="font-bold flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-blue-700" />
              Role System Guidelines
            </h3>
            <ul className="list-disc list-inside space-y-1 text-xs text-blue-700">
              <li>Level indicates privileges (higher levels override lower levels).</li>
              <li>A cycle checker enforces that parents cannot loop refer to children.</li>
              <li>System-protected roles (Admin, Superadmin) cannot be deleted or modified.</li>
              <li>Manager assignments can be set/cleared for any active member.</li>
            </ul>
          </div>
        </div>
      </div>

      {/* ── Add Role Modal ──────────────────────────────────────────────── */}
      {isAddOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={closeAddModal} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h3 className="text-lg font-bold text-gray-900">Add Role</h3>
              <button onClick={closeAddModal} className="p-1 rounded-md hover:bg-gray-100 transition-colors">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <form onSubmit={handleCreateSubmit}>
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Role Name
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={e => setName(e.target.value)}
                    placeholder="e.g. Lead Engineer"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Parent Role
                  </label>
                  <select
                    value={parentRoleId}
                    onChange={e => setParentRoleId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">No Parent (Root)</option>
                    {flatRoles.map(r => (
                      <option key={r.id} value={r.id}>
                        {r.name} (Lvl {r.level})
                      </option>
                    ))}
                  </select>
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

      {/* ── Edit Role Modal ─────────────────────────────────────────────── */}
      {editingRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={closeEditModal} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h3 className="text-lg font-bold text-gray-900">Edit Role</h3>
              <button onClick={closeEditModal} className="p-1 rounded-md hover:bg-gray-100 transition-colors">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <form onSubmit={handleUpdateSubmit}>
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    Role Name
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
                    Parent Role
                  </label>
                  <select
                    value={parentRoleId}
                    onChange={e => setParentRoleId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">No Parent (Root)</option>
                    {flatRoles
                      .filter(r => r.id !== editingRole.id) // Cannot set self as parent
                      .map(r => (
                        <option key={r.id} value={r.id}>
                          {r.name} (Lvl {r.level})
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
      {deletingRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setDeletingRole(null)} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h3 className="text-lg font-bold text-gray-900">Delete Role</h3>
              <button onClick={() => setDeletingRole(null)} className="p-1 rounded-md hover:bg-gray-100 transition-colors">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <div className="px-6 py-5 flex items-start gap-4">
              <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">Delete "{deletingRole.name}"?</p>
                <p className="text-sm text-gray-500 mt-1.5">
                  Are you sure you want to delete this role? It will be soft-deleted and marked as inactive.
                </p>
                
                {deletingRole.member_count > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 mt-4 text-xs text-red-700 font-medium">
                    This role currently has <span className="font-bold">{deletingRole.member_count}</span> assigned users. 
                    Deletion is blocked. Please reassign all users in the Users directory before trying again.
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
              <button type="button" onClick={() => setDeletingRole(null)} className="btn-secondary text-sm">
                {deletingRole.member_count > 0 ? 'Close' : 'Cancel'}
              </button>
              {deletingRole.member_count === 0 && (
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(deletingRole.id)}
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
