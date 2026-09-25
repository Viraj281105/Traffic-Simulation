import {
  useEffect,
  useState,
  type CSSProperties,
  type ComponentType,
} from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  BarChart3,
  Code2,
  Moon,
  Orbit,
  Sun,
  TrendingUp,
  Clock,
  BarChart2,
} from "lucide-react";

type IconComponent = ComponentType<{ size?: number; strokeWidth?: number }>;

const steps: { icon: IconComponent; title: string; body: string }[] = [
  {
    icon: Clock,
    title: "Describe your junction",
    body: "How busy it is, how many lanes each approach has, and how long to watch. No traffic-engineering terms needed; specialists can open every setting.",
  },
  {
    icon: BarChart2,
    title: "Watch both run",
    body: "A traffic signal and a roundabout run side by side on exactly the same vehicles, arriving at exactly the same moments. Only the control differs.",
  },
  {
    icon: BarChart3,
    title: "Read the results",
    body: "How long drivers wait, how much traffic gets through, how long queues get and whether every direction is treated alike, each in plain words with why it happened.",
  },
  {
    icon: TrendingUp,
    title: "Check and compare",
    body: "Repeat the comparison over new traffic patterns to see whether the difference holds up, then try busier or quieter traffic and read the scenarios side by side.",
  },
];

const buildings = [
  { w: "10%", h: "20%", x: "10%", y: "10%" },
  { w: "13%", h: "28%", x: "23%", y: "8%" },
  { w: "10%", h: "17%", x: "73%", y: "9%" },
  { w: "14%", h: "25%", x: "83%", y: "15%" },
  { w: "13%", h: "24%", x: "8%", y: "70%" },
  { w: "9%", h: "17%", x: "22%", y: "78%" },
  { w: "14%", h: "23%", x: "72%", y: "73%" },
  { w: "10%", h: "18%", x: "86%", y: "67%" },
];

// The everyday questions the results answer, with the measurement behind
// each (frontend/src/metrics/plainLanguage.ts PLAIN_METRIC_MAP). Names only:
// results come from running the simulation, not from this page.
const metricGroups = [
  {
    title: "For people using the junction",
    metrics: [
      {
        name: "How long do drivers wait?",
        unit: "seconds",
        desc: "Time lost per driver; the wait 1 in 20 exceed; stops",
      },
      {
        name: "How much gets through?",
        unit: "vehicles",
        desc: "Vehicles served from the same arrivals",
      },
      {
        name: "How long do queues get?",
        unit: "vehicles",
        desc: "Typical and longest queue; time congested",
      },
      {
        name: "Is every direction treated alike?",
        unit: "even / uneven",
        desc: "How waiting is shared between approaches",
      },
    ],
  },
  {
    title: "For judging the evidence",
    metrics: [
      {
        name: "Why did it happen?",
        unit: "explained",
        desc: "How each control works, and what this run showed",
      },
      {
        name: "How reliable is it?",
        unit: "repeat check",
        desc: "Does the difference hold across traffic patterns?",
      },
    ],
  },
  {
    title: "For specialists",
    metrics: [
      {
        name: "Every metric, on demand",
        unit: "30+",
        desc: "Delay distribution, TTC/PET, capacity, CSV export",
      },
      {
        name: "Research lab",
        unit: "tools",
        desc: "Traffic-level sweeps, Monte Carlo statistics, saved runs",
      },
    ],
  },
];

import { Reveal } from "./components/Reveal";

