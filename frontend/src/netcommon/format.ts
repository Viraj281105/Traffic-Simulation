import { isNum, num } from "../insights/format";

export {
  UNAVAILABLE,
  dateTime,
  interval,
  isNum,
  num,
  pValueText,
  percent,
  withUnit,
} from "../insights/format";

/** "3 min 20 s" for a duration in seconds; "Not available" when missing. */
export function clock(seconds: number | null | undefined): string {
  if (!isNum(seconds)) return num(seconds);
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${String(m)} min ${String(s)} s` : `${String(s)} s`;
}
