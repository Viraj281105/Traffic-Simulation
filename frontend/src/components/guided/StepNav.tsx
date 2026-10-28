import { Check } from "lucide-react";
import { useNavIndicator } from "../ui/useNavIndicator";

export type GuidedStage = "setup" | "watch" | "results";

/** "Watch it run", "Watch both run", "Watch all 3 run", … */
function watchLabel(count: number): string {
  if (count === 1) return "Watch it run";
  if (count === 2) return "Watch both run";
  return `Watch all ${String(count)} run`;
}

/** The three steps of a comparison. Any step can be revisited; Results
 *  unlocks once there is something to read. */
export function StepNav({
  stage,
  onChange,
  resultsAvailable,
  strategyCount = 2,
}: {
  stage: GuidedStage;
  onChange: (stage: GuidedStage) => void;
  resultsAvailable: boolean;
  /** How many strategies the comparison runs (names the watch step). */
  strategyCount?: number;
}) {
  const STEPS: { stage: GuidedStage; label: string }[] = [
    { stage: "setup", label: "Configure" },
    { stage: "watch", label: watchLabel(strategyCount) },
    { stage: "results", label: "Results" },
  ];
  const ref = useNavIndicator<HTMLElement>(stage);
  const currentIndex = STEPS.findIndex((s) => s.stage === stage);
  return (
    <nav className="step-nav" aria-label="Comparison steps" ref={ref}>
      <ol>
        {STEPS.map((step, i) => {
          const current = step.stage === stage;
          const passed = i < currentIndex;
          const disabled = step.stage === "results" && !resultsAvailable;
          return (
            <li key={step.stage}>
              {i > 0 && (
                <span
                  className={`step-connector${i <= currentIndex ? " is-done" : ""}`}
                  aria-hidden="true"
                />
              )}
              <button
                type="button"
                className={`step-btn${current ? " is-current" : ""}${passed ? " is-passed" : ""}`}
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
                  {passed ? <Check size={13} strokeWidth={2.6} /> : i + 1}
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
