import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowRight, Check } from "lucide-react";
import {
  AnimatePresence,
  motion,
  useInView,
  useReducedMotion,
} from "framer-motion";
import { Reveal } from "../components/Reveal";
import { VIEW_ROUTES } from "../../routing";

const QUESTION =
  "Compare a conventional roundabout, a signalised roundabout and an adaptive signal under highly aggressive driving and uneven peak-hour demand.";

/** Reveals `text` one character at a time once on screen. */
function useTyped(text: string, active: boolean, reduced: boolean): string {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (reduced || !active) return;
    const id = window.setInterval(() => {
      setN((v) => {
        if (v >= text.length) {
          window.clearInterval(id);
          return v;
        }
        return v + 2;
      });
    }, 22);
    return () => {
      window.clearInterval(id);
    };
  }, [text, active, reduced]);
  return reduced ? text : text.slice(0, n);
}

// An example proposal as the rule-based assistant returned it for the
// question above (Plan → Experiment Copilot).
const PROPOSAL: [string, string][] = [
  ["Alternatives", "roundabout, adaptive, signalised_roundabout"],
  ["Baseline", "roundabout"],
  ["Driver aggression", "high"],
  ["Demand", "peak"],
  ["Uneven demand", "yes"],
  ["Primary indicator", "averageDelay"],
];

function CopilotVisual() {
  const ref = useRef<HTMLDivElement | null>(null);
  const inView = useInView(ref, { once: true, margin: "-15%" });
  const reduced = useReducedMotion() ?? false;
  const typed = useTyped(QUESTION, inView, reduced);
  const done = typed.length >= QUESTION.length;
  return (
    <div ref={ref} className="pv">
      <div className="pv__prompt">
        <span className="pv__label">Your question</span>
        <p>
          {typed}
          {!done ? <i className="pv__caret" aria-hidden="true" /> : null}
        </p>
      </div>
      <motion.ul
        className="pv__fields"
        initial={false}
        animate={done ? "on" : "off"}
        variants={{
          on: { transition: { staggerChildren: reduced ? 0 : 0.09 } },
          off: {},
        }}
      >
        {PROPOSAL.map(([k, v]) => (
          <motion.li
            key={k}
            variants={{
              off: { opacity: reduced ? 1 : 0, x: reduced ? 0 : -10 },
              on: { opacity: 1, x: 0 },
            }}
          >
            <span>{k}</span>
            <strong>{v}</strong>
            <em>rule</em>
          </motion.li>
        ))}
      </motion.ul>
      <motion.div
        className="pv__confirm"
        initial={false}
        animate={{ opacity: done || reduced ? 1 : 0.25 }}
      >
        <span>
          <Check size={14} aria-hidden="true" /> Validated by the server
        </span>
        <span>Nothing runs until you confirm</span>
      </motion.div>
    </div>
  );
}

function DiscoveryVisual() {
  // A schematic of the method, not data: each column is a generation and the
  // cloud narrows toward a front.
  const gens = [0, 1, 2, 3, 4];
  const dots = (g: number) =>
    Array.from({ length: 9 }, (_, i) => {
      const spread = 1 - g * 0.18;
      const base = (i / 8) * 2 - 1;
      const wob = Math.sin(i * 12.9898 + g * 4.1) * 0.5;
      return {
        y: 50 - (base * 0.55 + wob * 0.3) * spread * 42 - g * 3,
        keep: i % 3 === 0,
      };
    });
  return (
    <div className="pv pv--disc">
      <svg
        viewBox="0 0 400 190"
        role="img"
        aria-label="Schematic: a population of candidate settings is evaluated generation after generation, the non-dominated ones are kept, and the final set is tested on seeds the search never saw."
      >
        {gens.map((g) => (
          <g key={g} transform={`translate(${(40 + g * 72).toString()},0)`}>
            <text x="0" y="178" textAnchor="middle" className="pv__tick">
              gen {g + 1}
            </text>
            {dots(g).map((d, i) => (
              <circle
                key={i}
                cx={(i % 3) * 8 - 8}
                cy={d.y * 1.6 + 8}
                r={d.keep ? 4.5 : 3}
                className={d.keep ? "pv__dot is-keep" : "pv__dot"}
                style={{
                  animationDelay: `${(g * 0.25 + i * 0.05).toFixed(2)}s`,
                }}
              />
            ))}
          </g>
        ))}
        <path d="M30 120 C120 96 220 84 372 52" className="pv__front" />
      </svg>
      <ol className="pv__steps">
        <li>Evolve candidate settings</li>
        <li>Keep the non-dominated set</li>
        <li>Test on held-out seeds, against unchanged baselines</li>
      </ol>
    </div>
  );
}

// The eight scenario families of the stress generator (stress-v1) and the
// failure classes the lab reports.
const FAMILIES = [
  "Uneven directional split",
  "Extreme turning",
  "High aggression",
  "Heavy-vehicle mixes",
  "Near capacity",
  "Over capacity",
  "Three-arm junctions",
  "Extra ring lanes",
];
const FAILURES: [string, string][] = [
  ["collision", "any collision in the run"],
  ["gridlock", "fewer than 5% of spawned vehicles finished"],
  ["vehicle_limit", "the run hit the engine's vehicle limit"],
  ["starvation", "directional fairness index below 0.3"],
  ["excessive_queue", ""],
  ["spillback", ""],
];

