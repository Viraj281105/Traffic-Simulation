/**
 * The backend keeps each browser's live and comparison simulations in a
 * session named by a cookie that the first /api/simulation response sets
 * (backend/src/main.py, live-session middleware). Requests sent before that
 * cookie exists each start a separate session, and a WebSocket opened
 * without it is bound to the backend's shared "default" session. On a first
 * visit the dashboard used to do both at once — config sync, status checks
 * and the stream all on mount — so the stream could show a different
 * simulation from the one the user had just configured and started.
 *
 * Every live request and stream therefore waits for one side-effect-free
 * request (GET /api/simulation/status) that establishes the session first.
 *
 * IMPORTANT: the session-establishment request MUST include the auth token
 * so the backend assigns the cookie to the authenticated session (keyed by
 * Cognito sub). Without it the backend creates an anonymous UUID session;
 * the WebSocket then reads that anonymous session while all REST calls land
 * in the authenticated one, so the stream never sees the simulation.
 */
import { API_BASE_URL } from "../config";
import { getAuthToken } from "../auth/cognito";

let ready = false;
let pending: Promise<void> | null = null;

export function ensureLiveSession(): Promise<void> {
  if (ready) return Promise.resolve();
  pending ??= getAuthToken()
    .catch(() => null)
    .then((token) => {
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      return fetch(`${API_BASE_URL}/api/simulation/status`, { headers });
    })
    // An unreachable backend fails the requests that follow, where the
    // error is reported; it must not block them here.
    .then(
      () => undefined,
      () => undefined,
    )
    .finally(() => {
      ready = true;
    });
  return pending;
}

/** Runs `callback` once the session exists — immediately if it already
 *  does. Returns a function that cancels a callback still waiting. */
export function whenLiveSessionReady(callback: () => void): () => void {
  if (ready) {
    callback();
    return () => undefined;
  }
  let cancelled = false;
  void ensureLiveSession().then(() => {
    if (!cancelled) callback();
  });
  return () => {
    cancelled = true;
  };
}
