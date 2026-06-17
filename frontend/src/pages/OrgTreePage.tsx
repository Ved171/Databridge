import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, ChevronDown, ChevronRight, Users, Shield, Briefcase, Building, Sparkles } from 'lucide-react'
import api from '../lib/api'

interface UserData {
  id: string
  email: string
  name: string
  role: string
  role_id?: string | null
  department_id?: string | null
  is_superadmin?: boolean
  is_active: boolean
}

interface DepartmentData {
  id: string
  name: string
  slug: string
  color: string
  is_active: boolean
}

interface RoleData {
  id: string
  name: string
  slug: string
  color: string
}

interface ManagerAssignment {
  id: string
  manager_user_id: string
  member_user_id: string
}

interface OrgNode {
  id: string
  user: UserData
  children: OrgNode[]
}

interface DeptData {
  dept: DepartmentData | null
  managers: OrgNode[]
  unassigned: OrgNode[]
}

interface OrgTreePageProps {
  embedded?: boolean
}

export function OrgTreePage({ embedded = false }: OrgTreePageProps = {}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [collapsedDepts, setCollapsedDepts] = useState<Record<string, boolean>>({})
  const [collapsedManagers, setCollapsedManagers] = useState<Record<string, boolean>>({})

  const { data: users = [], isLoading: isUsersLoading, isError: isUsersError } = useQuery<UserData[]>({
    queryKey: ['users'],
    queryFn: () => api.get('/api/users/').then(r => r.data),
  })

  const { data: departments = [], isLoading: isDeptsLoading } = useQuery<DepartmentData[]>({
    queryKey: ['departments'],
    queryFn: () => api.get('/api/departments/').then(r => r.data),
  })

  const { data: roles = [] } = useQuery<RoleData[]>({
    queryKey: ['flatRoles'],
    queryFn: () => api.get('/api/roles/').then(r => r.data),
  })

  const { data: assignments = [], isLoading: isAssignmentsLoading } = useQuery<ManagerAssignment[]>({
    queryKey: ['managerAssignments'],
    queryFn: () => api.get('/api/users/manager-assignments').then(r => r.data),
  })

  const deptMap = useMemo(() => {
    const map: Record<string, DepartmentData> = {}
    departments.forEach(d => { map[d.id] = d })
    return map
  }, [departments])

  const roleMap = useMemo(() => {
    const map: Record<string, RoleData> = {}
    roles.forEach(r => { map[r.id] = r; map[r.slug] = r })
    return map
  }, [roles])

  const { superadmins, deptSections } = useMemo(() => {
    if (users.length === 0) return { superadmins: [], deptSections: [] }

    const nodeMap: Record<string, OrgNode> = {}
    users.forEach(u => { nodeMap[u.id] = { id: u.id, user: u, children: [] } })

    const memberOfManager = new Set<string>()

    assignments.forEach(a => {
      const member = nodeMap[a.member_user_id]
      const manager = nodeMap[a.manager_user_id]
      if (member && manager) {
        memberOfManager.add(a.member_user_id)
        if (!manager.children.some(c => c.id === member.id)) {
          manager.children.push(member)
        }
      }
    })

    Object.values(nodeMap).forEach(n => {
      n.children.sort((a, b) => a.user.name.localeCompare(b.user.name))
    })

    const superadminNodes = Object.values(nodeMap)
      .filter(n => n.user.is_superadmin || n.user.role === 'superadmin')
      .sort((a, b) => a.user.name.localeCompare(b.user.name))

    const superadminIds = new Set(superadminNodes.map(n => n.id))
    const nonSuper = Object.values(nodeMap).filter(n => !superadminIds.has(n.id))

    const deptIdsWithUsers = new Set<string | null>()
    nonSuper.forEach(n => deptIdsWithUsers.add(n.user.department_id ?? null))

    const orderedDepts = departments
      .filter(d => deptIdsWithUsers.has(d.id))
      .sort((a, b) => a.name.localeCompare(b.name))

    const buildSection = (deptId: string | null): DeptData => {
      const deptUsers = nonSuper.filter(n => (n.user.department_id ?? null) === deptId)
      const deptUserIds = new Set(deptUsers.map(n => n.id))

      const managers: OrgNode[] = []
      const unassigned: OrgNode[] = []

      deptUsers.forEach(n => {
        const isDirectReportOfDeptMember =
          memberOfManager.has(n.id) &&
          assignments.some(a =>
            a.member_user_id === n.id &&
            deptUserIds.has(a.manager_user_id) &&
            !superadminIds.has(a.manager_user_id)
          )

        if (!isDirectReportOfDeptMember) {
          const roleObj = n.user.role_id ? roleMap[n.user.role_id] : null
          const label = n.user.is_superadmin ? 'Super admin' : (roleObj?.name || 'Member')
          const isMgr = n.children.some(c => !superadminIds.has(c.id)) || 
                        label.toLowerCase().includes('manager') || 
                        label.toLowerCase().includes('admin')

          if (isMgr) {
            managers.push(n)
          } else {
            unassigned.push(n)
          }
        }
      })

      managers.sort((a, b) => a.user.name.localeCompare(b.user.name))
      unassigned.sort((a, b) => a.user.name.localeCompare(b.user.name))

      return { dept: deptId ? (deptMap[deptId] ?? null) : null, managers, unassigned }
    }

    const sections: DeptData[] = []
    orderedDepts.forEach(d => sections.push(buildSection(d.id)))
    if (deptIdsWithUsers.has(null)) sections.push(buildSection(null))

    return { superadmins: superadminNodes, deptSections: sections }
  }, [users, assignments, departments, deptMap])

  const getAvatarColor = (name: string) => {
    const palettes = [
      { bg: '#EEEDFE', text: '#3C3489' },
      { bg: '#E1F5EE', text: '#085041' },
      { bg: '#E6F1FB', text: '#0C447C' },
      { bg: '#FAEEDA', text: '#633806' },
      { bg: '#FBEAF0', text: '#72243E' },
      { bg: '#EAF3DE', text: '#27500A' },
      { bg: '#FAECE7', text: '#712B13' },
    ]
    let hash = 0
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
    return palettes[Math.abs(hash) % palettes.length]
  }

  const getInitials = (name: string) => {
    const parts = name.trim().split(/\s+/)
    return parts.length >= 2 ? (parts[0][0] + parts[1][0]).toUpperCase() : name.slice(0, 2).toUpperCase()
  }

  const getRoleInfo = (user: UserData) => {
    const roleObj = user.role_id ? roleMap[user.role_id] : null
    const label = user.is_superadmin ? 'Super admin' : (roleObj?.name || 'Member')
    const color = user.is_superadmin
      ? { bg: '#EEEDFE', text: '#3C3489', border: '#AFA9EC' }
      : roleObj?.color
        ? { bg: `#${roleObj.color}18`, text: `#${roleObj.color}`, border: `#${roleObj.color}40` }
        : { bg: 'var(--color-background-secondary)', text: 'var(--color-text-secondary)', border: 'var(--color-border-tertiary)' }
    return { label, color }
  }

  const matchesSearch = (user: UserData): boolean => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    const dept = user.department_id ? deptMap[user.department_id] : null
    const roleObj = user.role_id ? roleMap[user.role_id] : null
    return (
      user.name.toLowerCase().includes(q) ||
      user.email.toLowerCase().includes(q) ||
      user.role.toLowerCase().includes(q) ||
      (dept?.name.toLowerCase().includes(q) ?? false) ||
      (roleObj?.name.toLowerCase().includes(q) ?? false)
    )
  }

  const nodeMatchesSearch = (node: OrgNode): boolean => {
    if (matchesSearch(node.user)) return true
    return node.children.some(c => nodeMatchesSearch(c))
  }

  const toggleManager = (id: string) => {
    setCollapsedManagers(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const stats = useMemo(() => ({
    total: users.length,
    active: users.filter(u => u.is_active).length,
    superadminCount: users.filter(u => u.is_superadmin || u.role === 'superadmin').length,
    managers: new Set(assignments.map(a => a.manager_user_id)).size,
  }), [users, assignments])

  const isLoading = isUsersLoading || isDeptsLoading || isAssignmentsLoading

  // ── Sub-components ──────────────────────────────────────────

  const Avatar = ({ name, size = '10' }: { name: string; size?: '8' | '9' | '10' }) => {
    const { bg, text } = getAvatarColor(name)
    const sizeClasses = {
      '8': 'w-8 h-8 text-xs',
      '9': 'w-9 h-9 text-sm',
      '10': 'w-10 h-10 text-sm'
    }
    return (
      <div 
        className={`${sizeClasses[size]} rounded-full flex items-center justify-center font-bold shadow-inner shrink-0`}
        style={{ backgroundColor: bg, color: text }}
      >
        {getInitials(name)}
      </div>
    )
  }

  const RoleBadge = ({ user }: { user: UserData }) => {
    const { label, color } = getRoleInfo(user)
    return (
      <span 
        className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border shrink-0"
        style={{ backgroundColor: color.bg, color: color.text, borderColor: color.border }}
      >
        {label}
      </span>
    )
  }

  const MemberCard = ({ node }: { node: OrgNode }) => {
    if (!nodeMatchesSearch(node)) return null
    const user = node.user
    
    return (
      <div className={`flex items-center gap-4 p-4 rounded-xl border bg-white shadow-sm hover:shadow-md transition-all duration-200 ${user.is_active ? 'border-gray-100 hover:border-brand-200 hover:-translate-y-[1px]' : 'opacity-65 border-gray-50'}`}>
        <Avatar name={user.name} size="8" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-gray-900 text-sm truncate">{user.name}</span>
            <span className={`w-2 h-2 rounded-full ${user.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
          </div>
          <span className="text-xs text-gray-400 block truncate">{getRoleInfo(user).label}</span>
        </div>
        <RoleBadge user={user} />
      </div>
    )
  }

  const ManagerBlock = ({ node, deptColor }: { node: OrgNode; deptColor: string }) => {
    if (!nodeMatchesSearch(node)) return null
    const isCollapsed = collapsedManagers[node.id] ?? false
    const user = node.user
    const visibleChildren = node.children.filter(c => nodeMatchesSearch(c))

    return (
      <div className="mb-3">
        <button
          onClick={() => toggleManager(node.id)}
          className={`w-full flex items-center justify-between p-4 rounded-xl border bg-white shadow-sm hover:shadow-md transition-all duration-200 text-left ${user.is_active ? 'border-gray-100 hover:border-brand-200 hover:-translate-y-[1px]' : 'opacity-65 border-gray-50'}`}
          style={{ borderLeft: `4px solid #${deptColor}` }}
        >
          <div className="flex items-center gap-4 min-w-0">
            <Avatar name={user.name} size="9" />
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-gray-900 text-sm truncate">{user.name}</span>
                <span className={`w-2 h-2 rounded-full ${user.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
              </div>
              <span className="text-xs text-gray-400 block truncate">{getRoleInfo(user).label}</span>
            </div>
          </div>
          
          <div className="flex items-center gap-2 shrink-0">
            <RoleBadge user={user} />
            <span 
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border"
              style={{ backgroundColor: `#${deptColor}15`, color: `#${deptColor}`, borderColor: `#${deptColor}30` }}
            >
              <Users className="w-3 h-3" />
              {visibleChildren.length} {visibleChildren.length === 1 ? 'report' : 'reports'}
            </span>
            {isCollapsed ? (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            )}
          </div>
        </button>

        {!isCollapsed && visibleChildren.length > 0 && (
          <div className="relative pl-7 mt-2 space-y-2">
            <div className="absolute left-[14px] top-0 bottom-6 w-[2px] bg-gray-200" />
            {visibleChildren.map(child => (
              <div key={child.id} className="relative">
                <div className="absolute left-[-14px] top-1/2 -translate-y-1/2 w-[14px] h-[2px] bg-gray-200" />
                <MemberCard node={child} />
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  const DeptSection = ({ section }: { section: DeptData }) => {
    const deptColor = section.dept?.color ?? '94a3b8'
    const visibleManagers = section.managers.filter(n => nodeMatchesSearch(n))
    const visibleUnassigned = section.unassigned.filter(n => nodeMatchesSearch(n))
    if (visibleManagers.length === 0 && visibleUnassigned.length === 0) return null

    return (
      <div>
        {visibleManagers.map(mgr => (
          <ManagerBlock key={mgr.id} node={mgr} deptColor={deptColor} />
        ))}

        {visibleUnassigned.length > 0 && (
          <div className={`${visibleManagers.length > 0 ? 'mt-4' : ''}`}>
            <div className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2 pl-1">
              Unassigned members
            </div>
            <div className="relative pl-7 space-y-2">
              <div className="absolute left-[14px] top-0 bottom-6 w-[2px] bg-gray-200" />
              {visibleUnassigned.map(node => (
                <div key={node.id} className="relative">
                  <div className="absolute left-[-14px] top-1/2 -translate-y-1/2 w-[14px] h-[2px] bg-gray-200" />
                  <MemberCard node={node} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={embedded ? 'p-6' : 'p-8'}>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { icon: <Users className="w-5 h-5" />, label: 'Total Users', value: stats.total, bg: 'bg-indigo-50', color: 'text-indigo-650' },
          { icon: <Sparkles className="w-5 h-5" />, label: 'Active Users', value: stats.active, bg: 'bg-green-50', color: 'text-green-650' },
          { icon: <Shield className="w-5 h-5" />, label: 'Super Admins', value: stats.superadminCount, bg: 'bg-amber-50', color: 'text-amber-650' },
          { icon: <Briefcase className="w-5 h-5" />, label: 'People Managers', value: stats.managers, bg: 'bg-purple-50', color: 'text-purple-650' },
        ].map(s => (
          <div key={s.label} className="card p-4 flex items-center gap-3.5 border border-gray-100">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${s.bg} ${s.color}`}>
              {s.icon}
            </div>
            <div>
              <p className="text-xs font-medium text-gray-400">{s.label}</p>
              <p className="text-lg font-bold text-gray-900 mt-0.5">{s.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          placeholder="Search by name, email, role or department..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-12 py-2.5 border border-gray-200 rounded-xl text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 focus:outline-none transition-all bg-white"
          style={{ boxSizing: 'border-box' }}
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 hover:text-gray-600 font-medium"
          >
            Clear
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400 text-sm gap-2">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-500" />
          Loading organization hierarchy...
        </div>
      ) : isUsersError ? (
        <div className="text-center py-20 text-red-500">Failed to load organization tree.</div>
      ) : (
        <div>
          {/* Superadmins */}
          {superadmins.filter(n => nodeMatchesSearch(n)).length > 0 && (
            <div className="mb-6">
              <div className="text-xs font-bold text-indigo-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5" />
                Super admins
              </div>
              <div className="flex flex-col gap-2">
                {superadmins.filter(n => nodeMatchesSearch(n)).map(node => (
                  <div key={node.id} className={`flex items-center gap-4 p-4 rounded-xl border bg-white shadow-sm hover:shadow-md transition-all duration-200 border-gray-100 border-l-4 border-l-[#7F77DD] ${node.user.is_active ? 'hover:border-brand-200 hover:-translate-y-[1px]' : 'opacity-65 border-gray-50'}`}>
                    <Avatar name={node.user.name} size="9" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-gray-900 text-sm truncate">{node.user.name}</span>
                        <span className={`w-2 h-2 rounded-full ${node.user.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
                      </div>
                      <span className="text-xs text-gray-400 block truncate">{getRoleInfo(node.user).label}</span>
                    </div>
                    <RoleBadge user={node.user} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Dept sections mapping as collapsible blocks */}
          {deptSections.length > 0 && (
            <div className="flex flex-col gap-4">
              {deptSections.map((section) => {
                const key = section.dept?.id ?? 'NO_DEPT'
                const label = section.dept?.name ?? 'No department'
                const color = section.dept?.color ?? '94a3b8'
                const isDeptCollapsed = collapsedDepts[key] ?? false
                
                const visibleManagers = section.managers.filter(n => nodeMatchesSearch(n))
                const visibleUnassigned = section.unassigned.filter(n => nodeMatchesSearch(n))
                const memberCount = visibleManagers.length + visibleUnassigned.length
                
                if (memberCount === 0) return null

                return (
                  <div key={key} className="bg-white rounded-2xl border border-gray-150 overflow-hidden shadow-sm hover:shadow-md transition-all duration-200">
                    {/* Collapsible Header Row */}
                    <button
                      onClick={() => setCollapsedDepts(prev => ({ ...prev, [key]: !isDeptCollapsed }))}
                      className="w-full flex items-center justify-between p-5 text-left border-none bg-gray-50/50 hover:bg-gray-55 transition-colors"
                      style={{ borderLeft: `4px solid #${color}` }}
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: `#${color}` }} />
                        <span className="font-bold text-gray-900 text-sm tracking-tight">
                          {label}
                        </span>
                        <span 
                          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border"
                          style={{ backgroundColor: `#${color}15`, color: `#${color}`, borderColor: `#${color}30` }}
                        >
                          {memberCount}
                        </span>
                      </div>
                      {isDeptCollapsed ? (
                        <ChevronRight className="w-5 h-5 text-gray-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-gray-400" />
                      )}
                    </button>

                    {/* Collapsible Content */}
                    {!isDeptCollapsed && (
                      <div className="p-5 bg-white border-t border-gray-100">
                        <DeptSection section={section} />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}