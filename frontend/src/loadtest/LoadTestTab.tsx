import { useRef, useState } from "react";
import { Gauge } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { readText } from "../netcommon/readFile";
import { useRemote } from "../insights/useRemote";
import { getLatestLoadTest, parseLoadTest } from "./api";
import { LoadTestDashboard } from "./LoadTestDashboard";
import type { LoadTestSummary } from "./types";

/** The Load tests tab: the newest published summary, or a summary file the
 *  person opens. */
export function LoadTestTab() {
  const file = useRef<HTMLInputElement>(null);
  const latest = useRemote(
    getLatestLoadTest,
    "The latest load test could not be loaded.",
  );
  const [opened, setOpened] = useState<LoadTestSummary | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const summary = opened ?? (latest.status === "ready" ? latest.data : null);
  return (
    <Panel
      id="nw-loadtest"
      title="Load tests"
      subtitle="Response time, error rate and virtual users from a k6 run, against the thresholds the test set."
    >
      <div className="nw-stack">
        <div className="nw-form">
          <button
            type="button"
            className="nw-btn"
            onClick={() => file.current?.click()}
          >
            Open a summary file
          </button>
          <input
            ref={file}
            type="file"
            accept="application/json,.json"
            hidden
            aria-label="Load-test summary file"
            onChange={(e) => {
              const chosen = e.target.files?.[0];
              e.target.value = "";
              if (!chosen) return;
              readText(chosen)
                .then((text) => {
                  setOpened(parseLoadTest(text));
                  setProblem(null);
                })
                .catch((err: unknown) => {
                  setProblem(
                    err instanceof Error
                      ? err.message
                      : "That file is not usable.",
                  );
                });
            }}
          />
        </div>
        {problem && <p role="alert">{problem}</p>}
        {!summary && latest.status === "loading" && <Skeleton lines={4} />}
        {!summary && latest.status === "error" && (
          <p role="alert">{latest.message}</p>
        )}
        {!summary &&
          (latest.status === "notFound" || latest.status === "idle") && (
            <EmptyHint icon={<Gauge size={22} />} title="No load test yet">
              No result has been published. Run the k6 test, then open its
              summary file here.
            </EmptyHint>
          )}
        {summary && <LoadTestDashboard summary={summary} />}
      </div>
    </Panel>
  );
}
