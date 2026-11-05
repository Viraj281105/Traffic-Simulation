/** Number formatting shared by the result screens. A missing value is shown
 *  as unavailable, never as zero. */

export const UNAVAILABLE = "Not available";

export function isNum(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Up to `digits` decimals, no trailing zeros; "Not available" when missing. */
export function num(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return UNAVAILABLE;
  return Number(value.toFixed(digits)).toLocaleString("en-US", {
    maximumFractionDigits: digits,
  });
}

/** "12.4 s", or "Not available". */
export function withUnit(
  value: number | null | undefined,
  unit: string,
  digits = 2,
): string {
  if (!isNum(value)) return UNAVAILABLE;
  return unit ? `${num(value, digits)} ${unit}` : num(value, digits);
}

export function interval(
  ci: readonly [number, number] | null | undefined,
  unit: string,
  digits = 2,
): string {
  if (!ci || !isNum(ci[0]) || !isNum(ci[1])) return UNAVAILABLE;
  const suffix = unit ? ` ${unit}` : "";
  return `${num(ci[0], digits)} to ${num(ci[1], digits)}${suffix}`;
}

/** "p = 0.012", "p < 0.001". */
export function pValueText(p: number | null | undefined): string {
  if (!isNum(p)) return "p-value not available";
  if (p < 0.001) return "p < 0.001";
  return `p = ${p
    .toFixed(p < 0.01 ? 4 : 3)
    .replace(/0+$/, "")
    .replace(/\.$/, "")}`;
}

export function percent(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** A stored ISO timestamp as a local date-time; the raw text if unparsable. */
export function dateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
