import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import toast from 'react-hot-toast'
import { AlertCircle } from 'lucide-react'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Login failed. Please check your email and password.'
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  const normalizedError = error.toLowerCase()
  const emailHasError = normalizedError.includes('email') || normalizedError.includes('username')
  const passwordHasError = normalizedError.includes('password')

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="font-headline text-2xl font-extrabold text-on-surface tracking-tight">DataBridge</h1>
          <p className="text-xs text-text-muted mt-1">AI Data Gateway</p>
        </div>

        <div className="card p-8">
          <h2 className="headline-lg mb-1">Sign in</h2>
          <p className="text-sm text-text-muted mb-6">Access your data platform workspace</p>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <p>{error}</p>
              </div>
            )}
            <div>
              <label className="label">Email</label>
              <input
                className={`input ${emailHasError ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : ''}`}
                type="email"
                value={email}
                onChange={e => {
                  setEmail(e.target.value)
                  if (error) setError('')
                }}
                required
                aria-invalid={emailHasError}
              />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                className={`input ${passwordHasError ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : ''}`}
                type="password"
                value={password}
                onChange={e => {
                  setPassword(e.target.value)
                  if (error) setError('')
                }}
                required
                aria-invalid={passwordHasError}
              />
            </div>
            <button className="btn-primary w-full py-2.5" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
