import { useEffect, useState } from "react";
import { Download, FlaskConical, Square } from "lucide-react";
import "../copilot/Copilot.css";
import "./Discovery.css";
import {
  cancelSearch,
  downloadSearchPackage,
  estimate,
  getSearch,
  getSearchResult,
  listSearches,
  startSearch,
  type ObjectiveRow,
  type SearchResult,
  type SearchSpec,
  type SearchStatus,
} from "../../services/v3/discovery";
import { ExperimentsApiError, saveBlob } from "../../services/v3/experiments";

const POLL_MS = 2000;

const DEFAULT_SPEC: SearchSpec = {
  name: "Discovery search",
  regime: {
    name: "Declared regime",
    vehiclesPerHour: 700,
    unevenDemand: true,
    lanesPerArm: 1,
    aggression: "high",
    mix: "default",
    duration: 150,
    warmup: 30,
  },
  budget: {
    population: 10,
    generations: 6,
    tuningSeeds: 2,
    selectionSeeds: 3,
    heldOutSeeds: 10,
    paretoCap: 6,
    shortlist: 3,
    unseenGrid: true,
  },
  seed: 1,
};

function fmt(value: number | null | undefined, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(digits)
    : "—";
}

function objectiveCells(row: ObjectiveRow) {
  return (
    <>
      <td>{fmt(row?.averageDelay)}</td>
      <td>{fmt(row?.throughput, 1)}</td>
      <td>{fmt(row?.maxQueueLength, 1)}</td>
      <td>{fmt(row?.nearMissesPer1000, 1)}</td>
    </>
  );
}

function describeGenome(genome: Record<string, unknown>): string {
  return Object.entries(genome)
    .map(
      ([k, v]) =>
        `${k}=${typeof v === "number" || typeof v === "string" || typeof v === "boolean" ? String(v) : "…"}`,
    )
    .join(", ");
}

function message(err: unknown, fallback: string): string {
  return err instanceof ExperimentsApiError ? err.message : fallback;
}

/** The Control Strategy Discovery Lab: a bounded evolutionary search for one
 *  declared regime, judged against the unchanged baselines on held-out seeds. */
