/**
 * Polling a study job leaves no abort listeners behind (checkpoint 12): each
 * one-second wait used to add a listener that stayed on the signal until the
 * job ended, about 3,600 for an hour-long study.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../services/api", () => ({ get: api.get, post: api.post }));

import { runStudyJob, STUDY_POLL_INTERVAL_MS } from "../services/studyJobs";

const job = (status: string, result: unknown = null) => ({
  jobId: "j1",
  kind: "sweep",
  status,
  progress: {},
  result,
  error: null,
});

beforeEach(() => {
  vi.useFakeTimers();
  api.post.mockResolvedValue(job("running"));
});
afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("study job polling", () => {
  it("removes each wait's abort listener when the wait ends", async () => {
    let polls = 0;
    api.get.mockImplementation(() => {
      polls += 1;
      return Promise.resolve(
        polls < 20 ? job("running") : job("completed", { ok: 1 }),
      );
    });
    const ctrl = new AbortController();
    const added = vi.spyOn(ctrl.signal, "addEventListener");
    const removed = vi.spyOn(ctrl.signal, "removeEventListener");
    const done = runStudyJob("/r", {}, () => {}, ctrl.signal);
    await vi.advanceTimersByTimeAsync(STUDY_POLL_INTERVAL_MS * 25);
    await expect(done).resolves.toEqual({ ok: 1 });
    expect(added).toHaveBeenCalledTimes(20);
    expect(removed).toHaveBeenCalledTimes(20);
  });

  it("still rejects promptly when aborted during a wait", async () => {
    api.get.mockResolvedValue(job("running"));
    const ctrl = new AbortController();
    const done = runStudyJob("/r", {}, () => {}, ctrl.signal).catch(
      (e: unknown) => e,
    );
    await vi.advanceTimersByTimeAsync(STUDY_POLL_INTERVAL_MS / 2);
    ctrl.abort(new Error("stopped"));
    await expect(done).resolves.toEqual(new Error("stopped"));
  });
});
