/** The statistics the study uses, with the run's own alpha and level. */
export function MethodologyTab({
  resultAlpha,
  resultLevelPct,
}: {
  resultAlpha: number;
  resultLevelPct: number;
}) {
  return (
    <div className="methodology-full-view">
      <div className="methodology-proof-grid">
        <div className="proof-card">
          <h4>1. Statistical Significance (Welch&apos;s Two-Sample Test)</h4>
          <p>
            Evaluates whether the difference between sample means μ₁ and μ₂
            exceeds what would be expected from chance alone under unequal
            variances (σ₁² ≠ σ₂²):
          </p>
          <div className="math-box">t = (X̄₁ - X̄₂) / √(s₁²/N₁ + s₂²/N₂)</div>
          <p className="proof-sub">
            Significance criterion: <strong>p &lt; {resultAlpha}</strong>{" "}
            (rejects H₀ at the {resultLevelPct}% level the run used). The test
            is unpaired even though both controls share seeds, which is the
            conservative choice.
          </p>
        </div>

        <div className="proof-card">
          <h4>2. Practical Magnitude (Cohen&apos;s d Effect Size)</h4>
          <p>
            Standardized metric indicating the real-world operational separation
            between the two traffic intersections independent of sample size N:
          </p>
          <div className="math-box">d = (X̄₁ - X̄₂) / s_pooled</div>
          <div className="effect-scale-pills">
            <span className="scale-pill neg">&lt;0.2 Negligible</span>
            <span className="scale-pill sm">0.2–0.5 Small</span>
            <span className="scale-pill med">0.5–0.8 Medium</span>
            <span className="scale-pill lg">&gt;0.8 Large Effect</span>
          </div>
        </div>

        <div className="proof-card">
          <h4>3. Confidence intervals (Student-t)</h4>
          <p>
            A range around each mean that should contain the long-run mean in
            the stated share of repeated studies. The t-distribution is used
            because only a few seeds are run (at N = 5 the 95% multiplier is
            2.776, not 1.96):
          </p>
          <div className="math-box">CI = X̄ ± t(N−1) × (s / √N)</div>
          <p className="proof-sub">
            Non-overlapping intervals are consistent with a real difference; the
            Welch test above is the formal check.
          </p>
        </div>
      </div>
    </div>
  );
}
