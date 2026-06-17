import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { PageTabs } from '../components/PageTabs'
import { UsersPage } from './UsersPage'
import { DepartmentsPage } from './DepartmentsPage'
import { RolesPage } from './RolesPage'
import { OrgTreePage } from './OrgTreePage'

export function PeoplePage() {
  const { user } = useAuthStore()
  const [searchParams, setSearchParams] = useSearchParams()

  const isAdminLike = user?.is_superadmin || user?.role === 'admin' || user?.role === 'workspace_admin' || user?.role === 'superadmin'
  const isSuperAdmin = user?.is_superadmin || user?.role === 'superadmin' || user?.role === 'super_admin'

  const tabs = useMemo(() => {
    const items = []
    if (isAdminLike) {
      items.push({ id: 'users', label: 'Users' })
    }
    items.push({ id: 'org', label: 'Org Tree' })
    if (isSuperAdmin) {
      items.push({ id: 'departments', label: 'Departments' })
      items.push({ id: 'roles', label: 'Roles' })
    }
    return items
  }, [isAdminLike, isSuperAdmin])

  const activeTab = tabs.some(t => t.id === searchParams.get('tab'))
    ? searchParams.get('tab')!
    : tabs[0]?.id ?? 'users'

  const setTab = (id: string) => setSearchParams({ tab: id })

  if (tabs.length === 0) {
    return (
      <div className="p-8 text-sm text-text-muted">You do not have access to people management.</div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-6 pb-0 flex-shrink-0 border-b border-border-default bg-surface">
        <h1 className="headline-lg mb-1">People</h1>
        <p className="text-sm text-text-muted mb-4">Manage users, departments, and roles</p>
        <PageTabs tabs={tabs} active={activeTab} onChange={setTab} />
      </div>
      <div className="flex-1 overflow-y-auto min-h-0">
        {activeTab === 'users' && <UsersPage embedded />}
        {activeTab === 'org' && <OrgTreePage embedded />}
        {activeTab === 'departments' && <DepartmentsPage embedded />}
        {activeTab === 'roles' && <RolesPage embedded />}
      </div>
    </div>
  )
}
