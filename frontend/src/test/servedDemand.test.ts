import { describe, expect, it } from "vitest";
import { servedDemandNote } from "../metrics/servedDemand";

const served = (lowerDelayServedLess: boolean, comparable = false) => ({
  admittedShareOfNominalDifference: -0.3,
  unfinishedShareDifference: 0.01,
  comparable,
  lowerDelayServedLess,
});

describe("served-demand note on a delay reading", () => {
  it("cautions when the lower-delay side served less", () => {
    const note = servedDemandNote(served(true));
    expect(note).toMatch(/served less of the demand/);
    // A caution, never a verdict.
    expect(note).toMatch(/may explain/);
    expect(note).not.toMatch(/worse|better/i);
  });

  it("says nothing when the populations differ the other way", () => {
    // Different populations, but the lower-delay side served more: the
    // difference strengthens the reading, so no caution is shown.
    expect(servedDemandNote(served(false, false))).toBeNull();
  });

  it("says nothing for results saved before the field existed", () => {
    expect(servedDemandNote(undefined)).toBeNull();
  });
});
