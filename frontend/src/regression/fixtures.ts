import type { NightlyRegression } from "./types";

export const nightlyFixture: NightlyRegression = {
  generatedAt: "2026-11-04T05:00:00Z",
  runs: [
    {
      id: "n3",
      startedAt: "2026-11-04T02:00:00Z",
      gitCommit: "59f57cc",
      status: "fail",
      durationSeconds: 754,
      checks: [
        {
          id: "c1",
          name: "Fixed-time junction, average delay",
          status: "fail",
          metric: "mean_delay",
          expected: 21.4,
          actual: 24.9,
          tolerance: 1,
          unit: "s",
          message: "Average delay moved outside the allowed range.",
        },
        { id: "c2", name: "Vehicle conservation", status: "pass" },
      ],
      logUrl: null,
    },
    {
      id: "n2",
      startedAt: "2026-11-03T02:00:00Z",
      gitCommit: "3c75956",
      status: "pass",
      durationSeconds: 731,
      checks: [
        {
          id: "c1",
          name: "Fixed-time junction, average delay",
          status: "pass",
        },
        { id: "c2", name: "Vehicle conservation", status: "pass" },
      ],
    },
    {
      id: "n1",
      startedAt: "2026-11-02T02:00:00Z",
      gitCommit: "953b9c1",
      status: "error",
      durationSeconds: 12,
      checks: [
        {
          id: "c1",
          name: "Fixed-time junction, average delay",
          status: "error",
          message: "The golden file could not be read.",
        },
      ],
    },
  ],
};
