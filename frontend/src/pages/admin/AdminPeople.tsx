import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { useToast } from "../../components/Toast";
import { DataTable, Metric, PageHeader, Panel } from "../../components/ui";
import { api, extractErrorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dateTime, humanStatus } from "../../lib/format";
import type { User, UserRole } from "../../types";

export function AdminUsers() {
  const { user: me } = useAuth();
  const { push } = useToast();
  const [q, setQ] = useState("");
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ user: User; role: UserRole } | null>(null);
  const load = useCallback(() => {
    api.get<User[]>("/api/admin/users", { params: { q: q || undefined } }).then((r) => setUsers(r.data)).catch((e) => setError(extractErrorMessage(e)));
  }, [q]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  async function apply() {
    if (!pending) return;
    try {
      await api.patch(`/api/admin/users/${pending.user.id}`, { role: pending.role });
      push(`${pending.user.full_name} is now ${humanStatus(pending.role)}`, "success");
      load();
    } catch (e) {
      push(extractErrorMessage(e), "error");
    } finally {
      setPending(null);
    }
  }

  return (
    <AppShell>
      <PageHeader title="People" description="Change roles here. Role changes sign the person out everywhere so new permissions apply immediately." />
      <label htmlFor="user-search" className="sr-only">Search people</label>
      <input id="user-search" type="search" className="field mb-4 max-w-md" placeholder="Search by name or email" value={q} onChange={(e) => setQ(e.target.value)} />
      {error && <ErrorState message={error} />}
      {!users && !error && <Skeleton className="h-48" />}
      {users && (
        <DataTable rows={users} rowKey={(u) => u.id} empty={<EmptyState title="No matching people" />}
          columns={[
            { header: "Name", cell: (u) => <><p className="font-medium text-ink-900">{u.full_name}</p><p className="text-xs text-ink-500">{u.email}</p></> },
            { header: "Joined", cell: (u) => dateTime(u.created_at) },
            { header: "Role", cell: (u) => (
              <select aria-label={`Role for ${u.full_name}`} className="field w-36" value={u.role} disabled={u.id === me?.id}
                onChange={(e) => setPending({ user: u, role: e.target.value as UserRole })}>
                {(["CUSTOMER", "STAFF", "ADMIN"] as UserRole[]).map((r) => <option key={r} value={r}>{humanStatus(r)}</option>)}
              </select>
            ) },
          ]} />
      )}
      <ConfirmDialog open={!!pending} title="Change role?" confirmLabel="Change role" danger={pending?.role === "ADMIN"}
        body={pending ? `${pending.user.full_name} will become ${humanStatus(pending.role)} and be signed out of all devices.` : ""}
        onConfirm={apply} onCancel={() => setPending(null)} />
    </AppShell>
  );
}

interface KnowledgeStatus {
  embedding_model: string; llm_configured: boolean; llm_provider: string | null; llm_model: string | null;
  documents: { id: string; source: string; title: string; category: string; access_level: string; version: number; chunks: number; indexed_at: string }[];
}

export function AdminKnowledge() {
  const { push } = useToast();
  const [status, setStatus] = useState<KnowledgeStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    api.get<KnowledgeStatus>("/api/admin/knowledge").then((r) => setStatus(r.data)).catch((e) => setError(extractErrorMessage(e)));
  }, []);
  useEffect(load, [load]);
  async function reindex() {
    setBusy(true);
    try {
      const { data } = await api.post("/api/admin/knowledge/reindex");
      push(`Index updated: ${data.added} added, ${data.updated} updated, ${data.removed} removed`, "success");
      load();
    } catch (e) {
      push(extractErrorMessage(e), "error");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AppShell>
      <PageHeader title="Wayzen knowledge" description="Documents Wayzen retrieves from. Help articles live in backend/knowledge; venue documents update when venues change."
        actions={<Button loading={busy} onClick={() => void reindex()}>Re-index now</Button>} />
      {error && <ErrorState message={error} />}
      {!status && !error && <Skeleton className="h-48" />}
      {status && (
        <>
          <div className="mb-6 grid gap-3 sm:grid-cols-3">
            <Metric label="Answer generation" value={status.llm_configured ? "On" : "Limited mode"} hint={status.llm_configured ? `${status.llm_provider}: ${status.llm_model}` : "Set LLM_PROVIDER, LLM_MODEL and LLM_API_KEY"} />
            <Metric label="Embedding model" value={<span className="text-base">{status.embedding_model}</span>} />
            <Metric label="Indexed documents" value={status.documents.length} hint={`${status.documents.reduce((n, d) => n + d.chunks, 0)} chunks`} />
          </div>
          <Panel>
            <DataTable rows={status.documents} rowKey={(d) => d.id} empty={<EmptyState title="Nothing indexed" body="Run python -m app.rag.ingest or press Re-index now." />}
              columns={[
                { header: "Document", cell: (d) => <><p className="font-medium text-ink-900">{d.title}</p><p className="text-xs text-ink-500">{d.source}</p></> },
                { header: "Category", cell: (d) => d.category },
                { header: "Access", cell: (d) => humanStatus(d.access_level) },
                { header: "Version", cell: (d) => `v${d.version}, ${d.chunks} chunks` },
                { header: "Indexed", cell: (d) => dateTime(d.indexed_at) },
              ]} />
          </Panel>
        </>
      )}
    </AppShell>
  );
}
