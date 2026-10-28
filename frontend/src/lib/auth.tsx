import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import axios from "axios";
import { Navigate, useLocation } from "react-router-dom";
import { api, extractErrorMessage, setCsrfToken, setUnauthorizedHandler } from "./api";
import { Button } from "../components/Button";
import { ErrorState } from "../components/States";
import type { User, UserRole } from "../types";

interface RegisterInput {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<User>;
  register: (input: RegisterInput) => Promise<User>;
  logout: () => Promise<void>;
  logoutEverywhere: () => Promise<void>;
  updateProfile: (changes: Partial<Pick<User, "full_name" | "pref_sound_enabled" | "pref_browser_enabled">>) => Promise<void>;
  retry: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// oxlint-disable-next-line react/only-export-components -- shared helper for routing by role.
export function homeFor(user: User): string {
  if (user.role === "ADMIN") return "/admin/venues";
  if (user.role === "STAFF") return "/staff/venues";
  return "/dashboard";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSession = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<{ user: User; csrf_token: string }>("/api/auth/session");
      setCsrfToken(data.csrf_token);
      setUser(data.user);
      setError(null);
    } catch (failure) {
      if (axios.isAxiosError(failure) && failure.response?.status === 401) {
        setUser(null);
        setError(null);
      } else {
        setError(extractErrorMessage(failure));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setCsrfToken(null);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  async function login(email: string, password: string) {
    const { data } = await api.post<{ user: User; csrf_token: string }>("/api/auth/login", { email, password });
    setCsrfToken(data.csrf_token);
    setUser(data.user);
    return data.user;
  }

  async function register(input: RegisterInput) {
    const { data } = await api.post<{ user: User; csrf_token: string }>("/api/auth/register", {
      full_name: input.fullName,
      email: input.email,
      password: input.password,
      confirm_password: input.confirmPassword,
    });
    setCsrfToken(data.csrf_token);
    setUser(data.user);
    return data.user;
  }

  async function logout() {
    try {
      await api.post("/api/auth/logout");
    } finally {
      setCsrfToken(null);
      setUser(null);
    }
  }

  async function logoutEverywhere() {
    try {
      await api.post("/api/auth/logout-all");
    } finally {
      setCsrfToken(null);
      setUser(null);
    }
  }

  async function updateProfile(changes: Parameters<AuthContextValue["updateProfile"]>[0]) {
    const { data } = await api.patch<User>("/api/auth/me", changes);
    setUser(data);
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, error, login, register, logout, logoutEverywhere, updateProfile, retry: loadSession }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// oxlint-disable-next-line react/only-export-components -- Context provider and hook share one public API.
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function RequireAuth({ children, roles }: { children: ReactNode; roles?: UserRole[] }) {
  const { user, loading, error, retry } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-ink-400" role="status">
        Loading your account…
      </div>
    );
  }
  if (!user && error)
    return (
      <div className="mx-auto mt-20 max-w-md space-y-4 p-6">
        <ErrorState message={error} />
        <Button onClick={retry}>Try again</Button>
      </div>
    );
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user)} replace />;
  return <>{children}</>;
}
