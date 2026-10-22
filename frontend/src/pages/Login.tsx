import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { extractErrorMessage } from '../lib/api'
import { Button } from '../components/Button'
import { ErrorState } from '../components/States'

export default function Login() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      const dest = (location.state as { from?: Location })?.from?.pathname
      navigate(dest || '/dashboard')
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (user) {
    return <Navigate to={user.role === 'CUSTOMER' ? '/dashboard' : '/staff/dashboard'} replace />
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-8 flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-ink-900 text-sm font-bold text-white">Q</div>
          <span className="text-sm font-semibold text-ink-900">QueueFlow</span>
        </Link>
        <h1 className="text-xl font-semibold text-ink-900">Log in</h1>
        <p className="mt-1 text-sm text-ink-500">Track your place in line, wherever you are.</p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          {error && <ErrorState message={error} />}
          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-ink-700">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-ink-200 px-3 py-2.5 text-sm outline-none focus:border-signal-500"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-ink-700">Password</label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-ink-200 px-3 py-2.5 text-sm outline-none focus:border-signal-500"
            />
          </div>
          <Button type="submit" loading={loading} className="mt-2 w-full">
            Log in
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-500">
          Don't have an account?{' '}
          <Link to="/register" className="font-medium text-signal-700 hover:underline">
            Register
          </Link>
        </p>
      </div>
    </div>
  )
}