function StressVisual() {
  return (
    <div className="pv pv--stress">
      <div className="pv__chips">
        {FAMILIES.map((f, i) => (
          <span key={f} style={{ animationDelay: `${(i * 0.07).toFixed(2)}s` }}>
            {f}
          </span>
        ))}
      </div>
      <ul className="pv__fail">
        {FAILURES.map(([name, rule]) => (
          <li key={name}>
            <code>{name}</code>
            {rule ? <span>{rule}</span> : null}
          </li>
        ))}
      </ul>
      <p className="pv__foot">
        Stationary extremes only: no surges, incidents or closures.
      </p>
    </div>
  );
}

function PlannerVisual() {
  const cols = ["Fixed-time", "Adaptive", "Roundabout"];
  return (
    <div className="pv pv--plan">
      <div
        className="pv__matrix"
        role="img"
        aria-label="Each seed is run once under every control, so every control sees the same arrivals."
      >
        <span />
        {cols.map((c) => (
          <b key={c}>{c}</b>
        ))}
        {[1, 2, 3].map((s) => (
          <div key={s} className="pv__row">
            <i>Seed {s}</i>
            {cols.map((c) => (
              <span key={c} className="pv__cell" />
            ))}
          </div>
        ))}
      </div>
      <p className="pv__foot">
        Same arrivals for every control. Differences are paired per seed and
        reported with their uncertainty; the Planner does not rank or recommend.
      </p>
    </div>
  );
}

interface Tab {
  id: string;
  label: string;
  title: string;
  body: string;
  badge?: string;
  href: string;
  visual: ReactNode;
}

const TABS: Tab[] = [
  {
    id: "copilot",
    label: "Experiment Copilot",
    title: "Ask in words. Review before anything runs.",
    body: "The assistant turns a question into an experiment the server has already validated. A model never writes or runs it.",
    badge: "Rule-based; AI optional",
    href: VIEW_ROUTES.copilot,
    visual: <CopilotVisual />,
  },
  {
    id: "discovery",
    label: "Discovery Lab",
    title: "Search settings, judge on unseen seeds.",
    body: "A bounded evolutionary search for one regime you declare. Results are experimental and compared with the unchanged baselines.",
    badge: "Experimental",
    href: VIEW_ROUTES.discovery,
    visual: <DiscoveryVisual />,
  },
  {
    id: "stress",
    label: "Stress Lab",
    title: "Find where a control breaks.",
    body: "Reproducible hard scenarios, classified failures per strategy, and a breakpoint explorer for where the lowest-delay strategy changes.",
    href: VIEW_ROUTES.stress,
    visual: <StressVisual />,
  },
  {
    id: "planner",
    label: "Planner",
    title: "Matched seeds, honest intervals.",
    body: "Compare alternatives for one junction on the same simulated traffic and read the differences with their uncertainty.",
    href: VIEW_ROUTES.planner,
    visual: <PlannerVisual />,
  },
];

/** The experimentation tools, each with a visual of how it works. */
export function Platform() {
  const [active, setActive] = useState(0);
  const reduced = useReducedMotion() ?? false;
  const tab = TABS[active];
  return (
    <section
      className="platform section-wrap"
      id="platform"
      aria-labelledby="platform-title"
    >
      <Reveal width="100%">
        <div className="studio__head">
          <div>
            <p className="eyebrow">Experimentation platform</p>
            <h2 id="platform-title" className="display">
              From one run
              <br />
              <em>to robust evidence.</em>
            </h2>
          </div>
          <p className="studio__note">
            Four tools in the Plan section, each built to say what it cannot
            show.
          </p>
        </div>
        <div
          className="platform__tabs"
          role="tablist"
          aria-label="Experimentation tools"
        >
          {TABS.map((t, i) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={i === active}
              aria-controls={`panel-${t.id}`}
              tabIndex={i === active ? 0 : -1}
              className={i === active ? "is-on" : ""}
              onClick={() => {
                setActive(i);
              }}
              onKeyDown={(e) => {
                if (e.key === "ArrowRight")
                  setActive((active + 1) % TABS.length);
                if (e.key === "ArrowLeft")
                  setActive((active + TABS.length - 1) % TABS.length);
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div
          className="platform__stage"
          role="tabpanel"
          id={`panel-${tab.id}`}
          aria-labelledby={`tab-${tab.id}`}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={tab.id}
              className="platform__grid"
              initial={reduced ? false : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0 }}
              transition={{ duration: reduced ? 0 : 0.3 }}
            >
              <div className="platform__visual">{tab.visual}</div>
              <div className="platform__copy">
                {tab.badge ? (
                  <span className="lp-badge">{tab.badge}</span>
                ) : null}
                <h3>{tab.title}</h3>
                <p>{tab.body}</p>
                <a
                  className="platform__link"
                  href={tab.href}
                  data-testid={`feature-${tab.id}`}
                >
                  Open {tab.label} <ArrowRight size={14} aria-hidden="true" />
                </a>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </Reveal>
    </section>
  );
}