export function DiscoveryPage() {
  const [spec, setSpec] = useState<SearchSpec>(DEFAULT_SPEC);
  const [cost, setCost] = useState<{
    runs: number;
    simulatedSeconds: number;
  } | null>(null);
  const [searches, setSearches] = useState<SearchStatus[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [status, setStatus] = useState<SearchStatus | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    estimate(spec)
      .then(setCost)
      .catch(() => {
        setCost(null);
      });
  }, [spec]);

  useEffect(() => {
    listSearches()
      .then(setSearches)
      .catch(() => {
        setSearches([]);
      });
  }, [tick]);

  useEffect(() => {
    if (!selected) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      getSearch(selected)
        .then((s) => {
          if (stop) return;
          setStatus(s);
          if (s.status === "queued" || s.status === "running") {
            timer = setTimeout(load, POLL_MS);
            return;
          }
          setTick((n) => n + 1);
          if (s.resultAvailable) {
            void getSearchResult(selected).then((r) => {
              if (!stop) setResult(r);
            });
          }
        })
        .catch((err: unknown) => {
          setError(message(err, "The search could not be loaded."));
        });
    };
    load();
    return () => {
      stop = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [selected]);

  const regime = (patch: Partial<SearchSpec["regime"]>) => {
    setSpec((s) => ({ ...s, regime: { ...s.regime, ...patch } }));
  };
  const budget = (patch: Partial<SearchSpec["budget"]>) => {
    setSpec((s) => ({ ...s, budget: { ...s.budget, ...patch } }));
  };

  const start = () => {
    setBusy(true);
    setError(null);
    startSearch(spec)
      .then((s) => {
        setResult(null);
        setSelected(s.id);
        setTick((n) => n + 1);
      })
      .catch((err: unknown) => {
        setError(message(err, "The search could not be started."));
      })
      .finally(() => {
        setBusy(false);
      });
  };

  const running = status?.status === "queued" || status?.status === "running";

  return (
    <div className="copilot-page">
      <header className="copilot-header">
        <p className="guided-eyebrow">Plan</p>
        <h1>Control Strategy Discovery Lab</h1>
        <p>
          A bounded multi-objective evolutionary search over the parameters of
          the registered control strategies, for one traffic regime you declare.
          Candidates are compared with the unchanged fixed-time, adaptive and
          roundabout baselines on held-out seeds the search never saw. It is not
          a learned model, and its results apply to this simulator only.
        </p>
      </header>

      <section className="copilot-card" aria-labelledby="disc-regime">
        <h2 id="disc-regime">Regime and budget</h2>
        <div className="discovery-form">
          <label>
            Vehicles per hour per arm
            <input
              type="number"
              min={100}
              max={1200}
              value={spec.regime.vehiclesPerHour}
              onChange={(e) => {
                regime({ vehiclesPerHour: Number(e.target.value) });
              }}
            />
          </label>
          <label>
            Driver aggression
            <select
              value={spec.regime.aggression ?? ""}
              onChange={(e) => {
                regime({
                  aggression: (e.target.value ||
                    null) as SearchSpec["regime"]["aggression"],
                });
              }}
            >
              <option value="">Scenario default</option>
              <option value="standard">Standard</option>
              <option value="moderate">Moderate</option>
              <option value="high">High</option>
            </select>
          </label>
          <label>
            Vehicle mix
            <select
              value={spec.regime.mix}
              onChange={(e) => {
                regime({ mix: e.target.value as SearchSpec["regime"]["mix"] });
              }}
            >
              <option value="default">Default</option>
              <option value="heavy_vehicles">Many buses and trucks</option>
              <option value="two_wheelers">Many two-wheelers</option>
            </select>
          </label>
          <label className="discovery-check">
            <input
              type="checkbox"
              checked={spec.regime.unevenDemand}
              onChange={(e) => {
                regime({ unevenDemand: e.target.checked });
              }}
            />
            Uneven directional demand
          </label>
          <label>
            Population
            <input
              type="number"
              min={4}
              max={24}
              value={spec.budget.population}
              onChange={(e) => {
                budget({ population: Number(e.target.value) });
              }}
            />
          </label>
          <label>
            Generations
            <input
              type="number"
              min={1}
              max={20}
              value={spec.budget.generations}
              onChange={(e) => {
                budget({ generations: Number(e.target.value) });
              }}
            />
          </label>
          <label>
            Search seed
            <input
              type="number"
              min={0}
              value={spec.seed}
              onChange={(e) => {
                setSpec((s) => ({ ...s, seed: Number(e.target.value) }));
              }}
            />
          </label>
        </div>
        <p className="copilot-muted">
          {cost
            ? `Budget: at most ${cost.runs.toString()} simulation runs, ${Math.round(cost.simulatedSeconds).toLocaleString()} simulated seconds reserved against your daily quota (unused runs are refunded). Wall-clock time: unverified.`
            : "This specification is outside the allowed bounds."}
        </p>
        <div className="copilot-actions">
          <button
            type="button"
            className="pb-btn pb-primary"
            disabled={busy || !cost || running}
            onClick={start}
          >
            <FlaskConical size={15} aria-hidden="true" />
            Start search
          </button>
        </div>
        {error ? (
          <p className="copilot-error" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      {searches.length ? (
        <section className="copilot-card" aria-labelledby="disc-list">
          <h2 id="disc-list">Your searches</h2>
          <ul className="discovery-list">
            {searches.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={`uf-link discovery-pick ${s.id === selected ? "is-current" : ""}`}
                  onClick={() => {
                    setResult(null);
                    setSelected(s.id);
                  }}
                >
                  {s.name} · {s.status} · {s.runs.used.toString()} of{" "}
                  {s.runs.planned.toString()} runs
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {status ? (
        <section className="copilot-card" aria-labelledby="disc-status">
          <h2 id="disc-status">{status.name}</h2>
          <p role="status">
            {status.status} · phase {status.phase} ·{" "}
            {status.runs.used.toString()} of at most{" "}
            {status.runs.planned.toString()} runs
            {status.error ? ` · ${status.error}` : ""}
          </p>
          {running ? (
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={() => {
                void cancelSearch(status.id).then(setStatus);
              }}
            >
              <Square size={14} aria-hidden="true" />
              Cancel (stops at the next batch)
            </button>
          ) : null}
        </section>
      ) : null}

      {result ? (
        <DiscoveryResult result={result} searchId={selected ?? ""} />
      ) : null}
    </div>
  );
}

function DiscoveryResult({
  result,
  searchId,
}: {
  result: SearchResult;
  searchId: string;
}) {
  const held = result.heldOut;
  return (
    <section className="copilot-card" aria-labelledby="disc-result">
      <h2 id="disc-result">Result</h2>
      <p className="uf-badge discovery-badge">EXPERIMENTAL</p>
      <p className="copilot-note">{result.experimental}</p>
      <p className="copilot-muted">
        {result.method} Seeds: {result.seedPools.tuning.toString()} for tuning,{" "}
        {result.seedPools.selection.toString()} for selection,{" "}
        {result.seedPools.heldOut.toString()} held out (their hash was recorded
        before the search began). Trace <code>{result.traceFingerprint}</code>.
        {result.complete
          ? ""
          : " This search did not finish: the result is incomplete."}
      </p>

      {held ? (
        <>
          <h3>Held-out evaluation against the baselines</h3>
          <p className="copilot-muted">
            {held.differenceMeaning}. 95% bootstrap intervals over{" "}
            {held.seeds.toString()} held-out seeds.
          </p>
          {result.bestOnTuningLosesOnHeldOut ? (
            <p className="copilot-warnings">
              The best candidate on the tuning seeds does worse than a baseline
              on the held-out seeds.
            </p>
          ) : null}
          <div className="comparison-table-wrap">
            <table className="copilot-table">
              <thead>
                <tr>
                  <th scope="col">Option</th>
                  <th scope="col">Mean delay (s)</th>
                  <th scope="col">Throughput</th>
                  <th scope="col">Max queue</th>
                  <th scope="col">Near misses /1000</th>
                  <th scope="col">vs fixed-time</th>
                  <th scope="col">vs adaptive</th>
                  <th scope="col">vs roundabout</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(held.candidates).map(([key, row]) => (
                  <tr key={key}>
                    <th scope="row" title={describeGenome(row.genome)}>
                      Candidate <code>{key.slice(0, 8)}</code> (
                      {String(row.genome.strategy)})
                    </th>
                    {objectiveCells(row.objectives)}
                    {["fixed_time", "adaptive", "roundabout"].map((b) => {
                      const v = row.versusBaselines[b] as
                        (typeof row.versusBaselines)[string] | undefined;
                      return (
                        <td key={b}>
                          {v?.meanDifference != null && v.ci95
                            ? `${fmt(v.meanDifference)} [${fmt(v.ci95[0])}, ${fmt(v.ci95[1])}]`
                            : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {Object.entries(held.baselines).map(([name, row]) => (
                  <tr key={name}>
                    <th scope="row">Baseline: {name}</th>
                    {objectiveCells(row.objectives)}
                    <td colSpan={3}>{row.infeasible ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {result.preferenceChanges?.length ? (
        <>
          <h3>Where the preference changes (unseen conditions)</h3>
          <table className="copilot-table">
            <thead>
              <tr>
                <th scope="col">Demand</th>
                <th scope="col">Aggression</th>
                <th scope="col">Lowest mean delay</th>
                <th scope="col">Seeds</th>
              </tr>
            </thead>
            <tbody>
              {result.preferenceChanges.map((row) => (
                <tr key={`${row.demandScale.toString()}-${row.aggression}`}>
                  <td>×{row.demandScale.toString()}</td>
                  <td>{row.aggression}</td>
                  <td>{row.lowestDelay ?? "none feasible"}</td>
                  <td>{row.seeds.toString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="copilot-muted">
            Two seeds per cell: a coarse indication of where the preferred
            option changes, with wide uncertainty.
          </p>
        </>
      ) : null}

      <h3>Pareto set on the tuning seeds</h3>
      <table className="copilot-table">
        <thead>
          <tr>
            <th scope="col">Candidate</th>
            <th scope="col">Mean delay (s)</th>
            <th scope="col">Throughput</th>
            <th scope="col">Max queue</th>
            <th scope="col">Near misses /1000</th>
          </tr>
        </thead>
        <tbody>
          {result.pareto.map((p) => (
            <tr key={p.candidate}>
              <th scope="row" title={describeGenome(p.genome)}>
                <code>{p.candidate.slice(0, 8)}</code> (gen{" "}
                {p.generation.toString()})
              </th>
              {objectiveCells(p.tuningObjectives)}
            </tr>
          ))}
        </tbody>
      </table>

      {result.complete ? (
        <button
          type="button"
          className="pb-btn pb-secondary"
          onClick={() => {
            void downloadSearchPackage(searchId).then(({ filename, blob }) => {
              saveBlob(filename, blob);
            });
          }}
        >
          <Download size={14} aria-hidden="true" />
          Download package
        </button>
      ) : null}
    </section>
  );
}
