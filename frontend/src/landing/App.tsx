import { useEffect, useState } from "react";
import { ArrowRight, Moon, Sun } from "lucide-react";

const steps: { title: string; body: string }[] = [
  {
    title: "Describe your junction",
    body: "How busy it is, how many lanes each approach has, and how long to watch. Specialists can open every setting.",
  },
  {
    title: "Watch both run",
    body: "A traffic signal and a roundabout run side by side on the same vehicles, arriving at the same moments. Only the control differs.",
  },
  {
    title: "Read the results",
    body: "Time lost, traffic served, queue length and how evenly each direction is treated, each with the reason it happened.",
  },
  {
    title: "Check the result",
    body: "Repeat the comparison over new traffic patterns to see whether a difference holds, then try busier or quieter traffic.",
  },
];

// The everyday questions the results answer, with the measurement behind
// each (frontend/src/metrics/plainLanguage.ts PLAIN_METRIC_MAP). Names only:
// results come from running the simulation, not from this page.
const questions: { name: string; measure: string }[] = [
  {
    name: "How much time do drivers lose?",
    measure:
      "Extra travel time per driver, the 95th percentile, time nearly stopped, stops",
  },
  {
    name: "How much gets through?",
    measure: "Vehicles served from the same arrivals",
  },
  {
    name: "How long do queues get?",
    measure: "Typical and longest queue, time congested",
  },
  {
    name: "Is every direction treated alike?",
    measure: "How waiting is shared between approaches",
  },
  {
    name: "How reliable is the difference?",
    measure: "Repeat runs over new traffic patterns, Welch t-test",
  },
];

const limits = [
  "Calibrated for one lane per approach; two and three lanes are modelled but indicative.",
  "Cars only: no pedestrians, cyclists, buses or heavy vehicles.",
  "No crash-risk estimate: near-miss measures are indicators, not probabilities.",
  "Fixed-time signal only (no actuated or adaptive control).",
];

