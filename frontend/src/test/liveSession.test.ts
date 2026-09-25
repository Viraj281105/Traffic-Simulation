import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

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

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]).toEqual(["/api/simulation/status"]);
    // Nothing connects until the session cookie can exist.
    expect(connect).not.toHaveBeenCalled();

    finish();
    await Promise.all([first, second]);
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
