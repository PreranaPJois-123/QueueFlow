import { type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

interface NavItem {
  to: string
  label: string
}

const customerNav: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/services', label: 'Services' },
  { to: '/my-ticket', label: 'My ticket' },
  { to: '/appointments', label: 'Appointments' },
  { to: '/profile', label: 'Profile' },
]

const staffNav: NavItem[] = [
  { to: '/staff/dashboard', label: 'Dashboard' },
  { to: '/staff/queues', label: 'Queues' },
  { to: '/staff/customers', label: 'Customers' },
  { to: '/staff/analytics', label: 'Analytics' },
  { to: '/staff/settings', label: 'Settings' },
]

export function AppShell({ children, variant }: { children: ReactNode; variant: 'customer' | 'staff' }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const items = variant === 'customer' ? customerNav : staffNav

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <aside className="hidden w-60 flex-col border-r border-ink-100 bg-white px-4 py-6 md:flex">
        <div className="mb-8 flex items-center gap-2 px-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-ink-900 text-sm font-bold text-white">
            Q
          </div>
          <span className="text-sm font-semibold text-ink-900">QueueFlow</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? 'bg-signal-50 text-signal-700' : 'text-ink-500 hover:bg-ink-50 hover:text-ink-800'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto border-t border-ink-100 pt-4">
          <p className="truncate px-2 text-sm font-medium text-ink-800">{user?.full_name}</p>
          <p className="truncate px-2 text-xs text-ink-400">{user?.email}</p>
          <button
            onClick={handleLogout}
            className="mt-3 w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-ink-500 hover:bg-ink-50 hover:text-ink-800"
          >
            Log out
          </button>
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-ink-100 bg-white px-4 py-3 md:hidden">
          <span className="text-sm font-semibold text-ink-900">QueueFlow</span>
          <button onClick={handleLogout} className="text-sm text-ink-500">
            Log out
          </button>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-ink-100 bg-white px-2 py-2 md:hidden">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                `whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium ${
                  isActive ? 'bg-signal-50 text-signal-700' : 'text-ink-500'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  )
}
