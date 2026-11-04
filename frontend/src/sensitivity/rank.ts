import type { SensitivityInput } from "./types";

/** Most influential first. */
export function rankInputs(inputs: SensitivityInput[]): SensitivityInput[] {
  return [...inputs].sort(
    (x, y) =>
      (y.total ?? y.firstOrder) - (x.total ?? x.firstOrder) ||
      y.firstOrder - x.firstOrder ||
      x.label.localeCompare(y.label),
  );
}
