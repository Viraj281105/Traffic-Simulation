import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { LOGO_GEOMETRY, LOGO_PALETTES } from "../components/ui/logoGeometry";

/** The favicon is a static copy of the logo (browsers can't render a React
 *  component as a tab icon); this keeps it in step with the one geometry
 *  and palette the app draws. */
describe("favicon.svg", () => {
  const favicon = readFileSync(
    resolve(__dirname, "../../public/favicon.svg"),
    "utf8",
  );

  it("uses the logo's road and flow paths", () => {
    expect(favicon).toContain(`d="${LOGO_GEOMETRY.road}"`);
    expect(favicon).toContain(`d="${LOGO_GEOMETRY.flow}"`);
  });

  it("uses the logo's roundabout, stroke and separation widths", () => {
    expect(favicon).toContain(`r="${String(LOGO_GEOMETRY.ring.r)}"`);
    expect(favicon).toContain(
      `stroke-width="${String(LOGO_GEOMETRY.strokeWidth)}"`,
    );
    expect(favicon).toContain(
      `stroke-width="${String(LOGO_GEOMETRY.gapWidth)}"`,
    );
  });

  it("draws every quadrant", () => {
    for (const deg of LOGO_GEOMETRY.rotations.filter((d) => d !== 0)) {
      expect(favicon).toContain(`rotate(${String(deg)} 50 50)`);
    }
  });

  it("uses the light and dark logo palettes", () => {
    for (const { road, flow } of Object.values(LOGO_PALETTES)) {
      expect(favicon).toContain(road);
      expect(favicon).toContain(flow);
    }
  });
});
