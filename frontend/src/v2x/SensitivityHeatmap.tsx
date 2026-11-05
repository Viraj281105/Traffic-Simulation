import "../netcommon/network.css";
import { RAMP_STOPS, rampColor } from "../netcommon/colors";
import { num, percent } from "../netcommon/format";
import type { Sensitivity } from "./types";

const LABEL_W = 84;
const TOP = 40;
const CELL_W = 84;
const CELL_H = 34;

/** Delay saved (seconds per vehicle) by message latency (rows) and message
 *  loss (columns). Deeper colour is a bigger saving; every cell also prints
 *  its number. */
export function SensitivityHeatmap({ grid }: { grid: Sensitivity }) {
  const best = Math.max(0, ...grid.cells.map((c) => c.delayBenefitSeconds));
  const cellAt = (lat: number, loss: number) =>
    grid.cells.find((c) => c.latencyMs === lat && c.lossProbability === loss);
  const width = LABEL_W + CELL_W * grid.lossProbabilities.length + 8;
  const height = TOP + CELL_H * grid.latenciesMs.length + 24;
  return (
    <figure className="nw-stack" style={{ margin: 0 }}>
      <svg
        className="nw-heat"
        viewBox={`0 0 ${String(width)} ${String(height)}`}
        role="img"
        aria-label={`Delay saved per vehicle for ${String(grid.latenciesMs.length)} message latencies and ${String(grid.lossProbabilities.length)} loss rates, with ${percent(grid.penetration)} of vehicles connected`}
      >
        <text className="nw-svg__tick" x={LABEL_W} y={12}>
          Messages lost
        </text>
        {grid.lossProbabilities.map((loss, c) => (
          <text
            key={loss}
            className="nw-svg__tick"
            x={LABEL_W + c * CELL_W + CELL_W / 2}
            y={TOP - 8}
            textAnchor="middle"
          >
            {percent(loss)}
          </text>
        ))}
        {grid.latenciesMs.map((lat, r) => (
          <g key={lat}>
            <text
              className="nw-svg__label"
              x={LABEL_W - 6}
              y={TOP + r * CELL_H + CELL_H / 2 + 4}
              textAnchor="end"
            >
              {`${num(lat, 0)} ms`}
            </text>
            {grid.lossProbabilities.map((loss, c) => {
              const cell = cellAt(lat, loss);
              const v = cell?.delayBenefitSeconds ?? 0;
              return (
                <g key={loss} data-cell={`${String(lat)}x${String(loss)}`}>
                  <rect
                    x={LABEL_W + c * CELL_W}
                    y={TOP + r * CELL_H}
                    width={CELL_W - 2}
                    height={CELL_H - 2}
                    fill={rampColor(best > 0 ? v / best : 0)}
                  >
                    <title>
                      {`Latency ${num(lat, 0)} ms, ${percent(loss)} lost: ${num(v, 2)} s saved per vehicle, delivery ${
                        cell?.deliveryRatio == null
                          ? "not available"
                          : percent(cell.deliveryRatio)
                      }`}
                    </title>
                  </rect>
                  <text
                    className="nw-svg__label"
                    x={LABEL_W + c * CELL_W + CELL_W / 2}
                    y={TOP + r * CELL_H + CELL_H / 2 + 3}
                    textAnchor="middle"
                  >
                    {num(v, 2)}
                  </text>
                </g>
              );
            })}
          </g>
        ))}
        <text className="nw-svg__tick" x={4} y={height - 6}>
          Latency of each message (rows)
        </text>
      </svg>
      <figcaption className="nw-ramp">
        Less saved
        {RAMP_STOPS.map((s) => (
          <span
            key={s}
            className="nw-ramp__cell"
            style={{ background: rampColor(s) }}
            aria-hidden="true"
          />
        ))}
        More saved (up to {num(best, 2)} s per vehicle)
      </figcaption>
      <p className="nw-muted">{grid.note}</p>
    </figure>
  );
}
