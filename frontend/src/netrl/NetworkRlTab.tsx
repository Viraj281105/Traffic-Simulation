import { useId, useRef, useState } from "react";
import { Brain } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel } from "../components/dashboard/Dashboard";
import { readText } from "../netcommon/readFile";
import { RUN_ID_PATTERN } from "../routing";
import { RlComparisonChart } from "../rlcompare/RlComparisonChart";
import { parseEvalDocument } from "./api";
import { NetworkRlComparison } from "./NetworkRlComparison";
import type { RlEvalDocument } from "./types";

/** The RL tab: RL against the baselines on the network (from an evaluation
 *  file) and, below it, a junction-level comparison by id. */
export function NetworkRlTab() {
  const uid = useId();
  const file = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [doc, setDoc] = useState<RlEvalDocument | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [draftId, setDraftId] = useState("");
  const [comparisonId, setComparisonId] = useState("");

  const open = (source: string) => {
    try {
      setDoc(parseEvalDocument(source));
      setProblem(null);
    } catch (err) {
      setDoc(null);
      setProblem(
        err instanceof Error ? err.message : "That file is not usable.",
      );
    }
  };

  return (
    <div className="nw-stack">
      <Panel
        id="nw-rl"
        title="RL against baselines on the network"
        subtitle="Per-seed paired comparison with the server's interval, p-value and verdict."
      >
        <div className="nw-stack">
          <div className="nw-form">
            <button
              type="button"
              className="nw-btn"
              onClick={() => file.current?.click()}
            >
              Open an evaluation file
            </button>
            <input
              ref={file}
              type="file"
              accept="application/json,.json"
              hidden
              aria-label="Network RL evaluation file"
              onChange={(e) => {
                const chosen = e.target.files?.[0];
                e.target.value = "";
                if (!chosen) return;
                readText(chosen)
                  .then((content) => {
                    setText(content);
                    open(content);
                  })
                  .catch(() => {
                    setProblem("That file could not be read.");
                  });
              }}
            />
          </div>
          <div className="uf-field">
            <label className="uf-label" htmlFor={`${uid}-eval`}>
              Or paste the urbanflow-rl-eval JSON
            </label>
            <textarea
              id={`${uid}-eval`}
              className="nw-textarea"
              value={text}
              onChange={(e) => {
                setText(e.target.value);
              }}
            />
          </div>
          <div className="nw-form">
            <button
              type="button"
              className="nw-btn nw-btn--primary"
              disabled={!text.trim()}
              onClick={() => {
                open(text);
              }}
            >
              Show comparison
            </button>
          </div>
          {problem && <p role="alert">{problem}</p>}
          {doc ? (
            <NetworkRlComparison doc={doc} />
          ) : (
            !problem && (
              <EmptyHint icon={<Brain size={22} />} title="No evaluation open">
                Open the JSON written by the network RL evaluation to compare
                the learned policy with fixed-time and max-pressure control seed
                by seed.
              </EmptyHint>
            )
          )}
        </div>
      </Panel>
      <Panel
        id="nw-rl-junction"
        title="Junction comparison by ID"
        subtitle="RL against fixed-time on one junction (the Trust and reports screen)."
      >
        <div className="nw-stack">
          <form
            className="nw-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (RUN_ID_PATTERN.test(draftId)) setComparisonId(draftId);
            }}
          >
            <div className="uf-field">
              <label className="uf-label" htmlFor={`${uid}-id`}>
                RL comparison ID
              </label>
              <input
                id={`${uid}-id`}
                className="uf-input"
                value={draftId}
                onChange={(e) => {
                  setDraftId(e.target.value.trim());
                }}
              />
            </div>
            <button
              type="submit"
              className="nw-btn"
              disabled={!RUN_ID_PATTERN.test(draftId)}
            >
              Show
            </button>
          </form>
          {comparisonId && <RlComparisonChart comparisonId={comparisonId} />}
        </div>
      </Panel>
    </div>
  );
}
