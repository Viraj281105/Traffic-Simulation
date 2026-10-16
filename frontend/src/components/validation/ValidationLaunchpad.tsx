import { FlaskConical, Microscope, Zap } from "lucide-react";

/** The empty state: three ready-made study sizes. */
export function ValidationLaunchpad({
  onLaunchPreset,
}: {
  onLaunchPreset: (seeds: number, duration: number) => void;
}) {
  const handleLaunchPreset = onLaunchPreset;
  return (
    <div className="validation-empty-card">
      <div className="empty-icon-halo">
        <Microscope size={26} strokeWidth={1.7} aria-hidden="true" />
      </div>
      <h3>Stochastic Validation Engine Ready</h3>
      <p className="empty-desc">
        A single run reflects one random arrival sequence. Monte Carlo
        validation repeats the comparison over several seeds (both controls
        share each seed) and tests whether the differences in mean delay,
        throughput and queue are statistically significant, with 95% confidence
        intervals.
      </p>

      <div className="preflight-grid">
        <button
          type="button"
          className="preflight-card"
          onClick={() => {
            handleLaunchPreset(3, 120);
          }}
        >
          <div className="preflight-header">
            <span className="preflight-badge quick">
              <Zap size={14} aria-hidden="true" className="uf-glyph" /> Quick
              Check
            </span>
            <span className="preflight-time">~15s</span>
          </div>
          <h4>3 Seeds × 120 Seconds</h4>
          <p>
            A fast look at seed-to-seed variation. Too few seeds for strong
            conclusions.
          </p>
          <span className="preflight-cta">Launch Quick Check →</span>
        </button>

        <button
          type="button"
          className="preflight-card featured"
          onClick={() => {
            handleLaunchPreset(5, 240);
          }}
        >
          <div className="preflight-header">
            <span className="preflight-badge standard">
              <FlaskConical size={14} aria-hidden="true" className="uf-glyph" />{" "}
              Recommended
            </span>
            <span className="preflight-time">~40s</span>
          </div>
          <h4>5 Seeds × 240 Seconds</h4>
          <p>
            A reasonable default: enough seeds for a first Welch t-test, still
            quick to run.
          </p>
          <span className="preflight-cta">Launch Standard Rigor →</span>
        </button>

        <button
          type="button"
          className="preflight-card"
          onClick={() => {
            handleLaunchPreset(10, 300);
          }}
        >
          <div className="preflight-header">
            <span className="preflight-badge rigor">
              <Microscope size={14} aria-hidden="true" className="uf-glyph" />{" "}
              High Rigor
            </span>
            <span className="preflight-time">~2 min</span>
          </div>
          <h4>10 Seeds × 300 Seconds</h4>
          <p>
            More seeds and longer runs give narrower confidence intervals;
            slower to run.
          </p>
          <span className="preflight-cta">Launch High Rigor →</span>
        </button>
      </div>
    </div>
  );
}
