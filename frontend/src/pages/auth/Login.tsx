import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../../components/Button";
import { ErrorState } from "../../components/States";
import { TextField } from "../../components/ui";
import { extractErrorMessage } from "../../lib/api";
import { homeFor, useAuth } from "../../lib/auth";
import { EMAIL_RE } from "../../lib/validation/auth";
import { AuthLayout } from "./AuthLayout";

export default function Login() {
  const { login, user, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string; search?: string } } | null)?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) return <Navigate to={from ? from.pathname + (from.search || "") : homeFor(user)} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!EMAIL_RE.test(email.trim())) next.email = "Enter a valid email address";
    if (!password) next.password = "Enter your password";
    setErrors(next);
    if (Object.keys(next).length) return;
    setSubmitting(true);
    setFailure(null);
    try {
      const signedIn = await login(email.trim(), password);
      navigate(from ? from.pathname + (from.search || "") : homeFor(signedIn), { replace: true });
    } catch (error) {
      setFailure(extractErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Sign in" subtitle="Manage your appointments, queue tokens and reservations."
      footer={<>New to QueueFlow? <Link to="/register" className="font-semibold text-ink-900 underline">Create an account</Link></>}>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {failure && <ErrorState message={failure} />}
        <TextField label="Email" type="email" autoComplete="email" value={email} error={errors.email}
          onChange={(e) => setEmail(e.target.value)} />
        <TextField label="Password" type="password" autoComplete="current-password" value={password}
          error={errors.password} onChange={(e) => setPassword(e.target.value)} />
        <div className="flex justify-end">
          <Link to="/forgot-password" className="text-sm font-medium text-ink-600 underline">Forgot password?</Link>
        </div>
        <Button type="submit" loading={submitting} className="w-full">Sign in</Button>
      </form>
    </AuthLayout>
  );
}
