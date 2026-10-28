import { useEffect, useRef } from "react";
import { ArrowRight, KeyRound, ShieldAlert } from "lucide-react";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { Reveal } from "../components/Reveal";
import { VIEW_ROUTES } from "../../routing";
import { useSceneData } from "../scene/SceneContext";
import { SimCanvas } from "../scene/SimCanvas";
import { useSimClock } from "../scene/clock";
import type { Camera } from "../scene/render";

// The token scopes of the API (services/v3/tokens.ts). Not imported from
// there so the landing page does not load the sign-in code.
const SCOPES = [
  "experiments:read",
  "experiments:run",
  "packages:read",
  "packages:write",
  "tokens:read",
  "tokens:manage",
] as const;

const TERMINAL: { prompt: string; text: string; note?: string }[] = [
  { prompt: "$", text: "pip install ./sdk/python" },
  {
    prompt: "$",
    text: "export URBANFLOW_TOKEN=uf_pat_…",
    note: "created in the app, shown once",
  },
  { prompt: ">>>", text: "api = Client(URL, TOKEN)" },
  { prompt: ">>>", text: "api.validate(experiment)", note: "no work is done" },
  { prompt: ">>>", text: "result = api.run(experiment, on_progress=print)" },
  { prompt: ">>>", text: 'api.export_package(experiment_id, "run.ufpkg")' },
  {
    prompt: ">>>",
    text: 'report = api.verify_package("run.ufpkg")',
    note: "integrity, not authenticity",
  },
];

/** The Python client and personal access tokens. */
export function Developers() {
  const reduced = useReducedMotion() ?? false;
  const termRef = useRef<HTMLDivElement | null>(null);
  const termIn = useInView(termRef, { once: true, margin: "-15%" });
  return (
    <section
      className="devs section-wrap"
      id="developers"
      aria-labelledby="developers-title"
    >
      <Reveal width="100%">
        <div className="devs__grid">
          <div>
            <p className="eyebrow">Developer platform</p>
            <h2 id="developers-title" className="display">
              Run it
              <br />
              <em>from code.</em>
            </h2>
            <p className="devs__lead">
              Personal access tokens, a standard-library Python client and a
              command line for the same experiments.
            </p>
            <ul className="devs__scopes" aria-label="Token permissions">
              {SCOPES.map((s) => (
                <li key={s}>
                  <code>{s}</code>
                </li>
              ))}
            </ul>
            <p className="devs__facts">
              1 to 90 day lifetime · revoked at once · limited to 60 requests a
              minute each
            </p>
            <a
              className="pb-btn pb-secondary pb-lg"
              href={VIEW_ROUTES.tokens}
              data-testid="link-create-token"
            >
              <KeyRound size={16} aria-hidden="true" /> Create a token
            </a>
          </div>
          <div
            className="term"
            role="img"
            aria-label="A terminal session: install the client, export a token, validate and run an experiment, export a package and verify it."
          >
            <div className="term__bar" aria-hidden="true">
              <i />
              <i />
              <i />
              <span>urbanflow_client</span>
            </div>
            <motion.div
              ref={termRef}
              className="term__body"
              initial="off"
              animate={termIn || reduced ? "on" : "off"}
              variants={{
                off: {},
                on: { transition: { staggerChildren: reduced ? 0 : 0.28 } },
              }}
            >
              {TERMINAL.map((l) => (
                <motion.p
                  key={l.text}
                  variants={{
                    off: { opacity: reduced ? 1 : 0, x: reduced ? 0 : -8 },
                    on: { opacity: 1, x: 0 },
                  }}
                >
                  <b>{l.prompt}</b> {l.text}
                  {l.note ? <em> # {l.note}</em> : null}
                </motion.p>
              ))}
            </motion.div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

// What UrbanFlow does not claim (docs/v3-release-candidate.md, claims register).
const LIMITS = [
  [
    "A simulator, not the street",
    "Results describe robustness under stated assumptions in this simulator, not real-world performance.",
  ],
  [
    "Safety proxies, not forecasts",
    "Near misses and overlaps are model outputs, not a calibrated crash model.",
  ],
  [
    "Search is experimental",
    "Discovery candidates are never called best, optimal or recommended.",
  ],
  [
    "Stationary extremes",
    "Stress scenarios hold demand constant: no surges, incidents or closures.",
  ],
  [
    "You confirm, the server checks",
    "A model never writes or runs an experiment on its own.",
  ],
  [
    "Integrity is not authenticity",
    "A verified package is internally consistent; it does not prove who made it.",
  ],
] as const;

export function Limits() {
  return (
    <section
      className="limits section-wrap"
      id="limits"
      aria-labelledby="limits-title"
    >
      <Reveal width="100%">
        <div className="limits__head">
          <ShieldAlert size={18} aria-hidden="true" />
          <h2 id="limits-title">What it does not claim</h2>
        </div>
        <ul className="limits__grid">
          {LIMITS.map(([t, b]) => (
            <li key={t}>
              <h3>{t}</h3>
              <p>{b}</p>
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  );
}

/** Closing call to action over the metered-entry roundabout, slowly orbiting. */
export function FinalCta() {
  const data = useSceneData();
  const reduced = useReducedMotion() ?? false;
  const clock = useSimClock(!reduced, 1, reduced ? 30 : 12);
  const camera = useRef<Camera>({
    yaw: -20,
    elev: 34,
    zoom: 1.05,
    shiftY: -0.2,
    shiftX: 0,
  });
  useEffect(() => {
    if (reduced) return;
    let raf = 0;
    const loop = () => {
      camera.current.yaw = -20 + Math.sin(performance.now() / 7000) * 22;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
    };
  }, [reduced]);
  return (
    <section
      className="finale"
      data-surface="dark"
      aria-labelledby="final-title"
    >
      <div className="finale__scene" aria-hidden="true">
        {data ? (
          <SimCanvas
            data={data}
            strategy="metered_entry_roundabout"
            theme="dark"
            clock={clock}
            camera={camera}
            label=""
            className="finale__canvas"
            maxDpr={1.5}
          />
        ) : null}
      </div>
      <div className="finale__scrim" aria-hidden="true" />
      <Reveal width="100%">
        <div className="finale__copy">
          <h2 id="final-title" className="display">
            Open your own
            <br />
            <em>junction.</em>
          </h2>
          <p>Describe it, run it, and read the evidence.</p>
          <div className="hero-stage__actions">
            <a
              className="pb-btn pb-primary pb-lg"
              href={VIEW_ROUTES.comparative}
              data-testid="link-run-another-scenario"
            >
              Launch UrbanFlow <ArrowRight size={16} />
            </a>
            <a
              className="pb-btn pb-lg hero-stage__ghost"
              href={VIEW_ROUTES.planner}
              data-testid="link-plan-study"
            >
              Plan a study <ArrowRight size={16} />
            </a>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
