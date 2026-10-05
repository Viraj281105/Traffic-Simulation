import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { usePathname } from "../../routing";
import { UrbanFlowLogo } from "./UrbanFlowLogo";

/**
 * The page-change loader: the UrbanFlow mark centred on the page for about a
 * second and a half whenever the route changes, and on first load. The flow
 * draws in and travels, the central roundabout breathes, the whole mark eases
 * gently in scale and opacity, and a thin line fills beneath.
 *
 * Nothing waits on it: the new page renders and starts underneath (a running
 * simulation keeps running), and the overlay only covers the swap. A route
 * change while it is still showing extends that same overlay instead of
 * mounting a second one, so one navigation never flashes it twice (the
 * dashboard's own /app → /app/comparative redirect lands inside it). Under
 * prefers-reduced-motion the mark stays still and the fade is instant.
 */

/** How long the overlay holds before fading; with the fade, ~1.6 s in all. */
export const ROUTE_LOADER_HOLD_MS = 1300;
export const ROUTE_LOADER_FADE_MS = 280;

type Phase = "shown" | "leaving" | "hidden";

export function RouteLoader({ routeKey }: { routeKey: string }) {
  // The first render is the initial load, so it starts shown.
  const [phase, setPhase] = useState<Phase>("shown");
  const [cycle, setCycle] = useState(0);
  const [lastKey, setLastKey] = useState(routeKey);

  // A new route shows the loader in the same commit as the new page, so the
  // swap itself is never seen.
  if (routeKey !== lastKey) {
    setLastKey(routeKey);
    setPhase("shown");
    setCycle((c) => c + 1);
  }

  useEffect(() => {
    if (phase === "hidden") return;
    const timer = setTimeout(
      () => {
        setPhase(phase === "shown" ? "leaving" : "hidden");
      },
      phase === "shown" ? ROUTE_LOADER_HOLD_MS : ROUTE_LOADER_FADE_MS,
    );
    return () => {
      clearTimeout(timer);
    };
  }, [phase, cycle]);

  if (phase === "hidden") return null;

  return (
    <div
      className={`uf-route-loader${phase === "leaving" ? " is-leaving" : ""}`}
      data-testid="route-loader"
      aria-hidden="true"
      style={
        {
          "--loader-hold": `${String(ROUTE_LOADER_HOLD_MS)}ms`,
          "--loader-fade": `${String(ROUTE_LOADER_FADE_MS)}ms`,
        } as CSSProperties
      }
    >
      <div className="uf-route-loader__inner">
        <span className="uf-loader">
          <UrbanFlowLogo size={112} animated />
        </span>
        <span className="uf-route-loader__progress" />
      </div>
    </div>
  );
}

/** The dashboard's loader: first load and every change of URL path (each
 *  view, saved run, comparison and the not-found page). */
export function AppRouteLoader() {
  return <RouteLoader routeKey={usePathname()} />;
}
