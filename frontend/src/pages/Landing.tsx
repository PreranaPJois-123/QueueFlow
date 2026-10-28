import { Link, Navigate } from "react-router-dom";
import { BellRing, CalendarSearch, MessageCircleQuestion, ShieldCheck, Ticket } from "lucide-react";
import { homeFor, useAuth } from "../lib/auth";
import { kindMeta } from "../lib/kinds";
import type { VenueKind } from "../types";

const PLACES: { kind: VenueKind; title: string; body: string }[] = [
  { kind: "HOSPITAL", title: "See a doctor without the waiting room",
    body: "Choose a specialization and doctor, pick a real free slot, and get a token for the desk." },
  { kind: "SHOP", title: "Book the chair, not the queue",
    body: "Salons, repair desks and consultations. Pick who you want and see how long it takes." },
  { kind: "HOTEL", title: "Know the total before you reserve",
    body: "Live availability for your dates with nightly rate, taxes and cancellation terms upfront." },
];

const STEPS = [
  { icon: CalendarSearch, title: "Pick a time that's actually free", body: "Slots come from each doctor's or stylist's real schedule; taken times never show." },
  { icon: Ticket, title: "Get your token", body: "Your booking reference and queue token are issued the moment you confirm." },
  { icon: BellRing, title: "Arrive when it's your turn", body: "Watch the queue move live, and get an alert about 20 minutes before you're up." },
];

