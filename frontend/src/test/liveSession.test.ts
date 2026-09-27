import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

// Mock getAuthToken so the test doesn't depend on Cognito SDK
vi.mock("../auth/cognito", () => ({
  getAuthToken: vi.fn().mockResolvedValue("test-token"),
}));

async function freshModule() {
  return import("../services/liveSession");
}

describe("live session", () => {
  it("establishes the session with one request shared by every caller", async () => {
    let finish: () => void = () => undefined;
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          finish = () => {
            resolve(new Response("{}"));
          };
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { ensureLiveSession, whenLiveSessionReady } = await freshModule();

    const connect = vi.fn();
    whenLiveSessionReady(connect);
    const first = ensureLiveSession();
    const second = ensureLiveSession();

    // Nothing connects until the session cookie can exist.
    expect(connect).not.toHaveBeenCalled();

    finish();
    await Promise.all([first, second]);

    // fetch must have been called exactly once with the auth header
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/simulation/status");
    expect(
      (fetchMock.mock.calls[0][1] as RequestInit | undefined)?.headers,
    ).toMatchObject({ Authorization: "Bearer test-token" });

    expect(connect).toHaveBeenCalledTimes(1);

    // Once established, callers run immediately.
    const later = vi.fn();
    whenLiveSessionReady(later);
    expect(later).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not block callers when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const { ensureLiveSession } = await freshModule();

    await expect(ensureLiveSession()).resolves.toBeUndefined();
  });

  it("drops a callback cancelled while waiting", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
    const { ensureLiveSession, whenLiveSessionReady } = await freshModule();

    const connect = vi.fn();
    const cancel = whenLiveSessionReady(connect);
    cancel();
    await ensureLiveSession();

    expect(connect).not.toHaveBeenCalled();
  });
});
