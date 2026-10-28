import { BookOpen } from "lucide-react";

/** The hypotheses, criterion and effect-size scale, shown above the studio. */
export function MethodologyDrawer({ alpha }: { alpha: number }) {
  return (
    <div className="methodology-drawer">
      <div className="methodology-drawer-header">
        <h4>
          <BookOpen size={14} aria-hidden="true" className="uf-glyph" />{" "}
          Statistical Hypothesis & Testing Framework
        </h4>
        <span className="drawer-sub">
          Mathematical criteria for formal validation
        </span>
      </div>
      <div className="methodology-drawer-grid">
        <div className="methodology-card">
          <span className="method-tag null">H₀ Null Hypothesis</span>
          <h5>
            μ<sub>signal</sub> = μ<sub>roundabout</sub>
          </h5>
          <p>
            Assumes any gap is due to which vehicles happened to arrive when.
            Rejected (the difference is statistically supported) when{" "}
            <strong>p &lt; {alpha}</strong>. Not rejecting it does not show the
            controls are equal.
          </p>
        </div>

        <div className="methodology-card">
          <span className="method-tag alt">H₁ Alternative Hypothesis</span>
          <h5>
            μ<sub>signal</sub> ≠ μ<sub>roundabout</sub>
          </h5>
          <p>
            Means the difference is unlikely to be explained by arrival
            randomness alone, for this scenario and these seeds. It does not say
            which control is better, or that the result holds elsewhere.
          </p>
        </div>

        <div className="methodology-card">
          <span className="method-tag effect">Cohen&apos;s d Effect Size</span>
          <div className="effect-scale-grid">
            <span className="scale-pill neg">&lt;0.2 Negligible</span>
            <span className="scale-pill sm">0.2–0.5 Small</span>
            <span className="scale-pill med">0.5–0.8 Medium</span>
            <span className="scale-pill lg">&gt;0.8 Large</span>
          </div>
          <p className="effect-note">
            Quantifies practical real-world magnitude beyond statistical
            p-value.
          </p>
        </div>
      </div>
    </div>
  );
}
