import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2, ShieldCheck, Plus, X, Copy, Check, Users, Building, ShieldAlert, AlertTriangle } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/auth'

interface PromoteTarget {
  id: string
  name: string
  currentRole: string
}

interface UserData {
  id: string
  name: string
  email: string
  is_superadmin: boolean
  is_active: boolean
  force_password_change: boolean
  department_id: string | null
  role_id: string | null
  role?: string
  created_at: string
}

interface UsersPageProps {
  embedded?: boolean
}

export function UsersPage({ embedded = false }: UsersPageProps = {}) {
  const qc = useQueryClient()
  const { user: me } = useAuthStore()

  // State variables
  const [promoteTarget, setPromoteTarget] = useState<PromoteTarget | null>(null)
  const [selectedRole, setSelectedRole] = useState<string>('')
  
  // Delete Confirmation State
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null)
  
  // Invite Modal State
  const [isInviteOpen, setIsInviteOpen] = useState(false)
  const [inviteName, setInviteName] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteDeptId, setInviteDeptId] = useState<string>('')
  const [inviteRoleId, setInviteRoleId] = useState<string>('')
  const [inviteErrors, setInviteErrors] = useState<{ dept?: string; role?: string }>({})
  const [createdUser, setCreatedUser] = useState<UserData | null>(null)
  const [copied, setCopied] = useState(false)

  // Fetch Users
  const { data: users = [], isLoading } = useQuery<UserData[]>({
    queryKey: ['users'],
    queryFn: () => api.get('/api/users/').then(r => r.data),
  })

  // Fetch Departments
  const { data: departments = [] } = useQuery<any[]>({
    queryKey: ['departments'],
    queryFn: () => api.get('/api/departments/').then(r => r.data),
  })

  // Fetch Roles
  const { data: roles = [] } = useQuery<any[]>({
    queryKey: ['roles'],
    queryFn: () => api.get('/api/roles/').then(r => r.data),
  })

  // Delete User
  const deleteUser = useMutation({
    mutationFn: (id: string) => api.delete(`/api/users/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      toast.success('User has been permanently deleted')
      setDeleteTarget(null)
    },
    onError: (e: any) => {
      toast.error(e.response?.data?.detail || 'Failed to delete user')
      setDeleteTarget(null)
    },
  })

  // Promote User
  const promote = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      api.patch(`/api/users/${id}/promote?role=${role}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      toast.success('Role updated successfully')
      setPromoteTarget(null)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to change role'),
  })

  // Create User
  const inviteUserMutation = useMutation({
    mutationFn: (payload: { name: string; email: string; department_id: string | null; role_id: string | null }) =>
      api.post('/api/users/', payload),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setCreatedUser(res.data)
      toast.success('User account created successfully!')
    },
    onError: (e: any) => {
      toast.error(e.response?.data?.detail || 'Failed to create user')
    }
  })

  const openPromoteModal = (u: any) => {
    const currentRole = u.is_superadmin ? 'superadmin' : (u.role || 'member')
    setPromoteTarget({ id: u.id, name: u.name, currentRole })
    setSelectedRole(currentRole)
  }

  const handleInviteSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inviteName.trim() || !inviteEmail.trim()) return

    // Validate department & role selection
    const errors: { dept?: string; role?: string } = {}
    if (!inviteDeptId) errors.dept = 'Please select a department'
    if (!inviteRoleId) errors.role = 'Please select an access role'
    if (Object.keys(errors).length > 0) {
      setInviteErrors(errors)
      return
    }
    setInviteErrors({})

    inviteUserMutation.mutate({
      name: inviteName.trim(),
      email: inviteEmail.trim(),
      department_id: inviteDeptId,
      role_id: inviteRoleId
    })
  }

  const closeInviteModal = () => {
    setIsInviteOpen(false)
    setInviteName('')
    setInviteEmail('')
    setInviteDeptId('')
    setInviteRoleId('')
    setInviteErrors({})
    setCreatedUser(null)
    setCopied(false)
  }

  const handleCopy = () => {
    if (!createdUser) return
    const textToCopy = `Account Details:
Name: ${createdUser.name}
Email: ${createdUser.email}
Temporary Password: 123456789

Instructions: Please log in at http://192.168.2.149:5178/login using your email and the temporary password. You will be prompted to set a new password on your first login.`
    navigator.clipboard.writeText(textToCopy)
    setCopied(true)
    toast.success('Credentials info copied to clipboard!')
    setTimeout(() => setCopied(false), 2000)
  }

  const getDepartmentName = (deptId: string | null) => {
    if (!deptId) return 'None'
    const dept = departments.find(d => d.id === deptId)
    return dept ? dept.name : 'None'
  }

  const getRoleName = (roleId: string | null) => {
    if (!roleId) return 'Member'
    const r = roles.find(item => item.id === roleId)
    return r ? r.name : 'Member'
  }

  const getRoleBadgeColor = (u: UserData) => {
    const roleSlug = u.is_superadmin ? 'superadmin' : (u.role || 'member')
    const foundRole = roles.find(r => r.slug === roleSlug)
    const color = foundRole?.color || '1E40AF'
    const clean = color.startsWith('#') ? color : '#' + color
    return {
      backgroundColor: clean + '12',
      color: clean,
      borderColor: clean + '25',
    }
  }

  const getDeptBadgeStyle = (deptId: string | null) => {
    if (!deptId) return { backgroundColor: '#F3F4F6', color: '#4B5563', borderColor: '#E5E7EB' }
    const hash = deptId.split('').reduce((acc, char) => char.charCodeAt(0) + ((acc << 5) - acc), 0)
    const colors = ['10B981', '3B82F6', '6366F1', '8B5CF6', 'EC4899', 'F59E0B']
    const hex = colors[Math.abs(hash) % colors.length]
    return {
      backgroundColor: '#' + hex + '15',
      color: '#' + hex,
      borderColor: '#' + hex + '30',
    }
  }

  return (
    <div className={embedded ? 'p-6' : 'p-8'}>
      {/* Header */}
      {!embedded && (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Users className="w-6 h-6 text-gray-700" />
              Users
            </h1>
            <p className="text-gray-500 mt-1 text-sm">Manage user accounts, roles, departments, and activation states</p>
          </div>

          {me?.is_superadmin && (
            <button
              onClick={() => setIsInviteOpen(true)}
              className="btn-primary py-2 px-4 flex items-center gap-2 text-sm justify-center"
            >
              <Plus className="w-4 h-4" /> Create User
            </button>
          )}
        </div>
      )}
      {embedded && me?.is_superadmin && (
        <div className="flex justify-end mb-4">
          <button
            onClick={() => setIsInviteOpen(true)}
            className="btn-primary py-2 px-4 flex items-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" /> Create User
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-gray-400">Loading users...</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">User</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Department</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Role</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Joined</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.map((u: UserData) => (
                <tr key={u.id} className={u.is_active ? '' : 'opacity-60'}>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 bg-brand-100 rounded-full flex items-center justify-center">
                        <span className="text-brand-700 font-semibold text-sm">
                          {u.name.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 text-sm">{u.name}</p>
                        <p className="text-xs text-gray-400">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`badge ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {u.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-700">
                    <span
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border whitespace-nowrap"
                      style={getDeptBadgeStyle(u.department_id)}
                    >
                      <Building className="w-3.5 h-3.5" />
                      {getDepartmentName(u.department_id)}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border whitespace-nowrap"
                      style={getRoleBadgeColor(u)}
                    >
                      {getRoleName(u.role_id)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    {(() => {
                      const RANK: Record<string, number> = { superadmin: 4, manager: 2, member: 1 }
                      const myRole = me?.is_superadmin ? 'superadmin' : (me?.role || 'member')
                      const targetRole = u.is_superadmin ? 'superadmin' : (u.role || 'member')
                      
                      // Superadmins can promote/demote or toggle active status of any user (other than themselves)
                      const canManage = u.id !== me?.id && (me?.is_superadmin || (RANK[targetRole] || 1) < (RANK[myRole] || 1))

                      if (!canManage) return null
                      return (
                        <div className="flex items-center gap-2 justify-end">
                          <button
                            className="btn-secondary text-xs py-1.5 flex items-center gap-1 whitespace-nowrap"
                            onClick={() => openPromoteModal(u)}
                          >
                             Change Role
                          </button>

                          <button
                            className="text-xs py-1.5 px-3 rounded-lg font-medium flex items-center gap-1 border transition-colors whitespace-nowrap border-red-200 text-red-600 hover:bg-red-50"
                            onClick={() => setDeleteTarget({ id: u.id, name: u.name })}
                          >
                            <Trash2 className="w-3.5 h-3.5" /> Delete
                          </button>
                        </div>
                      )
                    })()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* â”€â”€ Promote Modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      {promoteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setPromoteTarget(null)}
          />

          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Change Role</h3>
                <p className="text-sm text-gray-500 mt-0.5">
                  Update role for <span className="font-medium text-gray-700">{promoteTarget.name}</span>
                </p>
              </div>
              <button
                className="p-1 rounded-md hover:bg-gray-100 transition-colors"
                onClick={() => setPromoteTarget(null)}
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div className="px-6 py-4 space-y-2">
              {roles
                .filter(opt => {
                  const RANK: Record<string, number> = { superadmin: 3, manager: 2, member: 1 }
                  const myRank = RANK[me?.is_superadmin ? 'superadmin' : (me?.role || 'member')] || 1
                  return me?.is_superadmin ? true : opt.level < myRank
                })
                .map((opt) => (
                  <label
                    key={opt.id}
                    className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                      selectedRole === opt.slug
                        ? 'border-brand-500 bg-brand-50/10'
                        : 'border-gray-100 hover:border-gray-200 bg-white'
                    }`}
                  >
                    <input
                      type="radio"
                      name="role"
                      value={opt.slug}
                      checked={selectedRole === opt.slug}
                      onChange={() => setSelectedRole(opt.slug)}
                      className="mt-0.5 accent-brand-600"
                    />
                    <div>
                      <p className="font-medium text-sm text-gray-900">{opt.name}</p>
                      <p className="text-xs text-gray-500 mt-0.5">Access Rank Level: {opt.level}</p>
                    </div>
                  </label>
                ))}
            </div>

            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
              <button
                className="btn-secondary text-sm"
                onClick={() => setPromoteTarget(null)}
              >
                Cancel
              </button>
              <button
                className="btn-primary text-sm animate-pulse-once"
                disabled={selectedRole === promoteTarget.currentRole || promote.isPending}
                onClick={() => promote.mutate({ id: promoteTarget.id, role: selectedRole })}
              >
                {promote.isPending ? 'Updating...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* â”€â”€ Create User Modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      {isInviteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm animate-fade-in" onClick={closeInviteModal} />
          {/* Modal Body */}
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100 flex flex-col max-h-[90vh] animate-scale-in">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0 bg-gray-50/50">
              <h3 className="text-lg font-bold text-gray-900">Create New User</h3>
              <button onClick={closeInviteModal} className="p-1 rounded-md hover:bg-gray-100 transition-colors ml-2">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            {createdUser ? (
              <div className="flex-1 overflow-y-auto p-6 space-y-5">
                <div className="bg-green-50 border border-green-200 text-green-800 rounded-xl p-4 flex gap-3 text-sm">
                  <Check className="w-5 h-5 text-green-600 flex-shrink-0" />
                  <div>
                    <p className="font-semibold">User Account Created!</p>
                    <p className="text-xs text-green-700 mt-0.5">
                      The user account has been successfully created with the default password.
                    </p>
                  </div>
                </div>

                <div className="space-y-4 bg-gray-50 border border-gray-100 rounded-xl p-4 text-sm">
                  <div>
                    <span className="text-gray-400 text-xs font-semibold block uppercase">Name</span>
                    <span className="text-gray-900 font-medium">{createdUser.name}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 text-xs font-semibold block uppercase">Email Address</span>
                    <span className="text-gray-900 font-mono">{createdUser.email}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 text-xs font-semibold block uppercase">Temporary Password</span>
                    <span className="text-gray-900 font-mono font-semibold">123456789</span>
                  </div>
                  <div>
                    <span className="text-gray-400 text-xs font-semibold block uppercase font-mono">Invite / Login URL</span>
                    <div className="flex items-center gap-2 mt-1.5 bg-white border border-gray-200 rounded-lg p-2 font-mono text-xs shadow-inner">
                      <span className="text-gray-800 break-all select-all flex-1">{window.location.origin + '/login'}</span>
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(window.location.origin + '/login')
                          toast.success('Invite URL copied!')
                        }}
                        className="text-brand-600 hover:text-brand-850 p-1 rounded hover:bg-gray-100"
                        title="Copy URL"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <div className="border-t border-gray-200 pt-2 text-xs text-gray-500">
                    The user will be required to change this password immediately upon their first login.
                  </div>
                </div>

                <div className="space-y-2 pt-2">
                  <button
                    onClick={handleCopy}
                    className="w-full btn-secondary py-2.5 px-4 flex items-center justify-center gap-2 text-sm text-brand-600 border-brand-200 font-semibold"
                  >
                    {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
                    {copied ? 'Copied Credentials' : 'Copy Credentials Info'}
                  </button>
                  <button onClick={closeInviteModal} className="w-full btn-primary py-2.5 px-4 text-sm font-semibold">
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleInviteSubmit} className="flex-1 flex flex-col justify-between overflow-hidden">
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                  <div>
                    <label className="label">Full Name</label>
                    <input
                      type="text"
                      required
                      value={inviteName}
                      onChange={e => setInviteName(e.target.value)}
                      placeholder="e.g. Jane Doe"
                      className="input"
                    />
                  </div>

                  <div>
                    <label className="label">Email Address</label>
                    <input
                      type="email"
                      required
                      value={inviteEmail}
                      onChange={e => setInviteEmail(e.target.value)}
                      placeholder="e.g. jane@example.com"
                      className="input"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="label">Department <span className="text-red-500">*</span></label>
                      <select
                        value={inviteDeptId}
                        onChange={e => { setInviteDeptId(e.target.value); setInviteErrors(prev => ({ ...prev, dept: undefined })) }}
                        className={`input ${inviteErrors.dept ? 'border-red-400 ring-1 ring-red-300' : ''}`}
                      >
                        <option value="">Select Department...</option>
                        {departments.map(d => (
                          <option key={d.id} value={d.id}>
                            {d.name}
                          </option>
                        ))}
                      </select>
                      {inviteErrors.dept && <p className="text-xs text-red-500 mt-1">{inviteErrors.dept}</p>}
                    </div>

                    <div>
                      <label className="label">Access Role <span className="text-red-500">*</span></label>
                      <select
                        value={inviteRoleId}
                        onChange={e => { setInviteRoleId(e.target.value); setInviteErrors(prev => ({ ...prev, role: undefined })) }}
                        className={`input ${inviteErrors.role ? 'border-red-400 ring-1 ring-red-300' : ''}`}
                      >
                        <option value="">Select Role...</option>
                        {roles
                          .filter(r => {
                            const RANK: Record<string, number> = { superadmin: 3, manager: 2, member: 1 }
                            const myRank = RANK[me?.is_superadmin ? 'superadmin' : (me?.role || 'member')] || 1
                            return me?.is_superadmin ? true : r.level < myRank
                          })
                          .map(r => (
                            <option key={r.id} value={r.id}>
                              {r.name} (Lvl {r.level})
                            </option>
                          ))}
                      </select>
                      {inviteErrors.role && <p className="text-xs text-red-500 mt-1">{inviteErrors.role}</p>}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 flex-shrink-0">
                  <button type="button" onClick={closeInviteModal} className="btn-secondary text-sm">
                    Cancel
                  </button>
                  <button type="submit" disabled={inviteUserMutation.isPending || !inviteName.trim() || !inviteEmail.trim()} className="btn-primary text-sm px-5 font-semibold">
                    {inviteUserMutation.isPending ? 'Creating user...' : 'Create User'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ── Delete Confirmation Modal ──────────────────────────────────────── */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setDeleteTarget(null)} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden border border-gray-100">
            <div className="px-6 py-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900">Delete User</h3>
              </div>
              <p className="text-sm text-gray-600">
                Are you sure you want to permanently delete <span className="font-semibold text-gray-900">{deleteTarget.name}</span>?
                This action cannot be undone.
              </p>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
              <button className="btn-secondary text-sm" onClick={() => setDeleteTarget(null)}>Cancel</button>
              <button
                className="text-sm py-2 px-4 rounded-lg font-semibold text-white bg-red-600 hover:bg-red-700 transition-colors flex items-center gap-1.5"
                disabled={deleteUser.isPending}
                onClick={() => deleteUser.mutate(deleteTarget.id)}
              >
                <Trash2 className="w-3.5 h-3.5" />
                {deleteUser.isPending ? 'Deleting...' : 'Delete Permanently'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
