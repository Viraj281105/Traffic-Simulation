/** Test helper for the /app/network screens: a fake fetch that answers from a
 *  table of contract fixtures and records each call's key and JSON body.
 *  Routes are keyed "METHOD /path?query" (query exactly as sent). */
import { vi } from "vitest";

export function failWith(status: number, message: string): unknown {
  return { __status: status, body: { error: { message } } };
}

export interface RecordedCall {
  key: string;
  body: unknown;
}

export function stubNet(routes: Record<string, unknown>) {
  const calls: RecordedCall[] = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url,
      "http://api.test",
    );
    const key = `${init?.method ?? "GET"} ${url.pathname}${url.search}`;
    let body: unknown = undefined;
    if (typeof init?.body === "string") {
      try {
        body = JSON.parse(init.body);
      } catch {
        body = init.body;
      }
    }
    calls.push({ key, body });
    const reply = routes[key];
    if (reply === undefined) {
      return Promise.resolve(
        new Response(JSON.stringify({ error: { message: "Not found" } }), {
          status: 404,
        }),
      );
    }
    const failed =
      typeof reply === "object" && reply !== null && "__status" in reply;
    const status = failed ? (reply as { __status: number }).__status : 200;
    const payload = failed ? (reply as { body?: unknown }).body : reply;
    return Promise.resolve(
      new Response(JSON.stringify(payload ?? null), { status }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}
