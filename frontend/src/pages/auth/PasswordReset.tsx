import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "../../components/Button";
import { ErrorState } from "../../components/States";
import { TextField } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { api, extractErrorMessage } from "../../lib/api";
import { EMAIL_RE, passwordProblem } from "../../lib/validation/auth";
import { AuthLayout } from "./AuthLayout";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  const [emailEnabled, setEmailEnabled] = useState<boolean | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get("/api/auth/capabilities").then((r) => setEmailEnabled(r.data.password_reset_email)).catch(() => setEmailEnabled(null));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!EMAIL_RE.test(email.trim())) return setError("Enter a valid email address");
    setSubmitting(true);
    setError(null);
    try {
      const { data } = await api.post("/api/auth/password-reset/request", { email: email.trim() });
      setSent(data.detail);
    } catch (failure) {
      setError(extractErrorMessage(failure));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Reset your password" subtitle="We'll email you a link to choose a new password."
      footer={<Link to="/login" className="font-semibold text-ink-900 underline">Back to sign in</Link>}>
      {emailEnabled === false && (
        <p className="mb-4 rounded-xl bg-amber-100 px-4 py-3 text-sm text-amber-600">
          Email delivery is not configured on this QueueFlow installation, so reset links cannot be sent. Ask an administrator for help.
        </p>
      )}
      {sent ? (
        <p className="rounded-xl bg-signal-50 px-4 py-3 text-sm text-signal-700" role="status">{sent}</p>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <TextField label="Email" type="email" autoComplete="email" value={email} error={error ?? undefined}
            onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" loading={submitting} className="w-full">Send reset link</Button>
        </form>
      )}
    </AuthLayout>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const { push } = useToast();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({});
  const [failure, setFailure] = useState<string | null>(token ? null : "This reset link is incomplete. Request a new one.");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    const problem = passwordProblem(password);
    if (problem) next.password = problem;
    if (password !== confirm) next.confirm = "Passwords don't match";
    setErrors(next);
    if (Object.keys(next).length || !token) return;
    setSubmitting(true);
    try {
      await api.post("/api/auth/password-reset/confirm", { token, new_password: password, confirm_password: confirm });
      push("Password updated. Sign in with your new password.", "success");
      navigate("/login", { replace: true });
    } catch (error) {
      setFailure(extractErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Choose a new password" subtitle="This signs you out on every device."
      footer={<Link to="/forgot-password" className="font-semibold text-ink-900 underline">Request a new link</Link>}>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {failure && <ErrorState message={failure} />}
        <TextField label="New password" type="password" autoComplete="new-password" value={password}
          error={errors.password} hint="At least 10 characters, with a letter and a number." onChange={(e) => setPassword(e.target.value)} />
        <TextField label="Confirm new password" type="password" autoComplete="new-password" value={confirm}
          error={errors.confirm} onChange={(e) => setConfirm(e.target.value)} />
        <Button type="submit" loading={submitting} disabled={!token} className="w-full">Update password</Button>
      </form>
    </AuthLayout>
  );
}
