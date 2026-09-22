import { describe, expect, it } from "vitest";
import { parseStoredTimestamp } from "../utils/time";

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
