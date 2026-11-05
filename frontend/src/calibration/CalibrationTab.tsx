import { useId, useRef, useState } from "react";
import { Scale } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { getGrid } from "../mapview/api";
import { readText } from "../netcommon/readFile";
import { errorText } from "../netcommon/api";
import { DEFAULT_SCENARIO } from "../netcommon/scenario";
import { useAction } from "../netcommon/useAction";
import { isRecord, parseJson, readInputs } from "./inputs";
import { fitNetwork, recalibrateNetwork, validateCounts } from "./api";
import { CalibrationReportView } from "./CalibrationReportView";
import type { CalibrationReport, CountsValidation, FitInputs } from "./types";

type Outcome =
  | { kind: "report"; report: CalibrationReport }
  | { kind: "counts"; validation: CountsValidation };

/** The calibration tab: bring a network, its demand and a counts file, and
 *  read the report. Nothing is stored by the server. */
export function CalibrationTab() {
  const uid = useId();
  const reportFile = useRef<HTMLInputElement>(null);
  const countsFile = useRef<HTMLInputElement>(null);
  const [graphText, setGraphText] = useState("");
  const [flowsText, setFlowsText] = useState("");
  const [counts, setCounts] = useState("");
  const [local, setLocal] = useState<string | null>(null);
  const [state, start] = useAction<Outcome>(
    "The calibration could not be run.",
  );
  const [shown, setShown] = useState<CalibrationReport | null>(null);

  const run = (job: (inputs: FitInputs) => Promise<Outcome>) => {
    setLocal(null);
    let inputs: FitInputs;
    try {
      inputs = readInputs(graphText, flowsText, counts);
    } catch (err) {
      setLocal(
        err instanceof Error ? err.message : "The inputs are not usable.",
      );
      return;
    }
    start(async () => {
      const outcome = await job(inputs);
      if (outcome.kind === "report") setShown(outcome.report);
      return outcome;
    });
  };

  const loadExample = () => {
    setLocal(null);
    getGrid(DEFAULT_SCENARIO).then(
      (grid) => {
        setGraphText(JSON.stringify(grid.graph, null, 2));
        setFlowsText(JSON.stringify(grid.flows, null, 2));
        setLocal("Example network loaded. Add a counts file, then calibrate.");
      },
      (err: unknown) => {
        setLocal(errorText(err, "The example network could not be loaded."));
      },
    );
  };

  const readFile = (file: File | undefined, apply: (text: string) => void) => {
    if (!file) return;
    readText(file)
      .then(apply)
      .catch(() => {
        setLocal("That file could not be read.");
      });
  };

  const openReport = (text: string) => {
    try {
      const doc = parseJson(text, "report");
      if (!isRecord(doc) || doc.format !== "urbanflow-network-calibration") {
        throw new Error("That file is not a network calibration report.");
      }
      setLocal(null);
      setShown(doc as unknown as CalibrationReport);
    } catch (err) {
      setLocal(
        err instanceof Error ? err.message : "That report is not usable.",
      );
    }
  };

  const busy = state.status === "loading";
  return (
    <Panel
      id="nw-calibration"
      title="Network calibration"
      subtitle="Fit the model to traffic counts and check the G-CAL gate."
    >
      <div className="nw-stack">
        <div className="nw-form">
          <button
            type="button"
            className="nw-btn"
            disabled={busy}
            onClick={loadExample}
          >
            Load example network
          </button>
          <button
            type="button"
            className="nw-btn"
            onClick={() => reportFile.current?.click()}
          >
            Open a saved report
          </button>
          <input
            ref={reportFile}
            type="file"
            accept="application/json,.json"
            hidden
            aria-label="Saved calibration report"
            onChange={(e) => {
              readFile(e.target.files?.[0], openReport);
              e.target.value = "";
            }}
          />
        </div>
        <div className="nw-cols">
          <div className="uf-field">
            <label className="uf-label" htmlFor={`${uid}-graph`}>
              Network (urbanflow-graph JSON)
            </label>
            <textarea
              id={`${uid}-graph`}
              className="nw-textarea"
              value={graphText}
              onChange={(e) => {
                setGraphText(e.target.value);
              }}
            />
          </div>
          <div className="uf-field">
            <label className="uf-label" htmlFor={`${uid}-flows`}>
              Demand (list of origin, destination, vehiclesPerHour)
            </label>
            <textarea
              id={`${uid}-flows`}
              className="nw-textarea"
              value={flowsText}
              onChange={(e) => {
                setFlowsText(e.target.value);
              }}
            />
          </div>
        </div>
        <div className="uf-field">
          <label className="uf-label" htmlFor={`${uid}-counts`}>
            Counts (CSV with link_id, interval_start, count)
          </label>
          <textarea
            id={`${uid}-counts`}
            className="nw-textarea"
            value={counts}
            onChange={(e) => {
              setCounts(e.target.value);
            }}
          />
          <button
            type="button"
            className="nw-btn"
            onClick={() => countsFile.current?.click()}
          >
            Load counts file
          </button>
          <input
            ref={countsFile}
            type="file"
            accept=".csv,text/csv"
            hidden
            aria-label="Counts file"
            onChange={(e) => {
              readFile(e.target.files?.[0], setCounts);
              e.target.value = "";
            }}
          />
        </div>
        <div className="nw-form">
          <button
            type="button"
            className="nw-btn"
            disabled={busy}
            onClick={() => {
              run(async (i) => ({
                kind: "counts",
                validation: await validateCounts(i.graph, i.countsCsv),
              }));
            }}
          >
            Check counts
          </button>
          <button
            type="button"
            className="nw-btn nw-btn--primary"
            disabled={busy}
            onClick={() => {
              run(async (i) => ({
                kind: "report",
                report: await fitNetwork(i),
              }));
            }}
          >
            {busy ? "Working…" : "Calibrate"}
          </button>
          {shown && (
            <button
              type="button"
              className="nw-btn"
              disabled={busy}
              onClick={() => {
                run(async (i) => ({
                  kind: "report",
                  report: await recalibrateNetwork(i, shown.parameters.fitted),
                }));
              }}
            >
              Recalibrate from this report
            </button>
          )}
        </div>
        {local && <p role="alert">{local}</p>}
        {busy && <Skeleton lines={4} />}
        {state.status === "error" && <p role="alert">{state.message}</p>}
        {state.status === "ready" && state.data.kind === "counts" && (
          <CountsCheck validation={state.data.validation} />
        )}
        {shown ? (
          <CalibrationReportView report={shown} />
        ) : (
          state.status === "idle" && (
            <EmptyHint icon={<Scale size={22} />} title="No report yet">
              Load the example network or paste your own, add a counts file and
              press Calibrate. Or open a report you saved earlier.
            </EmptyHint>
          )
        )}
      </div>
    </Panel>
  );
}

/** The result of checking a counts file against the network. */
export function CountsCheck({
  validation: v,
}: {
  validation: CountsValidation;
}) {
  return (
    <div className="nw-stack" role="status">
      <p className="nw-headline">
        {v.valid
          ? `The counts file is usable: ${String(v.provenance.rows)} rows on ${String(v.provenance.links)} links.`
          : "The counts file cannot be used yet."}
      </p>
      {[...v.errors, ...v.warnings].length > 0 && (
        <ul className="nw-facts">
          {v.errors.map((e) => (
            <li key={e}>Problem: {e}</li>
          ))}
          {v.warnings.map((w) => (
            <li key={w}>Note: {w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
