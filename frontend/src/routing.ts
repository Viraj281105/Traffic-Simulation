/**
 * Client-side routing for the dashboard (app.html).
 *
 * Each dashboard view has its own URL so a refresh, a bookmark, a shared link
 * and browser back/forward all land on the same view. The landing page is a
 * separate document (index.html at "/") and is not routed here.
 *
 * The route list is mirrored by the nginx SPA fallback
 * (templates/default.conf.template) and the Vite dev/preview fallback
 * (vite.config.ts); routing.test.ts keeps nginx in step with it.
 */
import { useSyncExternalStore } from "react";
import type { MouseEvent } from "react";

export const VIEW_ROUTES = {
  comparative: "/app/comparative",
  signal: "/app/signal",
  roundabout: "/app/roundabout",
  history: "/app/history",
  volume: "/app/volume",
  validation: "/app/validation",
} as const;

export type RoutedView = keyof typeof VIEW_ROUTES;

export const DEFAULT_VIEW: RoutedView = "comparative";

/** Where the dashboard lived before it had routes (and bare /app): these
 *  redirect to the default view rather than being "not found". */
const DASHBOARD_ENTRY_PATHS = new Set(["/app", "/app.html"]);

/** Saved-run pages. They live under the History section of the dashboard
 *  and, like the views above, are mirrored by the nginx and Vite fallbacks. */
export const RUNS_PREFIX = "/app/runs/";
export const COMPARE_ROUTE = "/app/compare";

/** Same rule as the backend's run-id validation (main.py _RUN_ID_PATTERN). */
export const RUN_ID_PATTERN = /^[A-Za-z0-9_-]{1,128}$/;

/** Most runs one comparison shows side by side. */
export const MAX_COMPARE_RUNS = 6;

export function runPath(runId: string): string {
  return RUNS_PREFIX + encodeURIComponent(runId);
}

export function comparePath(runIds: string[]): string {
  return `${COMPARE_ROUTE}?runs=${runIds.map(encodeURIComponent).join(",")}`;
}

/** The run ids a comparison URL names: well-formed, de-duplicated, in
 *  order, at most MAX_COMPARE_RUNS. */
export function parseCompareRuns(search: string): string[] {
  const raw = new URLSearchParams(search).get("runs") ?? "";
  const ids: string[] = [];
  for (const part of raw.split(",")) {
    const id = part.trim();
    if (RUN_ID_PATTERN.test(id) && !ids.includes(id)) ids.push(id);
  }
  return ids.slice(0, MAX_COMPARE_RUNS);
}

export type Route =
  | { kind: "view"; view: RoutedView }
  | { kind: "run"; runId: string }
  | { kind: "compare" }
  | { kind: "redirect"; to: string }
  | { kind: "notFound"; path: string };

function normalise(pathname: string): string {
  const trimmed = pathname.replace(/\/+$/, "");
  return trimmed === "" ? "/" : trimmed;
}

export function resolveRoute(pathname: string): Route {
  const path = normalise(pathname);
  if (DASHBOARD_ENTRY_PATHS.has(path)) {
    return { kind: "redirect", to: VIEW_ROUTES[DEFAULT_VIEW] };
  }
  for (const [view, route] of Object.entries(VIEW_ROUTES)) {
    if (route === path) return { kind: "view", view: view as RoutedView };
  }
  if (path === COMPARE_ROUTE) return { kind: "compare" };
  if (path === "/app/runs") {
    return { kind: "redirect", to: VIEW_ROUTES.history };
  }
  if (path.startsWith(RUNS_PREFIX)) {
    const runId = path.slice(RUNS_PREFIX.length);
    if (RUN_ID_PATTERN.test(runId)) return { kind: "run", runId };
  }
  return { kind: "notFound", path: pathname };
}

const NAVIGATE_EVENT = "app:navigate";

/** Push (or replace) a history entry and notify subscribers. */
export function navigate(to: string, options: { replace?: boolean } = {}) {
  const current = window.location.pathname + window.location.search;
  if (to === current) return;
  if (options.replace) {
    window.history.replaceState(null, "", to);
  } else {
    window.history.pushState(null, "", to);
  }
  window.dispatchEvent(new Event(NAVIGATE_EVENT));
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("popstate", onChange);
  window.addEventListener(NAVIGATE_EVENT, onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(NAVIGATE_EVENT, onChange);
  };
}

const getPathname = () => window.location.pathname;
const getSearch = () => window.location.search;

/** The current location's pathname, re-rendering on navigation. */
export function usePathname(): string {
  return useSyncExternalStore(subscribe, getPathname);
}

/** The current location's query string, re-rendering on navigation. */
export function useSearch(): string {
  return useSyncExternalStore(subscribe, getSearch);
}

/** Click handler for in-app links: navigates client-side for a plain left
 *  click and leaves modified clicks (new tab, etc.) to the browser. */
export function followLink(event: MouseEvent<HTMLAnchorElement>, to: string) {
  if (
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return;
  }
  event.preventDefault();
  navigate(to);
}
