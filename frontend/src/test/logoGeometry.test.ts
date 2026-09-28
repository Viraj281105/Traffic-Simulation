import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { LOGO_GEOMETRY } from "../components/ui/logoGeometry";

/** The favicon is a static copy of the logo (browsers can't render a React
 *  component as a tab icon); this keeps its paths in step with the one
 *  geometry the app draws. */
describe("favicon.svg", () => {
  const favicon = readFileSync(
    resolve(__dirname, "../../public/favicon.svg"),
    "utf8",
  );

  it("uses the logo's arm and flow paths", () => {
    expect(favicon).toContain(`d="${LOGO_GEOMETRY.arm}"`);
    expect(favicon).toContain(`d="${LOGO_GEOMETRY.flow}"`);
  });

  it("uses the logo's ring and island", () => {
    const { ring, island } = LOGO_GEOMETRY;
    expect(favicon).toContain(`r="${String(ring.r)}"`);
    expect(favicon).toContain(`r="${String(island.r)}"`);
  });

  it("draws every arm rotation", () => {
    for (const deg of LOGO_GEOMETRY.armRotations.filter((d) => d !== 0)) {
      expect(favicon).toContain(`rotate(${String(deg)} 32 32)`);
    }
  });
});
