import { describe, expect, it } from "vitest";
import { formatDuration, parseStoredTimestamp } from "../utils/time";

describe("parseStoredTimestamp", () => {
  it("reads SQLite CURRENT_TIMESTAMP values as UTC", () => {
    expect(parseStoredTimestamp("2026-09-04 10:31:23").toISOString()).toBe(
      "2026-09-04T10:31:23.000Z",
    );
  });

  it("respects an explicit zone", () => {
    expect(
      parseStoredTimestamp("2026-09-04T10:31:23+05:30").toISOString(),
    ).toBe("2026-09-04T05:01:23.000Z");
    expect(parseStoredTimestamp("2026-09-04T10:31:23Z").toISOString()).toBe(
      "2026-09-04T10:31:23.000Z",
    );
  });
});

describe("formatDuration", () => {
  it("reads as seconds, then minutes and seconds", () => {
    expect(formatDuration(0)).toBe("0s");
    expect(formatDuration(41.6)).toBe("42s");
    expect(formatDuration(78)).toBe("1m 18s");
    expect(formatDuration(605)).toBe("10m 05s");
    expect(formatDuration(-3)).toBe("0s");
  });
});
