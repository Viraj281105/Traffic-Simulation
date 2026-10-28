import { motion, useReducedMotion } from "framer-motion";
import { Reveal } from "../components/Reveal";
import evidence from "../data/evidence.json";
import { Counter } from "./parts";

interface Row {
  alt: string;
  scale: number;
  vph: number;
  mean: number;
  ciLow: number;
  ciHigh: number;
}
interface Delta {
  alt: string;
  scale: number;
  delta: number;
  ciLow: number;
  ciHigh: number;
  verdict: string;
}

const rows = evidence.rows as Row[];
const deltas = evidence.deltas as Delta[];
const labels = evidence.labels as Record<string, string>;
const ALT_COLOUR: Record<string, string> = {
  base: "var(--series-signal)",
  adaptive: "var(--color-accent)",
  rbt: "var(--series-roundabout)",
};
const SCALES = Array.from(new Set(rows.map((r) => r.scale)));
const ALTS = Array.from(new Set(rows.map((r) => r.alt)));

const W = 560;
const H = 250;
const PAD = { l: 44, r: 12, t: 14, b: 40 };

function MeanDelayChart() {
  const reduced = useReducedMotion();
  const top = Math.max(...rows.map((r) => r.ciHigh)) * 1.05;
  const y = (v: number) => PAD.t + (1 - v / top) * (H - PAD.t - PAD.b);
  const groupW = (W - PAD.l - PAD.r) / SCALES.length;
  const barW = Math.min(30, (groupW - 24) / ALTS.length);
  const ticks = [0, 20, 40, 60].filter((t) => t <= top);
  return (
    <svg
      viewBox={`0 0 ${W.toString()} ${H.toString()}`}
      className="evchart"
      role="img"
      aria-label="Mean delay in seconds per vehicle for the fixed-time signal, the adaptive signal and the roundabout at three demand levels, with 95 percent intervals over three seeds. The intervals overlap at every demand level."
    >
      {ticks.map((t) => (
        <g key={t}>
          <line
            x1={PAD.l}
            x2={W - PAD.r}
            y1={y(t)}
            y2={y(t)}
            stroke="currentColor"
            strokeOpacity="0.12"
          />
          <text
            x={PAD.l - 8}
            y={y(t) + 4}
            textAnchor="end"
            className="evchart__tick"
          >
            {t.toString()}
          </text>
        </g>
      ))}
      {SCALES.map((scale, gi) => {
        const gx = PAD.l + gi * groupW + groupW / 2;
        const vph = rows.find((r) => r.scale === scale)?.vph ?? 0;
        return (
          <g key={scale}>
            {ALTS.map((alt, ai) => {
              const r = rows.find((q) => q.scale === scale && q.alt === alt);
              if (!r) return null;
              const x = gx + (ai - (ALTS.length - 1) / 2) * (barW + 6);
              return (
                <g key={alt}>
                  <motion.rect
                    x={x - barW / 2}
                    width={barW}
                    rx="4"
                    fill={ALT_COLOUR[alt]}
                    fillOpacity="0.85"
                    initial={reduced ? false : { y: y(0), height: 0 }}
                    whileInView={{ y: y(r.mean), height: y(0) - y(r.mean) }}
                    viewport={{ once: true, margin: "-10%" }}
                    transition={{
                      duration: 0.8,
                      delay: 0.08 * (gi * 3 + ai),
                      ease: [0.2, 0.8, 0.2, 1],
                    }}
                  />
                  <motion.g
                    initial={reduced ? false : { opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.9 + 0.08 * (gi * 3 + ai) }}
                    stroke="currentColor"
                    strokeWidth="1.5"
                  >
                    <line x1={x} x2={x} y1={y(r.ciLow)} y2={y(r.ciHigh)} />
                    <line
                      x1={x - 5}
                      x2={x + 5}
                      y1={y(r.ciHigh)}
                      y2={y(r.ciHigh)}
                    />
                    <line
                      x1={x - 5}
                      x2={x + 5}
                      y1={y(Math.max(0, r.ciLow))}
                      y2={y(Math.max(0, r.ciLow))}
                    />
                  </motion.g>
                </g>
              );
            })}
            <text
              x={gx}
              y={H - 20}
              textAnchor="middle"
              className="evchart__group"
            >
              {vph.toLocaleString()} veh/h
            </text>
            <text
              x={gx}
              y={H - 5}
              textAnchor="middle"
              className="evchart__tick"
            >
              demand ×{scale.toString()}
            </text>
          </g>
        );
      })}
      <text x={6} y={12} className="evchart__tick">
        s per vehicle
      </text>
    </svg>
  );
}

