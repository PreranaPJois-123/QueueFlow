import { useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import {
  BarChart3, BedDouble, Bell, BookOpenText, CalendarCheck, ClipboardList, Building2, LayoutDashboard, ListOrdered,
  LogOut, Menu, Scissors, ShieldCheck, Stethoscope, Ticket, Users, UserRound, X, type LucideIcon,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { useRealtime } from "../lib/realtime";
import { NotificationBell } from "./NotificationBell";
import { Wayzen } from "./Wayzen";
import type { UserRole } from "../types";

interface NavItem { to: string; label: string; icon: LucideIcon }
interface NavGroup { label?: string; items: NavItem[] }

const explore: NavGroup = {
  label: "Find a place",
  items: [
    { to: "/hospitals", label: "Hospitals", icon: Stethoscope },
    { to: "/shops", label: "Shops", icon: Scissors },
    { to: "/hotels", label: "Hotels", icon: BedDouble },
  ],
};

function navFor(role: UserRole | null): NavGroup[] {
  if (role === null) return [explore];
  const groups: NavGroup[] = [
    { items: [
      { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
      { to: "/bookings", label: "My bookings", icon: CalendarCheck },
      { to: "/notifications", label: "Notifications", icon: Bell },
    ] },
    explore,
    { label: "Walk-in queues", items: [
      { to: "/services", label: "Join a queue", icon: ListOrdered },
      { to: "/my-ticket", label: "My ticket", icon: Ticket },
    ] },
  ];
  if (role === "STAFF" || role === "ADMIN") {
    groups.push({ label: "Staff", items: [
      { to: "/staff/venues", label: "Venue queues", icon: ClipboardList },
      { to: "/staff/queues", label: "Walk-in queues", icon: ListOrdered },
      { to: "/staff/analytics", label: "Analytics", icon: BarChart3 },
    ] });
  }
  if (role === "ADMIN") {
    groups.push({ label: "Administration", items: [
      { to: "/admin/venues", label: "Venues", icon: Building2 },
      { to: "/admin/users", label: "People", icon: Users },
      { to: "/admin/knowledge", label: "Wayzen knowledge", icon: BookOpenText },
    ] });
  }
  groups.push({ items: [{ to: "/profile", label: "Profile & security", icon: ShieldCheck }] });
  return groups;
}

function NavLinks({ groups, onNavigate, unread }: { groups: NavGroup[]; onNavigate?: () => void; unread: number }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-6">
      {groups.map((group, i) => (
        <div key={group.label || i}>
          {group.label && <p className="mb-2 px-3 text-[11px] font-medium text-ink-400">{group.label}</p>}
          <div className="flex flex-col gap-0.5">
            {group.items.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} onClick={onNavigate}
                className={({ isActive }) => `group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive
                  ? "bg-white/10 text-white" : "text-ink-300 hover:bg-white/5 hover:text-white"}`}>
                {({ isActive }) => (
                  <>
                    <Icon aria-hidden className={`h-4 w-4 shrink-0 ${isActive ? "text-serving" : "text-ink-400 group-hover:text-ink-200"}`} strokeWidth={2} />
                    <span className="flex-1">{label}</span>
                    {to === "/notifications" && unread > 0 && (
                      <span className="rounded-full bg-rose-500 px-1.5 text-[11px] font-semibold text-white">{unread}</span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

function Brand({ dark = true }: { dark?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5 px-3">
      <span aria-hidden className="font-display flex h-8 w-8 items-center justify-center rounded-lg bg-serving text-sm font-bold text-ink-950">Q</span>
      <span className={`font-display text-base font-semibold ${dark ? "text-white" : "text-ink-900"}`}>QueueFlow</span>
    </Link>
  );
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("");
}

export function AppShell({ children }: { children: ReactNode; variant?: "customer" | "staff" }) {
  const { user, logout } = useAuth();
  const { unread } = useRealtime();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const groups = navFor(user?.role ?? null);

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  const account = user ? (
    <div className="rounded-xl bg-white/5 p-3">
      <div className="flex items-center gap-3">
        <span aria-hidden className="font-display flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-night-3 text-sm font-semibold text-white">
          {initials(user.full_name) || <UserRound className="h-4 w-4" />}
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-white">{user.full_name}</p>
          <p className="truncate text-xs text-ink-400">{user.email}</p>
        </div>
      </div>
      <button onClick={handleLogout} className="mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-ink-300 hover:bg-white/5 hover:text-white">
        <LogOut aria-hidden className="h-4 w-4" /> Log out
      </button>
    </div>
  ) : (
    <div className="flex flex-col gap-2">
      <Link to="/login" className="rounded-lg bg-serving px-3 py-2 text-center text-sm font-semibold text-ink-950">Sign in</Link>
      <Link to="/register" className="rounded-lg px-3 py-2 text-center text-sm font-medium text-ink-300 hover:bg-white/5 hover:text-white">Create account</Link>
    </div>
  );

  const sidebar = (onNavigate?: () => void) => (
    <>
      <div className="flex-1 overflow-y-auto"><NavLinks groups={groups} onNavigate={onNavigate} unread={unread} /></div>
      {account}
    </>
  );

  return (
    <div className="flex min-h-screen bg-paper">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-white focus:p-4">Skip to content</a>
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col gap-8 bg-night px-3 py-6 lg:flex">
        <Brand />
        {sidebar()}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-ink-100 bg-paper/90 px-4 py-3 backdrop-blur lg:justify-end lg:px-8">
          <div className="flex items-center gap-2 lg:hidden">
            <button onClick={() => setMenuOpen(true)} aria-label="Open menu" aria-expanded={menuOpen}
              className="rounded-lg border border-ink-200 bg-white p-2 text-ink-700"><Menu className="h-4 w-4" /></button>
            <Brand dark={false} />
          </div>
          {user ? <NotificationBell /> : <Link to="/login" className="rounded-lg bg-ink-900 px-3 py-1.5 text-sm font-medium text-white">Sign in</Link>}
        </header>
        {menuOpen && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
            <div className="absolute inset-0 bg-ink-950/50" onClick={() => setMenuOpen(false)} />
            <div className="absolute inset-y-0 left-0 flex w-72 flex-col gap-8 bg-night px-3 py-5">
              <div className="flex items-center justify-between"><Brand />
                <button onClick={() => setMenuOpen(false)} aria-label="Close menu" className="px-3 text-ink-300"><X className="h-5 w-5" /></button>
              </div>
              {sidebar(() => setMenuOpen(false))}
            </div>
          </div>
        )}
        <main id="main" className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-10">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
      <Wayzen />
    </div>
  );
}
