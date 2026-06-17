import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserCheck, UserX, ShieldCheck, ChevronUp, X } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/auth'

interface PromoteTarget {
  id: string
  name: string
  currentRole: string
}

const ROLE_OPTIONS = [
  { value: 'member', label: 'Member', desc: 'Standard user with basic read access', color: 'bg-gray-100 text-gray-700 border-gray-200', rank: 1 },
  { value: 'workspace_admin', label: 'Workspace Admin', desc: 'Can manage connectors and workspace members', color: 'bg-purple-50 text-purple-700 border-purple-200', rank: 2 },
  { value: 'admin', label: 'Admin', desc: 'Full access - manage users, connectors, and all settings', color: 'bg-brand-50 text-brand-700 border-brand-200', rank: 3 },
  { value: 'superadmin', label: 'Super Admin', desc: 'System-wide full access', color: 'bg-red-50 text-red-700 border-red-200', rank: 4 },
]

export function UsersPage() {
  const qc = useQueryClient()
  const { user: me } = useAuthStore()
  const [promoteTarget, setPromoteTarget] = useState<PromoteTarget | null>(null)
  const [selectedRole, setSelectedRole] = useState<string>('')

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get('/api/users/').then(r => r.data),
  })

  const toggleActive = useMutation({
    mutationFn: (id: string) => api.patch(`/api/users/${id}/toggle-active`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); toast.success('Updated') },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const promote = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      api.patch(`/api/users/${id}/promote?role=${role}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      toast.success('Role updated successfully')
      setPromoteTarget(null)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const openPromoteModal = (u: any) => {
    const currentRole = u.is_superadmin ? 'superadmin' : (u.role || 'member')
    setPromoteTarget({ id: u.id, name: u.name, currentRole })
    setSelectedRole(currentRole)
  }

  const getRoleBadge = (u: any) => {
    const role = u.is_superadmin ? 'superadmin' : (u.role || 'member')
    switch (role) {
      case 'superadmin':
        return (
          <span className="badge bg-red-100 text-red-700 flex items-center gap-1 w-fit">
            <ShieldCheck className="w-3 h-3" /> Super Admin
          </span>
        )
      case 'admin':
        return (
          <span className="badge bg-brand-100 text-brand-700 flex items-center gap-1 w-fit">
            <ShieldCheck className="w-3 h-3" /> Admin
          </span>
        )
      case 'workspace_admin':
        return (
          <span className="badge bg-purple-100 text-purple-700 flex items-center gap-1 w-fit">
            <ShieldCheck className="w-3 h-3" /> Workspace Admin
          </span>
        )
      default:
        return <span className="badge bg-gray-100 text-gray-600">Member</span>
    }
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Users</h1>
        <p className="text-gray-500 mt-1 text-sm">Manage user accounts and access</p>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">User</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Role</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Joined</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.map((u: any) => (
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
                  <td className="px-6 py-4">
                    {getRoleBadge(u)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    {(() => {
                      const RANK: Record<string, number> = { superadmin: 4, admin: 3, workspace_admin: 2, member: 1 }
                      const myRole = me?.is_superadmin ? 'superadmin' : (me?.role || 'member')
                      const targetRole = u.is_superadmin ? 'superadmin' : (u.role || 'member')
                      const canManage = u.id !== me?.id && (RANK[targetRole] || 1) < (RANK[myRole] || 1)

                      if (!canManage) return null
                      return (
                        <div className="flex items-center gap-2 justify-end">
                          <button
                            className="btn-secondary text-xs py-1.5 flex items-center gap-1"
                            onClick={() => openPromoteModal(u)}
                          >
                            Change Role
                          </button>

                          <button
                            className={`text-xs py-1.5 px-3 rounded-lg font-medium flex items-center gap-1 border transition-colors ${u.is_active
                                ? 'border-red-200 text-red-600 hover:bg-red-50'
                                : 'border-green-200 text-green-600 hover:bg-green-50'
                              }`}
                            onClick={() => toggleActive.mutate(u.id)}
                          >
                            {u.is_active
                              ? <><UserX className="w-3.5 h-3.5" /> Disable</>
                              : <><UserCheck className="w-3.5 h-3.5" /> Enable</>
                            }
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

      {/* ── Promote Modal ──────────────────────────────────────────────── */}
      {promoteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setPromoteTarget(null)}
          />

          {/* Modal */}
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            {/* Header */}
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

            {/* Role Options */}
            <div className="px-6 py-4 space-y-2">
              {ROLE_OPTIONS.filter(opt => {
                const RANK: Record<string, number> = { superadmin: 4, admin: 3, workspace_admin: 2, member: 1 }
                const myRank = RANK[me?.is_superadmin ? 'superadmin' : (me?.role || 'member')] || 1
                return opt.rank < myRank
              }).map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${selectedRole === opt.value
                      ? opt.color + ' border-current'
                      : 'border-gray-100 hover:border-gray-200 bg-white'
                    }`}
                >
                  <input
                    type="radio"
                    name="role"
                    value={opt.value}
                    checked={selectedRole === opt.value}
                    onChange={() => setSelectedRole(opt.value)}
                    className="mt-0.5 accent-brand-600"
                  />
                  <div>
                    <p className="font-medium text-sm">{opt.label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{opt.desc}</p>
                  </div>
                </label>
              ))}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50">
              <button
                className="btn-secondary text-sm"
                onClick={() => setPromoteTarget(null)}
              >
                Cancel
              </button>
              <button
                className="btn-primary text-sm"
                disabled={selectedRole === promoteTarget.currentRole || promote.isPending}
                onClick={() => promote.mutate({ id: promoteTarget.id, role: selectedRole })}
              >
                {promote.isPending ? 'Updating...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
