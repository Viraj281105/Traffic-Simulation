import type { StatResult } from "./validationModel";

export function CIBar({
  label,
  stat,
  color,
  maxMean,
  ciMargin,
}: {
  label: string;
  stat: StatResult;
  color: string;
  maxMean: number;
  ciMargin?: number;
}) {
  const activeCI = ciMargin !== undefined ? ciMargin : stat.ci95;
  const pct = maxMean > 0 ? Math.min(100, (stat.mean / maxMean) * 100) : 0;
  const ciWidthPct =
    maxMean > 0 ? Math.min(100, (activeCI / maxMean) * 100) : 0;
  const ciLeft = Math.max(0, pct - ciWidthPct / 2);

  return (
    <div className="ci-row">
      <div className="ci-label-group">
        <span className="ci-model-name" style={{ borderLeftColor: color }}>
          {label}
        </span>
        <span className="ci-range-hint">
          Min {stat.min.toFixed(1)} · Max {stat.max.toFixed(1)}
        </span>
      </div>

      <div className="ci-track-container">
        <div className="ci-bar-track">
          <div
            className="ci-bar-fill"
            style={{
              width: `${pct.toString()}%`,
              background: `linear-gradient(90deg, ${color}88, ${color})`,
            }}
          />
          <div
            className="ci-bar-ci"
            style={{
              left: `${ciLeft.toString()}%`,
              width: `${Math.max(4, ciWidthPct).toString()}%`,
            }}
            title={`CI: [${(stat.mean - activeCI).toFixed(2)} – ${(stat.mean + activeCI).toFixed(2)}]`}
          />
        </div>
      </div>

      <div className="ci-values">
        <span className="ci-mean" style={{ color }}>
          {stat.mean.toFixed(2)}
        </span>
        <span className="ci-range">
          ±{activeCI.toFixed(2)}{" "}
          <span className="ci-sigma">(σ={stat.std.toFixed(2)})</span>
        </span>
      </div>
    </div>
  );
}
