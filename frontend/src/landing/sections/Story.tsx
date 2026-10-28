import { useCallback, useEffect, useRef, useState } from "react";
import {
  AnimatePresence,
  motion,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useSpring,
} from "framer-motion";
import { useSceneData, useSceneTheme } from "../scene/SceneContext";
import { SimCanvas } from "../scene/SimCanvas";
import { useSimClock } from "../scene/clock";
import type { Camera } from "../scene/render";
import { STRATEGY_IDS, type StrategyId } from "../scene/sceneData";
import {
  METRIC_VIEW,
  STRATEGY_COLOUR,
  STRATEGY_INK,
  STRATEGY_SHORT,
} from "../scene/strategyStyle";
import { useHud } from "../scene/useHud";
import { Counter, QueueSpark } from "./parts";

interface Chapter {
  n: string;
  kicker: string;
  title: string;
  line: string;
  strategy: StrategyId;
  evidence?: boolean;
}

const CHAPTERS: Chapter[] = [
  {
    n: "01",
    kicker: "The problem",
    title: "One rule for every driver.",
    line: "A fixed-time signal follows its timetable whether or not anyone is waiting.",
    strategy: "fixed_time",
  },
  {
    n: "02",
    kicker: "Let the road decide",
    title: "Detectors end each green.",
    line: "The adaptive signal keeps the same phases, but detectors at the stop lines decide when each green ends.",
    strategy: "adaptive",
  },
  {
    n: "03",
    kicker: "Take the signal away",
    title: "Give way, then go.",
    line: "A roundabout has no signal: drivers give way to circulating traffic and enter at an accepted gap.",
    strategy: "roundabout",
  },
  {
    n: "04",
    kicker: "Meter the entries",
    title: "Signals at the door.",
    line: "Signals meter entry on designated approaches while circulating traffic keeps priority.",
    strategy: "metered_entry_roundabout",
  },
  {
    n: "05",
    kicker: "Read the evidence",
    title: "Same cars. Different rule.",
    line: "One run of each, on identical traffic. Indicative, not a ranking.",
    strategy: "metered_entry_roundabout",
    evidence: true,
  },
];

function lerp(a: number, b: number, k: number): number {
  return a + (b - a) * k;
}

/** The pinned story: one junction, one set of recorded cars, and the control
 *  changes as you scroll. Under reduced motion it becomes a plain tab viewer
 *  with a still frame. */