export default function Landing() {
  const { user, loading } = useAuth();
  if (!loading && user) return <Navigate to={homeFor(user)} replace />;
  return (
    <div className="min-h-screen bg-paper text-ink-900">
      <div className="relative overflow-hidden bg-night text-white">
        <div aria-hidden className="absolute -right-32 top-10 h-[28rem] w-[28rem] rounded-full bg-serving/15 blur-3xl" />
        <div aria-hidden className="absolute -left-40 bottom-0 h-80 w-80 rounded-full bg-care-600/30 blur-3xl" />
        <header className="relative mx-auto flex max-w-6xl items-center justify-between px-4 py-5 md:px-8">
          <Link to="/" className="flex items-center gap-2.5">
            <span aria-hidden className="font-display flex h-9 w-9 items-center justify-center rounded-lg bg-serving font-bold text-ink-950">Q</span>
            <span className="font-display text-lg font-semibold">QueueFlow</span>
          </Link>
          <nav className="flex items-center gap-1 text-sm font-medium">
            <Link to="/hospitals" className="hidden rounded-lg px-3 py-2 text-ink-300 hover:text-white sm:inline">Browse</Link>
            <Link to="/login" className="rounded-lg px-3 py-2 text-ink-200 hover:text-white">Sign in</Link>
            <Link to="/register" className="rounded-lg bg-white px-4 py-2 font-semibold text-ink-900 hover:bg-ink-100">Create account</Link>
          </nav>
        </header>
        <section className="relative mx-auto grid max-w-6xl items-center gap-14 px-4 pb-24 pt-10 md:grid-cols-[1.1fr_1fr] md:px-8 md:pt-16">
          <div>
            <h1 className="text-4xl font-semibold leading-[1.04] md:text-6xl">Wait less. Know exactly when it's your turn.</h1>
            <p className="mt-6 max-w-xl text-lg text-ink-300">
              Book hospital consultations and shop services with a queue token that updates live, and reserve hotel rooms with the final price shown before you confirm.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link to="/hospitals" className="rounded-xl bg-serving px-5 py-3 text-sm font-semibold text-ink-950 hover:brightness-105">Find a hospital</Link>
              <Link to="/shops" className="rounded-xl bg-white/10 px-5 py-3 text-sm font-semibold text-white ring-1 ring-white/15 hover:bg-white/15">Shops</Link>
              <Link to="/hotels" className="rounded-xl bg-white/10 px-5 py-3 text-sm font-semibold text-white ring-1 ring-white/15 hover:bg-white/15">Hotels</Link>
            </div>
          </div>
          <figure aria-label="Example of a QueueFlow token" className="relative">
            <div className="stub stub-enter mx-auto max-w-md text-ink-900 shadow-[0_40px_80px_-30px_rgba(0,0,0,0.7)]" style={{ ["--stub-cut" as string]: "58%", ["--color-paper" as string]: "#0f1218" }}>
              <div className="grid grid-cols-[58%_42%]">
                <div className="space-y-3 p-6">
                  <p className="text-xs text-ink-400">Example ticket</p>
                  <p className="font-display text-xl font-semibold">Cardiology consultation</p>
                  <p className="text-sm text-ink-500">Thursday, 10:40 am</p>
                  <p className="text-sm text-ink-600">3 ahead of you, about 25 min to go</p>
                </div>
                <div className="stub-divider flex flex-col justify-center gap-1 rounded-r-2xl bg-amber-100/60 p-6">
                  <p className="text-xs text-ink-500">Your token</p>
                  <p className="token-display font-display text-5xl font-bold">C-014</p>
                  <p className="mt-2 text-xs text-ink-500">Now serving <span className="font-semibold text-ink-900">C-011</span></p>
                </div>
              </div>
            </div>
            <figcaption className="mx-auto mt-8 flex max-w-sm items-start gap-3 rounded-2xl bg-white/5 p-4 text-sm text-ink-200 ring-1 ring-white/10">
              <BellRing aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-serving" />
              <span>"Your appointment is approaching. Your turn is expected in approximately 20 minutes. Please be ready."</span>
            </figcaption>
          </figure>
        </section>
      </div>

      <main>
        <section className="mx-auto max-w-6xl px-4 py-20 md:px-8">
          <h2 className="max-w-xl text-3xl font-semibold">One app for the places you queue</h2>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {PLACES.map(({ kind, title, body }) => {
              const meta = kindMeta[kind];
              const Icon = meta.icon;
              return (
                <Link key={kind} to={meta.path} className="surface group flex flex-col rounded-3xl p-7 transition-shadow hover:shadow-xl">
                  <span className={`flex h-12 w-12 items-center justify-center rounded-2xl ${meta.tint}`}>
                    <Icon aria-hidden className={`h-6 w-6 ${meta.text}`} strokeWidth={1.75} />
                  </span>
                  <p className={`mt-6 text-sm font-semibold ${meta.text}`}>{meta.plural}</p>
                  <h3 className="mt-1 text-xl font-semibold">{title}</h3>
                  <p className="mt-2 flex-1 text-ink-600">{body}</p>
                  <span className={`mt-6 text-sm font-semibold ${meta.text} group-hover:underline`}>Browse {meta.plural.toLowerCase()}</span>
                </Link>
              );
            })}
          </div>
        </section>

        <section className="border-y border-ink-100 bg-white">
          <div className="mx-auto max-w-6xl px-4 py-20 md:px-8">
            <h2 className="text-3xl font-semibold">How it works</h2>
            <ol className="mt-10 grid gap-8 md:grid-cols-3">
              {STEPS.map(({ icon: Icon, title, body }, i) => (
                <li key={title} className="relative">
                  <div className="flex items-center gap-3">
                    <span className="font-display flex h-10 w-10 items-center justify-center rounded-full bg-ink-900 text-sm font-semibold text-white">{i + 1}</span>
                    <Icon aria-hidden className="h-5 w-5 text-ink-400" />
                  </div>
                  <h3 className="mt-5 text-lg font-semibold">{title}</h3>
                  <p className="mt-2 text-ink-600">{body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-20 md:px-8">
          <div className="relative grid gap-8 overflow-hidden rounded-3xl bg-night p-8 text-white md:grid-cols-[1fr_auto] md:items-center md:p-12">
            <div aria-hidden className="absolute -right-10 -top-10 h-56 w-56 rounded-full bg-serving/20 blur-3xl" />
            <div className="relative">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-serving text-ink-950"><MessageCircleQuestion aria-hidden className="h-5 w-5" /></span>
              <h2 className="mt-5 text-2xl font-semibold md:text-3xl">Ask Wayzen</h2>
              <p className="mt-3 max-w-2xl text-ink-300">
                QueueFlow's assistant answers from our help articles and venue details, shows where each answer came from, and can line up a booking for you to confirm. It never books anything without your OK, and it doesn't give medical advice.
              </p>
              <p className="mt-4 flex items-center gap-2 text-sm text-ink-400"><ShieldCheck aria-hidden className="h-4 w-4" /> Only you can see your bookings and conversations.</p>
            </div>
            <Link to="/register" className="relative rounded-xl bg-serving px-5 py-3 text-center text-sm font-semibold text-ink-950">Create a free account</Link>
          </div>
        </section>
      </main>
      <footer className="border-t border-ink-100 px-4 py-8 text-center text-sm text-ink-500">
        QueueFlow. Venues marked Sample are demonstrations, not real businesses.
      </footer>
    </div>
  );
}