function App() {
  const [isLight, setIsLight] = useState(
    () => sessionStorage.getItem("signals-theme") === "light",
  );
  useEffect(() => {
    document.title = "UrbanFlow — Signal or roundabout?";
    document.documentElement.classList.toggle("light", isLight);
    document.documentElement.classList.toggle("dark", !isLight);
    sessionStorage.setItem("signals-theme", isLight ? "light" : "dark");
  }, [isLight]);

  const toggleTheme = () => {
    setIsLight((current) => !current);
  };

  return (
    <main className="site-shell">
      <header className="top-nav">
        <a className="brand" href="#top" data-testid="link-brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">URBANFLOW</span>
        </a>
        <nav className="nav-links" aria-label="Primary navigation">
          <a href="#how" data-testid="link-compare">
            How it works
          </a>
          <a href="#metrics" data-testid="link-metrics">
            What you learn
          </a>
          <a href="#method" data-testid="link-methodology">
            Method
          </a>
          <button
            className="theme-button"
            type="button"
            onClick={toggleTheme}
            aria-label={
              isLight ? "Switch to dark mode" : "Switch to light mode"
            }
            data-testid="button-theme-toggle"
          >
            {isLight ? <Moon size={15} /> : <Sun size={15} />}
          </button>
        </nav>
      </header>

      <section className="hero" id="top" aria-labelledby="hero-title">
        <div className="hero-grid">
          <div className="hero-copy">
            <div className="hero-kicker eyebrow">
              <span className="signal-dot" /> For anyone weighing up a junction
            </div>
            <Reveal>
              <h1 id="hero-title" className="display">
                SIGNAL OR
                <br />
                <em>ROUNDABOUT?</em>
                <br />
                TRY BOTH.
              </h1>
            </Reveal>
            <Reveal delay={0.2}>
              <p className="hero-sub">
                UrbanFlow runs a traffic signal and a roundabout side by side on
                the same virtual junction, with exactly the same cars, and shows
                in plain language how each handles your traffic, and how sure
                you can be. No traffic-engineering background needed.
              </p>
            </Reveal>
            <div className="hero-actions">
              <a
                className="primary-btn"
                href="/app/comparative"
                data-testid="link-explore-simulation"
              >
                Compare your junction <ArrowDownRight size={15} />
              </a>
              <a
                className="ghost-btn"
                href="#how"
                data-testid="link-read-method"
              >
                How it works <ArrowRight size={14} />
              </a>
            </div>
            <div className="hero-meta" aria-label="At a glance">
              <span>
                <strong className="mono">3</strong> steps: describe, watch, read
              </span>
              <span>
                <strong className="mono">Same</strong> cars for both
              </span>
              <span>
                <strong className="mono">No</strong> verdict: your call
              </span>
            </div>
          </div>
          <div
            className="hero-visual"
            aria-label="Animated isometric intersection visualization"
          >
            <div className="city-canvas">
              <div className="city-base" aria-hidden="true" />
              <div className="road-mark road-h" />
              <div className="road-mark road-v" />
              {buildings.map((building, index) => (
                <div
                  className={`building building-${String(index + 1)}`}
                  key={`${building.x}-${building.y}`}
                  style={
                    {
                      "--w": building.w,
                      "--h": building.h,
                      "--x": building.x,
                      "--y": building.y,
                    } as CSSProperties
                  }
                />
              ))}
              <span
                className="car one"
                style={{ "--car-color": "hsl(188 100% 61%)" } as CSSProperties}
                aria-hidden="true"
              />
              <span
                className="car two"
                style={{ "--car-color": "hsl(22 100% 69%)" } as CSSProperties}
                aria-hidden="true"
              />
              <span
                className="car three"
                style={{ "--car-color": "hsl(260 54% 72%)" } as CSSProperties}
                aria-hidden="true"
              />
              <span
                className="car four"
                style={{ "--car-color": "hsl(188 100% 61%)" } as CSSProperties}
                aria-hidden="true"
              />
              <span
                className="car five"
                style={{ "--car-color": "hsl(22 100% 69%)" } as CSSProperties}
                aria-hidden="true"
              />
              <span
                className="car six"
                style={{ "--car-color": "hsl(188 100% 61%)" } as CSSProperties}
                aria-hidden="true"
              />
              <div className="radar" />
            </div>
          </div>
        </div>
        <div className="scroll-cue">
          <span className="scroll-line" /> Scroll to see how it works
        </div>
      </section>

      <section
        className="section-wrap section-space"
        id="compare"
        aria-labelledby="compare-title"
      >
        <Reveal>
          <div className="section-heading">
            <div>
              <div className="eyebrow">01 / The premise</div>
              <h2 id="compare-title" className="display">
                Two rules.
                <br />
                One junction.
              </h2>
            </div>
            <p>
              Same junction, same traffic, same drivers. The only difference is
              the rule that decides who goes next.
            </p>
          </div>
        </Reveal>
        <div className="compare-grid">
          <article
            className="strategy-card signal"
            data-testid="card-signal-control"
          >
            <div className="strategy-tag">
              <span className="strategy-index">CONTROL 01</span>
              <span>FIXED-TIME</span>
            </div>
            <h3 className="display">
              Signal
              <br />
              control
            </h3>
            <p>
              Each direction gets a fixed turn on green. Predictable, but a
              driver arriving on red waits even when the road is empty.
            </p>
            <div className="mini-intersection signal-mini" aria-hidden="true">
              <span className="mini-road mini-road-h" />
              <span className="mini-road mini-road-v" />
              <span className="mini-building mini-building-a" />
              <span className="mini-building mini-building-b" />
              <span className="mini-building mini-building-c" />
              <span className="mini-signal-light" />
            </div>
          </article>
          <article
            className="strategy-card roundabout"
            data-testid="card-roundabout-control"
          >
            <div className="strategy-tag">
              <span className="strategy-index">CONTROL 02</span>
              <span>MODERN</span>
            </div>
            <h3 className="display">
              Roundabout
              <br />
              control
            </h3>
            <p>
              No red lights. Drivers give way to circling traffic and go when
              there is a gap: smooth when it is quiet, queues when gaps run out.
            </p>
            <div
              className="mini-intersection roundabout-mini"
              aria-hidden="true"
            >
              <span className="mini-road mini-road-h" />
              <span className="mini-road mini-road-v" />
              <span className="mini-building mini-building-a" />
              <span className="mini-building mini-building-b" />
              <span className="mini-building mini-building-c" />
              <span className="mini-roundabout-ring" />
            </div>
          </article>
        </div>
      </section>

      <section
        className="capabilities section-space"
        id="how"
        aria-labelledby="capabilities-title"
      >
        <Reveal width="100%">
          <div className="section-wrap">
            <div className="section-heading">
              <div>
                <div className="eyebrow">02 / How it works</div>
                <h2 id="capabilities-title" className="display">
                  Four steps
                  <br />
                  <em>to evidence.</em>
                </h2>
              </div>
              <p>
                One guided path from your question to results you can explain to
                others, with every technical detail there if you want it.
              </p>
            </div>
            <div className="capability-grid">
              {steps.map(({ icon: Icon, title, body }, index) => (
                <article
                  className="capability"
                  key={title}
                  data-testid={`card-capability-${String(index)}`}
                >
                  <div className="capability-index mono">0{index + 1}</div>
                  <div className="capability-icon">
                    <Icon size={24} strokeWidth={1.5} />
                  </div>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </article>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      <section
        className="section-wrap section-space metrics-section"
        id="metrics"
        aria-labelledby="metrics-title"
      >
        <Reveal width="100%">
          <div className="metrics-layout">
            <div className="metrics-intro">
              <div className="eyebrow">03 / What you learn</div>
              <h2 id="metrics-title" className="display">
                Plain answers,
                <br />
                <em>full evidence.</em>
              </h2>
              <p>
                Results are written as answers to everyday questions, each with
                the measurement behind it one click away. Which option does
                better depends on your traffic and layout: UrbanFlow shows the
                evidence and leaves the decision to you.
              </p>
              <div className="hero-actions" style={{ marginTop: 30 }}>
                <a
                  className="ghost-btn"
                  href="/app/comparative"
                  data-testid="link-see-result"
                >
                  Start a comparison <ArrowDownRight size={14} />
                </a>
              </div>
            </div>
            <div className="metric-list">
              {metricGroups.map((group) => (
                <div className="metric-group" key={group.title}>
                  <div className="metric-group-title">{group.title}</div>
                  {group.metrics.map((metric) => (
                    <div
                      className="metric-row"
                      key={metric.name}
                      data-testid={`metric-row-${metric.name.toLowerCase().replace(/ /g, "-")}`}
                    >
                      <span className="metric-name">{metric.name}</span>
                      <span className="metric-value">{metric.unit}</span>
                      <span className="metric-desc">{metric.desc}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      <section
        className="section-wrap section-space"
        id="method"
        aria-labelledby="method-title"
      >
        <Reveal width="100%">
          <div className="methodology">
            <div className="methodology-copy">
              <div className="eyebrow">
                04 / Under the hood, for specialists
              </div>
              <h2 id="method-title" className="display">
                Make the
                <br />
                <em>invisible</em>
                <br />
                count.
              </h2>
              <p>
                UrbanFlow turns a familiar planning argument into a repeatable
                experiment. Identical arrival sequences (same random seed) enter
                the same geometry; an Intelligent Driver Model drives every
                vehicle; the controller is the only variable. The model is
                calibrated for one lane per approach and does not include
                pedestrians, cyclists, heavy vehicles or crash risk.
              </p>
              <p>
                Every stop, delay and queue is recorded; a saved run keeps its
                exact settings, seed and code version, and the Research lab adds
                traffic-level sweeps and Monte Carlo statistics.
              </p>
            </div>
            <div className="tech-stack" aria-label="Technology context">
              <div className="tech-item">
                <strong>
                  <Code2 size={18} />
                </strong>
                <span>
                  Python simulation core
                  <br />
                  reproducible scenarios
                </span>
              </div>
              <div className="tech-item">
                <strong>
                  <Activity size={18} />
                </strong>
                <span>
                  IDM vehicle dynamics
                  <br />
                  car-following &amp; braking
                </span>
              </div>
              <div className="tech-item">
                <strong>
                  <Orbit size={18} />
                </strong>
                <span>
                  Agent-based flow
                  <br />
                  lane-level interaction
                </span>
              </div>
              <div className="tech-item">
                <strong>
                  <BarChart3 size={18} />
                </strong>
                <span>
                  Metric pipeline
                  <br />
                  computed server-side
                </span>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      <section className="section-wrap final-cta" aria-labelledby="final-title">
        <Reveal width="100%">
          <div className="eyebrow">05 / Your next junction</div>
          <h2 id="final-title" className="display">
            Before the concrete,
            <br />
            <em>the evidence.</em>
          </h2>
          <p>
            Describe your junction and see how a signal and a roundabout would
            handle its traffic.
          </p>
          <a
            className="primary-btn"
            href="/app/comparative"
            data-testid="link-run-another-scenario"
          >
            Compare your junction <ArrowRight size={15} />
          </a>
        </Reveal>
      </section>

      <footer className="footer">
        <div className="section-wrap footer-inner">
          <span>URBANFLOW — SIGNAL OR ROUNDABOUT, TESTED</span>
          <span>EVIDENCE FOR THE PEOPLE WHO DECIDE</span>
        </div>
      </footer>
    </main>
  );
}

export default App;
