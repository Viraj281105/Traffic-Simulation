import { useState, useEffect, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  Play,
  Save,
  Download,
  FolderOpen,
  Plus,
  Trash2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  type ScenarioItemConfig,
  type ScenarioSimulationResult,
} from "./planningTypes";
import {
  calculateDelta,
  formatDeltaText,
  exportComparisonCsv,
} from "./planningUtils";
import { DEFAULT_SCENARIO, cloneScenario } from "../../scenario/scenarioModel";
import {
  STRATEGIES,
  STRATEGY_TITLE,
  type Strategy,
  type ScenarioDocument,
} from "../../scenario/scenarioTypes";
import {
  createSuite,
  getSuites,
  getSuiteById,
  type ScenarioSuite,
} from "../../services/api";
import { STUDY_JOB_ROUTES } from "../../services/studyJobs";
import { useStudyJob } from "../../hooks/useStudyJob";
import { StudyProgress } from "../ui/StudyProgress";
import { downloadText } from "../../metrics/catalog";
import {
  SERIES,
  CHART_AXIS,
  CHART_GRID,
  TOOLTIP_STYLE,
} from "../../theme/chart";
import "./ScenarioPlanningDashboard.css";

interface Stat {
  mean: number;
  ci: number;
}

/** The parts of a control-comparison study result this dashboard reads. */
interface StudyResult {
  results: {
    controls: Partial<Record<Strategy, Partial<Record<string, Stat>>>>;
  }[];
  collisionCount: Partial<Record<Strategy, number>>;
}

/** The study compares at least two controls; a lone strategy is paired with one it is not. */
function partnerOf(strategy: Strategy): Strategy {
  return strategy === "fixed_time" ? "adaptive" : "fixed_time";
}

