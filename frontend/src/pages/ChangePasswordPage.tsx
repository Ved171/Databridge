import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import toast from 'react-hot-toast'
import { KeyRound, Lock, LogOut } from 'lucide-react'
import api from '../lib/api'

export function ChangePasswordPage() {
  const navigate = useNavigate()
  const { logout } = useAuthStore()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match.')
      return
    }

    if (newPassword.length < 8) {
      toast.error('New password must be at least 8 characters long.')
      return
    }

    setLoading(true)
    try {
      await api.post('/api/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })
      toast.success('Password changed successfully. Please log in again.')
      
      // Logout and redirect to login
      logout()
      navigate('/login')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to change password.')
    } finally {
      setLoading(false)
    }
  }

  const handleCancelLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="flex justify-center mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-brand-600 rounded-xl flex items-center justify-center">
              <Lock className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-bold text-gray-900 text-lg">DataBridge</p>
              <p className="text-gray-500 text-xs">Security Settings</p>
            </div>
          </div>
        </div>

        <div className="card p-8 relative">
          <button
            onClick={handleCancelLogout}
            className="absolute top-4 right-4 p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            title="Log out"
          >
            <LogOut className="w-4 h-4" />
          </button>

          <h1 className="text-xl font-bold text-gray-900 mb-2">Change Password</h1>
          <p className="text-gray-500 text-xs mb-6">
            For security reasons, you must change your password before continuing.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Current Password</label>
              <input
                className="input"
                type="password"
                value={currentPassword}
                onChange={e => setCurrentPassword(e.target.value)}
                required
                placeholder="Current password"
              />
            </div>

            <div>
              <label className="label">New Password</label>
              <input
                className="input"
                type="password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                required
                placeholder="At least 8 characters"
              />
            </div>

            <div>
              <label className="label">Confirm New Password</label>
              <input
                className="input"
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                required
                placeholder="Repeat new password"
              />
            </div>

            <button className="btn-primary w-full mt-2" disabled={loading}>
              {loading ? 'Updating Password...' : 'Update Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
