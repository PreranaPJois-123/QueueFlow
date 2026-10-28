/** Client-side checks mirroring the server's password policy (the server
 * remains authoritative and re-validates everything). */
export interface RegisterFields {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function passwordProblem(password: string, email = ""): string | null {
  if (password.length < 10) return "Use at least 10 characters";
  if (password.length > 128) return "Use at most 128 characters";
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return "Include at least one letter and one number";
  const name = email.split("@")[0].toLowerCase();
  if (name.length >= 4 && password.toLowerCase().includes(name)) return "Don't include your email name";
  return null;
}

export function validateRegister(f: RegisterFields): Partial<Record<keyof RegisterFields, string>> {
  const errors: Partial<Record<keyof RegisterFields, string>> = {};
  if (!f.fullName.trim()) errors.fullName = "Enter your name";
  if (!EMAIL_RE.test(f.email.trim())) errors.email = "Enter a valid email address";
  const pw = passwordProblem(f.password, f.email);
  if (pw) errors.password = pw;
  if (!f.confirmPassword) errors.confirmPassword = "Re-enter your password";
  else if (f.password !== f.confirmPassword) errors.confirmPassword = "Passwords don't match";
  return errors;
}
