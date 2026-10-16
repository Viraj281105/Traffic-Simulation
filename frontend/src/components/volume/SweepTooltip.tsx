import { winnerLabel, type SweepWinner } from "../volumeSweepModel";

export type XAxisMode = "volume" | "rate";

/** Recharts tooltip for the sweep curves: each series' value with its spread
 *  or peak, and the tier's relative delta. */
export const SweepTooltip = ({
  active,
  payload,
  label,
  unit = "",
  xMode = "volume",
}: {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    color: string;
    payload?: unknown;
  }>;
  label?: number | string;
  unit?: string;
  xMode?: XAxisMode;
}) => {
  if (!active || !payload || payload.length === 0) return null;

  const raw = payload[0].payload as
    | {
        winner?: SweepWinner;
        delayDeltaPercent?: number;
        throughputDeltaPercent?: number;
        queueDeltaPercent?: number;
        signalDelayStdDev?: number;
        roundaboutDelayStdDev?: number;
        signalDelayMin?: number;
        signalDelayMax?: number;
        roundaboutDelayMin?: number;
        roundaboutDelayMax?: number;
        signalQueueMax?: number;
        roundaboutQueueMax?: number;
      }
    | undefined;

  return (
    <div className="custom-chart-tooltip">
      <div className="tooltip-header">
        <span className="tooltip-x-val">
          {xMode === "volume"
            ? `${String(label)} veh/h`
            : `${String(label)} veh/s`}
        </span>
        {raw?.winner && (
          <span className={`tooltip-winner-badge winner-${raw.winner}`}>
            {winnerLabel(raw.winner)}
          </span>
        )}
      </div>
      <div className="tooltip-metrics">
        {payload.map((p) => {
          let extraInfo = "";
          if (
            p.name === "Fixed-Time Signal" &&
            raw?.signalDelayStdDev !== undefined &&
            unit === "s"
          ) {
            const minStr =
              raw.signalDelayMin !== undefined
                ? `${raw.signalDelayMin.toFixed(1)}–`
                : "";
            const maxStr =
              raw.signalDelayMax !== undefined
                ? `${raw.signalDelayMax.toFixed(1)}s`
                : "";
            extraInfo = ` (±${raw.signalDelayStdDev.toFixed(2)}s, [${minStr}${maxStr}])`;
          } else if (
            p.name === "Modern Roundabout" &&
            raw?.roundaboutDelayStdDev !== undefined &&
            unit === "s"
          ) {
            const minStr =
              raw.roundaboutDelayMin !== undefined
                ? `${raw.roundaboutDelayMin.toFixed(1)}–`
                : "";
            const maxStr =
              raw.roundaboutDelayMax !== undefined
                ? `${raw.roundaboutDelayMax.toFixed(1)}s`
                : "";
            extraInfo = ` (±${raw.roundaboutDelayStdDev.toFixed(2)}s, [${minStr}${maxStr}])`;
          } else if (
            p.name === "Fixed-Time Signal" &&
            raw?.signalQueueMax !== undefined &&
            unit.includes("veh")
          ) {
            extraInfo = ` (Peak: ${raw.signalQueueMax.toFixed(1)})`;
          } else if (
            p.name === "Modern Roundabout" &&
            raw?.roundaboutQueueMax !== undefined &&
            unit.includes("veh")
          ) {
            extraInfo = ` (Peak: ${raw.roundaboutQueueMax.toFixed(1)})`;
          }

          return (
            <div key={p.name} className="volume-tooltip-row">
              <span
                className="volume-tooltip-dot"
                style={{ background: p.color }}
              />
              <span className="volume-tooltip-name">{p.name}:</span>
              <span className="volume-tooltip-val" style={{ color: p.color }}>
                {p.value.toFixed(2)}
                {unit}
                {extraInfo && (
                  <span
                    className="tooltip-extra"
                    style={{
                      fontSize: "11px",
                      opacity: 0.85,
                      marginLeft: "4px",
                    }}
                  >
                    {extraInfo}
                  </span>
                )}
              </span>
            </div>
          );
        })}
        {raw?.delayDeltaPercent !== undefined && unit === "s" && (
          <div
            className="tooltip-delta-row"
            style={{
              marginTop: "6px",
              paddingTop: "6px",
              borderTop: "1px solid rgba(255,255,255,0.1)",
              fontSize: "11px",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span style={{ color: "hsl(var(--muted-foreground))" }}>
              Δ Relative Difference:
            </span>
            <span
              style={{
                fontWeight: 700,
                color:
                  raw.delayDeltaPercent > 0
                    ? "#38bdf8"
                    : raw.delayDeltaPercent < 0
                      ? "#10b981"
                      : "#f59e0b",
              }}
            >
              {raw.delayDeltaPercent > 0
                ? `+${raw.delayDeltaPercent.toFixed(1)}% (signal lower)`
                : raw.delayDeltaPercent < 0
                  ? `${raw.delayDeltaPercent.toFixed(1)}% (roundabout lower)`
                  : "0.0% (Parity)"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
