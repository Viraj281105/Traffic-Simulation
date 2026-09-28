/**
 * The local development auth bypass (src/auth/cognito.ts).
 *
 * The dev server acts as a signed-in local developer until Cognito is
 * connected; a production build never does. The Vite environment is fixed
 * when the module loads, so each case stubs it and imports a fresh copy.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

type AuthModule = typeof import("../auth/cognito");

async function loadAuth(env: {
  DEV: boolean;
  bypass?: string;
}): Promise<AuthModule> {
  vi.stubEnv("DEV", env.DEV);
  vi.stubEnv("PROD", !env.DEV);
  vi.stubEnv("VITE_DEV_AUTH_BYPASS", env.bypass ?? "");
  vi.resetModules();
  return import("../auth/cognito");
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("devAuthBypassEnabled", () => {
  it("is on for a development build", () => {
    return loadAuth({ DEV: true }).then(({ devAuthBypassEnabled }) => {
      expect(devAuthBypassEnabled({ DEV: true })).toBe(true);
      expect(
        devAuthBypassEnabled({ DEV: true, VITE_DEV_AUTH_BYPASS: "true" }),
      ).toBe(true);
    });
  });

  it("is never on for a production build, whatever the variable says", () => {
    return loadAuth({ DEV: true }).then(({ devAuthBypassEnabled }) => {
      expect(devAuthBypassEnabled({ DEV: false })).toBe(false);
      expect(
        devAuthBypassEnabled({ DEV: false, VITE_DEV_AUTH_BYPASS: "true" }),
      ).toBe(false);
    });
  });

  it("can be switched off on the dev server to test real sign-in", () => {
    return loadAuth({ DEV: true }).then(({ devAuthBypassEnabled }) => {
      expect(
        devAuthBypassEnabled({ DEV: true, VITE_DEV_AUTH_BYPASS: "false" }),
      ).toBe(false);
    });
  });
});

describe("DEV mode", () => {
  it("bypasses authentication with the development token", async () => {
    const auth = await loadAuth({ DEV: true });
    expect(auth.DEV_AUTH_BYPASS).toBe(true);
    await expect(auth.getAuthToken()).resolves.toBe(auth.DEV_AUTH_TOKEN);
  });

  it("sends the development token on authenticated API calls", async () => {
    await loadAuth({ DEV: true });
    const { listReplays } = await import("../services/api");
    const { DEV_AUTH_TOKEN } = await import("../auth/cognito");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("[]", { status: 200 }));

    await listReplays();

    const init = fetchMock.mock.calls[0][1];
    expect(new Headers(init?.headers).get("Authorization")).toBe(
      `Bearer ${DEV_AUTH_TOKEN}`,
    );
  });

  it("uses Cognito again when the bypass is switched off", async () => {
    const auth = await loadAuth({ DEV: true, bypass: "false" });
    expect(auth.DEV_AUTH_BYPASS).toBe(false);
    await expect(auth.getAuthToken()).resolves.toBeNull();
  });
});

describe("production mode", () => {
  it("does not bypass authentication", async () => {
    const auth = await loadAuth({ DEV: false, bypass: "true" });
    expect(auth.DEV_AUTH_BYPASS).toBe(false);
    // No Cognito user signed in: no token at all, never the dev marker.
    await expect(auth.getAuthToken()).resolves.toBeNull();
  });

  it("keeps the Cognito token flow intact", async () => {
    const auth = await loadAuth({ DEV: false });
    const session = {
      getIdToken: () => ({ getJwtToken: () => "cognito-id-token" }),
    };
    vi.spyOn(auth.userPool, "getCurrentUser").mockReturnValue({
      getSession: (cb: (err: Error | null, s: typeof session) => void) => {
        cb(null, session);
      },
    } as unknown as ReturnType<typeof auth.userPool.getCurrentUser>);

    await expect(auth.getAuthToken()).resolves.toBe("cognito-id-token");
  });

  it("still reports a failed Cognito session as an error", async () => {
    const auth = await loadAuth({ DEV: false });
    vi.spyOn(auth.userPool, "getCurrentUser").mockReturnValue({
      getSession: (cb: (err: Error | null, s: null) => void) => {
        cb(new Error("expired"), null);
      },
    } as unknown as ReturnType<typeof auth.userPool.getCurrentUser>);

    await expect(auth.getAuthToken()).rejects.toThrow("expired");
  });
});
