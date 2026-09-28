/**
 * The page-change loader: ~1 s of the coded UrbanFlow mark on first load and
 * on every route change, never two at once, and never restarted as a second
 * flash when a redirect lands while it is showing.
 */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ROUTE_LOADER_FADE_MS,
  ROUTE_LOADER_HOLD_MS,
  RouteLoader,
} from "../components/ui/RouteLoader";

const TOTAL = ROUTE_LOADER_HOLD_MS + ROUTE_LOADER_FADE_MS;

const loaders = () => document.querySelectorAll(".uf-route-loader");
const advance = (ms: number) => {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
};
/** Hold, then fade: the fade timer starts only once the hold has ended. */
const runToEnd = () => {
  advance(ROUTE_LOADER_HOLD_MS);
  advance(ROUTE_LOADER_FADE_MS);
};

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("RouteLoader", () => {
  it("shows the coded logo, centred, for about a second on first load", () => {
    render(<RouteLoader routeKey="/app/comparative" />);

    const loader = screen.getByTestId("route-loader");
    expect(
      loader.querySelector("svg.uf-logo.uf-logo--animated"),
    ).not.toBeNull();
    expect(loader.querySelector("img")).toBeNull();
    expect(loader).toHaveAttribute("aria-hidden", "true");
    expect(TOTAL).toBeGreaterThanOrEqual(900);
    expect(TOTAL).toBeLessThanOrEqual(1100);

    advance(ROUTE_LOADER_HOLD_MS);
    expect(loader).toHaveClass("is-leaving");
    advance(ROUTE_LOADER_FADE_MS);
    expect(loaders()).toHaveLength(0);
  });

  it("shows again on every route change", () => {
    const { rerender } = render(<RouteLoader routeKey="/app/comparative" />);
    runToEnd();
    expect(loaders()).toHaveLength(0);

    rerender(<RouteLoader routeKey="/app/history" />);
    expect(loaders()).toHaveLength(1);
    runToEnd();
    expect(loaders()).toHaveLength(0);

    rerender(<RouteLoader routeKey="/app/validation" />);
    expect(loaders()).toHaveLength(1);
  });

  it("extends the same overlay when the route changes while it shows", () => {
    const { rerender } = render(<RouteLoader routeKey="/app" />);
    const first = screen.getByTestId("route-loader");
    advance(ROUTE_LOADER_HOLD_MS - 100);

    // e.g. the /app → /app/comparative redirect.
    rerender(<RouteLoader routeKey="/app/comparative" />);
    expect(loaders()).toHaveLength(1);
    expect(screen.getByTestId("route-loader")).toBe(first);

    advance(ROUTE_LOADER_HOLD_MS - 1);
    expect(first).not.toHaveClass("is-leaving");
    advance(1);
    expect(first).toHaveClass("is-leaving");
    advance(ROUTE_LOADER_FADE_MS);
    expect(loaders()).toHaveLength(0);
  });

  it("comes back from its fade instead of mounting a second loader", () => {
    const { rerender } = render(<RouteLoader routeKey="/app/signal" />);
    const first = screen.getByTestId("route-loader");
    advance(ROUTE_LOADER_HOLD_MS + 50);
    expect(first).toHaveClass("is-leaving");

    rerender(<RouteLoader routeKey="/app/roundabout" />);
    expect(loaders()).toHaveLength(1);
    expect(screen.getByTestId("route-loader")).toBe(first);
    expect(first).not.toHaveClass("is-leaving");
  });

  it("does not re-show when the same route re-renders", () => {
    const { rerender } = render(<RouteLoader routeKey="/app/research" />);
    runToEnd();
    rerender(<RouteLoader routeKey="/app/research" />);
    expect(loaders()).toHaveLength(0);
  });
});
