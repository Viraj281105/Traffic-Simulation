import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import nginxTemplate from "../../templates/default.conf.template?raw";
import { VIEW_ROUTES, navigate, resolveRoute, usePathname } from "../routing";

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("resolveRoute", () => {
  it.each(Object.entries(VIEW_ROUTES))("maps %s to %s", (view, path) => {
    expect(resolveRoute(path)).toEqual({ kind: "view", view });
    expect(resolveRoute(`${path}/`)).toEqual({ kind: "view", view });
  });

  it.each(["/app", "/app/", "/app.html"])(
    "redirects the dashboard entry %s to the default view",
    (path) => {
      expect(resolveRoute(path)).toEqual({
        kind: "redirect",
        to: VIEW_ROUTES.comparative,
      });
    },
  );

  it.each(["/nope", "/app/nope", "/app/signal/extra", "/index.html"])(
    "treats %s as not found",
    (path) => {
      expect(resolveRoute(path)).toEqual({ kind: "notFound", path });
    },
  );
});

describe("navigation", () => {
  it("updates the URL and subscribers, and follows back/forward", () => {
    window.history.replaceState(null, "", VIEW_ROUTES.comparative);
    const { result } = renderHook(() => usePathname());
    expect(result.current).toBe(VIEW_ROUTES.comparative);

    act(() => {
      navigate(VIEW_ROUTES.history);
    });
    expect(window.location.pathname).toBe(VIEW_ROUTES.history);
    expect(result.current).toBe(VIEW_ROUTES.history);

    act(() => {
      window.history.replaceState(null, "", VIEW_ROUTES.signal);
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current).toBe(VIEW_ROUTES.signal);
  });

  it("replaces instead of pushing when asked", () => {
    window.history.replaceState(null, "", "/app.html");
    const before = window.history.length;
    navigate(VIEW_ROUTES.comparative, { replace: true });
    expect(window.history.length).toBe(before);
    expect(window.location.pathname).toBe(VIEW_ROUTES.comparative);
  });
});

describe("nginx SPA fallback", () => {
  it("serves the dashboard for exactly the client-side view routes", () => {
    const match = /location ~ \^\/app\/\(([^)]*)\)/.exec(nginxTemplate);
    expect(match).not.toBeNull();
    const nginxViews = (match?.[1] ?? "").split("|").sort();
    const clientViews = Object.values(VIEW_ROUTES)
      .map((path) => path.replace("/app/", ""))
      .sort();
    expect(nginxViews).toEqual(clientViews);
  });

  it("answers unknown paths with a 404 rendered by the dashboard", () => {
    expect(nginxTemplate).toMatch(/error_page 404 \/app\.html;/);
    expect(nginxTemplate).not.toMatch(/try_files \$uri \$uri\/ \/index\.html;/);
  });
});
