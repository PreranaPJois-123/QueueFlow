import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api } from './api'
import type { User, UserRole } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  async function fetchMe() {
    try {
      const { data } = await api.get<User>('/api/auth/me')
      setUser(data)
    } catch {
      setUser(null)
      localStorage.removeItem('queueflow_token')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const token = localStorage.getItem('queueflow_token')
    if (token) {
      fetchMe()
    } else {
      setLoading(false)
    }
  }, [])

  async function login(email: string, password: string) {
    const { data } = await api.post('/api/auth/login', { email, password })
    localStorage.setItem('queueflow_token', data.access_token)
    try {
      const { data: me } = await api.get<User>('/api/auth/me')
      setUser(me)
    } catch (error) {
      localStorage.removeItem('queueflow_token')
      setUser(null)
      throw error
    }
  }

  async function register(email: string, password: string, fullName: string) {
    await api.post('/api/auth/register', { email, password, full_name: fullName })
    await login(email, password)
  }

  function logout() {
    localStorage.removeItem('queueflow_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function RequireAuth({ children, roles }: { children: ReactNode; roles?: UserRole[] }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-ink-400">
        Loading…
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to={user.role === 'CUSTOMER' ? '/dashboard' : '/staff/dashboard'} replace />
  }
  return <>{children}</>
}
