/** Test helper: a fake fetch that answers from a table of fixtures, so the
 *  result screens are tested against the contract in src/CONTRACTS.md while
 *  the backends are still being built. */
import { vi } from "vitest";

export type Reply = unknown;

export function failWith(status: number, message: string): Reply {
  return { __status: status, body: { error: { message } } };
}

/** Routes are keyed "METHOD /path?query" (query exactly as sent). */
export function stubApi(routes: Record<string, Reply>) {
  const calls: { key: string; init?: RequestInit }[] = [];
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
    calls.push({ key, init });
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
    const body = failed ? (reply as { body?: unknown }).body : reply;
    return Promise.resolve(
      new Response(JSON.stringify(body ?? null), { status }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}
