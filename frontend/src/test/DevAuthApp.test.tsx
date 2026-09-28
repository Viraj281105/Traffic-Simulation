/**
 * The dashboard under the local development auth bypass: every
 * authenticated page is reachable without Cognito, and with the bypass off
 * the Cognito sign-in flow behaves exactly as before.
 *
 * The bypass flag itself (and that a production build never sets it) is
 * covered in devAuthBypass.test.ts; here it is toggled directly.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authState = { bypass: true };
const listReplays = vi.fn();

vi.mock("../auth/cognito", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../auth/cognito")>();
  return {
    ...actual,
    get DEV_AUTH_BYPASS() {
      return authState.bypass;
    },
    getCurrentUser: () => null,
    getAuthToken: () => Promise.resolve(null),
  };
});

vi.mock("../services/api", () => ({
  updateSimulationConfig: vi.fn().mockResolvedValue(undefined),
  saveReplay: vi.fn().mockResolvedValue({ runId: "r1" }),
  listReplays: () => listReplays() as Promise<unknown>,
  deleteReplay: vi.fn().mockResolvedValue({ status: "ok" }),
  listSweeps: vi.fn().mockResolvedValue([]),
  getRunRecord: vi.fn().mockResolvedValue(null),
  getReplay: vi.fn().mockResolvedValue(null),
  reproduceRun: vi.fn(),
  updateRunMetadata: vi.fn(),
  runExportUrl: () => "",
  ApiError: class ApiError extends Error {
    status = 500;
  },
}));

vi.mock("../hooks/useWebSocketSnapshot", () => ({
  useWebSocketSnapshot: () => ({
    snapshot: null,
    connectionStatus: "connected",
    isPlaying: false,
    error: null,
    play: vi.fn().mockResolvedValue(undefined),
    pause: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock("../hooks/useSimulationPolling", () => ({
  useSimulationPolling: () => ({
    vehicle: null,
    status: null,
    isLoading: false,
    error: null,
    start: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn().mockResolvedValue(undefined),
    reset: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock("../hooks/useContainerSize", () => ({
  useContainerSize: () => [() => undefined, { width: 800, height: 600 }],
}));

import { App } from "../App";

beforeEach(() => {
  vi.clearAllMocks();
  listReplays.mockResolvedValue([]);
  sessionStorage.clear();
  window.history.replaceState(null, "", "/app/comparative");
});

describe("with the DEV auth bypass", () => {
  beforeEach(() => {
    authState.bypass = true;
  });

  it("starts signed in as the local developer, marked DEV AUTH", () => {
    render(<App />);
    expect(
      screen.queryByRole("button", { name: /sign in/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Local developer")).toBeInTheDocument();
    expect(screen.getByText("DEV AUTH")).toBeInTheDocument();
  });

  it("opens the Research lab without asking to sign in", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: "Research lab" }));

    expect(window.location.pathname).toBe("/app/research");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("loads saved runs without Cognito", async () => {
    window.history.replaceState(null, "", "/app/history");
    render(<App />);

    await waitFor(() => {
      expect(listReplays).toHaveBeenCalled();
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("without the bypass (production and VITE_DEV_AUTH_BYPASS=false)", () => {
  beforeEach(() => {
    authState.bypass = false;
  });

  it("keeps the Cognito sign-in flow", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole("button", { name: /sign in/i })).toBeVisible();
    expect(screen.queryByText("DEV AUTH")).not.toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Research lab" }));

    expect(window.location.pathname).toBe("/app/comparative");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
