import { useState } from "react";
import { API_BASE_URL } from "../config";

/** Result of POST /api/v1/study/validate/repeatability
 *  (backend/src/study/validation.py run_invariant_checks). */
interface GeometryIntegrity {
  valid: boolean;
  isDeterministic: boolean;
  violations: string[];
}

interface IntegrityResult {
  valid: boolean;
  isDeterministic: boolean;
  ticksTested: number;
  violations: string[];
  /** Each geometry is reported on its own: a pass on one is never read as a
   *  pass on both. */
  geometries?: { signal: GeometryIntegrity; roundabout: GeometryIntegrity };
  signalGreenExclusivityValid?: boolean;
  /** What the run actually checked, as stated by the backend. */
  checked?: string[];
}

const GEOMETRY_NAME = {
  signal: "Signal",
  roundabout: "Roundabout",
} as const;

/**
 * Runs the backend's model-integrity checks on BOTH the signal and the
 * roundabout engine: vehicle conservation and non-negative speeds on every
 * tick, no conflicting signal greens (signal), and a same-seed re-run that
 * must reproduce delay and throughput on each. Results are shown per
 * geometry.
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
            Steps both the signal and the roundabout for 20 s of simulated time.
            On every tick it checks, for each, that no vehicle is lost or
            created and no speed is negative, and that the signal never shows
            conflicting greens; then it re-runs the same seed and confirms each
            geometry reproduces its delay and throughput. It checks the
            simulation&apos;s internal consistency, not that its results match
            the real world.
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
              {(["signal", "roundabout"] as const).map((g) => {
                const r = state.result.geometries?.[g];
                const ok = r ? r.valid : state.result.valid;
                const det = r
                  ? r.isDeterministic
                  : state.result.isDeterministic;
                return (
                  <li key={g} className={ok && det ? "ok" : "bad"}>
                    {ok && det ? "✓" : "✗"} {GEOMETRY_NAME[g]}:{" "}
                    {ok
                      ? `all invariants held over ${state.result.ticksTested.toLocaleString()} ticks`
                      : "an invariant was violated"}
                    ;{" "}
                    {det
                      ? "same seed reproduced the same delay and throughput"
                      : "same seed did not reproduce delay and throughput"}
                  </li>
                );
              })}
              {state.result.signalGreenExclusivityValid !== undefined && (
                <li
                  className={
                    state.result.signalGreenExclusivityValid ? "ok" : "bad"
                  }
                >
                  {state.result.signalGreenExclusivityValid ? "✓" : "✗"} Signal:
                  no conflicting greens at the same time
                </li>
              )}
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
