import { useCallback, useEffect, useState } from "react";
import "../netcommon/network.css";
import { Panel, Pill, Skeleton } from "../components/dashboard/Dashboard";
import { errorText } from "../netcommon/api";
import { useAction } from "../netcommon/useAction";
import {
  createRecommendation,
  getAudit,
  listRecommendations,
  transitionRecommendation,
  verifyAudit,
} from "./api";
import type {
  AuditLog,
  AuditVerification,
  RecState,
  Recommendation,
} from "./types";

interface Snapshot {
  items: Recommendation[];
  audit: AuditLog;
}

const NEXT: Record<RecState, { to: RecState; label: string }[]> = {
  draft: [
    { to: "submitted", label: "Submit" },
    { to: "withdrawn", label: "Withdraw" },
  ],
  submitted: [
    { to: "approved", label: "Approve" },
    { to: "rejected", label: "Reject" },
    { to: "withdrawn", label: "Withdraw" },
  ],
  approved: [],
  rejected: [],
  withdrawn: [],
};

function when(seconds: number): string {
  return new Date(seconds * 1000).toLocaleString();
}

async function fetchSnapshot(): Promise<Snapshot> {
  const [list, audit] = await Promise.all([listRecommendations(), getAudit()]);
  return { items: list.items, audit };
}