function DeltaChart() {
  const reduced = useReducedMotion();
  const entries = SCALES.flatMap((scale) =>
    ["adaptive", "rbt"].map((alt) => ({
      scale,
      alt,
      d: deltas.find((q) => q.scale === scale && q.alt === alt),
    })),
  );
  const lo = Math.min(...deltas.map((d) => d.ciLow), 0) * 1.08;
  const hi = Math.max(...deltas.map((d) => d.ciHigh), 0) * 1.08;
  const span = hi - lo || 1;
  const pos = (v: number) => `${(((v - lo) / span) * 100).toFixed(2)}%`;
  return (
    <ul
      className="forest2"
      aria-label="Difference in mean delay against the fixed-time signal, with 95 percent intervals"
    >
      {entries.map(({ scale, alt, d }, i) =>
        d ? (
          <li key={`${scale.toString()}-${alt}`}>
            <span className="forest2__label">
              {labels[alt]} <small>×{scale.toString()}</small>
            </span>
            <span className="forest2__track" aria-hidden="true">
              <span className="forest2__zero" style={{ left: pos(0) }} />
              <motion.span
                className="forest2__ci"
                style={{
                  left: pos(d.ciLow),
                  width: `calc(${pos(d.ciHigh)} - ${pos(d.ciLow)})`,
                  background: ALT_COLOUR[alt],
                }}
                initial={reduced ? false : { scaleX: 0, opacity: 0 }}
                whileInView={{ scaleX: 1, opacity: 1 }}
                viewport={{ once: true, margin: "-10%" }}
                transition={{ duration: 0.6, delay: 0.07 * i }}
              />
              <motion.span
                className="forest2__dot"
                style={{ left: pos(d.delta), background: ALT_COLOUR[alt] }}
                initial={reduced ? false : { scale: 0 }}
                whileInView={{ scale: 1 }}
                viewport={{ once: true }}
                transition={{
                  delay: 0.4 + 0.07 * i,
                  type: "spring",
                  stiffness: 300,
                  damping: 18,
                }}
              />
            </span>
            <span className="forest2__verdict">{d.verdict}</span>
          </li>
        ) : null,
      )}
    </ul>
  );
}

/** A real three-seed planning study: when the intervals overlap, UrbanFlow
 *  says "inconclusive" rather than naming a winner. */
export function Evidence() {
  const inconclusive = deltas.filter(
    (d) => d.verdict === "inconclusive",
  ).length;
  return (
    <section
      className="evidence section-wrap"
      id="evidence"
      aria-labelledby="evidence-title"
    >
      <Reveal width="100%">
        <div className="studio__head">
          <div>
            <p className="eyebrow">Evidence</p>
            <h2 id="evidence-title" className="display">
              Knowing when
              <br />
              <em>you do not know.</em>
            </h2>
          </div>
          <p className="studio__note">
            A planning study: three control options, three demand levels, three
            seeds each, paired on the same arrivals.
          </p>
        </div>

        <div className="evidence__stats">
          <div>
            <strong className="mono">
              <Counter value={inconclusive} />
              <span className="of"> of {deltas.length.toString()}</span>
            </strong>
            <span>delay comparisons came back inconclusive</span>
          </div>
          <div>
            <strong className="mono">
              <Counter value={evidence.seeds} />
            </strong>
            <span>seeds per condition: flagged “indicative only”</span>
          </div>
          <div>
            <strong className="mono">
              <Counter value={evidence.findings} />
            </strong>
            <span>findings written, each with its confidence</span>
          </div>
        </div>

        <div className="evidence__charts">
          <figure className="panel-card">
            <figcaption>
              Mean delay per vehicle, 95 % interval
              <span className="legend">
                {ALTS.map((a) => (
                  <i key={a}>
                    <b
                      style={{ background: ALT_COLOUR[a] }}
                      aria-hidden="true"
                    />
                    {labels[a]}
                  </i>
                ))}
              </span>
            </figcaption>
            <MeanDelayChart />
          </figure>
          <figure className="panel-card">
            <figcaption>
              Difference from the fixed-time signal (s)
              <small>
                Left of the line = less delay. Every interval crosses it.
              </small>
            </figcaption>
            <DeltaChart />
          </figure>
        </div>
        <p className="evidence__source">
          Precomputed study “{evidence.study}” (engine commit{" "}
          {evidence.gitCommit.slice(0, 7)},{" "}
          {evidence.durationSeconds.toString()} s runs). {evidence.flags[0]}{" "}
          More seeds narrow the intervals.
        </p>
      </Reveal>
    </section>
  );
}
