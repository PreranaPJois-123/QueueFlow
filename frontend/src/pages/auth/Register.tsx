import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Button } from "../../components/Button";
import { ErrorState } from "../../components/States";
import { TextField } from "../../components/ui";
import { extractErrorMessage, fieldErrors } from "../../lib/api";
import { homeFor, useAuth } from "../../lib/auth";
import { validateRegister, type RegisterFields } from "../../lib/validation/auth";
import { AuthLayout } from "./AuthLayout";

const SERVER_FIELDS: Record<string, keyof RegisterFields> = {
  full_name: "fullName", email: "email", password: "password", confirm_password: "confirmPassword",
};

export default function Register() {
  const { register, user, loading } = useAuth();
  const navigate = useNavigate();
  const [fields, setFields] = useState<RegisterFields>({ fullName: "", email: "", password: "", confirmPassword: "" });
  const [errors, setErrors] = useState<Partial<Record<keyof RegisterFields, string>>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) return <Navigate to={homeFor(user)} replace />;

  const set = (key: keyof RegisterFields) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setFields((f) => ({ ...f, [key]: e.target.value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const found = validateRegister(fields);
    setErrors(found);
    if (Object.keys(found).length) return;
    setSubmitting(true);
    setFailure(null);
    try {
      const created = await register({ ...fields, fullName: fields.fullName.trim(), email: fields.email.trim() });
      navigate(homeFor(created), { replace: true });
    } catch (error) {
      const server = fieldErrors(error);
      const mapped: typeof errors = {};
      for (const [k, v] of Object.entries(server)) if (SERVER_FIELDS[k]) mapped[SERVER_FIELDS[k]] = v;
      setErrors(mapped);
      if (!Object.keys(mapped).length) setFailure(extractErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Create your account" subtitle="Book appointments, track your queue token and reserve rooms."
      footer={<>Already have an account? <Link to="/login" className="font-semibold text-ink-900 underline">Sign in</Link></>}>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {failure && <ErrorState message={failure} />}
        <TextField label="Full name" autoComplete="name" value={fields.fullName} onChange={set("fullName")} error={errors.fullName} />
        <TextField label="Email" type="email" autoComplete="email" value={fields.email} onChange={set("email")} error={errors.email} />
        <TextField label="Password" type="password" autoComplete="new-password" value={fields.password}
          onChange={set("password")} error={errors.password} hint="At least 10 characters, with a letter and a number." />
        <TextField label="Confirm password" type="password" autoComplete="new-password" value={fields.confirmPassword}
          onChange={set("confirmPassword")} error={errors.confirmPassword} />
        <Button type="submit" loading={submitting} className="w-full">Create account</Button>
      </form>
    </AuthLayout>
  );
}