/** Governance tab: advisory recommendations with a hash-chained audit log. */
export function GovernanceTab() {
  const [snap, setSnap] = useState<
    | { status: "loading" }
    | { status: "error"; message: string }
    | { status: "ready"; data: Snapshot }
  >({ status: "loading" });
  const [actor, setActor] = useState("analyst");
  const [approver, setApprover] = useState(false);
  const [comment, setComment] = useState("");
  const [scenarioRef, setScenarioRef] = useState("");
  const [change, setChange] = useState('{"greenSeconds": 30}');
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [verify, startVerify] = useAction<AuditVerification>(
    "The audit log could not be verified.",
  );

  const show = useCallback((load: Promise<Snapshot>) => {
    return load.then(
      (data) => {
        setSnap({ status: "ready", data });
      },
      (err: unknown) => {
        setSnap({
          status: "error",
          message: errorText(err, "Recommendations could not be loaded."),
        });
      },
    );
  }, []);

  useEffect(() => {
    void show(fetchSnapshot());
  }, [show]);

  const refresh = () => show(fetchSnapshot());

  const act = async (run: () => Promise<unknown>, done: string) => {
    setNotice(null);
    setFormError(null);
    try {
      await run();
      setNotice(done);
      await refresh();
    } catch (err) {
      setFormError(errorText(err, "The request was refused."));
    }
  };

  const create = () => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(change);
    } catch {
      setFormError("The proposed change must be valid JSON.");
      return;
    }
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      Array.isArray(parsed)
    ) {
      setFormError("The proposed change must be a JSON object.");
      return;
    }
    void act(
      () =>
        createRecommendation({
          actor,
          scenarioRef,
          proposedChange: parsed as Record<string, unknown>,
          evidenceRefs: [],
        }),
      "Recommendation created as a draft.",
    );
  };

  return (
    <Panel
      id="coop-governance"
      title="Recommendations and audit log"
      subtitle="Advisory only: approving a recommendation records a decision. Nothing is applied to any signal or road."
    >
      <div className="nw-stack">
        <p className="nw-muted">
          Advisory only. These records never change a live system.
        </p>
        <form
          className="nw-form"
          onSubmit={(e) => {
            e.preventDefault();
            create();
          }}
        >
          <div className="uf-field">
            <label className="uf-label" htmlFor="gov-actor">
              Acting as
            </label>
            <input
              id="gov-actor"
              className="uf-input"
              value={actor}
              onChange={(e) => {
                setActor(e.target.value);
              }}
            />
          </div>
          <div className="uf-field">
            <label className="uf-label" htmlFor="gov-scenario">
              Scenario reference
            </label>
            <input
              id="gov-scenario"
              className="uf-input"
              value={scenarioRef}
              onChange={(e) => {
                setScenarioRef(e.target.value);
              }}
            />
          </div>
          <div className="uf-field">
            <label className="uf-label" htmlFor="gov-change">
              Proposed change (JSON)
            </label>
            <textarea
              id="gov-change"
              className="uf-input"
              rows={2}
              value={change}
              onChange={(e) => {
                setChange(e.target.value);
              }}
            />
          </div>
          <button
            type="submit"
            className="nw-btn nw-btn--primary"
            disabled={actor.trim() === "" || scenarioRef.trim() === ""}
          >
            Create recommendation
          </button>
        </form>
        <div className="nw-form">
          <div className="uf-field">
            <label className="uf-label" htmlFor="gov-comment">
              Comment for the next decision (needed to reject)
            </label>
            <input
              id="gov-comment"
              className="uf-input"
              value={comment}
              onChange={(e) => {
                setComment(e.target.value);
              }}
            />
          </div>
          <label>
            <input
              type="checkbox"
              checked={approver}
              onChange={(e) => {
                setApprover(e.target.checked);
              }}
            />{" "}
            I am acting as an approver
          </label>
        </div>
        {formError && <p role="alert">{formError}</p>}
        {notice && <p role="status">{notice}</p>}
        {snap.status === "loading" && <Skeleton lines={4} />}
        {snap.status === "error" && <p role="alert">{snap.message}</p>}
        {snap.status === "ready" && (
          <>
            <div className="uf-table-wrap nw-scroll">
              <table className="uf-table">
                <caption>Recommendations</caption>
                <thead>
                  <tr>
                    <th scope="col">Id</th>
                    <th scope="col">Scenario</th>
                    <th scope="col">State</th>
                    <th scope="col">Decision</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {snap.data.items.length === 0 && (
                    <tr>
                      <td colSpan={5}>No recommendations yet.</td>
                    </tr>
                  )}
                  {snap.data.items.map((r) => (
                    <tr key={r.id}>
                      <th scope="row">{r.id}</th>
                      <td>{r.scenarioRef}</td>
                      <td>
                        <Pill
                          tone={
                            r.state === "approved"
                              ? "good"
                              : r.state === "rejected"
                                ? "bad"
                                : "neutral"
                          }
                        >
                          {r.state}
                        </Pill>
                      </td>
                      <td>
                        {r.decidedBy
                          ? `${r.decidedBy}: ${r.decisionComment ?? "no comment"}`
                          : "Not decided"}
                      </td>
                      <td>
                        {NEXT[r.state].map((n) => (
                          <button
                            key={n.to}
                            type="button"
                            className="nw-btn"
                            aria-label={`${n.label} ${r.id}`}
                            onClick={() => {
                              void act(
                                () =>
                                  transitionRecommendation(r.id, {
                                    actor,
                                    roles: approver ? ["approver"] : [],
                                    to: n.to,
                                    comment: comment.trim() || null,
                                  }),
                                `${r.id} is now ${n.to}.`,
                              );
                            }}
                          >
                            {n.label}
                          </button>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="uf-table-wrap nw-scroll">
              <table className="uf-table">
                <caption>
                  Audit log, {snap.data.audit.total} entries (newest last). Each
                  entry is chained to the one before it.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">When</th>
                    <th scope="col">Who</th>
                    <th scope="col">What</th>
                    <th scope="col">About</th>
                  </tr>
                </thead>
                <tbody>
                  {snap.data.audit.entries.map((e) => (
                    <tr key={e.seq}>
                      <th scope="row">{e.seq}</th>
                      <td>{when(e.timestamp)}</td>
                      <td>{e.actor}</td>
                      <td>{e.action}</td>
                      <td>{e.subject}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <button
                type="button"
                className="nw-btn"
                disabled={verify.status === "loading"}
                onClick={() => {
                  startVerify(verifyAudit);
                }}
              >
                Verify the audit log
              </button>
              {verify.status === "error" && (
                <p role="alert">{verify.message}</p>
              )}
              {verify.status === "ready" && (
                <p role="status">
                  <Pill tone={verify.data.ok ? "good" : "bad"}>
                    {verify.data.ok ? "Chain intact" : "Chain broken"}
                  </Pill>{" "}
                  {verify.data.ok
                    ? `${String(verify.data.length)} entries checked.`
                    : `${verify.data.error ?? "Unknown problem"} (entry ${String(verify.data.badSeq)}).`}
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}
