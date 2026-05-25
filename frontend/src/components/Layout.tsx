import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Database, Shield, MessageSquare,
  Users, LogOut, ChevronRight, Zap
} from 'lucide-react'
import { useAuthStore } from '../store/auth'
import clsx from 'clsx'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/connectors', icon: Database, label: 'Connectors' },
  { to: '/permissions', icon: Shield, label: 'Permissions', adminOnly: true },
  // { to: '/query',       icon: MessageSquare,   label: 'Query' },
  { to: '/mcp', icon: Zap, label: 'MCP Integration' },
  { to: '/users', icon: Users, label: 'Users', adminOnly: true },
]

export function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const isAdminLike = user?.is_superadmin || user?.role === 'admin' || user?.role === 'workspace_admin' || user?.role === 'superadmin'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-60 bg-gray-900 flex flex-col">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="text-white font-bold text-sm">DataBridge</p>
              <p className="text-gray-500 text-xs">AI Data Gateway</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            if (item.adminOnly && !isAdminLike) return null
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-brand-600 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800'
                  )
                }
              >
                <item.icon className="w-4 h-4 flex-shrink-0" />
                {item.label}
              </NavLink>
            )
          })}
        </nav>

        {/* User */}
        <div className="px-3 py-4 border-t border-gray-800">
          <div className="px-3 py-2 mb-1">
            <p className="text-white text-sm font-medium truncate">{user?.name}</p>
            <p className="text-gray-500 text-xs truncate">{user?.email}</p>
            {(user?.is_superadmin || user?.role === 'superadmin') && (
              <span className="badge bg-red-900 text-red-200 mt-1">Super Admin</span>
            )}
            {(!user?.is_superadmin && user?.role === 'admin') && (
              <span className="badge bg-brand-900 text-brand-200 mt-1">Admin</span>
            )}
            {user?.role === 'workspace_admin' && (
              <span className="badge bg-purple-900 text-purple-200 mt-1">Workspace Admin</span>
            )}
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-3 py-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg text-sm transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
