import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { Reveal } from "../components/Reveal";
import { useSceneData } from "../scene/SceneContext";
import { SimCanvas } from "../scene/SimCanvas";
import { seekClock, useSimClock } from "../scene/clock";
import type { Camera } from "../scene/render";
import {
  STRATEGY_IDS,
  formatClock,
  seriesAt,
  windowLength,
  type SceneData,
  type StrategyId,
} from "../scene/sceneData";
import {
  METRIC_VIEW,
  STRATEGY_COLOUR,
  STRATEGY_SHORT,
} from "../scene/strategyStyle";

const TILE_CAMERA: Camera = {
  yaw: -30,
  elev: 52,
  zoom: 0.96,
  shiftY: 0.02,
  shiftX: 0,
};

function Tile({
  data,
  id,
  clock,
  focus,
  onFocus,
}: {
  data: SceneData;
  id: StrategyId;
  clock: ReturnType<typeof useSimClock>;
  focus: StrategyId | null;
  onFocus: (id: StrategyId | null) => void;
}) {
  const camera = useRef<Camera>({ ...TILE_CAMERA });
  const [queued, setQueued] = useState(0);
  useEffect(() => {
    const run = data.runs[id];
    const len = windowLength(data);
    const read = () => {
      const local = ((clock.current.t % len) + len) % len;
      setQueued(seriesAt(run, data.provenance.window[0] + local).queued);
    };
    read();
    const timer = window.setInterval(() => {
      if (!document.hidden) read();
    }, 300);
    return () => {
      window.clearInterval(timer);
    };
  }, [data, id, clock]);
  return (
    <button
      type="button"
      className={`tile${focus === id ? " is-focus" : ""}${focus && focus !== id ? " is-dim" : ""}`}
      onMouseEnter={() => {
        onFocus(id);
      }}
      onMouseLeave={() => {
        onFocus(null);
      }}
      onFocus={() => {
        onFocus(id);
      }}
      onBlur={() => {
        onFocus(null);
      }}
      aria-label={`${STRATEGY_SHORT[id]}: ${queued.toString()} vehicles queued now`}
    >
      <SimCanvas
        data={data}
        strategy={id}
        clock={clock}
        camera={camera}
        maxDpr={1.5}
        label={`${STRATEGY_SHORT[id]} control, replayed from the engine.`}
        className="tile__canvas"
      />
      <span className="tile__name">
        <i style={{ background: STRATEGY_COLOUR[id] }} aria-hidden="true" />
        {STRATEGY_SHORT[id]}
      </span>
      <span className="tile__queue mono" aria-hidden="true">
        {queued.toString()} queued
      </span>
    </button>
  );
}

/** Four junctions on identical traffic, advancing on one clock, with the
 *  measured outcome of each run beside them. */
