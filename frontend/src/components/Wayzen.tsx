import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, extractErrorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { WayzenAction, WayzenMessage } from "../types";
import { Button } from "./Button";

interface Status {
  mode: "full" | "limited";
  welcome: string;
  suggested_questions: string[];
}

const SESSION_KEY = "wayzen_session";
const store = {
  get: () => { try { return sessionStorage.getItem(SESSION_KEY); } catch { return null; } },
  set: (v: string | null) => { try { if (v) sessionStorage.setItem(SESSION_KEY, v); else sessionStorage.removeItem(SESSION_KEY); } catch { /* storage unavailable */ } },
};

const SUMMARY_LABELS: Record<string, string> = {
  venue: "Place", service: "Service", provider: "With", when: "When", duration_minutes: "Duration (min)",
  price: "Price", room_type: "Room", check_in: "Check-in", check_out: "Check-out", guests: "Guests",
  rooms: "Rooms", nights: "Nights", free_cancellation_until: "Free cancellation until", reference: "Reference",
  stay: "Stay", charge: "Charge",
};

function ActionCard({ action, onChange }: { action: WayzenAction; onChange: (a: WayzenAction) => void }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState<"confirm" | "dismiss" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isCancel = action.type.startsWith("cancel");

  async function run(kind: "confirm" | "dismiss") {
    setBusy(kind);
    setError(null);
    try {
      const { data } = await api.post(`/api/wayzen/actions/${action.id}/${kind}`);
      onChange(kind === "confirm" ? { ...action, status: "executed", result: data.result } : data);
    } catch (e) {
      setError(extractErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  const reference = action.result?.reference;
  return (
    <div className="mt-2 rounded-xl border border-ink-200 bg-white p-3.5 text-sm">
      <p className="font-semibold text-ink-900">{String(action.summary.title || "Review and confirm")}</p>
      {action.summary.sample_listing && <p className="mt-1 text-xs text-ink-500">Sample listing: no real business receives this booking.</p>}
      <dl className="mt-2 space-y-1">
        {Object.entries(action.summary).filter(([k, v]) => SUMMARY_LABELS[k] && v !== null && v !== "").map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3">
            <dt className="text-ink-500">{SUMMARY_LABELS[k]}</dt>
            <dd className="text-right font-medium text-ink-800">{String(v)}</dd>
          </div>
        ))}
      </dl>
      {action.status === "pending" && (
        <div className="mt-3 flex gap-2">
          <Button size="sm" variant={isCancel ? "danger" : "primary"} loading={busy === "confirm"} disabled={!!busy}
            onClick={() => void run("confirm")}>{isCancel ? "Confirm cancellation" : "Confirm booking"}</Button>
          <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => void run("dismiss")}>Not now</Button>
        </div>
      )}
      {action.status === "executed" && (
        <p className="mt-3 font-medium text-signal-700">
          {isCancel ? "Cancelled." : "Confirmed."} {reference && (
            <button className="underline" onClick={() => navigate(reference.startsWith("QF-R") ? `/reservations/${reference}` : `/bookings/${reference}`)}>
              View {reference}
            </button>
          )}
        </p>
      )}
      {["dismissed", "expired", "failed"].includes(action.status) && (
        <p className="mt-3 text-ink-500">{action.status === "failed" ? `Not completed: ${action.result?.error ?? "unavailable"}` : action.status === "expired" ? "This summary expired. Ask again for current availability." : "Dismissed."}</p>
      )}
      {error && <p className="mt-2 text-rose-600">{error}</p>}
    </div>
  );
}

function renderText(text: string) {
  return text.split(/\n{2,}/).map((para, i) => (
    <p key={i} className="whitespace-pre-line">{para}</p>
  ));
}

