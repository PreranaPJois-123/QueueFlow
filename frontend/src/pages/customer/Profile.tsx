import { useAuth } from '../../lib/auth'
import { AppShell } from '../../components/AppShell'

export default function Profile() {
  const { user } = useAuth()
  if (!user) return null

  return (
    <AppShell variant="customer">
      <h1 className="text-xl font-semibold text-ink-900">Profile</h1>
      <div className="mt-6 max-w-md rounded-2xl border border-ink-100 bg-white p-6">
        <dl className="flex flex-col gap-4 text-sm">
          <div>
            <dt className="text-ink-400">Full name</dt>
            <dd className="mt-0.5 font-medium text-ink-900">{user.full_name}</dd>
          </div>
          <div>
            <dt className="text-ink-400">Email</dt>
            <dd className="mt-0.5 font-medium text-ink-900">{user.email}</dd>
          </div>
          <div>
            <dt className="text-ink-400">Role</dt>
            <dd className="mt-0.5 font-medium text-ink-900">{user.role.charAt(0) + user.role.slice(1).toLowerCase()}</dd>
          </div>
          <div>
            <dt className="text-ink-400">Member since</dt>
            <dd className="mt-0.5 font-medium text-ink-900">{new Date(user.created_at).toLocaleDateString()}</dd>
          </div>
        </dl>
      </div>
    </AppShell>
  )
}
