/**
 * @vitest-environment jsdom
 *
 * The landing page's "Login" lands on the dashboard with its Cognito sign-in
 * dialog open (F-18); a visitor already signed in is not asked again.
 */
import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SIGN_IN_HREF, SIGN_IN_PARAM } from "../routing";

const cognito = vi.hoisted((): { user: unknown } => ({ user: null }));
vi.mock("../auth/cognito", () => ({
  DEV_AUTH_BYPASS: false,
  DEV_AUTH_PROFILE: { name: "dev", email: "" },
  getCurrentUser: () => cognito.user,
}));

import { useAuthSession } from "../hooks/useAuthSession";

afterEach(() => {
  window.history.replaceState(null, "", "/");
  cognito.user = null;
});

describe("sign-in link", () => {
  it("points at the dashboard with the sign-in flag", () => {
    const url = new URL(SIGN_IN_HREF, "https://example.test");
    expect(url.pathname).toBe("/app/comparative");
    expect(url.searchParams.get(SIGN_IN_PARAM)).toBe("1");
  });

  it("opens the sign-in dialog on arrival", () => {
    window.history.replaceState(null, "", SIGN_IN_HREF);
    const { result } = renderHook(() => useAuthSession());
    expect(result.current.showLogin).toBe(true);
  });

  it("stays closed without the flag or once signed in", () => {
    window.history.replaceState(null, "", "/app/comparative");
    expect(renderHook(() => useAuthSession()).result.current.showLogin).toBe(
      false,
    );
    cognito.user = { getSession: () => {} };
    window.history.replaceState(null, "", SIGN_IN_HREF);
    expect(renderHook(() => useAuthSession()).result.current.showLogin).toBe(
      false,
    );
  });
});
