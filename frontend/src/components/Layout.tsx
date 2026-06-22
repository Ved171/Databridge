import { useState, useEffect, useRef } from 'react'
import { Outlet, NavLink, useNavigate, Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Database, ShieldCheck, Users,
  LogOut, Zap, Plus, Menu, X, Bell,
} from 'lucide-react'
import { useAuthStore } from '../store/auth'
import clsx from 'clsx'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/connectors', icon: Database, label: 'Connectors' },
  { to: '/access', icon: ShieldCheck, label: 'Access Control', adminOnly: true },
  { to: '/people', icon: Users, label: 'People' },
  { to: '/mcp', icon: Zap, label: 'MCP Integration' },
]

const parseUTC = (dateStr: string | null | undefined): Date | null => {
  if (!dateStr) return null
  let normalized = dateStr
  if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !/-\d{2}:\d{2}$/.test(dateStr)) {
    normalized = dateStr + 'Z'
  }
  return new Date(normalized)
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const qc = useQueryClient()
  const [showNotifications, setShowNotifications] = useState(false)
  const notificationsRef = useRef<HTMLDivElement>(null)

  const { data: notifications = [] } = useQuery<any[]>({
    queryKey: ['notifications'],
    queryFn: () => api.get('/api/notifications/').then(r => r.data),
    refetchInterval: 10000,
  })

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (notificationsRef.current && !notificationsRef.current.contains(event.target as Node)) {
        setShowNotifications(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  const isAdminLike = user?.is_superadmin || user?.role === 'admin' || user?.role === 'workspace_admin' || user?.role === 'superadmin'

  const handleLogout = () => {
    logout()
    navigate('/login')
    onNavigate?.()
  }

  const unreadCount = notifications.filter(n => !n.is_read).length

  const markReadMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/notifications/${id}/read`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
    }
  })

  const markAllReadMutation = useMutation({
    mutationFn: () => api.post('/api/notifications/read-all'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
    }
  })

  return (
    <>
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-headline text-lg font-extrabold text-on-surface tracking-tight">DataBridge</h1>
            <p className="text-xs text-text-muted mt-0.5">AI Data Gateway</p>
          </div>
          
          {/* Notifications Dropdown */}
          <div className="relative" ref={notificationsRef}>
            <button
              onClick={() => {
                const willShow = !showNotifications;
                setShowNotifications(willShow);
                if (willShow && unreadCount > 0) {
                  markAllReadMutation.mutate();
                }
              }}
              className="p-1.5 rounded-full text-sidebar-text hover:bg-sidebar-hover hover:text-on-surface transition-colors relative"
            >
              <Bell className="w-5 h-5" />
              {unreadCount > 0 && (
                <span className="absolute top-0.5 right-0.5 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center animate-pulse">
                  {unreadCount}
                </span>
              )}
            </button>

            {showNotifications && (
              <div className="absolute left-6 mt-2 w-72 bg-white rounded-lg shadow-xl border border-border-default z-50 py-2 animate-scale-in text-on-surface">
                <div className="px-4 py-2 border-b border-border-muted flex items-center justify-between">
                  <span className="text-xs font-bold text-text-primary">Notifications</span>
                </div>
                <div className="max-h-60 overflow-y-auto divide-y divide-border-muted">
                  {notifications.length === 0 ? (
                    <div className="px-4 py-6 text-center text-xs text-text-muted italic">
                      No notifications
                    </div>
                  ) : (
                    notifications.map((n: any) => (
                      <div
                        key={n.id}
                        onClick={() => !n.is_read && markReadMutation.mutate(n.id)}
                        className={clsx(
                          "px-4 py-2.5 text-left text-xs transition-colors cursor-pointer hover:bg-surface-container-low",
                          !n.is_read && "bg-accent-50/40"
                        )}
                      >
                        <div className="flex items-center justify-between gap-1 mb-0.5">
                          <span className={clsx("font-semibold truncate", !n.is_read ? "text-accent-700" : "text-text-primary")}>
                            {n.title}
                          </span>
                          <span className="text-[9px] text-text-muted whitespace-nowrap">
                            {(() => {
                              const parsed = parseUTC(n.created_at)
                              return parsed ? `${parsed.toLocaleDateString()} ${parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''
                            })()}
                          </span>
                        </div>
                        <p className={clsx("line-clamp-2", !n.is_read ? "text-text-primary" : "text-text-muted")}>
                          {n.message}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <Link
          to="/connectors"
          onClick={onNavigate}
          className="mt-5 flex items-center justify-center gap-2 w-full bg-accent-500 hover:opacity-90 text-white text-sm font-medium py-2.5 rounded transition-opacity"
        >
          <Plus className="w-4 h-4" />
          New Connector
        </Link>
      </div>

      <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          if (item.adminOnly && !isAdminLike) return null
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={onNavigate}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-colors relative',
                  isActive
                    ? 'bg-sidebar-active text-on-surface before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:w-0.5 before:h-5 before:bg-accent-500 before:rounded-full'
                    : 'text-sidebar-text hover:bg-sidebar-hover hover:text-on-surface'
                )
              }
            >
              <item.icon className="w-4 h-4 flex-shrink-0" />
              {item.label}
            </NavLink>
          )
        })}
        {(() => {
          const hasShareAccess = user?.share_access_connector_ids && user.share_access_connector_ids.length > 0
          if (!hasShareAccess) return null
          const firstConnId = user.share_access_connector_ids![0]
          const isActive = location.pathname.includes('/team-access')
          return (
            <Link
              to={`/connectors/${firstConnId}/team-access`}
              onClick={onNavigate}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-colors relative',
                isActive
                  ? 'bg-sidebar-active text-on-surface before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:w-0.5 before:h-5 before:bg-accent-500 before:rounded-full'
                  : 'text-sidebar-text hover:bg-sidebar-hover hover:text-on-surface'
              )}
            >
              <Users className="w-4 h-4 flex-shrink-0" />
              Team Access
            </Link>
          )
        })()}
      </nav>

      <div className="px-3 py-4 border-t border-sidebar-border">
        <div className="px-3 py-2 mb-1">
          <p className="text-sm font-medium text-on-surface truncate">{user?.name}</p>
          <p className="text-xs text-text-muted truncate">{user?.email}</p>
          {(user?.is_superadmin || user?.role === 'superadmin') && (
            <span className="badge-error mt-1 inline-block">Super Admin</span>
          )}
          {(!user?.is_superadmin && user?.role === 'admin') && (
            <span className="badge bg-accent-50 text-accent-600 border border-accent-200 mt-1 inline-block">Admin</span>
          )}
          {user?.role === 'workspace_admin' && (
            <span className="badge bg-accent-50 text-accent-600 border border-accent-200 mt-1 inline-block">Workspace Admin</span>
          )}
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2 rounded text-sm text-sidebar-text hover:bg-sidebar-hover hover:text-on-surface transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </>
  )
}

export function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-screen bg-surface overflow-hidden">
      <aside className="hidden lg:flex w-sidebar bg-sidebar-bg border-r border-sidebar-border flex-col flex-shrink-0">
        <SidebarContent />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-sidebar bg-sidebar-bg flex flex-col shadow-xl">
            <div className="flex justify-end p-3">
              <button onClick={() => setMobileOpen(false)} className="p-1.5 rounded hover:bg-sidebar-hover">
                <X className="w-5 h-5 text-on-surface" />
              </button>
            </div>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="lg:hidden flex items-center px-4 py-3 border-b border-border-default bg-surface flex-shrink-0">
          <button onClick={() => setMobileOpen(true)} className="p-2 rounded hover:bg-surface-container-low">
            <Menu className="w-5 h-5 text-on-surface" />
          </button>
          <span className="ml-3 font-headline font-bold text-on-surface">DataBridge</span>
        </div>
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
