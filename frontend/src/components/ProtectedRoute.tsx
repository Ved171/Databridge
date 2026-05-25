import { useEffect } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../store/auth'

export function ProtectedRoute() {
  const { token, user, loadMe, loading } = useAuthStore()

  useEffect(() => {
    if (token && !user) loadMe()
  }, [token])

  if (!token) return <Navigate to="/login" replace />
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
    </div>
  )
  return <Outlet />
}
