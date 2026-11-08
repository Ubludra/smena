/**
 * Session state: token storage + authentication flow.
 *
 * Flow (mirrors the backend contract):
 *   boot → read saved token → validate via /auth/me → authed
 *        → no token → ask the platform adapter for a launch context:
 *            max          → POST /auth/max-launch (signed initData)
 *            browser-dev  → show the dev-login screen
 *            browser-locked → show "open Смена inside MAX" screen
 *
 * The token lives in localStorage: MAX webviews reload the page often, and
 * the threat model accepts token-in-storage here because the workspace is
 * single-user personal content behind a personal messenger session. If
 * stronger protection is ever required, move to httpOnly cookies — the
 * backend is already bearer-based, so only this file changes.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError, type ApiUser } from "../api/client";
import { detectPlatform } from "../../platform";

const TOKEN_KEY = "smena.token";

export type AuthStatus =
  | { state: "booting" }
  | { state: "anonymous"; launch: "dev-login" | "locked" }
  | { state: "max-error"; code: string | null }
  | { state: "authed"; user: ApiUser };

interface AuthContextValue {
  status: AuthStatus;
  token: string | null;
  loginDev: (displayName: string) => Promise<void>;
  logout: () => void;
  /** Called by the API layer on 401: forget the session, show login. */
  handleUnauthorized: () => void;
  retryBoot: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    // Private mode/quirky webviews: sessions work in memory instead.
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>({ state: "booting" });
  const [token, setToken] = useState<string | null>(loadToken);
  const [bootNonce, setBootNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function boot(): Promise<void> {
      const saved = loadToken();
      if (saved) {
        try {
          const user = await api.me(saved);
          if (!cancelled) {
            setToken(saved);
            setStatus({ state: "authed", user });
            return;
          }
        } catch (error) {
          if (error instanceof ApiError && error.isUnauthorized) {
            window.localStorage.removeItem(TOKEN_KEY);
            if (!cancelled) setToken(null);
            // Fall through to fresh authentication below.
          } else if (!cancelled) {
            // Network problem: don't log anyone out because Wi-Fi hiccuped.
            setStatus({ state: "max-error", code: "NETWORK" });
            return;
          }
        }
      }

      const platform = detectPlatform();
      const context = await platform.getLaunchContext();
      if (cancelled) return;

      if (context.kind === "max") {
        try {
          const session = await api.maxLaunch(context.initData);
          window.localStorage.setItem(TOKEN_KEY, session.access_token);
          setToken(session.access_token);
          setStatus({ state: "authed", user: session.user });
        } catch (error) {
          // Honest error screen: never silently fall back to a dev identity
          // inside MAX — that would fake a production path.
          setStatus({
            state: "max-error",
            code: error instanceof ApiError ? error.code : null,
          });
        }
      } else if (context.kind === "browser-dev") {
        setStatus({ state: "anonymous", launch: "dev-login" });
      } else {
        setStatus({ state: "anonymous", launch: "locked" });
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, [bootNonce]);

  const loginDev = useCallback(async (displayName: string) => {
    const session = await api.devLogin(displayName);
    window.localStorage.setItem(TOKEN_KEY, session.access_token);
    setToken(session.access_token);
    setStatus({ state: "authed", user: session.user });
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    // Re-run platform boot: inside MAX this re-verifies via max-launch
    // (fail closed); only an explicit dev build shows the dev-login screen.
    setStatus({ state: "booting" });
    setBootNonce((n) => n + 1);
  }, []);

  const handleUnauthorized = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    // Same rule on token expiry: the MAX runtime must never land on the
    // dev-login screen — it re-authenticates through the launch context.
    setStatus({ state: "booting" });
    setBootNonce((n) => n + 1);
  }, []);

  const retryBoot = useCallback(() => setBootNonce((n) => n + 1), []);

  const value = useMemo(
    () => ({ status, token, loginDev, logout, handleUnauthorized, retryBoot }),
    [status, token, loginDev, logout, handleUnauthorized, retryBoot],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

/** Token guaranteed non-null — only used under the authed app shell. */
export function useApiToken(): string {
  const { token } = useAuth();
  if (!token) throw new Error("no token in authed context");
  return token;
}
