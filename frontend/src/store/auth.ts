import { create } from 'zustand'
import api from '../lib/api'

interface User {
  id: string
  email: string
  name: string
  is_superadmin: boolean
  is_active: boolean
  role: string
  force_password_change?: boolean
  has_direct_reports?: boolean
  share_access_connector_ids?: string[]
}

interface AuthState {
  user: User | null
  token: string | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, name: string, password: string) => Promise<void>
  logout: () => void
  loadMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  loading: false,

  login: async (email, password) => {
    const { data } = await api.post('/api/auth/login', { email, password })
    localStorage.setItem('token', data.access_token)
    set({ token: data.access_token })
    const me = await api.get('/api/auth/me')
    set({ user: me.data })
  },

  register: async (email, name, password) => {
    await api.post('/api/auth/register', { email, name, password })
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ user: null, token: null })
  },

  loadMe: async () => {
    set({ loading: true })
    try {
      const { data } = await api.get('/api/auth/me')
      set({ user: data })
    } catch {
      set({ user: null, token: null })
      localStorage.removeItem('token')
    } finally {
      set({ loading: false })
    }
  },
}))
