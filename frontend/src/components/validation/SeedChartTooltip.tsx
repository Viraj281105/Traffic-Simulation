import type React from "react";
import {
  METRIC_UNITS,
  ROUND_COLOR,
  SIGNAL_COLOR,
  type MetricKey,
} from "./validationModel";

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    value: number;
    dataKey: string;
    color: string;
    name: string;
  }>;
  label?: string;
  metric: MetricKey;
}

export const SeedChartTooltip: React.FC<CustomTooltipProps> = ({
  active,
  payload,
  label,
  metric,
}) => {
  if (!active || !payload || payload.length < 2) return null;

  const sigVal = payload.find((p) => p.dataKey === "signal")?.value ?? 0;
  const rndVal = payload.find((p) => p.dataKey === "roundabout")?.value ?? 0;
  const delta = rndVal - sigVal;
  const unit = METRIC_UNITS[metric];

  // Which side has the lower delay/queue or the higher throughput: a plain
  // description of this seed, not a judgement of either control.
  const rndWins = metric === "throughput" ? rndVal > sigVal : rndVal < sigVal;

  return (
    <div className="validation-chart-tooltip">
      <div className="tooltip-seed-title">Seed #{label}</div>
      <div className="tooltip-metric-rows">
        <div className="validation-tooltip-row">
          <span
            className="validation-tooltip-dot"
            style={{ background: SIGNAL_COLOR }}
          />
          <span className="validation-tooltip-name">Signal:</span>
          <span className="validation-tooltip-val">
            {sigVal.toFixed(2)} {unit}
          </span>
        </div>
        <div className="validation-tooltip-row">
          <span
            className="validation-tooltip-dot"
            style={{ background: ROUND_COLOR }}
          />
          <span className="validation-tooltip-name">Roundabout:</span>
          <span className="validation-tooltip-val">
            {rndVal.toFixed(2)} {unit}
          </span>
        </div>
      </div>
      <div className="tooltip-delta-footer">
        <span className="tooltip-delta-label">Difference:</span>
        <span className="tooltip-delta-val">
          {delta > 0 ? `+${delta.toFixed(2)}` : delta.toFixed(2)} (
          {metric === "throughput"
            ? rndWins
              ? "more through the roundabout"
              : "more through the signal"
            : rndWins
              ? "lower at the roundabout"
              : "lower at the signal"}
          )
        </span>
      </div>
    </div>
  );
};
