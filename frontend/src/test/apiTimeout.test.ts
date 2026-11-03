/**
 * @vitest-environment jsdom
 *
 * F-28: API calls are abandoned after DEFAULT_REQUEST_TIMEOUT_MS instead of
 * waiting forever on a stalled backend; the synchronous re-run of a saved
 * run is the one call without a client timeout.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "http://api.test" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import {
  ApiError,
  ApiTimeoutError,
  DEFAULT_REQUEST_TIMEOUT_MS,
  get,
  post,
  reproduceRun,
} from "../services/api";

/** A fetch that never answers, but rejects when its signal aborts. */
function hangingFetch() {
  return vi.fn(
    (_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      }),
  );
}

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("API request timeout", () => {
  it("abandons a request that gets no answer", async () => {
    vi.stubGlobal("fetch", hangingFetch());
    const pending = get("/api/v1/study/history").catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(DEFAULT_REQUEST_TIMEOUT_MS - 1);
    let settled = false;
    void pending.then(() => {
      settled = true;
    });
    await Promise.resolve();
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    const err = await pending;
    expect(err).toBeInstanceOf(ApiTimeoutError);
    expect((err as ApiTimeoutError).message).toMatch(/within 60 s/);
  });

  it("leaves answers and HTTP errors as they were", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response(JSON.stringify({ ok: 1 })))
        .mockResolvedValueOnce(new Response("", { status: 404 })),
    );
    await expect(get("/a")).resolves.toEqual({ ok: 1 });
    await expect(get("/b")).rejects.toBeInstanceOf(ApiError);
  });

  it("can be lifted for a call that computes before answering", async () => {
    const fetchMock = hangingFetch();
    vi.stubGlobal("fetch", fetchMock);
    let settled = false;
    void post("/slow", undefined, { timeoutMs: null }).finally(() => {
      settled = true;
    });
    void reproduceRun("run_1").finally(() => {
      settled = true;
    });
    await vi.advanceTimersByTimeAsync(DEFAULT_REQUEST_TIMEOUT_MS * 5);
    expect(settled).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
