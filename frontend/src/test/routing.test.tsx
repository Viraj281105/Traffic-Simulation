import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import nginxTemplate from "../../templates/default.conf.template?raw";
import {
  MAX_COMPARE_RUNS,
  RUN_ID_PATTERN,
  VIEW_ROUTES,
  comparePath,
  navigate,
  parseCompareRuns,
  resolveRoute,
  runPath,
  usePathname,
} from "../routing";

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

describe("saved-run routes", () => {
  it("maps /app/runs/:runId to the run page", () => {
    const id = "0f3c9a1e-1111-4222-8333-944445555666";
    expect(resolveRoute(`/app/runs/${id}`)).toEqual({ kind: "run", runId: id });
    expect(resolveRoute(`/app/runs/${id}/`)).toEqual({
      kind: "run",
      runId: id,
    });
    expect(resolveRoute("/app/runs/sweep_ab12cd34_sig_40")).toEqual({
      kind: "run",
      runId: "sweep_ab12cd34_sig_40",
    });
  });

  it.each([
    "/app/runs/bad.id",
    "/app/runs/a/b",
    `/app/runs/${"x".repeat(129)}`,
  ])("treats malformed run path %s as not found", (path) => {
    expect(resolveRoute(path)).toEqual({ kind: "notFound", path });
  });

  it("maps /app/compare and redirects bare /app/runs to History", () => {
    expect(resolveRoute("/app/compare")).toEqual({ kind: "compare" });
    expect(resolveRoute("/app/runs")).toEqual({
      kind: "redirect",
      to: VIEW_ROUTES.history,
    });
  });

  it("builds and parses comparison URLs", () => {
    expect(comparePath(["a", "b"])).toBe("/app/compare?runs=a,b");
    expect(runPath("abc")).toBe("/app/runs/abc");
    expect(parseCompareRuns("?runs=a,b,a,,bad id,c")).toEqual(["a", "b", "c"]);
    expect(parseCompareRuns("")).toEqual([]);
    const many = Array.from({ length: 10 }, (_, i) => `r${i.toString()}`);
    expect(parseCompareRuns(`?runs=${many.join(",")}`)).toHaveLength(
      MAX_COMPARE_RUNS,
    );
  });

  it("is served the dashboard by nginx", () => {
    const match =
      /location ~ "\^\/app\/\(runs\(\/(\S+)\)\?\|compare\)\/\?\$" \{/.exec(
        nginxTemplate,
      );
    expect(match).not.toBeNull();
    // Same id rule as the client router.
    expect(match?.[1]).toBe("[A-Za-z0-9_-]{1,128}");
    expect(RUN_ID_PATTERN.source).toBe("^[A-Za-z0-9_-]{1,128}$");
  });

  it("quotes every nginx location regex that contains braces", () => {
    // nginx ends a directive at an unquoted "{", so a regex quantifier such
    // as {1,128} must be quoted or the container fails to start.
    for (const line of nginxTemplate.split("\n")) {
      const loc = /^\s*location ~\*? (.+) \{\s*$/.exec(line);
      if (loc && loc[1].includes("{")) {
        expect(loc[1].startsWith('"')).toBe(true);
      }
    }
  });
});
