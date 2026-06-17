import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/auth'

export function ProtectedRoute() {
  const { token, user, loadMe, loading } = useAuthStore()
  const location = useLocation()

  useEffect(() => {
    if (token && !user) loadMe()
  }, [token])

  if (!token) return <Navigate to="/login" replace />
  
  if (loading || (token && !user)) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
    </div>
  )

  // Force password change redirect
  if (user?.force_password_change && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }

  return <Outlet />
}
