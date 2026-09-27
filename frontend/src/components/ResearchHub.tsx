import { VIEW_ROUTES, followLink } from "../routing";
import { PLAIN_METRIC_MAP, metricDef } from "../metrics/plainLanguage";

const TOOLS: { href: string; title: string; body: string; use: string }[] = [
  {
    href: VIEW_ROUTES.volume,
    title: "Traffic-level sweep",
    body: "Runs both controls across a range of demand tiers, one random traffic pattern per tier, and plots delay, throughput and queue against volume, with where the lower-delay control changes and indicative level-of-service bands. Descriptive: use Statistical validation to test a difference.",
    use: "Where does the comparison change as traffic grows?",
  },
  {
    href: VIEW_ROUTES.validation,
    title: "Statistical validation",
    body: "Monte Carlo study on a configurable scenario: the same random patterns for both controls, Student-t confidence intervals, an unpaired Welch t-test, Cohen’s d, per-seed data and CSV export, plus model integrity checks on both geometries.",
    use: "Is a difference statistically robust for a study design?",
  },
  {
    href: VIEW_ROUTES.signal,
    title: "Signal on its own",
    body: "One fixed-time signal with its live metric set, phase state, queue labels and stop-line display.",
    use: "How does the signal behave in detail?",
  },
  {
    href: VIEW_ROUTES.roundabout,
    title: "Roundabout on its own",
    body: "One roundabout with its live metric set, circulating and yielding counts.",
    use: "How does the roundabout behave in detail?",
  },
  {
    href: VIEW_ROUTES.history,
    title: "Saved runs & reproducibility",
    body: "Every saved run with its exact configuration, seed, code version and metrics; re-run to check determinism, export JSON/CSV, compare up to six runs.",
    use: "Can this result be reproduced and audited?",
  },
];

/** Entry point for specialist tools. The guided comparison is the product's
 *  main path; these tools keep every research capability one click away. */
export function ResearchHub() {
  return (
    <div className="guided-page research-hub">
      <header className="guided-intro">
        <p className="guided-eyebrow">Research lab</p>
        <h1>Tools for deeper analysis</h1>
        <p>
          The guided comparison answers “how would a signal and a roundabout
          handle my junction?”. These tools are for going further: sweeping
          traffic levels, formal statistics, single-control detail and
          reproducibility. They use technical terms throughout.
        </p>
      </header>

      <div className="tool-grid">
        {TOOLS.map((tool) => (
          <a
            key={tool.href}
            className="tool-card"
            href={tool.href}
            onClick={(e) => {
              followLink(e, tool.href);
            }}
          >
            <span className="tool-use">{tool.use}</span>
            <span className="tool-title">{tool.title}</span>
            <span className="tool-body">{tool.body}</span>
          </a>
        ))}
      </div>

      <section className="results-section" aria-labelledby="map-title">
        <h2 id="map-title">How the guided results map to the metrics</h2>
        <p>
          The guided results translate a small set of catalog metrics into
          everyday questions. Every other metric remains in the “All
          measurements” table of each comparison and in exports.
        </p>
        <div className="multi-run-scroll">
          <table className="plain-table">
            <thead>
              <tr>
                <th scope="col">Everyday question</th>
                <th scope="col">What it shows</th>
                <th scope="col">Technical metrics</th>
              </tr>
            </thead>
            <tbody>
              {PLAIN_METRIC_MAP.map((row) => (
                <tr key={row.question}>
                  <th scope="row">{row.question}</th>
                  <td>{row.plain}</td>
                  <td>
                    {row.keys.map((key) => (
                      <span key={key} className="metric-key">
                        {metricDef(key).label} <code>{key}</code>
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