function mean(
  stats: Partial<Record<string, Stat>> | undefined,
  key: string,
): number | null {
  const value = stats?.[key]?.mean;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isSavedPlanning(value: unknown): value is {
  scenarios: ScenarioItemConfig[];
  results: ScenarioSimulationResult[];
} {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return Array.isArray(v.scenarios) && Array.isArray(v.results);
}

const DEFAULT_BASELINE: ScenarioItemConfig = {
  id: "base_1",
  name: "Baseline: Fixed-Time Signal",
  isBaseline: true,
  strategy: "fixed_time",
  volumeScale: 1.0,
  greenTime: 30,
  yellowTime: 4,
  duration: 120,
  vehicleMix: { car: 0.8, suv: 0.15, bus: 0.05, truck: 0.0, motorcycle: 0.0 },
  driverBehavior: {
    aggressiveTwoWheelers: false,
    unstructuredTraffic: false,
    laneChanging: true,
  },
};

const DEFAULT_INTERVENTION: ScenarioItemConfig = {
  id: "int_1",
  name: "Intervention 1: Adaptive Signal",
  isBaseline: false,
  strategy: "adaptive",
  volumeScale: 1.0,
  greenTime: 30,
  yellowTime: 4,
  duration: 120,
  vehicleMix: { car: 0.8, suv: 0.15, bus: 0.05, truck: 0.0, motorcycle: 0.0 },
  driverBehavior: {
    aggressiveTwoWheelers: false,
    unstructuredTraffic: false,
    laneChanging: true,
  },
};

export function ScenarioPlanningDashboard() {
  const [experimentName, setExperimentName] = useState(
    "Corridor Upgrade Experiment",
  );
  const [experimentDesc, setExperimentDesc] = useState(
    "Comparing baseline fixed-time against adaptive and geometry interventions",
  );
  const [scenarios, setScenarios] = useState<ScenarioItemConfig[]>([
    DEFAULT_BASELINE,
    DEFAULT_INTERVENTION,
  ]);
  const [seedsCount, setSeedsCount] = useState<number>(3);
  const [results, setResults] = useState<ScenarioSimulationResult[]>([]);
  const [running, setRunning] = useState<boolean>(false);
  const [currentRunningIndex, setCurrentRunningIndex] = useState<number>(0);
  const [savedSuites, setSavedSuites] = useState<ScenarioSuite[]>([]);
  const [showSavedModal, setShowSavedModal] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const study = useStudyJob();

  // Load saved suites on mount
  useEffect(() => {
    getSuites()
      .then((data) => {
        setSavedSuites(data.suites);
      })
      .catch((err: unknown) => {
        console.warn("Could not load saved suites:", err);
      });
  }, []);

  const baselineConfig = scenarios.find((s) => s.isBaseline) ?? scenarios[0];
  const baselineResult = results.find(
    (r) => r.scenarioId === baselineConfig.id,
  );

  // Add Intervention Scenario
  const handleAddScenario = () => {
    if (scenarios.length >= 6) return;
    const nextIdx = scenarios.length;
    const newScen: ScenarioItemConfig = {
      id: `int_${String(Date.now())}`,
      name: `Intervention ${String(nextIdx)}: Roundabout Conversion`,
      isBaseline: false,
      strategy: "roundabout",
      volumeScale: 1.0,
      greenTime: 30,
      yellowTime: 4,
      duration: 120,
      vehicleMix: {
        car: 0.8,
        suv: 0.15,
        bus: 0.05,
        truck: 0.0,
        motorcycle: 0.0,
      },
      driverBehavior: {
        aggressiveTwoWheelers: false,
        unstructuredTraffic: false,
        laneChanging: true,
      },
    };
    setScenarios([...scenarios, newScen]);
  };

  const handleRemoveScenario = (id: string) => {
    if (scenarios.length <= 2) return;
    setScenarios(scenarios.filter((s) => s.id !== id));
  };

  const handleUpdateScenario = (
    id: string,
    updates: Partial<ScenarioItemConfig>,
  ) => {
    setScenarios((prev) =>
      prev.map((s) => {
        if (s.id === id) {
          const updated = { ...s, ...updates };
          return updated;
        }
        if (updates.isBaseline && s.id !== id) {
          return { ...s, isBaseline: false };
        }
        return s;
      }),
    );
  };

  // Compile a scenario document from scenario item config
  const buildScenarioDoc = (item: ScenarioItemConfig): ScenarioDocument => {
    const doc = cloneScenario(DEFAULT_SCENARIO);
    doc.name = item.name;
    doc.simulation.duration = item.duration;
    // Ensure warmup is always shorter than duration
    doc.simulation.warmup = Math.min(
      30,
      Math.max(5, Math.floor(item.duration / 4)),
    );
    doc.signal.greenTime = item.greenTime;
    doc.signal.yellowTime = item.yellowTime;
    doc.roads.laneChanging = item.driverBehavior.laneChanging;
    doc.vehicles.mix = { ...item.vehicleMix };

    if (item.strategy === "roundabout") {
      doc.junction.type = "roundabout";
    } else if (item.strategy === "adaptive") {
      doc.junction.type = "adaptive_signal";
    } else {
      doc.junction.type = "fixed_time_signal";
    }

    // Demand is scaled by the study itself (demandScales), not here.
    return doc;
  };

  // Run every scenario through the control-comparison study, one after another.
  const handleRunExperiment = async () => {
    setRunning(true);
    setStatusMessage(null);
    const newResults: ScenarioSimulationResult[] = [];

    try {
      for (let i = 0; i < scenarios.length; i++) {
        setCurrentRunningIndex(i);
        const item = scenarios[i];
        const studyRes = await study.run<StudyResult>(
          STUDY_JOB_ROUTES.controlComparison,
          {
            scenario: buildScenarioDoc(item),
            strategies: [item.strategy, partnerOf(item.strategy)],
            numSeeds: seedsCount,
            demandScales: [item.volumeScale],
          },
        );
        const stats = studyRes.results[0]?.controls[item.strategy];
        const delay = mean(stats, "averageDelay");
        const wait = mean(stats, "averageWaitTime");
        const throughput = mean(stats, "throughput");
        const queue = mean(stats, "averageQueueLength");
        const maxQueue = mean(stats, "maxQueueLength");
        if (
          delay === null ||
          wait === null ||
          throughput === null ||
          queue === null ||
          maxQueue === null
        ) {
          throw new Error(
            `the study returned no measurements for ${item.name}`,
          );
        }
        newResults.push({
          scenarioId: item.id,
          name: item.name,
          strategy: item.strategy,
          volumeScale: item.volumeScale,
          duration: item.duration,
          seedCount: seedsCount,
          metrics: {
            averageWaitTime: Number(wait.toFixed(2)),
            averageDelay: Number(delay.toFixed(2)),
            throughput: Math.round(throughput),
            averageQueueLength: Number(queue.toFixed(2)),
            maxQueueLength: Math.round(maxQueue),
            collisionCount: studyRes.collisionCount[item.strategy] ?? 0,
          },
        });
      }

      setResults(newResults);
      setStatusMessage("Experiment completed: every figure below is measured.");
    } catch (err: unknown) {
      console.error("Experiment failed:", err);
      setStatusMessage(
        `Simulation error: ${err instanceof Error ? err.message : "the batch could not run"}`,
      );
    } finally {
      setRunning(false);
    }
  };

  // Save experiment configuration & results to SQLite
  const handleSaveExperiment = async () => {
    if (!results.length) return;
    try {
      const payload = {
        name: experimentName,
        description: experimentDesc,
        run_ids: [],
        config_variations: {
          scenarios,
          results,
          savedAt: new Date().toISOString(),
        },
      };
      const res = await createSuite(payload);
      setStatusMessage(
        `Experiment saved successfully (Suite ID: ${res.id.slice(0, 8)})`,
      );
      // refresh saved list
      const updated = await getSuites();
      setSavedSuites(updated.suites);
    } catch (err: unknown) {
      console.error(err);
      setStatusMessage("Failed to save experiment to database.");
    }
  };

  // Reopen past experiment from SQLite
  const handleLoadExperiment = async (suiteId: string) => {
    try {
      const res = await getSuiteById(suiteId);
      const variations = res.suite.config_variations;
      if (isSavedPlanning(variations)) {
        setExperimentName(res.suite.name);
        setExperimentDesc(res.suite.description);
        setScenarios(variations.scenarios);
        setResults(variations.results);
        setShowSavedModal(false);
        setStatusMessage(
          `Loaded saved experiment "${res.suite.name}" without re-running simulations.`,
        );
      } else {
        setStatusMessage("This suite does not contain scenario planning data.");
      }
    } catch (err: unknown) {
      console.error(err);
      setStatusMessage("Failed to load saved experiment.");
    }
  };

  // Export comparison data to CSV
  const handleExportCsv = () => {
    if (!baselineResult) return;
    const csvContent = exportComparisonCsv(
      experimentName,
      baselineResult,
      results,
    );
    downloadText(
      `scenario_comparison_${String(Date.now())}.csv`,
      csvContent,
      "text/csv",
    );
  };

  // Chart data preparation
  const chartData = useMemo(() => {
    return results.map((r) => ({
      name: r.name,
      delay: r.metrics.averageDelay,
      wait: r.metrics.averageWaitTime,
      throughput: r.metrics.throughput,
      queue: r.metrics.averageQueueLength,
      collisions: r.metrics.collisionCount,
    }));
  }, [results]);

  return (
    <div className="scenario-planning-dashboard">
      <header className="planning-header">
        <div className="planning-header-title">
          <h1>Scenario Planning & Comparison</h1>
          <p>
            Create baseline and intervention scenarios, run batch experiments,
            and compare data-driven KPIs.
          </p>
        </div>
        <div className="planning-header-actions">
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={() => {
              setShowSavedModal(true);
            }}
          >
            <FolderOpen size={16} aria-hidden="true" />
            Saved Experiments ({savedSuites.length})
          </button>
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={handleExportCsv}
            disabled={!results.length}
          >
            <Download size={16} aria-hidden="true" />
            Export CSV
          </button>
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={() => {
              void handleSaveExperiment();
            }}
            disabled={!results.length}
          >
            <Save size={16} aria-hidden="true" />
            Save Experiment
          </button>
          <button
            type="button"
            className="pb-btn pb-primary"
            onClick={() => {
              void handleRunExperiment();
            }}
            disabled={running}
          >
            <Play size={16} aria-hidden="true" />
            {running ? "Running Experiment…" : "Run Batch Experiment"}
          </button>
        </div>
      </header>

      {statusMessage && (
        <div className="planning-status" role="status">
          {statusMessage}
        </div>
      )}

      {running && (
        <StudyProgress
          title={`Simulating ${scenarios[currentRunningIndex]?.name ?? ""} (${String(currentRunningIndex + 1)} of ${String(scenarios.length)})`}
          progress={study.progress}
        />
      )}

      {/* ── Scenario Builder Section ── */}
      <section className="planning-card">
        <div className="planning-card-header">
          <h2 className="planning-card-title">
            Configure Scenarios ({scenarios.length})
          </h2>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <label
              style={{
                fontSize: "0.85rem",
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
              }}
            >
              Seeds per scenario:
              <select
                value={seedsCount}
                onChange={(e) => {
                  setSeedsCount(Number(e.target.value));
                }}
                disabled={running}
                style={{ padding: "0.2rem 0.5rem", borderRadius: "4px" }}
              >
                <option value={1}>1 (Fast)</option>
                <option value={3}>3 (Balanced)</option>
                <option value={5}>5 (High Precision)</option>
              </select>
            </label>
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={handleAddScenario}
              disabled={running || scenarios.length >= 6}
            >
              <Plus size={15} /> Add Intervention
            </button>
          </div>
        </div>

        <div className="scenarios-grid">
          {scenarios.map((scen, idx) => (
            <div
              key={scen.id}
              className={`scenario-config-item ${scen.isBaseline ? "is-baseline" : ""}`}
            >
              <div className="scenario-item-header">
                <span
                  className={
                    scen.isBaseline
                      ? "scenario-badge-baseline"
                      : "scenario-badge-intervention"
                  }
                >
                  {scen.isBaseline ? "Baseline" : `Intervention ${String(idx)}`}
                </span>
                {!scen.isBaseline && (
                  <button
                    type="button"
                    onClick={() => {
                      handleRemoveScenario(scen.id);
                    }}
                    className="planning-remove"
                    title="Remove scenario"
                    aria-label={`Remove ${scen.name}`}
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>

              <div className="scenario-input-group">
                <label>Scenario Label</label>
                <input
                  type="text"
                  value={scen.name}
                  disabled={running}
                  onChange={(e) => {
                    handleUpdateScenario(scen.id, { name: e.target.value });
                  }}
                />
              </div>

              <div className="scenario-inputs-row">
                <div className="scenario-input-group">
                  <label>Controller Strategy</label>
                  <select
                    value={scen.strategy}
                    disabled={running}
                    onChange={(e) => {
                      handleUpdateScenario(scen.id, {
                        strategy: e.target.value as Strategy,
                      });
                    }}
                  >
                    {STRATEGIES.map((s) => (
                      <option key={s} value={s}>
                        {STRATEGY_TITLE[s]}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="scenario-input-group">
                  <label>Volume Multiplier</label>
                  <select
                    value={scen.volumeScale}
                    disabled={running}
                    onChange={(e) => {
                      handleUpdateScenario(scen.id, {
                        volumeScale: Number(e.target.value),
                      });
                    }}
                  >
                    <option value={0.75}>0.75× (-25%)</option>
                    <option value={1.0}>1.0× (Baseline)</option>
                    <option value={1.25}>1.25× (+25%)</option>
                    <option value={1.5}>1.5× (+50%)</option>
                  </select>
                </div>
              </div>

              <div className="scenario-inputs-row">
                <div className="scenario-input-group">
                  <label>Green Time (s)</label>
                  <input
                    type="number"
                    min={10}
                    max={120}
                    value={scen.greenTime}
                    disabled={running || scen.strategy === "roundabout"}
                    onChange={(e) => {
                      handleUpdateScenario(scen.id, {
                        greenTime: Number(e.target.value),
                      });
                    }}
                  />
                </div>

                <div className="scenario-input-group">
                  <label>Duration (s)</label>
                  <input
                    type="number"
                    min={60}
                    max={600}
                    value={scen.duration}
                    disabled={running}
                    onChange={(e) => {
                      handleUpdateScenario(scen.id, {
                        duration: Number(e.target.value),
                      });
                    }}
                  />
                </div>
              </div>

              <div
                style={{ display: "flex", gap: "1rem", marginTop: "0.25rem" }}
              >
                <label
                  style={{
                    fontSize: "0.82rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.3rem",
                  }}
                >
                  <input
                    type="radio"
                    name="baseline_select"
                    checked={scen.isBaseline}
                    disabled={running}
                    onChange={() => {
                      handleUpdateScenario(scen.id, { isBaseline: true });
                    }}
                  />
                  Set as Baseline
                </label>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Comparison Results Section ── */}
      {results.length > 0 && baselineResult && (
        <>
          {/* KPI Summary Cards */}
          <section className="planning-card">
            <h2
              className="planning-card-title"
              style={{ marginBottom: "1.25rem" }}
            >
              Key Performance Indicator Cards vs Baseline
            </h2>
            <div className="kpi-cards-grid">
              {results.map((res) => {
                const isBase = res.scenarioId === baselineResult.scenarioId;
                const delayDelta = calculateDelta(
                  res.metrics.averageDelay,
                  baselineResult.metrics.averageDelay,
                  true,
                );
                const waitDelta = calculateDelta(
                  res.metrics.averageWaitTime,
                  baselineResult.metrics.averageWaitTime,
                  true,
                );
                const tpDelta = calculateDelta(
                  res.metrics.throughput,
                  baselineResult.metrics.throughput,
                  false,
                );
                const qDelta = calculateDelta(
                  res.metrics.averageQueueLength,
                  baselineResult.metrics.averageQueueLength,
                  true,
                );

                return (
                  <div
                    key={res.scenarioId}
                    className="kpi-card"
                    style={isBase ? { borderColor: "var(--color-info)" } : {}}
                  >
                    <div className="kpi-card-header">
                      <span>{res.name}</span>
                      {isBase ? (
                        <span className="scenario-badge-baseline">Base</span>
                      ) : (
                        <span className="scenario-badge-intervention">
                          Intervention
                        </span>
                      )}
                    </div>

                    <div style={{ margin: "0.5rem 0" }}>
                      <div
                        style={{
                          fontSize: "0.82rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        Mean Delay
                      </div>
                      <div className="kpi-card-val">
                        {res.metrics.averageDelay} <small>s</small>
                      </div>
                      {!isBase && (
                        <div
                          className={`kpi-card-delta kpi-delta--${delayDelta.direction}`}
                        >
                          {delayDelta.direction === "better" ? (
                            <TrendingDown size={14} />
                          ) : (
                            <TrendingUp size={14} />
                          )}
                          {formatDeltaText(delayDelta, "s")}
                        </div>
                      )}
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr 1fr",
                        gap: "0.5rem",
                        borderTop: "1px solid var(--border-color)",
                        paddingTop: "0.5rem",
                      }}
                    >
                      <div>
                        <small style={{ color: "var(--text-muted)" }}>
                          Mean Wait
                        </small>
                        <div style={{ fontWeight: 600 }}>
                          {res.metrics.averageWaitTime} s
                        </div>
                        {!isBase && (
                          <small
                            className={`kpi-delta--${waitDelta.direction}`}
                          >
                            {formatDeltaText(waitDelta, "s")}
                          </small>
                        )}
                      </div>
                      <div>
                        <small style={{ color: "var(--text-muted)" }}>
                          Throughput
                        </small>
                        <div style={{ fontWeight: 600 }}>
                          {res.metrics.throughput} veh
                        </div>
                        {!isBase && (
                          <small className={`kpi-delta--${tpDelta.direction}`}>
                            {formatDeltaText(tpDelta, "")}
                          </small>
                        )}
                      </div>
                      <div>
                        <small style={{ color: "var(--text-muted)" }}>
                          Mean Queue
                        </small>
                        <div style={{ fontWeight: 600 }}>
                          {res.metrics.averageQueueLength} veh
                        </div>
                        {!isBase && (
                          <small className={`kpi-delta--${qDelta.direction}`}>
                            {formatDeltaText(qDelta, "")}
                          </small>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Performance Comparison Charts */}
          <section className="planning-card">
            <h2
              className="planning-card-title"
              style={{ marginBottom: "1.25rem" }}
            >
              Comparative Performance Visualizations
            </h2>
            <div style={{ width: "100%", height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartData}
                  margin={{ top: 20, right: 30, left: 0, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 12 }}
                    stroke={CHART_AXIS}
                  />
                  <YAxis
                    yAxisId="left"
                    orientation="left"
                    stroke={CHART_AXIS}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke={CHART_AXIS}
                  />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend />
                  <Bar
                    yAxisId="left"
                    dataKey="delay"
                    name="Mean Delay (s)"
                    fill={SERIES.signal}
                  />
                  <Bar
                    yAxisId="left"
                    dataKey="wait"
                    name="Mean Wait (s)"
                    fill={SERIES.neutral}
                  />
                  <Bar
                    yAxisId="right"
                    dataKey="throughput"
                    name="Throughput (veh)"
                    fill={SERIES.roundabout}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Detailed Metric Comparison Table */}
          <section className="planning-card">
            <h2
              className="planning-card-title"
              style={{ marginBottom: "1.25rem" }}
            >
              Detailed Scenario Comparison Table
            </h2>
            <div className="comparison-table-wrap">
              <table className="planning-table">
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th>Strategy</th>
                    <th>Volume</th>
                    <th>Mean Delay</th>
                    <th>Delay Change</th>
                    <th>Throughput</th>
                    <th>Throughput Change</th>
                    <th>Mean Queue</th>
                    <th>Max Queue</th>
                    <th>Collisions</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((res) => {
                    const isBase = res.scenarioId === baselineResult.scenarioId;
                    const delayDelta = calculateDelta(
                      res.metrics.averageDelay,
                      baselineResult.metrics.averageDelay,
                      true,
                    );
                    const tpDelta = calculateDelta(
                      res.metrics.throughput,
                      baselineResult.metrics.throughput,
                      false,
                    );

                    return (
                      <tr
                        key={res.scenarioId}
                        className={isBase ? "row-baseline" : ""}
                      >
                        <td>
                          <strong>{res.name}</strong>
                          {isBase && (
                            <span className="planning-baseline-tag">
                              (Baseline)
                            </span>
                          )}
                        </td>
                        <td>{STRATEGY_TITLE[res.strategy]}</td>
                        <td>{res.volumeScale}×</td>
                        <td>{res.metrics.averageDelay} s</td>
                        <td>
                          {isBase ? (
                            "—"
                          ) : (
                            <span
                              className={`kpi-delta--${delayDelta.direction}`}
                            >
                              {formatDeltaText(delayDelta, "s")}
                            </span>
                          )}
                        </td>
                        <td>{res.metrics.throughput} veh</td>
                        <td>
                          {isBase ? (
                            "—"
                          ) : (
                            <span className={`kpi-delta--${tpDelta.direction}`}>
                              {formatDeltaText(tpDelta)}
                            </span>
                          )}
                        </td>
                        <td>{res.metrics.averageQueueLength} veh</td>
                        <td>{res.metrics.maxQueueLength} veh</td>
                        <td>{res.metrics.collisionCount}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {/* ── Saved Experiments Modal ── */}
      {showSavedModal && (
        <div
          className="planning-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Saved experiments"
        >
          <div
            className="planning-card"
            style={{
              width: "90%",
              maxWidth: "600px",
              maxHeight: "80vh",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div className="planning-card-header">
              <h3 className="planning-card-title">Saved Experiments</h3>
              <button
                type="button"
                className="pb-btn pb-secondary"
                onClick={() => {
                  setShowSavedModal(false);
                }}
              >
                Close
              </button>
            </div>
            <div className="saved-experiments-list">
              {savedSuites.length === 0 ? (
                <p
                  style={{
                    color: "var(--text-muted)",
                    textAlign: "center",
                    padding: "2rem",
                  }}
                >
                  No saved experiments found for your account.
                </p>
              ) : (
                savedSuites.map((s) => (
                  <div key={s.id} className="saved-experiment-item">
                    <div>
                      <strong style={{ display: "block" }}>{s.name}</strong>
                      <small style={{ color: "var(--text-muted)" }}>
                        {s.created_at} · {s.description || "No description"}
                      </small>
                    </div>
                    <button
                      type="button"
                      className="pb-btn pb-secondary"
                      onClick={() => {
                        void handleLoadExperiment(s.id);
                      }}
                    >
                      Reopen
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
