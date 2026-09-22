import { Link } from 'react-router-dom'
import { Button } from '../components/Button'

const steps = [
  { title: 'Pick a service', body: 'Choose from the services on offer — a clinic visit, a counter, a consultation.' },
  { title: 'Join the queue', body: 'Get a token instantly. No app download, no physical line to stand in.' },
  { title: 'Watch your position update', body: 'Your ticket updates live as staff call the next customer — no refreshing.' },
  { title: 'Arrive when it matters', body: 'Get an alert when your turn is close, so you only need to show up on time.' },
]

const features = [
  { title: 'Live position tracking', body: 'Your dashboard reflects the real queue state the moment staff act on it, over a live connection.' },
  { title: 'Wait-time estimates', body: 'Estimates are built from each queue\u2019s own recent service history, not a guess.' },
  { title: 'Staff operations console', body: 'Call, skip, pause, or close a queue with guardrails that stop invalid actions before they happen.' },
  { title: 'Service analytics', body: 'See customers served, average wait, and average service time as they actually occurred.' },
]

export default function Landing() {
  return (
    <div className="bg-paper">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-ink-900 text-sm font-bold text-white">Q</div>
          <span className="text-sm font-semibold text-ink-900">QueueFlow</span>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/login" className="text-sm font-medium text-ink-600 hover:text-ink-900">Log in</Link>
          <Link to="/register">
            <Button size="sm">Get started</Button>
          </Link>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-10 px-6 pb-20 pt-10 md:grid-cols-2 md:items-center md:pt-16">
        <div>
          <h1 className="text-4xl font-semibold leading-tight text-ink-900 md:text-5xl">
            Skip the queue.
            <br />
            Know your turn.
          </h1>
          <p className="mt-5 max-w-md text-base text-ink-500">
            QueueFlow replaces the physical waiting line at clinics, banks, campus offices and service
            counters with a live ticket that tells you exactly when to show up.
          </p>
          <div className="mt-8 flex items-center gap-3">
            <Link to="/register">
              <Button>Join a queue</Button>
            </Link>
            <Link to="/register">
              <Button variant="secondary">I run a service desk</Button>
            </Link>
          </div>
        </div>

        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-400">Your ticket</p>
          <p className="token-display mt-2 text-5xl font-bold text-ink-900">#A047</p>
          <div className="mt-6 grid grid-cols-3 gap-4 border-t border-ink-100 pt-5 text-sm">
            <div>
              <p className="text-ink-400">Now serving</p>
              <p className="mt-1 font-semibold text-ink-900">#A043</p>
            </div>
            <div>
              <p className="text-ink-400">People ahead</p>
              <p className="mt-1 font-semibold text-ink-900">3</p>
            </div>
            <div>
              <p className="text-ink-400">Est. wait</p>
              <p className="mt-1 font-semibold text-signal-700">~12 min</p>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-ink-100 bg-white py-16">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-2xl font-semibold text-ink-900">How it works</h2>
          <div className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, i) => (
              <div key={step.title}>
                <p className="text-sm font-medium text-signal-700">{String(i + 1).padStart(2, '0')}</p>
                <p className="mt-2 text-sm font-semibold text-ink-900">{step.title}</p>
                <p className="mt-1 text-sm text-ink-500">{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-2xl font-semibold text-ink-900">Built for both sides of the counter</h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            {features.map((f) => (
              <div key={f.title} className="rounded-xl border border-ink-100 bg-white p-5">
                <p className="text-sm font-semibold text-ink-900">{f.title}</p>
                <p className="mt-1.5 text-sm text-ink-500">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-ink-100 py-16">
        <div className="mx-auto max-w-6xl px-6 text-center">
          <h2 className="text-2xl font-semibold text-ink-900">Ready to stop waiting in line?</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-ink-500">
            Create an account as a customer to join your first queue, or as staff to set up a service desk.
          </p>
          <div className="mt-6 flex justify-center">
            <Link to="/register">
              <Button>Get started</Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-ink-100 py-8 text-center text-xs text-ink-400">
        QueueFlow — a portfolio project.
      </footer>
    </div>
  )
}