export function CompareStudio() {
  const data = useSceneData();
  const reduced = useReducedMotion() ?? false;
  const [playing, setPlaying] = useState(!reduced);
  const [speed, setSpeed] = useState(1);
  const [metric, setMetric] = useState(0);
  const [focus, setFocus] = useState<StrategyId | null>(null);
  const clock = useSimClock(playing, speed, 8);
  const [scrub, setScrub] = useState(8);
  const len = data ? windowLength(data) : 60;

  // Keep the scrubber in step with the clock while it plays.
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setScrub(((clock.current.t % len) + len) % len);
    }, 250);
    return () => {
      window.clearInterval(timer);
    };
  }, [playing, clock, len]);

  const m = METRIC_VIEW[metric] ?? METRIC_VIEW[0];
  const values = data
    ? STRATEGY_IDS.map((id) => data.runs[id].metrics[m.key] ?? 0)
    : [];
  const top = Math.max(0.0001, ...values);
  const best = values.length
    ? m.better === "lower"
      ? Math.min(...values)
      : Math.max(...values)
    : 0;

  return (
    <section
      className="studio section-wrap"
      id="compare"
      aria-labelledby="studio-title"
    >
      <Reveal width="100%">
        <div className="studio__head">
          <div>
            <p className="eyebrow">Compare</p>
            <h2 id="studio-title" className="display">
              Four rules.
              <br />
              <em>One set of cars.</em>
            </h2>
          </div>
          <p className="studio__note">
            Scrub the replay, hover a junction, switch the measure. Every
            vehicle and number is a recording of the engine.
          </p>
        </div>

        <div className="studio__body">
          <div className="studio__grid">
            {data
              ? STRATEGY_IDS.map((id) => (
                  <Tile
                    key={id}
                    data={data}
                    id={id}
                    clock={clock}
                    focus={focus}
                    onFocus={setFocus}
                  />
                ))
              : STRATEGY_IDS.map((id) => (
                  <div
                    key={id}
                    className="tile tile--empty"
                    aria-hidden="true"
                  />
                ))}
          </div>

          <div className="studio__panel">
            <div className="seg" role="group" aria-label="Measure to compare">
              {METRIC_VIEW.map((mv, i) => (
                <button
                  key={mv.key}
                  type="button"
                  className={i === metric ? "is-on" : ""}
                  aria-pressed={i === metric}
                  onClick={() => {
                    setMetric(i);
                  }}
                >
                  {mv.label}
                </button>
              ))}
            </div>
            <p className="studio__hint">
              {m.better === "lower" ? "Lower is better" : "Higher is better"}
              {" · "}whole 150 s run, one seed
            </p>
            <ul className="bars">
              {STRATEGY_IDS.map((id, i) => {
                const v = values[i] ?? 0;
                return (
                  <li
                    key={id}
                    className={`bars__row${focus === id ? " is-focus" : ""}${v === best ? " is-best" : ""}`}
                    onMouseEnter={() => {
                      setFocus(id);
                    }}
                    onMouseLeave={() => {
                      setFocus(null);
                    }}
                  >
                    <span className="bars__name">{STRATEGY_SHORT[id]}</span>
                    <span className="bars__track">
                      <motion.span
                        className="bars__fill"
                        style={{ background: STRATEGY_COLOUR[id] }}
                        initial={false}
                        animate={{ width: `${((v / top) * 100).toFixed(1)}%` }}
                        transition={{
                          duration: reduced ? 0 : 0.7,
                          ease: [0.2, 0.8, 0.2, 1],
                        }}
                      />
                    </span>
                    <span className="bars__value mono">
                      {v.toFixed(m.digits)}
                      <small>{m.unit}</small>
                    </span>
                  </li>
                );
              })}
            </ul>
            <p className="studio__caveat">
              A single run each. Which control does better depends on the
              traffic and the layout; the Planner repeats this over many seeds
              and shows the uncertainty.
            </p>
          </div>
        </div>

        <div className="transport">
          <button
            type="button"
            className="transport__btn"
            onClick={() => {
              setPlaying((p) => !p);
            }}
            aria-label={playing ? "Pause the replay" : "Play the replay"}
          >
            {playing ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <input
            type="range"
            min={0}
            max={len}
            step={0.5}
            value={scrub}
            aria-label="Position in the replay"
            onChange={(e) => {
              const t = Number(e.target.value);
              seekClock(clock, t);
              setScrub(t);
            }}
          />
          <span className="mono transport__time">
            {formatClock((data?.provenance.window[0] ?? 40) + scrub)}
          </span>
          <div
            className="seg seg--small"
            role="group"
            aria-label="Replay speed"
          >
            {[0.5, 1, 2].map((s) => (
              <button
                key={s}
                type="button"
                className={s === speed ? "is-on" : ""}
                aria-pressed={s === speed}
                onClick={() => {
                  setSpeed(s);
                }}
              >
                {s}×
              </button>
            ))}
          </div>
        </div>
      </Reveal>
    </section>
  );
}
