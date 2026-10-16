// ── Level of service (shared bands) ────────────────────────────────────────
//
// One definition of the grade bands for the whole app: metrics/plainLanguage
// (LOS_THRESHOLDS / levelOfService), which uses the Highway Capacity Manual's
// signalised bands for the signal and its stricter unsignalised bands for the
// roundabout. Only the colours live here. The grade is an indicative reading
// of simulated delay, not an HCM analysis (see the reading guide tab).

import {
  LOS_WORDS,
  levelOfService,
  type LosGrade,
  type Side,
} from "../../metrics/plainLanguage";

export interface LOSInfo {
  grade: LosGrade;
  label: string;
  color: string;
  bg: string;
}

export const LOS_COLORS: Record<LosGrade, { color: string; bg: string }> = {
  A: { color: "#10b981", bg: "rgba(16, 185, 129, 0.15)" },
  B: { color: "#34d399", bg: "rgba(52, 211, 153, 0.15)" },
  C: { color: "#fbbf24", bg: "rgba(251, 191, 36, 0.15)" },
  D: { color: "#f97316", bg: "rgba(249, 115, 22, 0.15)" },
  E: { color: "#ef4444", bg: "rgba(239, 68, 68, 0.15)" },
  F: { color: "#f43f5e", bg: "rgba(244, 63, 94, 0.2)" },
};

export function getLevelOfService(delaySeconds: number, side: Side): LOSInfo {
  const grade = levelOfService(delaySeconds, side);
  return { grade, label: LOS_WORDS[grade], ...LOS_COLORS[grade] };
}