export function Story() {
  const data = useSceneData();
  const light = useSceneTheme() === "light";
  const reduced = useReducedMotion() ?? false;
  const track = useRef<HTMLElement | null>(null);
  const [index, setIndex] = useState(0);
  const chapter = CHAPTERS[index];
  const clock = useSimClock(!reduced, 1, reduced ? 24 : 6);
  const camera = useRef<Camera>({
    yaw: -38,
    elev: 40,
    zoom: 1,
    shiftY: 0.02,
    shiftX: 0.02,
  });
  const hud = useHud(data, chapter.strategy, clock);

  const { scrollYProgress } = useScroll({
    target: track,
    offset: ["start start", "end end"],
  });
  const smooth = useSpring(scrollYProgress, {
    stiffness: 90,
    damping: 26,
    mass: 0.4,
  });

  const aim = useCallback(
    (p: number) => {
      const c = camera.current;
      const narrow = window.innerWidth < 900;
      c.yaw = lerp(-40, 14, p);
      c.elev = lerp(38, 52, p);
      c.zoom = narrow ? 0.85 : lerp(1, 1.12, p);
      c.shiftX = narrow ? 0 : 0.02;
      c.shiftY = narrow ? -0.12 : 0.02;
    },
    [camera],
  );

  useMotionValueEvent(smooth, "change", (p) => {
    if (reduced) return;
    aim(p);
  });
  useMotionValueEvent(scrollYProgress, "change", (p) => {
    if (reduced) return;
    const next = Math.min(CHAPTERS.length - 1, Math.floor(p * CHAPTERS.length));
    setIndex((cur) => (cur === next ? cur : next));
  });
  useEffect(() => {
    aim(reduced ? 0.25 : smooth.get());
  }, [aim, reduced, smooth]);

  const jump = (i: number) => {
    const el = track.current;
    if (!el) return;
    if (reduced) {
      setIndex(i);
      return;
    }
    const range = el.offsetHeight - window.innerHeight;
    const top =
      el.getBoundingClientRect().top +
      window.scrollY +
      ((i + 0.5) / CHAPTERS.length) * range;
    window.scrollTo({ top, behavior: "smooth" });
  };

  const run = data?.runs[chapter.strategy];
  const colour = STRATEGY_COLOUR[chapter.strategy];

  return (
    <section
      className={`story${reduced ? " is-static" : ""}`}
      id="story"
      data-surface={light ? undefined : "dark"}
      aria-labelledby="story-title"
      ref={track}
    >
      <h2 id="story-title" className="sr-only">
        One junction under four control strategies
      </h2>
      <div className="story__stick">
        <div className="story__scene">
          {data ? (
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.div
                key={chapter.strategy}
                className="story__layer"
                initial={reduced ? false : { opacity: 0, scale: 1.04 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={reduced ? undefined : { opacity: 0 }}
                transition={{ duration: reduced ? 0 : 0.6 }}
              >
                <SimCanvas
                  data={data}
                  strategy={chapter.strategy}
                  clock={clock}
                  camera={camera}
                  label={`${STRATEGY_SHORT[chapter.strategy]} control on the recorded junction, replayed from the engine.`}
                  className="story__canvas"
                />
              </motion.div>
            </AnimatePresence>
          ) : null}
        </div>
        <div className="story__scrim" aria-hidden="true" />

        <div className="story__copy" aria-live="polite">
          <p
            className="story__kicker"
            style={{ color: STRATEGY_INK[chapter.strategy] }}
          >
            <span>{chapter.n}</span> {chapter.kicker}
          </p>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={chapter.n}
              initial={reduced ? false : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0, y: -10 }}
              transition={{ duration: reduced ? 0 : 0.35 }}
            >
              <h3 className="story__title display">{chapter.title}</h3>
              <p className="story__line">{chapter.line}</p>
            </motion.div>
          </AnimatePresence>
        </div>

        <aside className="story__card" aria-label="Measured results">
          {chapter.evidence && data ? (
            <EvidenceBars data={data} />
          ) : run ? (
            <>
              <div className="story__card-head">
                <span
                  className="story__swatch"
                  style={{ background: colour }}
                  aria-hidden="true"
                />
                <strong>{STRATEGY_SHORT[chapter.strategy]}</strong>
                <span className="story__live mono">
                  {hud.queued.toString()} queued now
                </span>
              </div>
              <QueueSpark
                run={run}
                second={hud.clock}
                colour={colour}
                label={`Vehicles queued over the 150 second run under ${STRATEGY_SHORT[chapter.strategy]}.`}
              />
              <p className="story__axis">
                Queue over the whole 150 s run, from the engine
              </p>
              <dl className="story__metrics">
                {METRIC_VIEW.map((m) => (
                  <div key={m.key}>
                    <dt>{m.label}</dt>
                    <dd className="mono">
                      <Counter
                        key={`${chapter.strategy}-${m.key}`}
                        value={run.metrics[m.key] ?? null}
                        digits={m.digits}
                      />
                      <small>{m.unit}</small>
                    </dd>
                  </div>
                ))}
              </dl>
            </>
          ) : (
            <p className="story__axis">Loading the recorded run…</p>
          )}
        </aside>

        <nav className="story__nav" aria-label="Story chapters">
          {CHAPTERS.map((c, i) => (
            <button
              key={c.n}
              type="button"
              className={i === index ? "is-on" : ""}
              aria-current={i === index ? "step" : undefined}
              onClick={() => {
                jump(i);
              }}
            >
              <span className="mono">{c.n}</span>
              <span className="story__nav-label">{c.kicker}</span>
            </button>
          ))}
        </nav>
      </div>
    </section>
  );
}

/** The four recorded runs side by side on the headline measures. */
function EvidenceBars({
  data,
}: {
  data: NonNullable<ReturnType<typeof useSceneData>>;
}) {
  return (
    <div className="story__evidence">
      <p className="story__axis">Whole run, one seed</p>
      {METRIC_VIEW.map((m) => {
        const values = STRATEGY_IDS.map(
          (id) => data.runs[id].metrics[m.key] ?? 0,
        );
        const top = Math.max(...values, 0.0001);
        return (
          <div key={m.key} className="ebars">
            <p className="ebars__label">
              {m.label}
              <small>
                {m.better === "lower" ? "lower is better" : "higher is better"}
              </small>
            </p>
            {STRATEGY_IDS.map((id, i) => {
              const v = values[i] ?? 0;
              return (
                <div key={id} className="ebars__row">
                  <span className="ebars__name">{STRATEGY_SHORT[id]}</span>
                  <span className="ebars__track">
                    <motion.span
                      className="ebars__fill"
                      style={{ background: STRATEGY_COLOUR[id] }}
                      initial={{ width: 0 }}
                      animate={{ width: `${((v / top) * 100).toFixed(1)}%` }}
                      transition={{
                        duration: 0.9,
                        delay: 0.1 * i,
                        ease: [0.2, 0.8, 0.2, 1],
                      }}
                    />
                  </span>
                  <span className="ebars__value mono">
                    {v.toFixed(m.digits)}
                  </span>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
