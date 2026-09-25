export type GuidedStage = "setup" | "watch" | "results";

const STEPS: { stage: GuidedStage; label: string }[] = [
  { stage: "setup", label: "Your junction" },
  { stage: "watch", label: "Watch both run" },
  { stage: "results", label: "Results" },
];

/** The three steps of a comparison. Any step can be revisited; Results
 *  unlocks once there is something to read. */
export function StepNav({
  stage,
  onChange,
  resultsAvailable,
}: {
  stage: GuidedStage;
  onChange: (stage: GuidedStage) => void;
  resultsAvailable: boolean;
}) {
  return (
    <nav className="step-nav" aria-label="Comparison steps">
      <ol>
        {STEPS.map((step, i) => {
          const current = step.stage === stage;
          const disabled = step.stage === "results" && !resultsAvailable;
          return (
            <li key={step.stage}>
              <button
                type="button"
                className={`step-btn${current ? " is-current" : ""}`}
                aria-current={current ? "step" : undefined}
                disabled={disabled}
                title={
                  disabled
                    ? "Results appear once the warm-up is over and vehicles have got through"
                    : undefined
                }
                onClick={() => {
                  onChange(step.stage);
                }}
              >
                <span className="step-index" aria-hidden="true">
                  {i + 1}
                </span>
                {step.label}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
