import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { BellRing, ReceiptText, Ticket } from "lucide-react";

const POINTS = [
  { icon: Ticket, text: "A queue token for every hospital and shop appointment" },
  { icon: BellRing, text: "An alert when your turn is about 20 minutes away" },
  { icon: ReceiptText, text: "Hotel totals with taxes calculated before you confirm" },
];

export function AuthLayout({ title, subtitle, children, footer }: {
  title: string; subtitle?: string; children: ReactNode; footer?: ReactNode;
}) {
  return (
    <div className="grid min-h-screen bg-paper lg:grid-cols-[1fr_1.1fr]">
      <aside className="relative hidden overflow-hidden bg-night p-12 text-white lg:flex lg:flex-col">
        <div aria-hidden className="absolute -bottom-24 -left-24 h-96 w-96 rounded-full bg-serving/15 blur-3xl" />
        <Link to="/" className="flex items-center gap-2.5">
          <span aria-hidden className="font-display flex h-9 w-9 items-center justify-center rounded-lg bg-serving font-bold text-ink-950">Q</span>
          <span className="font-display text-lg font-semibold">QueueFlow</span>
        </Link>
        <div className="relative mt-auto max-w-md">
          <p className="font-display text-4xl font-semibold leading-tight">Spend less of your day waiting in line.</p>
          <ul className="mt-8 space-y-4">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-ink-200">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/10"><Icon aria-hidden className="h-4 w-4 text-serving" /></span>
                <span className="pt-1.5">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
      <div className="flex flex-col px-4 py-10 sm:px-8">
        <Link to="/" className="mx-auto mb-10 flex items-center gap-2.5 lg:hidden">
          <span aria-hidden className="font-display flex h-9 w-9 items-center justify-center rounded-lg bg-ink-900 font-bold text-white">Q</span>
          <span className="font-display text-lg font-semibold text-ink-900">QueueFlow</span>
        </Link>
        <main className="m-auto w-full max-w-md">
          <h1 className="text-3xl font-semibold text-ink-900">{title}</h1>
          {subtitle && <p className="mt-2 text-ink-500">{subtitle}</p>}
          <div className="surface mt-8 rounded-2xl p-6 sm:p-8">{children}</div>
          {footer && <div className="mt-6 text-center text-sm text-ink-500">{footer}</div>}
        </main>
      </div>
    </div>
  );
}
