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

export type Route =
  | { kind: "view"; view: RoutedView }
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

/** The current location's pathname, re-rendering on navigation. */
export function usePathname(): string {
  return useSyncExternalStore(subscribe, getPathname);
}
