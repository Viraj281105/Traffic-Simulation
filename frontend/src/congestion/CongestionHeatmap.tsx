import "../netcommon/network.css";
import { RAMP_STOPS, rampColor } from "../netcommon/colors";
import { num } from "../netcommon/format";
import type { Heatmap } from "./types";

const LABEL_W = 92;
const TOP = 22;
const CELL_W_MAX = 48;
const CELL_H = 16;
const RIGHT = 12;
const WIDTH = 760;
/** Above this many cells the per-cell tooltips are left out to keep the page light. */
const MAX_TITLED_CELLS = 2500;

/**
 * Links by time: one row per link (the first link to congest at the top),
 * one column per time bucket, coloured by how full the link was. Pale is
 * empty, deep red is full. The per-link table next to it carries the same
 * onset and peak values as text.
 */
export function CongestionHeatmap({ heatmap }: { heatmap: Heatmap }) {
  const rows = heatmap.linkIds.length;
  const cols = heatmap.bucketStarts.length;
  if (rows === 0 || cols === 0) {
    return <p className="nw-muted">There is no heatmap to draw.</p>;
  }
  const cellW = Math.min(CELL_W_MAX, (WIDTH - LABEL_W - RIGHT) / cols);
  const width = LABEL_W + cellW * cols + RIGHT;
  const height = TOP + rows * CELL_H + 22;
  const titled = rows * cols <= MAX_TITLED_CELLS;
  const every = Math.max(1, Math.ceil(cols / 12));
  return (
    <figure className="nw-stack" style={{ margin: 0 }}>
      <svg
        className="nw-heat"
        viewBox={`0 0 ${String(width)} ${String(height)}`}
        role="img"
        aria-label={`Heatmap of how full each of ${String(rows)} links was in each of ${String(cols)} time buckets of ${num(heatmap.bucketSeconds, 0)} seconds. The link that congested first is at the top.`}
      >
        {heatmap.bucketStarts.map((t, c) =>
          c % every === 0 ? (
            <text
              key={t}
              className="nw-svg__tick"
              x={LABEL_W + c * cellW + cellW / 2}
              y={TOP - 8}
              textAnchor="middle"
            >
              {num(t, 0)}
            </text>
          ) : null,
        )}
        {heatmap.linkIds.map((id, r) => (
          <g key={id}>
            <text
              className="nw-svg__label"
              x={LABEL_W - 6}
              y={TOP + r * CELL_H + CELL_H - 4}
              textAnchor="end"
            >
              {id.length > 14 ? `${id.slice(0, 13)}…` : id}
            </text>
            {heatmap.values[r].map((v, c) => (
              <rect
                key={c}
                data-cell={`${id}@${String(heatmap.bucketStarts[c])}`}
                x={LABEL_W + c * cellW}
                y={TOP + r * CELL_H}
                width={cellW - 1}
                height={CELL_H - 1}
                fill={rampColor(v)}
              >
                {titled && (
                  <title>
                    {`${id} from ${num(heatmap.bucketStarts[c], 0)} s: ${num(v * 100, 0)}% full, queue ${num(heatmap.queue[r][c], 1)}, blocked ${num(heatmap.blockedFraction[r][c] * 100, 0)}% of the time`}
                  </title>
                )}
              </rect>
            ))}
          </g>
        ))}
        <text
          className="nw-svg__tick"
          x={LABEL_W + (cellW * cols) / 2}
          y={height - 4}
          textAnchor="middle"
        >
          Time (s)
        </text>
      </svg>
      <figcaption>
        <span
          className="nw-ramp"
          role="group"
          aria-label="Legend: how full a link was"
        >
          <span>Empty</span>
          {RAMP_STOPS.map((s) => (
            <span
              key={s}
              className="nw-ramp__cell"
              style={{ background: rampColor(s) }}
            >
              <span className="sr-only">{num(s * 100, 0)}% full</span>
            </span>
          ))}
          <span>Full</span>
        </span>
      </figcaption>
    </figure>
  );
}
