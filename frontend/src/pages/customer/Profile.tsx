import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorState } from "../../components/States";
import { useToast } from "../../components/Toast";
import { PageHeader, Panel, TextField } from "../../components/ui";
import { api, extractErrorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { humanStatus } from "../../lib/format";
import { playChime } from "../../lib/realtime";
import { passwordProblem } from "../../lib/validation/auth";

function Toggle({ label, description, checked, onChange, disabled }: {
  label: string; description: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean;
}) {
  return (
    <label className="flex items-start justify-between gap-4 py-3">
      <span>
        <span className="block text-sm font-medium text-ink-900">{label}</span>
        <span className="block text-sm text-ink-500">{description}</span>
      </span>
      <input type="checkbox" role="switch" className="mt-1 h-5 w-5 accent-ink-900" checked={checked} disabled={disabled}
        onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}

export default function Profile() {
  const { user, updateProfile, logoutEverywhere } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();
  const [name, setName] = useState(user?.full_name ?? "");
  const [savingName, setSavingName] = useState(false);
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [pwErrors, setPwErrors] = useState<{ current?: string; next?: string; confirm?: string }>({});
  const [pwFailure, setPwFailure] = useState<string | null>(null);
  const [savingPw, setSavingPw] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const permission = typeof Notification === "undefined" ? "unsupported" : Notification.permission;
  const [browserPermission, setBrowserPermission] = useState<string>(permission);
  if (!user) return null;

  async function saveName(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return push("Enter your name", "error");
    setSavingName(true);
    try {
      await updateProfile({ full_name: name.trim() });
      push("Name saved", "success");
    } catch (error) {
      push(extractErrorMessage(error), "error");
    } finally {
      setSavingName(false);
    }
  }

  async function setPref(key: "pref_sound_enabled" | "pref_browser_enabled", value: boolean) {
    if (key === "pref_browser_enabled" && value && browserPermission !== "granted") {
      if (browserPermission === "unsupported") return push("This browser doesn't support notifications", "error");
      const result = await Notification.requestPermission();
      setBrowserPermission(result);
      if (result !== "granted") return push("Browser notifications are blocked. Allow them in your browser's site settings.", "error");
    }
    try {
      await updateProfile({ [key]: value });
      if (key === "pref_sound_enabled" && value && !(await playChime())) {
        push("Sound is on, but your browser blocked playback. Click anywhere on the page and try the test sound.", "info");
      }
    } catch (error) {
      push(extractErrorMessage(error), "error");
    }
  }

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    const errors: typeof pwErrors = {};
    if (!pw.current) errors.current = "Enter your current password";
    const problem = passwordProblem(pw.next, user!.email);
    if (problem) errors.next = problem;
    if (pw.next !== pw.confirm) errors.confirm = "Passwords don't match";
    setPwErrors(errors);
    if (Object.keys(errors).length) return;
    setSavingPw(true);
    setPwFailure(null);
    try {
      await api.post("/api/auth/password", { current_password: pw.current, new_password: pw.next, confirm_password: pw.confirm });
      setPw({ current: "", next: "", confirm: "" });
      push("Password changed. Other devices were signed out.", "success");
    } catch (error) {
      setPwFailure(extractErrorMessage(error));
    } finally {
      setSavingPw(false);
    }
  }

  return (
    <AppShell>
      <PageHeader title="Profile and security" description={`${user.email}, ${humanStatus(user.role)} account`} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Your details">
          <form onSubmit={saveName} className="space-y-4">
            <TextField label="Full name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
            <Button type="submit" loading={savingName} disabled={name.trim() === user.full_name}>Save name</Button>
          </form>
        </Panel>
        <Panel title="Notifications">
          <div id="notifications" className="divide-y divide-ink-100">
            <Toggle label="Play a sound" description="Chime for turn alerts, your turn and delays. Browsers may require you to interact with the page first."
              checked={user.pref_sound_enabled} onChange={(v) => void setPref("pref_sound_enabled", v)} />
            <Toggle label="Browser notifications" description={browserPermission === "denied" ? "Blocked in this browser's site settings." : "Show alerts when QueueFlow is in a background tab."}
              checked={user.pref_browser_enabled && browserPermission === "granted"} disabled={browserPermission === "denied"}
              onChange={(v) => void setPref("pref_browser_enabled", v)} />
          </div>
          <Button variant="ghost" size="sm" className="mt-2" onClick={() => void playChime()}>Play test sound</Button>
          <p className="mt-2 text-xs text-ink-400">In-app notifications are always shown. Email and SMS alerts are not available.</p>
        </Panel>
        <Panel title="Change password">
          <form onSubmit={changePassword} noValidate className="space-y-4">
            {pwFailure && <ErrorState message={pwFailure} />}
            <TextField label="Current password" type="password" autoComplete="current-password" value={pw.current}
              error={pwErrors.current} onChange={(e) => setPw((p) => ({ ...p, current: e.target.value }))} />
            <TextField label="New password" type="password" autoComplete="new-password" value={pw.next}
              error={pwErrors.next} hint="At least 10 characters, with a letter and a number."
              onChange={(e) => setPw((p) => ({ ...p, next: e.target.value }))} />
            <TextField label="Confirm new password" type="password" autoComplete="new-password" value={pw.confirm}
              error={pwErrors.confirm} onChange={(e) => setPw((p) => ({ ...p, confirm: e.target.value }))} />
            <Button type="submit" loading={savingPw}>Change password</Button>
          </form>
        </Panel>
        <Panel title="Sessions">
          <p className="text-sm text-ink-600">Signed in on a shared or lost device? Sign out everywhere, including this browser.</p>
          <Button variant="danger" className="mt-4" onClick={() => setLogoutOpen(true)}>Log out of all devices</Button>
        </Panel>
      </div>
      <ConfirmDialog open={logoutOpen} danger title="Log out of all devices?" confirmLabel="Log out everywhere"
        body="Every active session, including this one, will end immediately."
        onConfirm={async () => { await logoutEverywhere(); navigate("/login"); }} onCancel={() => setLogoutOpen(false)} />
    </AppShell>
  );
}
