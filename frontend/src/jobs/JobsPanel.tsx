import { useState } from "react";
import "../netcommon/network.css";
import {
  Panel,
  Skeleton,
  StatGrid,
  StatTile,
} from "../components/dashboard/Dashboard";
import { NumberField } from "../netcommon/NumberField";
import { useAction } from "../netcommon/useAction";
import { SelectField } from "../rescommon/SelectField";
import { useLoad } from "../rescommon/useLoad";
import { accessMessage } from "../tenancy/api";
import { enqueueDryRun, getQueueStats } from "./api";
import type { DryRunResponse } from "./types";

const TAG_KEYS = ["project", "env", "owner"] as const;

function DryRun({ defaultTenant }: { defaultTenant: string }) {
  const [tenant, setTenant] = useState(defaultTenant);
  const [geometry, setGeometry] = useState<"signal" | "roundabout">("signal");
  const [seeds, setSeeds] = useState(5);
  const [duration, setDuration] = useState(30);
  const [tags, setTags] = useState<Record<string, string>>({
    project: "urbanflow",
    env: "",
    owner: "",
  });
  const [state, start] = useAction<DryRunResponse>(
    "The dry run could not be checked.",
  );
  return (
    <div className="nw-stack">
      <h3 className="nw-headline">Enqueue dry run</h3>
      <p className="nw-muted">
        Checks a job exactly as a real enqueue would and shows the message. It
        never sends anything.
      </p>
      <form
        className="nw-form"
        onSubmit={(e) => {
          e.preventDefault();
          const costTags: Record<string, string> = {};
          for (const [k, v] of Object.entries(tags)) {
            if (v.trim()) costTags[k] = v.trim();
          }
          start(() =>
            enqueueDryRun({
              run: { kind: "multi-seed", geometry, numSeeds: seeds, duration },
              tenant: tenant.trim(),
              costTags,
            }),
          );
        }}
      >
        <div className="uf-field">
          <label className="uf-label" htmlFor="job-tenant">
            Tenant
          </label>
          <input
            id="job-tenant"
            className="uf-input"
            value={tenant}
            onChange={(e) => {
              setTenant(e.target.value);
            }}
          />
        </div>
        <SelectField
          label="Junction type"
          value={geometry}
          options={[
            { id: "signal", label: "Signalised" },
            { id: "roundabout", label: "Roundabout" },
          ]}
          onChange={setGeometry}
        />
        <NumberField
          label="Seeds (1 to 100)"
          value={seeds}
          min={1}
          max={100}
          onChange={(v) => {
            setSeeds(Math.round(v));
          }}
        />
        <NumberField
          label="Run length (s)"
          value={duration}
          min={1}
          max={86400}
          onChange={setDuration}
        />
        {TAG_KEYS.map((k) => (
          <div className="uf-field" key={k}>
            <label className="uf-label" htmlFor={`job-tag-${k}`}>
              Cost tag: {k}
            </label>
            <input
              id={`job-tag-${k}`}
              className="uf-input"
              value={tags[k]}
              onChange={(e) => {
                setTags({ ...tags, [k]: e.target.value });
              }}
            />
          </div>
        ))}
        <button
          type="submit"
          className="nw-btn nw-btn--primary"
          disabled={state.status === "loading"}
        >
          Check the job
        </button>
      </form>
      {state.status === "loading" && <Skeleton lines={3} />}
      {state.status === "error" && <p role="alert">{state.message}</p>}
      {state.status === "ready" && (
        <div className="nw-stack">
          <p className="nw-verdict is-good" role="status">
            The job is valid. Nothing was enqueued (dry run). The message would
            be {state.data.messageBytes} bytes, run id{" "}
            {state.data.message.runId}.
          </p>
          <pre className="nw-textarea" aria-label="Message that would be sent">
            {JSON.stringify(state.data.message, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

/** Jobs panel: queue depth and the enqueue dry-run form. */
export function JobsPanel({ defaultTenant = "" }: { defaultTenant?: string }) {
  const stats = useLoad(getQueueStats, "The queue could not be read.");
  return (
    <Panel
      id="res-jobs"
      title="Jobs"
      subtitle="Background study jobs. This screen only reads the queue and checks jobs; it cannot start one."
    >
      <div className="nw-stack">
        {stats.status === "loading" && <Skeleton lines={2} />}
        {stats.status === "error" && (
          <p role="alert" className="nw-alert">
            {stats.httpStatus === 503
              ? "The queue is unavailable right now."
              : accessMessage(stats.httpStatus, stats.message)}
          </p>
        )}
        {stats.status === "ready" && (
          <>
            <StatGrid>
              <StatTile label="Waiting" value={String(stats.data.visible)} />
              <StatTile
                label="Being worked on"
                value={String(stats.data.inFlight)}
              />
              <StatTile
                label="Failed (dead letter)"
                value={String(stats.data.deadLetter)}
              />
            </StatGrid>
            <p className="nw-muted">
              Queue:{" "}
              {stats.data.backend === "sqs"
                ? "Amazon SQS"
                : "in-process memory"}
              . Enqueue is {stats.data.enqueueEnabled ? "on" : "off"} on this
              screen.
            </p>
          </>
        )}
        <DryRun defaultTenant={defaultTenant} />
      </div>
    </Panel>
  );
}
