/**
 * Client-side home of the Safe unlock token.
 *
 * The token is the short-lived (minutes) JWT issued by POST /safe/unlock
 * after the phone check. It lives in sessionStorage on purpose: closing the
 * tab/webview drops it, which is exactly the «Заблокировать» semantics —
 * forget the token. Server-side the token is stateless and expires alone.
 *
 * When sessionStorage is unavailable (private mode, quirky webviews) an
 * in-memory copy keeps the unlock alive for the page's lifetime only.
 */

const TOKEN_KEY = "smena.safe.token";
const EXPIRES_KEY = "smena.safe.expires";

/** Fallback used only when storage throws; cleared with the page. */
let memory: { token: string; expiresAt: number } | null = null;

/** Current valid token, or null when missing/expired (expired is purged). */
export function getSafeToken(): string | null {
  try {
    const token = window.sessionStorage.getItem(TOKEN_KEY);
    const expires = Number(window.sessionStorage.getItem(EXPIRES_KEY) ?? "0");
    if (!token || Date.now() >= expires) {
      if (token) clearSafeToken();
      memory = null;
      return null;
    }
    return token;
  } catch {
    if (memory && Date.now() < memory.expiresAt) return memory.token;
    memory = null;
    return null;
  }
}

export function setSafeToken(token: string, expiresInSeconds: number): void {
  // Expire ~30 s early so the UI never sends a token the server would
  // reject on the boundary (webview clocks are not our concern then).
  const expiresAt = Date.now() + Math.max(expiresInSeconds - 30, 10) * 1000;
  memory = { token, expiresAt };
  try {
    window.sessionStorage.setItem(TOKEN_KEY, token);
    window.sessionStorage.setItem(EXPIRES_KEY, String(expiresAt));
  } catch {
    // In-memory fallback already holds it.
  }
}

export function clearSafeToken(): void {
  memory = null;
  try {
    window.sessionStorage.removeItem(TOKEN_KEY);
    window.sessionStorage.removeItem(EXPIRES_KEY);
  } catch {
    // Nothing to clear: the memory copy is already gone.
  }
}