export function Wayzen() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [messages, setMessages] = useState<WayzenMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(store.get);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open || status) return;
    api.get<Status>("/api/wayzen/status").then((r) => setStatus(r.data)).catch(() => setError("Wayzen is unavailable right now."));
  }, [open, status]);

  useEffect(() => {
    if (!open || !user || !sessionId || messages.length) return;
    api.get<{ messages: WayzenMessage[] }>(`/api/wayzen/sessions/${sessionId}`)
      .then((r) => setMessages(r.data.messages))
      .catch(() => { store.set(null); setSessionId(null); });
  }, [open, user, sessionId, messages.length]);

  useEffect(() => {
    if (!user) { setMessages([]); setSessionId(null); store.set(null); }
  }, [user]);

  useEffect(() => {
    log.current?.scrollTo?.({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (open) setTimeout(() => input.current?.focus(), 50);
  }, [open]);

  const send = useCallback(async (text: string) => {
    const message = text.trim();
    if (!message || sending) return;
    setDraft("");
    setError(null);
    setSending(true);
    const optimistic: WayzenMessage = { id: `local-${Date.now()}`, role: "user", content: message, mode: null,
      sources: [], actions: [], created_at: new Date().toISOString() };
    setMessages((m) => [...m, optimistic]);
    try {
      const { data } = await api.post<{ session_id: string; message: WayzenMessage }>("/api/wayzen/chat",
        { message, session_id: sessionId });
      setSessionId(data.session_id);
      store.set(data.session_id);
      setMessages((m) => [...m, data.message]);
    } catch (e) {
      setMessages((m) => m.filter((x) => x.id !== optimistic.id));
      setDraft(message);
      setError(extractErrorMessage(e));
    } finally {
      setSending(false);
    }
  }, [sending, sessionId]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(draft);
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(draft);
    }
  }

  function newConversation() {
    setMessages([]);
    setSessionId(null);
    store.set(null);
  }

  function updateAction(messageId: string, action: WayzenAction) {
    setMessages((all) => all.map((m) => (m.id === messageId
      ? { ...m, actions: m.actions.map((a) => (a.id === action.id ? action : a)) } : m)));
  }

  return (
    <>
      {!open && (
        <button onClick={() => setOpen(true)} aria-label="Open Wayzen assistant"
          className="fixed bottom-5 right-5 z-40 flex items-center gap-2.5 rounded-full bg-ink-900 py-3 pl-3 pr-5 text-sm font-semibold text-white shadow-lg transition-transform hover:-translate-y-0.5">
          <span aria-hidden className="font-display flex h-7 w-7 items-center justify-center rounded-full bg-serving text-sm font-bold text-ink-900">W</span>
          Ask Wayzen
        </button>
      )}
      {open && (
        <section role="dialog" aria-label="Wayzen assistant"
          className="fixed inset-x-0 bottom-0 z-50 flex h-[85vh] flex-col overflow-hidden rounded-t-2xl border border-ink-200 bg-paper shadow-2xl sm:inset-x-auto sm:bottom-5 sm:right-5 sm:h-[min(640px,calc(100vh-2.5rem))] sm:w-[400px] sm:rounded-2xl">
          <header className="flex items-center justify-between gap-3 border-b border-ink-100 bg-white px-4 py-3">
            <div className="flex items-center gap-2.5">
              <span aria-hidden className="font-display flex h-8 w-8 items-center justify-center rounded-full bg-serving font-bold text-ink-900">W</span>
              <div>
                <p className="font-display text-sm font-semibold text-ink-900">Wayzen</p>
                <p className="text-xs text-ink-500">AI assistant for QueueFlow</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {messages.length > 0 && <button onClick={newConversation} className="rounded-md px-2 py-1 text-xs font-medium text-ink-500 hover:bg-ink-50">New chat</button>}
              <button onClick={() => setOpen(false)} aria-label="Close Wayzen" className="rounded-md px-2 text-xl leading-none text-ink-400 hover:text-ink-700">×</button>
            </div>
          </header>
          {status?.mode === "limited" && (
            <p className="border-b border-amber-100 bg-amber-100/60 px-4 py-2 text-xs text-amber-600">
              Limited mode: AI answers are not configured on this server. Wayzen shows matching help articles instead.
            </p>
          )}
          <div ref={log} className="flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite" aria-busy={sending}>
            {!user ? (
              <div className="rounded-xl bg-white p-4 text-sm text-ink-600">
                <p>{status?.welcome ?? "Hi! I'm Wayzen, your QueueFlow assistant."}</p>
                <p className="mt-3">Sign in to ask questions and manage your bookings with Wayzen.</p>
                <div className="mt-3 flex gap-2"><Link to="/login" className="action-link">Sign in</Link></div>
              </div>
            ) : messages.length === 0 ? (
              <div className="space-y-3">
                <div className="rounded-xl bg-white p-4 text-sm text-ink-700">{status?.welcome ?? "Hi! I'm Wayzen."}</div>
                <p className="px-1 text-xs text-ink-500">Try asking</p>
                <div className="flex flex-wrap gap-2">
                  {(status?.suggested_questions ?? []).map((q) => (
                    <button key={q} onClick={() => void send(q)} className="rounded-full border border-ink-200 bg-white px-3 py-1.5 text-left text-xs font-medium text-ink-700 hover:border-ink-400">{q}</button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => (
                <div key={m.id} className={m.role === "user" ? "flex justify-end" : ""}>
                  <div className={m.role === "user"
                    ? "max-w-[85%] rounded-2xl rounded-br-sm bg-ink-900 px-3.5 py-2.5 text-sm text-white"
                    : "max-w-[95%] space-y-2 text-sm text-ink-800"}>
                    {m.role === "assistant" && m.mode === "error" && <p className="text-xs font-medium text-rose-600">Generation unavailable</p>}
                    <div className="space-y-2">{renderText(m.content)}</div>
                    {m.role === "assistant" && m.sources.length > 0 && (
                      <details className="rounded-lg bg-white px-3 py-2" open={m.mode !== "generated"}>
                        <summary className="cursor-pointer text-xs font-medium text-ink-500">Sources ({m.sources.length})</summary>
                        <ul className="mt-2 space-y-2">
                          {m.sources.map((s) => (
                            <li key={s.id + s.source} className="text-xs">
                              <p className="font-semibold text-ink-800">[{s.id}] {s.title}{s.section && s.section !== s.title ? `, ${s.section.split(" > ").pop()}` : ""}</p>
                              <p className="mt-0.5 text-ink-500">{s.excerpt}{s.excerpt.length >= 280 ? "…" : ""}</p>
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                    {m.actions.map((a) => <ActionCard key={a.id} action={a} onChange={(next) => updateAction(m.id, next)} />)}
                  </div>
                </div>
              ))
            )}
            {sending && (
              <div className="flex items-center gap-1.5 px-1" role="status" aria-label="Wayzen is typing">
                {[0, 1, 2].map((i) => <span key={i} className="h-2 w-2 animate-bounce rounded-full bg-ink-300" style={{ animationDelay: `${i * 120}ms` }} />)}
              </div>
            )}
          </div>
          {error && <p className="border-t border-rose-100 bg-rose-50 px-4 py-2 text-xs text-rose-600">{error}</p>}
          {user && (
            <form onSubmit={onSubmit} className="flex items-end gap-2 border-t border-ink-100 bg-white p-3">
              <label htmlFor="wayzen-input" className="sr-only">Message Wayzen</label>
              <textarea id="wayzen-input" ref={input} rows={1} value={draft} maxLength={2000}
                onChange={(e) => setDraft(e.target.value)} onKeyDown={onKey} placeholder="Ask about bookings, venues or policies"
                className="field max-h-32 min-h-[42px] flex-1 resize-none" />
              <Button type="submit" disabled={!draft.trim()} loading={sending}>Send</Button>
            </form>
          )}
          <p className="bg-white px-4 pb-2 text-[11px] text-ink-400">Wayzen can make mistakes and does not give medical advice. In an emergency call 112.</p>
        </section>
      )}
    </>
  );
}
