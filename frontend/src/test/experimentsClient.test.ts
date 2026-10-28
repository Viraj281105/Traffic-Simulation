import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../auth/cognito", () => ({
  getAuthToken: () => Promise.resolve("token-123"),
}));

import {
  ExperimentsApiError,
  getExperiment,
  getExperimentResult,
  isActive,
} from "../services/v3/experiments";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

function reply(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      statusText: status === 404 ? "Not Found" : "",
      headers: { "Content-Type": "application/json" },
    }),
  );
}

describe("v3 experiments client", () => {
  it("fetches the status and the result from /api/v3 with the user's token", async () => {
    fetchMock.mockReturnValueOnce(reply(200, { id: "x", status: "running" }));
    const status = await getExperiment("x y");
    expect(status.status).toBe("running");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/v3\/experiments\/x%20y$/);
    expect(new Headers(init.headers).get("Authorization")).toBe(
      "Bearer token-123",
    );

    fetchMock.mockReturnValueOnce(reply(200, { experimentId: "x" }));
    await getExperimentResult("x");
    expect((fetchMock.mock.calls[1] as [string])[0]).toMatch(
      /\/api\/v3\/experiments\/x\/result$/,
    );
  });

  it("keeps the server's reasons from the error envelope", async () => {
    fetchMock.mockReturnValueOnce(
      reply(409, {
        error: {
          code: "HTTP_409",
          message: "Experiment is running; there is no result",
          details: null,
        },
      }),
    );
    const error = await getExperimentResult("x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ExperimentsApiError);
    expect((error as ExperimentsApiError).status).toBe(409);
    expect((error as ExperimentsApiError).reasons).toEqual([
      "Experiment is running; there is no result",
    ]);

    fetchMock.mockReturnValueOnce(
      reply(422, {
        error: { message: "bad", details: { errors: ["a", "b"] } },
      }),
    );
    const listed = await getExperiment("x").catch((e: unknown) => e);
    expect((listed as ExperimentsApiError).reasons).toEqual(["a", "b"]);
  });

  it("falls back to the status text when the body is not the envelope", async () => {
    fetchMock.mockReturnValueOnce(
      Promise.resolve(
        new Response("nope", { status: 404, statusText: "Not Found" }),
      ),
    );
    const error = await getExperiment("x").catch((e: unknown) => e);
    expect((error as ExperimentsApiError).reasons).toEqual(["Not Found"]);
  });

  it("reports an unreachable server as status 0", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const error = await getExperiment("x").catch((e: unknown) => e);
    expect((error as ExperimentsApiError).status).toBe(0);
    expect((error as ExperimentsApiError).message).toBe(
      "The server could not be reached.",
    );
  });

  it("knows which states are still going", () => {
    expect(isActive("queued")).toBe(true);
    expect(isActive("running")).toBe(true);
    expect(isActive("completed")).toBe(false);
    expect(isActive("failed")).toBe(false);
  });
});
