import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, extractErrorMessage } from "./api";
import axios from "axios";
import { Button } from "../components/Button";
import { ErrorState } from "../components/States";
import type { User, UserRole } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName: string,
  ) => Promise<void>;
  logout: () => void;
  updateProfile: (fullName: string) => Promise<void>;
  error: string | null;
  retry: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(
    () => !!localStorage.getItem("queueflow_token"),
  );
  const [error, setError] = useState<string | null>(null);

  async function fetchMe() {
    try {
      const { data } = await api.get<User>("/api/auth/me");
      setUser(data);
      setError(null);
    } catch (failure) {
      if (axios.isAxiosError(failure) && failure.response?.status === 401) {
        setUser(null);
        localStorage.removeItem("queueflow_token");
      } else {
        setError(extractErrorMessage(failure));
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const token = localStorage.getItem("queueflow_token");
    if (token) {
      void Promise.resolve().then(fetchMe);
    }
  }, []);

  async function login(email: string, password: string) {
    const { data } = await api.post("/api/auth/login", { email, password });
    localStorage.setItem("queueflow_token", data.access_token);
    try {
      const { data: me } = await api.get<User>("/api/auth/me");
      setUser(me);
    } catch (error) {
      localStorage.removeItem("queueflow_token");
      setUser(null);
      throw error;
    }
  }

  async function register(email: string, password: string, fullName: string) {
    await api.post("/api/auth/register", {
      email,
      password,
      full_name: fullName,
    });
    await login(email, password);
  }

  async function updateProfile(fullName: string) {
    const { data } = await api.patch<User>("/api/auth/me", {
      full_name: fullName,
    });
    setUser(data);
  }

  function logout() {
    localStorage.removeItem("queueflow_token");
    setUser(null);
    setError(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        updateProfile,
        error,
        retry: fetchMe,
      }}
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

export function RequireAuth({
  children,
  roles,
}: {
  children: ReactNode;
  roles?: UserRole[];
}) {
  const { user, loading, error, retry, logout } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-ink-400">
        Loading…
      </div>
    );
  }
  if (!user && error)
    return (
      <div className="mx-auto mt-20 max-w-md space-y-4 p-6">
        <ErrorState message={error} />
        <Button onClick={retry}>Retry connection</Button>
        <Button variant="secondary" onClick={logout}>
          Log out
        </Button>
      </div>
    );
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <Navigate
        to={user.role === "CUSTOMER" ? "/dashboard" : "/staff/dashboard"}
        replace
      />
    );
  }
  return <>{children}</>;
}