/** A static plan of the two junctions the product compares. */
function JunctionPlans() {
  return (
    <svg
      className="plans"
      viewBox="0 0 320 150"
      role="img"
      aria-label="Plan view of a signalised crossroads and a roundabout"
    >
      <g transform="translate(10 5)">
        <rect className="plan-road" x="55" y="0" width="30" height="140" />
        <rect className="plan-road" x="0" y="55" width="140" height="30" />
        <line className="plan-stop" x1="55" y1="52" x2="70" y2="52" />
        <line className="plan-stop" x1="70" y1="88" x2="85" y2="88" />
        <line className="plan-stop" x1="52" y1="70" x2="52" y2="85" />
        <line className="plan-stop" x1="88" y1="55" x2="88" y2="70" />
        <circle className="plan-signal" cx="92" cy="48" r="4" />
        <text className="plan-label" x="70" y="148" textAnchor="middle">
          Traffic signal
        </text>
      </g>
      <g transform="translate(170 5)">
        <rect className="plan-road" x="55" y="0" width="30" height="140" />
        <rect className="plan-road" x="0" y="55" width="140" height="30" />
        <circle className="plan-ring" cx="70" cy="70" r="32" />
        <circle className="plan-island" cx="70" cy="70" r="16" />
        <text className="plan-label" x="70" y="148" textAnchor="middle">
          Roundabout
        </text>
      </g>
    </svg>
  );
}

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

  return (
    <div className="site">
      <header className="site-header">
        <a className="brand" href="#top" data-testid="link-brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">URBANFLOW</span>
        </a>
        <nav className="site-nav" aria-label="Primary navigation">
          <a href="#how" data-testid="link-compare">
            How it works
          </a>
          <a href="#results" data-testid="link-metrics">
            Results
          </a>
          <a href="#method" data-testid="link-methodology">
            Method
          </a>
          <button
            className="uf-icon-btn theme-button"
            type="button"
            onClick={() => {
              setIsLight((current) => !current);
            }}
            aria-label={
              isLight ? "Switch to dark mode" : "Switch to light mode"
            }
            data-testid="button-theme-toggle"
          >
            {isLight ? <Moon /> : <Sun />}
          </button>
        </nav>
      </header>

      <main id="top">
        <section className="site-section hero" aria-labelledby="hero-title">
          <div className="hero-text">
            <p className="uf-eyebrow">Traffic simulation</p>
            <h1 id="hero-title" className="hero-title">
              Signal or roundabout? Run both under the same traffic.
            </h1>
            <p className="hero-lead">
              UrbanFlow simulates a fixed-time traffic signal and a roundabout
              on the same junction, with the same vehicles arriving at the same
              moments, and reports how each one handled that traffic. It does
              not pick a winner: which works better depends on the demand and
              the layout.
            </p>
            <div className="uf-page-actions">
              <a
                className="uf-btn uf-btn--primary"
                href="/app/comparative"
                data-testid="link-explore-simulation"
              >
                Compare a junction <ArrowRight aria-hidden="true" />
              </a>
              <a className="uf-btn" href="#how" data-testid="link-read-method">
                How it works
              </a>
            </div>
          </div>
          <div className="hero-figure">
            <JunctionPlans />
          </div>
        </section>

        <section className="site-section" id="how" aria-labelledby="how-title">
          <h2 id="how-title" className="uf-section-title">
            How it works
          </h2>
          <ol className="step-list">
            {steps.map((step, index) => (
              <li
                className="uf-card step"
                key={step.title}
                data-testid={`card-capability-${String(index)}`}
              >
                <span className="step-number" aria-hidden="true">
                  {index + 1}
                </span>
                <h3 className="uf-subsection-title">{step.title}</h3>
                <p className="uf-help">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section
          className="site-section"
          id="results"
          aria-labelledby="results-title"
        >
          <h2 id="results-title" className="uf-section-title">
            What the results answer
          </h2>
          <p className="section-lead">
            Each answer quotes the measurement behind it. Every metric, the
            charts and CSV exports are one level deeper, and the Research lab
            adds demand sweeps and repeated-run statistics.
          </p>
          <div className="uf-table-wrap">
            <table className="uf-table">
              <thead>
                <tr>
                  <th scope="col">Question</th>
                  <th scope="col">Measured as</th>
                </tr>
              </thead>
              <tbody>
                {questions.map((q) => (
                  <tr
                    key={q.name}
                    data-testid={`metric-row-${q.name.toLowerCase().replace(/ /g, "-")}`}
                  >
                    <th scope="row">{q.name}</th>
                    <td>{q.measure}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section
          className="site-section method"
          id="method"
          aria-labelledby="method-title"
        >
          <div>
            <h2 id="method-title" className="uf-section-title">
              Method
            </h2>
            <p className="section-lead">
              Every vehicle is driven by the Intelligent Driver Model. Both
              junctions get the same random arrivals (same seed), the same
              drivers (desired speeds around a 50 km/h limit) and the same
              curve-speed rule; the control is the only difference. A 30 s
              warm-up is excluded from the results, and a saved run keeps its
              settings, seed and code version so it can be reproduced.
            </p>
          </div>
          <div>
            <h3 className="uf-subsection-title">Limits</h3>
            <ul className="limit-list">
              {limits.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="site-section cta" aria-labelledby="cta-title">
          <h2 id="cta-title" className="uf-section-title">
            Try your junction
          </h2>
          <p className="section-lead">
            Choose how busy it is and how many lanes it has; the comparison
            takes two to ten minutes to watch.
          </p>
          <a
            className="uf-btn uf-btn--primary"
            href="/app/comparative"
            data-testid="link-run-another-scenario"
          >
            Compare a junction <ArrowRight aria-hidden="true" />
          </a>
        </section>
      </main>

      <footer className="site-footer">
        <span>UrbanFlow</span>
        <span>Traffic signal and roundabout comparison</span>
      </footer>
    </div>
  );
}

export default App;
