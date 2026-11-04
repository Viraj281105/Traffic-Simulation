import { useState } from "react";
import { FileUp } from "lucide-react";
import "../insights/Insights.css";
import {
  Panel,
  Pill,
  StatGrid,
  StatTile,
} from "../components/dashboard/Dashboard";
import { errorText } from "../insights/http";
import { num } from "../insights/format";
import { validateNetworkFile } from "./api";
import { FORMAT_OPTIONS, precheckFile } from "./uploadChecks";
import { MessageList } from "./MessageList";
import type {
  NetworkFormat,
  ValidationMessage,
  ValidationResult,
} from "./types";

export function ValidationReport({ result }: { result: ValidationResult }) {
  const errors = result.messages.filter((m) => m.severity === "error").length;
  const warnings = result.messages.filter(
    (m) => m.severity === "warning",
  ).length;
  return (
    <div className="ins-stack" aria-live="polite">
      <p className="ins-headline">
        {result.valid
          ? "This network can be used"
          : "This network cannot be used yet"}
        <Pill tone={result.valid ? "good" : "bad"}>
          {result.valid ? "Valid" : "Not valid"}
        </Pill>
      </p>
      <p className="ins-muted">
        {result.filename} read as {result.format}. {errors}{" "}
        {errors === 1 ? "error" : "errors"}, {warnings}{" "}
        {warnings === 1 ? "warning" : "warnings"}.
      </p>
      {result.summary && (
        <StatGrid>
          <StatTile
            label="Junctions"
            value={num(result.summary.junctions, 0)}
          />
          <StatTile label="Nodes" value={num(result.summary.nodes, 0)} />
          <StatTile label="Links" value={num(result.summary.links, 0)} />
          <StatTile
            label="Total length"
            value={num(result.summary.totalLengthKm, 1)}
            unit="km"
          />
        </StatGrid>
      )}
      <MessageList messages={result.messages} />
    </div>
  );
}

/** Choose a network file, send it to be validated, and read the messages. */
export function NetworkUpload({
  validate = validateNetworkFile,
}: {
  validate?: typeof validateNetworkFile;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<NetworkFormat>("auto");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [problems, setProblems] = useState<ValidationMessage[]>([]);

  const submit = () => {
    if (!file) return;
    const early = precheckFile(file);
    setResult(null);
    setProblems(early);
    if (early.length > 0) return;
    setBusy(true);
    validate(file, format)
      .then(setResult)
      .catch((err: unknown) => {
        setProblems([
          {
            severity: "error",
            code: "upload_failed",
            message: errorText(err, "The file could not be checked."),
          },
        ]);
      })
      .finally(() => {
        setBusy(false);
      });
  };

  return (
    <Panel
      id="ins-upload"
      title="Upload a network"
      subtitle="We check the file and tell you what is missing or unsupported before it is used."
    >
      <form
        className="ins-row"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <div className="uf-field">
          <label className="uf-label" htmlFor="ins-net-file">
            Network file
          </label>
          <input
            id="ins-net-file"
            className="uf-input"
            type="file"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setResult(null);
              setProblems([]);
            }}
          />
        </div>
        <div className="uf-field">
          <label className="uf-label" htmlFor="ins-net-format">
            File type
          </label>
          <select
            id="ins-net-format"
            className="uf-select"
            value={format}
            onChange={(e) => {
              setFormat(e.target.value as NetworkFormat);
            }}
          >
            {FORMAT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="ins-btn ins-btn--primary"
          disabled={!file || busy}
        >
          <FileUp size={15} aria-hidden="true" />
          {busy ? "Checking…" : "Check file"}
        </button>
      </form>
      {problems.length > 0 && <MessageList messages={problems} />}
      {result && <ValidationReport result={result} />}
    </Panel>
  );
}
