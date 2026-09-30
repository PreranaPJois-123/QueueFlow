import { useState } from "react";
import { useAuth } from "../lib/auth";
import { extractErrorMessage } from "../lib/api";
import { useToast } from "./Toast";
import { Card } from "./Product";
import { dateTime } from "../lib/format";
import { Button } from "./Button";
export function Account() {
  const { user, updateProfile, logout } = useAuth();
  const [name, setName] = useState(user?.full_name ?? "");
  const [pending, setPending] = useState(false);
  const { push } = useToast();
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      await updateProfile(name.trim());
      push("Profile updated", "success");
    } catch (e) {
      push(extractErrorMessage(e), "error");
    } finally {
      setPending(false);
    }
  }
  if (!user) return null;
  return (
    <Card title="Account information">
      <form onSubmit={save} className="space-y-4">
        <label className="label">
          Full name
          <input
            className="field mt-2"
            value={name}
            required
            maxLength={255}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          {[
            ["Email", user.email],
            ["Role", user.role],
            ["Member since", dateTime(user.created_at)],
            ["Account", user.is_active ? "Active" : "Inactive"],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-ink-500">{label}</dt>
              <dd className="mt-1 break-words font-medium">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-3">
          <Button
            type="submit"
            disabled={!name.trim() || name.trim() === user.full_name}
            loading={pending}
          >
            Save name
          </Button>
          <Button type="button" variant="secondary" onClick={logout}>
            Log out
          </Button>
        </div>
        <p className="text-xs text-ink-500">
          For email or account access changes, contact your administrator.
        </p>
      </form>
    </Card>
  );
}
