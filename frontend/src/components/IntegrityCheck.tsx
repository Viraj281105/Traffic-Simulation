import { useState } from "react";
import { API_BASE_URL } from "../config";

/** Result of POST /api/v1/study/validate/repeatability
 *  (backend/src/study/validation.py run_invariant_checks). */
interface IntegrityResult {
  valid: boolean;
  isDeterministic: boolean;
  ticksTested: number;
  violations: string[];
}

/**
 * Runs the backend's model-integrity checks: vehicle conservation and
 * non-negative speeds on every tick, plus a same-seed re-run that must
 * reproduce the same metrics.
 */
export function IntegrityCheck() {
  const [state, setState] = useState<
    | { kind: "idle" }
    | { kind: "running" }
    | { kind: "done"; result: IntegrityResult }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  const run = () => {
    setState({ kind: "running" });
    fetch(`${API_BASE_URL}/api/v1/study/validate/repeatability`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status.toString()}`);
        return r.json() as Promise<IntegrityResult>;
      })
      .then((result) => {
        setState({ kind: "done", result });
      })
      .catch((e: unknown) => {
        setState({
          kind: "error",
          message: e instanceof Error ? e.message : "Request failed",
        });
      });
  };

  return (
    <section className="integrity-card" aria-labelledby="integrity-title">
      <div className="integrity-head">
        <div>
          <h3 id="integrity-title">Model integrity check</h3>
          <p>
            Steps both controls for 20 s of simulated time, checking on every
            tick that no vehicle is lost or created and no speed is negative,
            then re-runs the same seed and confirms the metrics match.
          </p>
        </div>
        <button
          type="button"
          className="pb-btn pb-secondary"
          onClick={run}
          disabled={state.kind === "running"}
        >
          {state.kind === "running" ? "Checking…" : "Run integrity check"}
        </button>
      </div>

      <div aria-live="polite">
        {state.kind === "error" && (
          <p className="integrity-result bad" role="alert">
            The check could not run ({state.message}).
          </p>
        )}
        {state.kind === "done" && (
          <div className="integrity-result">
            <ul>
              <li className={state.result.valid ? "ok" : "bad"}>
                {state.result.valid ? "✓" : "✗"} All invariants held over{" "}
                {state.result.ticksTested.toLocaleString()} ticks
              </li>
              <li className={state.result.isDeterministic ? "ok" : "bad"}>
                {state.result.isDeterministic ? "✓" : "✗"} Same seed reproduced
                the same delay and throughput
              </li>
            </ul>
            {state.result.violations.length > 0 && (
              <details>
                <summary>
                  {state.result.violations.length.toLocaleString()} violation
                  {state.result.violations.length === 1 ? "" : "s"}
                </summary>
                <ul className="integrity-violations">
                  {state.result.violations.slice(0, 20).map((v) => (
                    <li key={v}>{v}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
