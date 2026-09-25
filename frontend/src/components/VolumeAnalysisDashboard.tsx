import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { API_BASE_URL } from "../config";
import type { RunningMetrics } from "../types/simulation";
import "./VolumeAnalysisDashboard.css";
import { CloseButton } from "./ui/CloseButton";
import { LoaderMark } from "./ui/Loader";
import { CHART_GRID, CHART_AXIS } from "../theme/chart";
import {
  SPEED_LIMITS,
  TIER_PRESETS,
  sweepRates,
  type TierPresetId,
} from "../types/demand";
import { TierMetrics } from "./TierMetrics";
import {
  LOS_THRESHOLDS,
  LOS_WORDS,
  SIDE_TITLE,
  levelOfService,
  type LosGrade,
  type Side,
} from "../metrics/plainLanguage";

// ── Types ──────────────────────────────────────────────────────────────────

type SweepWinner = "signal" | "roundabout" | "tie" | "inconclusive";

interface Calibration {
  calibrated: boolean;
  note: string;
}

interface TieTolerance {
  absSeconds: number;
  relative: number;
}

/** Same rule as backend study/tolerances.py and plainLanguage SIMILARITY.delay. */
const DEFAULT_TIE_TOLERANCE: TieTolerance = { absSeconds: 1, relative: 0.05 };

function tieText(t: TieTolerance | undefined): string {
  const tol = t ?? DEFAULT_TIE_TOLERANCE;
  return `≤${tol.absSeconds.toString()} s or ≤${(tol.relative * 100).toString()}%`;
}

function winnerLabel(w: SweepWinner): string {
  if (w === "roundabout") return "🔄 Lower delay: roundabout";
  if (w === "signal") return "🚦 Lower delay: signal";
  if (w === "tie") return "⚖️ About the same";
  return "❔ Inconclusive";
}

interface SweepRun {
  arrivalRate: number;
  hourlyVolumeVehPerHour: number;
  /** Lower mean delay at this tier. "inconclusive": too few vehicles got
   *  through, or the vehicle limit cut demand off, so no direction is given. */
  winner: SweepWinner;
  inconclusiveReason?: "low_sample" | "vehicle_limit_reached" | null;
  vehicleLimitReached?: boolean;
  delayDeltaPercent: number;
  throughputDeltaPercent?: number;
  queueDeltaPercent?: number;
  signal: {
    delay: number;
    delayMedian?: number;
    delayStdDev?: number;
    delayMin?: number;
    delayMax?: number;
    delayP95?: number;
    throughput: number;
    throughputRate?: number;
    queue: number;
    queueMax?: number;
    queueStdDev?: number;
    /** Full collector metrics for this tier's run (same set as live). */
    metrics?: RunningMetrics;
  };
  roundabout: {
    delay: number;
    delayMedian?: number;
    delayStdDev?: number;
    delayMin?: number;
    delayMax?: number;
    delayP95?: number;
    throughput: number;
    throughputRate?: number;
    queue: number;
    queueMax?: number;
    queueStdDev?: number;
    metrics?: RunningMetrics;
  };
}

interface SweepCurves {
  rates: number[];
  volumesVehPerHour: number[];
  signal: {
    delays: number[];
    delayStds?: number[];
    delayMins?: number[];
    delayMaxs?: number[];
    throughputs: number[];
    queues: number[];
    queueStds?: number[];
    queueMaxs?: number[];
  };
  roundabout: {
    delays: number[];
    delayStds?: number[];
    delayMins?: number[];
    delayMaxs?: number[];
    throughputs: number[];
    queues: number[];
    queueStds?: number[];
    queueMaxs?: number[];
  };
  crossoverArrivalRate: number | null;
  crossoverHourlyVolume: number | null;
  /** The two decided tiers the change lies between (not interpolated). */
  crossoverBracketArrivalRates?: [number, number] | null;
}

interface SweepSession {
  sessionId: string;
  name: string;
  duration: number;
  randomSeed: number;
  seedsPerTier?: number;
  tieTolerance?: TieTolerance;
  /** Absent on sweeps saved before calibration was recorded. */
  calibration?: Calibration;
  curves: SweepCurves;
  runs: SweepRun[];
}

interface SavedSweep {
  id: string;
  name: string;
  created_at: string;
}

/** Fields describing how a sweep was run, from either payload shape (flat, or
 *  nested under `results` for older saved sweeps). */
function sessionExtras(
  raw: Record<string, unknown>,
  rawResults: Record<string, unknown>,
): Pick<SweepSession, "calibration" | "tieTolerance" | "seedsPerTier"> {
  const pick = (key: string): unknown => raw[key] ?? rawResults[key];
  return {
    calibration: pick("calibration") as Calibration | undefined,
    tieTolerance: pick("tieTolerance") as TieTolerance | undefined,
    seedsPerTier: pick("seedsPerTier") as number | undefined,
  };
}

/**
 * Offered demand in veh/h is always derived from each tier's arrivalRate
 * (the whole junction's rate, split across the four approaches by the
 * spawner): veh/h = rate x 3600. Sweeps saved before the backend fix
 * stored rate x 3600 x 4, overstating demand four-fold, so stored hourly
 * values are recomputed rather than trusted.
 */
function withOfferedVolumes(session: SweepSession): SweepSession {
  const vph = (rate: number) => Math.round(rate * 3600);
  return {
    ...session,
    runs: session.runs.map((r) => ({
      ...r,
      hourlyVolumeVehPerHour: vph(r.arrivalRate),
    })),
    curves: {
      ...session.curves,
      volumesVehPerHour: session.curves.rates.map(vph),
      crossoverHourlyVolume:
        session.curves.crossoverArrivalRate === null
          ? null
          : vph(session.curves.crossoverArrivalRate),
    },
  };
}

const CONTROL_NAME = { signal: "signal", roundabout: "roundabout" } as const;

/** Describes the sweep's change of direction from the data itself: which
 *  control had the lower mean delay on each side, rather than assuming a
 *  direction. Tiers that were a tie or inconclusive take no part. */
function crossoverSummary(
  runs: SweepRun[],
  crossover: number | null,
  bracket?: [number, number] | null,
): string {
  const decided = runs.filter(
    (r) => r.winner === "signal" || r.winner === "roundabout",
  );
  const undecided = runs.length - decided.length;
  const suffix = ` (this sweep, one random pattern per tier${undecided > 0 ? `; ${undecided.toString()} tier${undecided === 1 ? " was" : "s were"} a tie or inconclusive` : ""}).`;
  if (crossover !== null) {
    const below = decided.filter(
      (r) => r.arrivalRate < (bracket?.[1] ?? Infinity),
    );
    const last = below.length > 0 ? below[below.length - 1] : undefined;
    const from = bracket
      ? `between ${Math.round(bracket[0] * 3600).toLocaleString()} and ${Math.round(bracket[1] * 3600).toLocaleString()} veh/h`
      : `at ≈${crossover.toLocaleString()} veh/h`;
    if (!last || (last.winner !== "signal" && last.winner !== "roundabout")) {
      return `The control with the lower mean delay changes ${from}${suffix}`;
    }
    const first = CONTROL_NAME[last.winner];
    const other = last.winner === "signal" ? "roundabout" : "signal";
    return `Lower mean delay: ${first} before, ${other} after, the change lying ${from}${suffix}`;
  }
  if (decided.length === 0) {
    return `No tier could be decided: every tier was within the tie tolerance or inconclusive.`;
  }
  const kinds = new Set(decided.map((r) => r.winner));
  if (kinds.size === 1) {
    return `The ${CONTROL_NAME[decided[0].winner as "signal" | "roundabout"]} had the lower mean delay at every decided tier${suffix}`;
  }
  return "No single change: the lower-delay control alternated more than once.";
}

type StudioTab = "curves" | "matrix" | "insights";
type MetricView = "all" | "delay" | "throughput" | "queue";
type XAxisMode = "volume" | "rate";

// ── Level of service (shared bands) ────────────────────────────────────────
//
// One definition of the grade bands for the whole app: metrics/plainLanguage
// (LOS_THRESHOLDS / levelOfService), which uses the Highway Capacity Manual's
// signalised bands for the signal and its stricter unsignalised bands for the
// roundabout. Only the colours live here. The grade is an indicative reading
// of simulated delay, not an HCM analysis (see the reading guide tab).

interface LOSInfo {
  grade: LosGrade;
  label: string;
  color: string;
  bg: string;
}

const LOS_COLORS: Record<LosGrade, { color: string; bg: string }> = {
  A: { color: "#10b981", bg: "rgba(16, 185, 129, 0.15)" },
  B: { color: "#34d399", bg: "rgba(52, 211, 153, 0.15)" },
  C: { color: "#fbbf24", bg: "rgba(251, 191, 36, 0.15)" },
  D: { color: "#f97316", bg: "rgba(249, 115, 22, 0.15)" },
  E: { color: "#ef4444", bg: "rgba(239, 68, 68, 0.15)" },
  F: { color: "#f43f5e", bg: "rgba(244, 63, 94, 0.2)" },
};

function getLevelOfService(delaySeconds: number, side: Side): LOSInfo {
  const grade = levelOfService(delaySeconds, side);
  return { grade, label: LOS_WORDS[grade], ...LOS_COLORS[grade] };
}

// ── Chart data builder ──────────────────────────────────────────────────────

function buildChartData(session: SweepSession) {
  if (!Array.isArray(session.runs)) return [];
  return session.runs.map((run) => {
    const sigDelay = Number(run.signal.delay.toFixed(2));
    const rndDelay = Number(run.roundabout.delay.toFixed(2));
    const sigDelayStd = Number((run.signal.delayStdDev ?? 0).toFixed(2));
    const rndDelayStd = Number((run.roundabout.delayStdDev ?? 0).toFixed(2));
    const sigDelayMin = Number(
      (run.signal.delayMin ?? Math.max(0, sigDelay - sigDelayStd)).toFixed(2),
    );
    const sigDelayMax = Number(
      (run.signal.delayMax ?? sigDelay + sigDelayStd).toFixed(2),
    );
    const rndDelayMin = Number(
      (run.roundabout.delayMin ?? Math.max(0, rndDelay - rndDelayStd)).toFixed(
        2,
      ),
    );
    const rndDelayMax = Number(
      (run.roundabout.delayMax ?? rndDelay + rndDelayStd).toFixed(2),
    );
    const sigQueue = Number(run.signal.queue.toFixed(2));
    const rndQueue = Number(run.roundabout.queue.toFixed(2));
    const sigQueueMax = Number((run.signal.queueMax ?? sigQueue).toFixed(2));
    const rndQueueMax = Number(
      (run.roundabout.queueMax ?? rndQueue).toFixed(2),
    );

    return {
      volume: run.hourlyVolumeVehPerHour,
      rate: Number(run.arrivalRate.toFixed(2)),
      signalDelay: sigDelay,
      signalDelayMin: sigDelayMin,
      signalDelayMax: sigDelayMax,
      signalDelayStdDev: sigDelayStd,
      roundaboutDelay: rndDelay,
      roundaboutDelayMin: rndDelayMin,
      roundaboutDelayMax: rndDelayMax,
      roundaboutDelayStdDev: rndDelayStd,
      signalThroughput: run.signal.throughput,
      roundaboutThroughput: run.roundabout.throughput,
      signalQueue: sigQueue,
      signalQueueMax: sigQueueMax,
      roundaboutQueue: rndQueue,
      roundaboutQueueMax: rndQueueMax,
      winner: run.winner,
      delayDeltaPercent: Number(run.delayDeltaPercent.toFixed(1)),
      throughputDeltaPercent: Number(
        (run.throughputDeltaPercent ?? 0).toFixed(1),
      ),
      queueDeltaPercent: Number((run.queueDeltaPercent ?? 0).toFixed(1)),
    };
  });
}

// ── Custom Tooltip ──────────────────────────────────────────────────────────

const CustomTooltip = ({
  active,
  payload,
  label,
  unit = "",
  xMode = "volume",
}: {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    color: string;
    payload?: unknown;
  }>;
  label?: number | string;
  unit?: string;
  xMode?: XAxisMode;
}) => {
  if (!active || !payload || payload.length === 0) return null;

  const raw = payload[0].payload as
    | {
        winner?: SweepWinner;
        delayDeltaPercent?: number;
        throughputDeltaPercent?: number;
        queueDeltaPercent?: number;
        signalDelayStdDev?: number;
        roundaboutDelayStdDev?: number;
        signalDelayMin?: number;
        signalDelayMax?: number;
        roundaboutDelayMin?: number;
        roundaboutDelayMax?: number;
        signalQueueMax?: number;
        roundaboutQueueMax?: number;
      }
    | undefined;

  return (
    <div className="custom-chart-tooltip">
      <div className="tooltip-header">
        <span className="tooltip-x-val">
          {xMode === "volume"
            ? `${String(label)} veh/h`
            : `${String(label)} veh/s`}
        </span>
        {raw?.winner && (
          <span className={`tooltip-winner-badge winner-${raw.winner}`}>
            {winnerLabel(raw.winner)}
          </span>
        )}
      </div>
      <div className="tooltip-metrics">
        {payload.map((p) => {
          let extraInfo = "";
          if (
            p.name === "Fixed-Time Signal" &&
            raw?.signalDelayStdDev !== undefined &&
            unit === "s"
          ) {
            const minStr =
              raw.signalDelayMin !== undefined
                ? `${raw.signalDelayMin.toFixed(1)}–`
                : "";
            const maxStr =
              raw.signalDelayMax !== undefined
                ? `${raw.signalDelayMax.toFixed(1)}s`
                : "";
            extraInfo = ` (±${raw.signalDelayStdDev.toFixed(2)}s, [${minStr}${maxStr}])`;
          } else if (
            p.name === "Modern Roundabout" &&
            raw?.roundaboutDelayStdDev !== undefined &&
            unit === "s"
          ) {
            const minStr =
              raw.roundaboutDelayMin !== undefined
                ? `${raw.roundaboutDelayMin.toFixed(1)}–`
                : "";
            const maxStr =
              raw.roundaboutDelayMax !== undefined
                ? `${raw.roundaboutDelayMax.toFixed(1)}s`
                : "";
            extraInfo = ` (±${raw.roundaboutDelayStdDev.toFixed(2)}s, [${minStr}${maxStr}])`;
          } else if (
            p.name === "Fixed-Time Signal" &&
            raw?.signalQueueMax !== undefined &&
            unit.includes("veh")
          ) {
            extraInfo = ` (Peak: ${raw.signalQueueMax.toFixed(1)})`;
          } else if (
            p.name === "Modern Roundabout" &&
            raw?.roundaboutQueueMax !== undefined &&
            unit.includes("veh")
          ) {
            extraInfo = ` (Peak: ${raw.roundaboutQueueMax.toFixed(1)})`;
          }

          return (
            <div key={p.name} className="tooltip-row">
              <span className="tooltip-dot" style={{ background: p.color }} />
              <span className="tooltip-name">{p.name}:</span>
              <span className="tooltip-val" style={{ color: p.color }}>
                {p.value.toFixed(2)}
                {unit}
                {extraInfo && (
                  <span
                    className="tooltip-extra"
                    style={{
                      fontSize: "11px",
                      opacity: 0.85,
                      marginLeft: "4px",
                    }}
                  >
                    {extraInfo}
                  </span>
                )}
              </span>
            </div>
          );
        })}
        {raw?.delayDeltaPercent !== undefined && unit === "s" && (
          <div
            className="tooltip-delta-row"
            style={{
              marginTop: "6px",
              paddingTop: "6px",
              borderTop: "1px solid rgba(255,255,255,0.1)",
              fontSize: "11px",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span style={{ color: "hsl(var(--muted-foreground))" }}>
              Δ Relative Difference:
            </span>
            <span
              style={{
                fontWeight: 700,
                color:
                  raw.delayDeltaPercent > 0
                    ? "#38bdf8"
                    : raw.delayDeltaPercent < 0
                      ? "#10b981"
                      : "#f59e0b",
              }}
            >
              {raw.delayDeltaPercent > 0
                ? `+${raw.delayDeltaPercent.toFixed(1)}% (signal lower)`
                : raw.delayDeltaPercent < 0
                  ? `${raw.delayDeltaPercent.toFixed(1)}% (roundabout lower)`
                  : "0.0% (Parity)"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

// ── Main Component ──────────────────────────────────────────────────────────

export const VolumeAnalysisDashboard: React.FC = () => {
  const [savedSweeps, setSavedSweeps] = useState<SavedSweep[]>([]);
  const [activeSession, setActiveSession] = useState<SweepSession | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Tab & View Controls
  const [activeTab, setActiveTab] = useState<StudioTab>("curves");
  const [showAdvancedDrawer, setShowAdvancedDrawer] = useState(false);
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);

  // Sweep config form state
  const [sweepDuration, setSweepDuration] = useState(240);
  const [randomSeed, setRandomSeed] = useState(42);

  // Advanced Config state
  const [demandTierPreset, setDemandTierPreset] = useState<
    "standard" | "dense" | "granular"
  >("standard");
  const [arrivalDistribution, setArrivalDistribution] = useState<
    "poisson" | "uniform"
  >("poisson");
  const [warmupTime, setWarmupTime] = useState(30.0);
  const [timeStep, setTimeStep] = useState(0.1);
  const [approachLength, setApproachLength] = useState(200.0);
  const [lanesCount, setLanesCount] = useState(1);
  const [speedProfileKey, setSpeedProfileKey] = useState<
    "standard" | "calmed" | "arterial"
  >("standard");

  // Scrubber volume override state
  const [scrubberVolumeOverride, setScrubberVolumeOverride] = useState<
    number | null
  >(null);

  // Interactive UI view controls
  const [metricView, setMetricView] = useState<MetricView>("delay");
  const [xAxisMode, setXAxisMode] = useState<XAxisMode>("volume");
  const [showUncertaintyBands, setShowUncertaintyBands] = useState(true);
  const [showDeltaTrend, setShowDeltaTrend] = useState(false);
  const [filterWinner, setFilterWinner] = useState<
    "all" | "roundabout" | "signal" | "tie"
  >("all");

  const [isRunning, setIsRunning] = useState(false);
  const [sweepError, setSweepError] = useState<string | null>(null);
  const [loadingSession, setLoadingSession] = useState(false);

  // Demand tiers: the three presets, as shares of the capacity measured for
  // the chosen lane count (types/demand.ts), so they span free flow to
  // oversaturation at every lane count.
  const ratesConfig = useMemo(() => {
    const id: TierPresetId =
      demandTierPreset === "dense"
        ? "wide"
        : demandTierPreset === "granular"
          ? "transition"
          : "standard";
    const preset = TIER_PRESETS.find((t) => t.id === id) ?? TIER_PRESETS[0];
    return { rates: sweepRates(preset, lanesCount), detail: preset.detail };
  }, [demandTierPreset, lanesCount]);

  // Reset advanced parameters to defaults
  const resetAdvancedDefaults = () => {
    setSweepDuration(240);
    setRandomSeed(42);
    setDemandTierPreset("standard");
    setArrivalDistribution("poisson");
    setWarmupTime(30.0);
    setTimeStep(0.1);
    setApproachLength(200.0);
    setLanesCount(1);
    setSpeedProfileKey("standard");
  };

  // Load a specific sweep session
  const loadSweep = useCallback((id: string) => {
    setSelectedId(id);
    setLoadingSession(true);
    setShowHistoryDrawer(false);
    setShowAdvancedDrawer(false);
    fetch(`${API_BASE_URL}/api/v1/study/sweeps/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status.toString()}`);
        return r.json();
      })
      .then((data: unknown) => {
        const raw = data as Record<string, unknown>;
        const rawResults =
          raw.results && typeof raw.results === "object"
            ? (raw.results as Record<string, unknown>)
            : {};
        const runs: SweepRun[] = Array.isArray(raw.runs)
          ? (raw.runs as SweepRun[])
          : Array.isArray(rawResults.runs)
            ? (rawResults.runs as SweepRun[])
            : [];
        const curves: SweepCurves = (raw.curves as SweepCurves | undefined) ??
          (rawResults.curves as SweepCurves | undefined) ?? {
            rates: [],
            volumesVehPerHour: [],
            signal: { delays: [], throughputs: [], queues: [] },
            roundabout: { delays: [], throughputs: [], queues: [] },
            crossoverArrivalRate: null,
            crossoverHourlyVolume: null,
          };
        const rawSessionId =
          typeof raw.sessionId === "string"
            ? raw.sessionId
            : typeof raw.id === "string"
              ? raw.id
              : typeof rawResults.sessionId === "string"
                ? rawResults.sessionId
                : id;
        const rawName =
          typeof raw.name === "string"
            ? raw.name
            : typeof rawResults.name === "string"
              ? rawResults.name
              : "Saved Sweep";
        const session: SweepSession = {
          sessionId: rawSessionId,
          name: rawName,
          duration: Number(raw.duration ?? rawResults.duration ?? 60),
          randomSeed: Number(raw.randomSeed ?? rawResults.randomSeed ?? 42),
          curves,
          runs,
          ...sessionExtras(raw, rawResults),
        };
        setActiveSession(withOfferedVolumes(session));
        setScrubberVolumeOverride(null);
        setLoadingSession(false);
      })
      .catch(() => {
        setLoadingSession(false);
        setSweepError("Failed to load sweep results.");
      });
  }, []);

  // Fetch saved sweep list
  const fetchSweeps = useCallback(() => {
    fetch(`${API_BASE_URL}/api/v1/study/sweeps`)
      .then((r) => r.json())
      .then((data: SavedSweep[]) => {
        setSavedSweeps(data);
      })
      .catch(() => {
        setSavedSweeps([]);
      });
  }, []);

  useEffect(() => {
    fetchSweeps();
  }, [fetchSweeps]);

  // Trigger new sweep via API
  const runSweep = () => {
    setIsRunning(true);
    setSweepError(null);
    setShowAdvancedDrawer(false);
    setShowHistoryDrawer(false);

    const customConfig = {
      simulation: {
        warmupTime,
        timeStep,
        duration: sweepDuration,
        randomSeed,
      },
      roads: {
        approachLength,
        laneWidth: 3.5,
        speedLimit: SPEED_LIMITS[speedProfileKey].metresPerSecond,
        lanesPerApproach: {
          north: lanesCount,
          south: lanesCount,
          east: lanesCount,
          west: lanesCount,
        },
      },
      traffic: {
        arrivalDistribution,
      },
    };

    fetch(`${API_BASE_URL}/api/v1/study/sweeps/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        duration: sweepDuration,
        randomSeed: randomSeed,
        arrivalRates: ratesConfig.rates,
        name: `Sweep (${ratesConfig.rates.length.toString()} tiers, ${sweepDuration.toString()}s)`,
        customConfig,
      }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status.toString()}`);
        return r.json();
      })
      .then((data: unknown) => {
        const raw = data as Record<string, unknown>;
        const rawResults =
          raw.results && typeof raw.results === "object"
            ? (raw.results as Record<string, unknown>)
            : {};
        const runs: SweepRun[] = Array.isArray(raw.runs)
          ? (raw.runs as SweepRun[])
          : Array.isArray(rawResults.runs)
            ? (rawResults.runs as SweepRun[])
            : [];
        const curves: SweepCurves = (raw.curves as SweepCurves | undefined) ??
          (rawResults.curves as SweepCurves | undefined) ?? {
            rates: [],
            volumesVehPerHour: [],
            signal: { delays: [], throughputs: [], queues: [] },
            roundabout: { delays: [], throughputs: [], queues: [] },
            crossoverArrivalRate: null,
            crossoverHourlyVolume: null,
          };
        const rawSessionId =
          typeof raw.sessionId === "string"
            ? raw.sessionId
            : typeof raw.id === "string"
              ? raw.id
              : typeof rawResults.sessionId === "string"
                ? rawResults.sessionId
                : "session";
        const rawName =
          typeof raw.name === "string"
            ? raw.name
            : typeof rawResults.name === "string"
              ? rawResults.name
              : "Completed Sweep";
        const session: SweepSession = {
          sessionId: rawSessionId,
          name: rawName,
          duration: Number(
            raw.duration ?? rawResults.duration ?? sweepDuration,
          ),
          randomSeed: Number(
            raw.randomSeed ?? rawResults.randomSeed ?? randomSeed,
          ),
          curves,
          runs,
          ...sessionExtras(raw, rawResults),
        };
        setActiveSession(withOfferedVolumes(session));
        setSelectedId(session.sessionId);
        setScrubberVolumeOverride(null);
        setIsRunning(false);
        fetchSweeps();
      })
      .catch((e: unknown) => {
        setSweepError(e instanceof Error ? e.message : "Sweep failed");
        setIsRunning(false);
      });
  };

  // Export CSV helper
  const exportCSV = () => {
    if (!activeSession || !Array.isArray(activeSession.runs)) return;
    const headers = [
      "Arrival Rate (veh/s)",
      "Hourly Volume (veh/h)",
      "Signal Delay (s)",
      "Roundabout Delay (s)",
      "Delay Delta (%)",
      "Signal Throughput (veh)",
      "Roundabout Throughput (veh)",
      "Signal Queue (veh)",
      "Roundabout Queue (veh)",
      "Lower mean delay (tie / inconclusive shown as such)",
    ];

    const rows = activeSession.runs.map((r) => [
      r.arrivalRate.toFixed(2),
      r.hourlyVolumeVehPerHour.toString(),
      r.signal.delay.toFixed(2),
      r.roundabout.delay.toFixed(2),
      r.delayDeltaPercent.toFixed(1),
      r.signal.throughput.toString(),
      r.roundabout.throughput.toString(),
      r.signal.queue.toFixed(1),
      r.roundabout.queue.toFixed(1),
      r.winner,
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `traffic_volume_sweep_${activeSession.sessionId.slice(0, 8)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const chartData = activeSession ? buildChartData(activeSession) : [];
  const crossover = activeSession?.curves.crossoverHourlyVolume ?? null;
  const xDataKey = xAxisMode === "volume" ? "volume" : "rate";

  const runsList = useMemo(() => {
    if (activeSession && Array.isArray(activeSession.runs)) {
      return activeSession.runs;
    }
    return [];
  }, [activeSession]);

  // Compute quick KPI metrics
  const roundaboutWins = runsList.filter(
    (r) => r.winner === "roundabout",
  ).length;
  const signalWins = runsList.filter((r) => r.winner === "signal").length;
  const tieWins = runsList.filter((r) => r.winner === "tie").length;
  const inconclusiveTiers = runsList.filter(
    (r) => r.winner === "inconclusive",
  ).length;
  const cappedTiers = runsList.filter((r) => r.vehicleLimitReached).length;
  const totalRuns = runsList.length;

  // Tier with the largest absolute mean-delay difference (roundabout − signal).
  const largestGap = runsList.reduce<{ run: SweepRun; diff: number } | null>(
    (best, run) => {
      const diff = run.roundabout.delay - run.signal.delay;
      return !best || Math.abs(diff) > Math.abs(best.diff)
        ? { run, diff }
        : best;
    },
    null,
  );

  // Filtered runs for table
  const filteredRuns = useMemo(() => {
    if (filterWinner === "all") return runsList;
    return runsList.filter((r) => r.winner === filterWinner);
  }, [runsList, filterWinner]);

  // Scrubber min/max & closest run computation
  const minVol = runsList[0]?.hourlyVolumeVehPerHour ?? 360;
  const maxVol = runsList[runsList.length - 1]?.hourlyVolumeVehPerHour ?? 2880;

  const currentScrubberVolume = useMemo(() => {
    if (scrubberVolumeOverride !== null) return scrubberVolumeOverride;
    if (activeSession?.curves.crossoverHourlyVolume) {
      return activeSession.curves.crossoverHourlyVolume;
    }
    if (runsList.length > 0) {
      const midIdx = Math.floor(runsList.length / 2);
      return runsList[midIdx].hourlyVolumeVehPerHour;
    }
    return 1440;
  }, [activeSession, scrubberVolumeOverride, runsList]);

  const currentScrubberRun = useMemo(() => {
    if (runsList.length === 0) return null;
    let closest = runsList[0];
    let minDiff = Math.abs(
      closest.hourlyVolumeVehPerHour - currentScrubberVolume,
    );
    for (const run of runsList) {
      const diff = Math.abs(run.hourlyVolumeVehPerHour - currentScrubberVolume);
      if (diff < minDiff) {
        minDiff = diff;
        closest = run;
      }
    }
    return closest;
  }, [runsList, currentScrubberVolume]);

  const maxDelayInRuns = useMemo(() => {
    if (runsList.length === 0) return 60;
    return Math.max(
      ...runsList.map((r) => Math.max(r.signal.delay, r.roundabout.delay)),
      10,
    );
  }, [runsList]);

  return (
    <div className="volume-dashboard">
      {/* ── Top Executive Header ───────────────────────── */}
      <div className="volume-header-row">
        <div className="header-title-group">
          <div className="header-badge-row">
            <h2>📈 Traffic Volume & Capacity Analysis</h2>
            <span className="header-mini-chip">Capacity Studio</span>
            <span className="header-version-chip">HCM 6th Ed.</span>
          </div>
          <p className="header-subtitle">
            Systematic sensitivity study comparing Fixed-Time Signals vs. Modern
            Roundabouts across demand tiers. Uses its own study scenario (set
            under Advanced Config), one seed per tier.
          </p>
        </div>

        <div className="header-actions">
          {/* Inline Duration & Seed controls in line with the heading */}
          <div className="header-inline-controls">
            <div className="inline-param">
              <label>Duration</label>
              <div className="inline-unit-wrap">
                <input
                  type="number"
                  min={10}
                  max={300}
                  step={10}
                  value={sweepDuration}
                  onChange={(e) => {
                    setSweepDuration(Number(e.target.value));
                  }}
                  title="Duration per rate tier (10–300s)"
                />
                <span>s</span>
              </div>
            </div>

            <div className="inline-param">
              <label>Seed</label>
              <div className="inline-seed-wrap">
                <input
                  type="number"
                  min={1}
                  value={randomSeed}
                  onChange={(e) => {
                    setRandomSeed(Number(e.target.value));
                  }}
                  title="Random seed for traffic generation"
                />
                <button
                  type="button"
                  className="dice-btn"
                  onClick={() => {
                    setRandomSeed(Math.floor(Math.random() * 999999) + 1);
                  }}
                  title="Randomize seed"
                >
                  🎲
                </button>
              </div>
            </div>

            <button
              type="button"
              className="header-run-btn"
              onClick={runSweep}
              disabled={isRunning}
              title="Execute capacity volume sweep"
            >
              {isRunning ? "⏳ Running…" : "▶ Run Sweep"}
            </button>
          </div>

          {/* Button strictly named 'Advanced Config' */}
          <button
            type="button"
            className={`header-tool-btn ${showAdvancedDrawer ? "active" : ""}`}
            onClick={() => {
              setShowAdvancedDrawer((prev) => !prev);
              setShowHistoryDrawer(false);
            }}
            title="Configure granular demand tiers, physics, geometry and speed dynamics"
          >
            ⚙️ Advanced Config
          </button>

          {/* Saved Sweeps button */}
          <button
            type="button"
            className={`header-tool-btn ${showHistoryDrawer ? "active" : ""}`}
            onClick={() => {
              setShowHistoryDrawer((prev) => !prev);
              setShowAdvancedDrawer(false);
            }}
            title="Browse and restore past saved sweep sessions"
          >
            📁 Saved Sweeps ({savedSweeps.length.toString()})
          </button>

          {activeSession && (
            <button
              type="button"
              className="export-csv-btn"
              onClick={exportCSV}
              title="Download study dataset as CSV"
            >
              📥 Export CSV
            </button>
          )}
        </div>
      </div>

      {/* ── Advanced Configuration Drawer ── */}
      {showAdvancedDrawer && (
        <div className="volume-advanced-drawer">
          <div className="advanced-drawer-header">
            <div>
              <h3>⚙️ Advanced Experiment Configuration</h3>
              <p>
                Tailor arrival spectrum granularity, integration fidelity, road
                geometry, and vehicle kinematics.
              </p>
            </div>
            <CloseButton
              label="Close advanced configuration"
              onClick={() => {
                setShowAdvancedDrawer(false);
              }}
            />
          </div>

          <div className="advanced-config-grid">
            {/* Card 1: Traffic Demand Spectrum & Rates */}
            <div className="advanced-card">
              <div className="advanced-card-header">
                <span className="card-badge">01</span>
                <div>
                  <h4>📊 Demand Spectrum & Arrivals</h4>
                  <span className="card-desc">
                    Volume sweep resolution & arrival process
                  </span>
                </div>
              </div>

              <div className="advanced-field-group">
                <label>
                  Demand Tiers Spectrum ({ratesConfig.rates.length} Points)
                </label>
                <div className="option-pill-group vertical">
                  <button
                    type="button"
                    className={`option-pill ${demandTierPreset === "standard" ? "active" : ""}`}
                    onClick={() => {
                      setDemandTierPreset("standard");
                    }}
                  >
                    <span className="pill-title">Standard 8-Tier</span>
                    <span className="pill-desc">20% to 160% of capacity</span>
                  </button>
                  <button
                    type="button"
                    className={`option-pill ${demandTierPreset === "dense" ? "active" : ""}`}
                    onClick={() => {
                      setDemandTierPreset("dense");
                    }}
                  >
                    <span className="pill-title">Dense Congestion 10-Tier</span>
                    <span className="pill-desc">10% to 200% of capacity</span>
                  </button>
                  <button
                    type="button"
                    className={`option-pill ${demandTierPreset === "granular" ? "active" : ""}`}
                    onClick={() => {
                      setDemandTierPreset("granular");
                    }}
                  >
                    <span className="pill-title">
                      Granular Transition 10-Tier
                    </span>
                    <span className="pill-desc">60% to 150% of capacity</span>
                  </button>
                </div>
              </div>

              <div className="advanced-field-group">
                <label>Arrival Distribution</label>
                <div className="option-pill-group">
                  <button
                    type="button"
                    className={`option-pill ${arrivalDistribution === "poisson" ? "active" : ""}`}
                    onClick={() => {
                      setArrivalDistribution("poisson");
                    }}
                  >
                    Poisson (Stochastic)
                  </button>
                  <button
                    type="button"
                    className={`option-pill ${arrivalDistribution === "uniform" ? "active" : ""}`}
                    onClick={() => {
                      setArrivalDistribution("uniform");
                    }}
                  >
                    Uniform (Deterministic)
                  </button>
                </div>
                <span className="field-hint">
                  Poisson captures realistic random platooning & headway gaps.
                </span>
              </div>
            </div>

            {/* Card 2: Simulation Physics & Road Geometry */}
            <div className="advanced-card">
              <div className="advanced-card-header">
                <span className="card-badge">02</span>
                <div>
                  <h4>⚙️ Physics & Road Geometry</h4>
                  <span className="card-desc">
                    Numerical step size, warmup duration & approach road
                  </span>
                </div>
              </div>

              <div className="advanced-field-group">
                <div className="field-label-row">
                  <label>Warmup Duration (t_warm)</label>
                  <span className="field-val-badge">
                    {warmupTime.toFixed(1)}s
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={60}
                  step={5}
                  value={warmupTime}
                  onChange={(e) => {
                    setWarmupTime(Number(e.target.value));
                  }}
                  className="advanced-slider"
                />
                <span className="field-hint">
                  Allows network queues to pre-populate before metrics accrue.
                </span>
              </div>

              <div className="advanced-field-group">
                <label>Integration Time Step (Δt)</label>
                <div className="option-pill-group">
                  <button
                    type="button"
                    className={`option-pill ${timeStep === 0.05 ? "active" : ""}`}
                    onClick={() => {
                      setTimeStep(0.05);
                    }}
                  >
                    0.05s (High Precision)
                  </button>
                  <button
                    type="button"
                    className={`option-pill ${timeStep === 0.1 ? "active" : ""}`}
                    onClick={() => {
                      setTimeStep(0.1);
                    }}
                  >
                    0.10s (Balanced)
                  </button>
                  <button
                    type="button"
                    className={`option-pill ${timeStep === 0.2 ? "active" : ""}`}
                    onClick={() => {
                      setTimeStep(0.2);
                    }}
                  >
                    0.20s (Fast Sweep)
                  </button>
                </div>
              </div>

              <div className="advanced-field-group">
                <label>Approach Road Length</label>
                <div className="option-pill-group">
                  <button
                    type="button"
                    className={`option-pill ${approachLength === 150 ? "active" : ""}`}
                    onClick={() => {
                      setApproachLength(150);
                    }}
                  >
                    150m (Urban Tight)
                  </button>
                  <button
                    type="button"
                    className={`option-pill ${approachLength === 200 ? "active" : ""}`}
                    onClick={() => {
                      setApproachLength(200);
                    }}
                  >
                    200m (Standard)
                  </button>
                  <button
                    type="button"
                    className={`option-pill ${approachLength === 300 ? "active" : ""}`}
                    onClick={() => {
                      setApproachLength(300);
                    }}
                  >
                    300m (Extended)
                  </button>
                </div>
              </div>
            </div>

            {/* Card 3: Intersection Lanes & Fleet Speed */}
            <div className="advanced-card">
              <div className="advanced-card-header">
                <span className="card-badge">03</span>
                <div>
                  <h4>🚗 Approach Lanes & Fleet Speed</h4>
                  <span className="card-desc">
                    Lane capacity configuration and driver velocity bounds
                  </span>
                </div>
              </div>

              <div className="advanced-field-group">
                <label>Lanes per Approach (All 4 Legs)</label>
                <div className="option-pill-group">
                  {[1, 2, 3].map((n) => (
                    <button
                      key={n}
                      type="button"
                      className={`option-pill ${lanesCount === n ? "active" : ""}`}
                      onClick={() => {
                        setLanesCount(n);
                      }}
                    >
                      {n === 1
                        ? "1 Lane (calibrated comparison)"
                        : `${String(n)} Lanes (exploratory)`}
                    </button>
                  ))}
                </div>
                <span className="field-hint">
                  One lane per approach is the calibrated comparison. With more
                  lanes both junctions model every lane, but drivers leaving the
                  roundabout from an inner ring cross the outer one without lane
                  markings, so multi-lane results are exploratory.
                </span>
              </div>

              <div className="advanced-field-group">
                <label>Road Speed Limit</label>
                <div className="option-pill-group vertical">
                  <button
                    type="button"
                    className={`option-pill ${speedProfileKey === "standard" ? "active" : ""}`}
                    onClick={() => {
                      setSpeedProfileKey("standard");
                    }}
                  >
                    <span className="pill-title">Standard Urban</span>
                    <span className="pill-desc">50 km/h limit</span>
                  </button>
                  <button
                    type="button"
                    className={`option-pill ${speedProfileKey === "calmed" ? "active" : ""}`}
                    onClick={() => {
                      setSpeedProfileKey("calmed");
                    }}
                  >
                    <span className="pill-title">Traffic Calmed</span>
                    <span className="pill-desc">30 km/h limit</span>
                  </button>
                  <button
                    type="button"
                    className={`option-pill ${speedProfileKey === "arterial" ? "active" : ""}`}
                    onClick={() => {
                      setSpeedProfileKey("arterial");
                    }}
                  >
                    <span className="pill-title">Arterial Corridor</span>
                    <span className="pill-desc">60 km/h limit</span>
                  </button>
                </div>
              </div>

              <div className="advanced-field-group">
                <label>Quick Duration Presets</label>
                <div className="preset-pill-row">
                  <button
                    type="button"
                    className={`preset-pill ${sweepDuration === 120 ? "active" : ""}`}
                    onClick={() => {
                      setSweepDuration(120);
                    }}
                  >
                    ⚡ 120s Rapid
                  </button>
                  <button
                    type="button"
                    className={`preset-pill ${sweepDuration === 240 ? "active" : ""}`}
                    onClick={() => {
                      setSweepDuration(240);
                    }}
                  >
                    ⚖️ 240s Balanced
                  </button>
                  <button
                    type="button"
                    className={`preset-pill ${sweepDuration === 300 ? "active" : ""}`}
                    onClick={() => {
                      setSweepDuration(300);
                    }}
                  >
                    🔬 300s High Rigor
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="advanced-drawer-footer">
            <div className="drawer-footprint-chip">
              Active Parameters:{" "}
              <strong>{ratesConfig.rates.length} Rates</strong> ·{" "}
              <strong>{arrivalDistribution.toUpperCase()}</strong> ·{" "}
              <strong>Δt={timeStep.toFixed(2)}s</strong> ·{" "}
              <strong>
                {lanesCount} Lanes/Leg{lanesCount === 1 ? "" : " (exploratory)"}
              </strong>{" "}
              · <strong>{approachLength}m Approach</strong>
            </div>

            <div className="drawer-actions-right">
              <button
                type="button"
                className="advanced-reset-btn"
                onClick={resetAdvancedDefaults}
              >
                ↺ Reset Defaults
              </button>
              <button
                type="button"
                className="advanced-close-btn"
                onClick={() => {
                  setShowAdvancedDrawer(false);
                }}
              >
                ✕ Close
              </button>
              <button
                type="button"
                className="advanced-apply-btn"
                onClick={runSweep}
                disabled={isRunning}
              >
                {isRunning ? "⏳ Simulating…" : "▶ Apply & Run Sweep"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Saved Sweeps History Drawer ── */}
      {showHistoryDrawer && (
        <div className="volume-history-drawer">
          <div className="history-drawer-header">
            <div>
              <h3>📁 Saved Sweep Experiments</h3>
              <p>
                Select any historical volume sweep run to reload its capacity
                curves and crossover metrics.
              </p>
            </div>
            <CloseButton
              label="Close saved sweeps"
              onClick={() => {
                setShowHistoryDrawer(false);
              }}
            />
          </div>

          {savedSweeps.length > 0 ? (
            <div className="saved-sweeps-grid">
              {savedSweeps.map((s) => (
                <div
                  key={s.id}
                  className={`saved-sweep-card ${selectedId === s.id ? "active" : ""}`}
                  onClick={() => {
                    loadSweep(s.id);
                  }}
                >
                  <div className="sweep-card-top">
                    <span className="sweep-card-name">{s.name}</span>
                    {selectedId === s.id && (
                      <span className="active-pill">Active</span>
                    )}
                  </div>
                  <div className="sweep-card-date">
                    🕒{" "}
                    {new Date(s.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}{" "}
                    · {new Date(s.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-saved-hint">
              <span>
                No past sweeps found. Click <strong>Run Sweep</strong> above to
                benchmark and save curves.
              </span>
            </div>
          )}
        </div>
      )}

      {/* ── Running / Status Feedback ── */}
      {isRunning && (
        <div className="sweep-running-banner">
          <LoaderMark />
          <span>
            Simulating {ratesConfig.rates.length} volume tiers across Fixed-Time
            Signal and Modern Roundabout models ({sweepDuration}s/tier)…
          </span>
        </div>
      )}

      {sweepError && <div className="sweep-error-banner">⚠ {sweepError}</div>}

      {/* ── Loading indicator ──────────────────────────── */}
      {loadingSession && (
        <div className="sweep-loading">
          <LoaderMark />
          <span>Retrieving sweep curves and telemetry…</span>
        </div>
      )}

      {/* ── Empty State Hero (When No Active Session) ── */}
      {!activeSession && !loadingSession && !isRunning && (
        <div className="empty-sweep-hero">
          <div className="empty-hero-icon">📈</div>
          <h3>Ready to Execute Volume & Capacity Sweep</h3>
          <p>
            Systematic sensitivity study comparing Fixed-Time Signals vs. Modern
            Roundabouts across demand tiers. Configure your parameters or click
            below to launch the automated benchmark sweep.
          </p>
          <div className="empty-hero-actions">
            <button
              type="button"
              className="hero-run-btn"
              onClick={runSweep}
              disabled={isRunning}
            >
              ▶ Run Volume Sweep ({ratesConfig.rates.length} Tiers)
            </button>
            <button
              type="button"
              className="hero-secondary-btn"
              onClick={() => {
                setShowAdvancedDrawer(true);
                setShowHistoryDrawer(false);
              }}
            >
              ⚙️ Advanced Config
            </button>
            {savedSweeps.length > 0 && (
              <button
                type="button"
                className="hero-secondary-btn"
                onClick={() => {
                  setShowHistoryDrawer(true);
                  setShowAdvancedDrawer(false);
                }}
              >
                📁 Load Past Sweep ({savedSweeps.length.toString()})
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Active Results View ───────────────────────── */}
      {activeSession && !loadingSession && (
        <>
          {activeSession.calibration &&
            !activeSession.calibration.calibrated && (
              <p className="sweep-banner is-exploratory" role="note">
                <strong>Exploratory, not calibrated.</strong>{" "}
                {activeSession.calibration.note}
              </p>
            )}
          {!activeSession.calibration && (
            <p className="sweep-banner" role="note">
              This sweep was saved before its lane configuration was recorded,
              so it cannot be identified as the calibrated one-lane comparison.
            </p>
          )}
          {cappedTiers > 0 && (
            <p className="sweep-banner is-exploratory" role="note">
              <strong>Demand was cut off.</strong> Vehicle generation reached
              its per-run limit in {cappedTiers.toString()} of{" "}
              {totalRuns.toString()} tiers, so those tiers did not receive their
              full demand and are marked inconclusive.
            </p>
          )}
          {/* Executive KPI Cards */}
          <div className="volume-kpi-grid">
            <div className="kpi-card kpi-crossover-card">
              <div className="kpi-top">
                <span className="kpi-icon-badge">🎯</span>
                <span className="kpi-category">Delay ordering</span>
              </div>
              <span className="kpi-label">
                Where the lower-delay control changes
              </span>
              <span className="kpi-value highlight-amber">
                {crossover
                  ? `${crossover.toLocaleString()} veh/h`
                  : "No change observed"}
              </span>
              <span className="kpi-hint">
                {crossover
                  ? crossoverSummary(
                      runsList,
                      crossover,
                      activeSession.curves.crossoverBracketArrivalRates,
                    )
                  : crossoverSummary(runsList, null)}
              </span>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-icon-badge">⚖️</span>
                <span className="kpi-category">Tier tally</span>
              </div>
              <span className="kpi-label">Lower mean delay, by tier</span>
              <span className="kpi-value">
                🔄 {roundaboutWins.toString()} · 🚦 {signalWins.toString()} · ⚖️{" "}
                {tieWins.toString()}
              </span>
              <span className="kpi-hint">
                Roundabout · signal · about the same (
                {tieText(activeSession.tieTolerance)})
                {inconclusiveTiers > 0
                  ? ` · ${inconclusiveTiers.toString()} inconclusive`
                  : ""}
                , of {totalRuns.toString()} tiers — one seed each
              </span>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-icon-badge">⏱️</span>
                <span className="kpi-category">Largest gap</span>
              </div>
              <span className="kpi-label">Largest mean-delay difference</span>
              <span className="kpi-value">
                {largestGap
                  ? `${Math.abs(largestGap.diff).toFixed(1)} s`
                  : "N/A"}
              </span>
              <span className="kpi-hint">
                {largestGap
                  ? `Lower for the ${largestGap.diff < 0 ? "roundabout" : "signal"} at ${largestGap.run.hourlyVolumeVehPerHour.toLocaleString()} veh/h (one seed)`
                  : "No tiers yet"}
              </span>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-icon-badge">🚦</span>
                <span className="kpi-category">Stress Boundary</span>
              </div>
              <span className="kpi-label">Peak Evaluated Volume</span>
              <span className="kpi-value highlight-blue">
                {activeSession.curves.volumesVehPerHour.length > 0
                  ? `${Math.max(...activeSession.curves.volumesVehPerHour).toLocaleString()} veh/h`
                  : "—"}
              </span>
              <span className="kpi-hint">
                Highest capacity stress tier analyzed
              </span>
            </div>
          </div>

          {/* ── Studio Navigation Tabs ─────────────────── */}
          <div className="studio-tabs-bar">
            <button
              type="button"
              className={`studio-tab-btn ${activeTab === "curves" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("curves");
              }}
            >
              📈 Interactive Curves & Crossover Studio
            </button>
            <button
              type="button"
              className={`studio-tab-btn ${activeTab === "matrix" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("matrix");
              }}
            >
              🔬 Head-to-Head Volume Matrix
            </button>
            <button
              type="button"
              className={`studio-tab-btn ${activeTab === "insights" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("insights");
              }}
            >
              📖 How to read this sweep
            </button>
          </div>

          {/* ── Interactive Volume Scrubber Bar ───────── */}
          {activeTab !== "insights" &&
            currentScrubberRun &&
            (() => {
              const sigLOS = getLevelOfService(
                currentScrubberRun.signal.delay,
                "signal",
              );
              const rndLOS = getLevelOfService(
                currentScrubberRun.roundabout.delay,
                "roundabout",
              );
              return (
                <div className="volume-scrubber-bar">
                  <div className="scrubber-bar-left">
                    <div className="scrubber-label-group">
                      <span className="scrubber-title">🎛️ Demand Explorer</span>
                      <span className="scrubber-rate">
                        Rate: {currentScrubberRun.arrivalRate.toFixed(2)} veh/s
                      </span>
                    </div>
                    <div className="scrubber-vol-badge">
                      <strong>
                        {currentScrubberRun.hourlyVolumeVehPerHour.toLocaleString()}
                      </strong>{" "}
                      veh/h
                    </div>
                  </div>

                  <div className="scrubber-bar-center">
                    <span className="slider-edge-label">
                      {minVol.toLocaleString()}
                    </span>
                    <div className="slider-input-wrapper">
                      <input
                        type="range"
                        min={minVol}
                        max={maxVol}
                        step={100}
                        value={currentScrubberVolume}
                        onChange={(e) => {
                          setScrubberVolumeOverride(Number(e.target.value));
                        }}
                        className="volume-slider-input"
                        aria-label="Volume demand scrubber"
                      />
                      {crossover && (
                        <div
                          className="slider-crossover-marker"
                          style={{
                            left: `${Math.max(0, Math.min(100, ((crossover - minVol) / (maxVol - minVol)) * 100)).toString()}%`,
                          }}
                          title={`Crossover: ${crossover.toLocaleString()} veh/h`}
                        >
                          <span className="marker-pin">📍</span>
                        </div>
                      )}
                    </div>
                    <span className="slider-edge-label">
                      {maxVol.toLocaleString()}
                    </span>
                  </div>

                  <div className="scrubber-bar-right">
                    <div className="scrubber-chip signal-chip">
                      <span className="chip-label">🚦 Fixed-Time Signal</span>
                      <span className="chip-val">
                        {currentScrubberRun.signal.delay.toFixed(1)}s
                      </span>
                      <span
                        className="los-chip mini"
                        style={{ color: sigLOS.color, background: sigLOS.bg }}
                      >
                        LOS {sigLOS.grade}
                      </span>
                    </div>

                    <div className="scrubber-chip roundabout-chip">
                      <span className="chip-label">🔄 Modern Roundabout</span>
                      <span className="chip-val">
                        {currentScrubberRun.roundabout.delay.toFixed(1)}s
                      </span>
                      <span
                        className="los-chip mini"
                        style={{ color: rndLOS.color, background: rndLOS.bg }}
                      >
                        LOS {rndLOS.grade}
                      </span>
                    </div>

                    <div
                      className={`scrubber-verdict-chip winner-${currentScrubberRun.winner}`}
                    >
                      <span className="verdict-name">
                        {winnerLabel(currentScrubberRun.winner)}
                      </span>
                      <span className="verdict-delta">
                        {currentScrubberRun.delayDeltaPercent > 0 ? "+" : ""}
                        {currentScrubberRun.delayDeltaPercent.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              );
            })()}

          {/* ── TAB 1: Curves & Crossover Studio ───────── */}
          {activeTab === "curves" && (
            <div className="chart-studio-container">
              {/* Integrated Chart Header Controls */}
              <div className="chart-studio-header">
                <div className="chart-studio-title">
                  <h4>
                    {metricView === "delay" &&
                      "Average Delay vs. Traffic Volume"}
                    {metricView === "throughput" &&
                      "Throughput vs. Traffic Volume"}
                    {metricView === "queue" &&
                      "Average Queue Length vs. Traffic Volume"}
                    {metricView === "all" &&
                      "All Performance Envelopes (Delay · Throughput · Queue)"}
                  </h4>
                  <p className="chart-studio-subtitle">
                    {metricView === "delay" &&
                      "Vehicular control delay comparison across demand tiers (HCM 6th Edition)"}
                    {metricView === "throughput" &&
                      "Total vehicles cleared through intersection per simulation interval"}
                    {metricView === "queue" &&
                      "Mean standing queue depth per approach lane across volume levels"}
                    {metricView === "all" &&
                      "Side-by-side telemetry across all operational dimensions"}
                  </p>
                </div>

                <div className="chart-studio-controls">
                  <div className="chart-metric-pills">
                    <button
                      type="button"
                      className={`metric-pill-btn ${metricView === "delay" ? "active" : ""}`}
                      onClick={() => {
                        setMetricView("delay");
                      }}
                    >
                      ⏱️ Delay
                    </button>
                    <button
                      type="button"
                      className={`metric-pill-btn ${metricView === "throughput" ? "active" : ""}`}
                      onClick={() => {
                        setMetricView("throughput");
                      }}
                    >
                      🚗 Throughput
                    </button>
                    <button
                      type="button"
                      className={`metric-pill-btn ${metricView === "queue" ? "active" : ""}`}
                      onClick={() => {
                        setMetricView("queue");
                      }}
                    >
                      📏 Queue
                    </button>
                    <button
                      type="button"
                      className={`metric-pill-btn ${metricView === "all" ? "active" : ""}`}
                      onClick={() => {
                        setMetricView("all");
                      }}
                    >
                      📊 All 3
                    </button>
                  </div>

                  <div className="chart-option-pills">
                    <button
                      type="button"
                      className={`option-pill-btn ${showUncertaintyBands ? "active" : ""}`}
                      onClick={() => {
                        setShowUncertaintyBands(!showUncertaintyBands);
                      }}
                      title="Toggle spread bands: how much individual drivers' delays varied within each run (±σ and min–max). This is not uncertainty about the average."
                    >
                      ± Driver spread
                    </button>
                    <button
                      type="button"
                      className={`option-pill-btn ${showDeltaTrend ? "active" : ""}`}
                      onClick={() => {
                        setShowDeltaTrend(!showDeltaTrend);
                      }}
                      title="Toggle relative percentage delta comparison curve"
                    >
                      % Delta Trend
                    </button>
                  </div>

                  <div className="chart-axis-pills">
                    <button
                      type="button"
                      className={`axis-pill-btn ${xAxisMode === "volume" ? "active" : ""}`}
                      onClick={() => {
                        setXAxisMode("volume");
                      }}
                    >
                      veh/h
                    </button>
                    <button
                      type="button"
                      className={`axis-pill-btn ${xAxisMode === "rate" ? "active" : ""}`}
                      onClick={() => {
                        setXAxisMode("rate");
                      }}
                    >
                      veh/s
                    </button>
                  </div>
                </div>
              </div>

              {/* Charts Grid */}
              <div className={`charts-grid view-${metricView}`}>
                {/* Delay Chart */}
                {(metricView === "all" || metricView === "delay") && (
                  <div className="chart-card">
                    {metricView === "all" && (
                      <div className="chart-card-mini-header">
                        <span className="mini-title">⏱️ Control Delay (s)</span>
                        <span className="mini-unit">s / vehicle</span>
                      </div>
                    )}
                    {chartData.length > 0 ? (
                      <ResponsiveContainer
                        width="100%"
                        height={metricView === "all" ? 280 : 400}
                      >
                        <LineChart
                          data={chartData}
                          margin={{ top: 16, right: 24, bottom: 12, left: 8 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke={CHART_GRID}
                          />
                          <XAxis
                            dataKey={xDataKey}
                            tick={{
                              fontSize: 12,
                              fill: "hsl(var(--muted-foreground))",
                            }}
                            tickFormatter={(v: number) => v.toString()}
                            label={{
                              value:
                                xAxisMode === "volume"
                                  ? "Hourly Volume (veh/h)"
                                  : "Arrival Rate (veh/s)",
                              position: "insideBottom",
                              offset: -6,
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 12,
                            }}
                          />
                          <YAxis
                            tick={{
                              fontSize: 12,
                              fill: "hsl(var(--muted-foreground))",
                            }}
                            label={{
                              value: "Delay (s)",
                              angle: -90,
                              position: "insideLeft",
                              offset: 8,
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 12,
                            }}
                          />
                          <Tooltip
                            content={
                              <CustomTooltip unit="s" xMode={xAxisMode} />
                            }
                          />
                          <Legend
                            wrapperStyle={{ fontSize: 13, paddingTop: 10 }}
                          />
                          {crossover && xAxisMode === "volume" && (
                            <ReferenceLine
                              x={crossover}
                              stroke="#f59e0b"
                              strokeDasharray="4 3"
                              strokeWidth={2}
                              label={{
                                value: `Crossover (${crossover.toLocaleString()} veh/h)`,
                                position: "top",
                                fill: "#f59e0b",
                                fontSize: 12,
                              }}
                            />
                          )}
                          <Line
                            type="monotone"
                            dataKey="signalDelay"
                            name="Fixed-Time Signal"
                            stroke="#38bdf8"
                            strokeWidth={3}
                            dot={{ r: 5, fill: "#38bdf8" }}
                            activeDot={{
                              r: 8,
                              stroke: "#7dd3fc",
                              strokeWidth: 2,
                            }}
                            animationDuration={450}
                            animationEasing="ease-out"
                          />
                          <Line
                            type="monotone"
                            dataKey="roundaboutDelay"
                            name="Modern Roundabout"
                            stroke="#10b981"
                            strokeWidth={3}
                            dot={{ r: 5, fill: "#10b981" }}
                            activeDot={{
                              r: 8,
                              stroke: "#34d399",
                              strokeWidth: 2,
                            }}
                            animationDuration={450}
                            animationEasing="ease-out"
                          />
                          {showUncertaintyBands && (
                            <>
                              <Line
                                type="monotone"
                                dataKey="signalDelayMax"
                                name="Signal driver spread, upper (max / +σ)"
                                stroke="#38bdf8"
                                strokeDasharray="3 3"
                                strokeOpacity={0.4}
                                strokeWidth={1.5}
                                dot={false}
                                activeDot={false}
                              />
                              <Line
                                type="monotone"
                                dataKey="signalDelayMin"
                                name="Signal driver spread, lower (min / −σ)"
                                stroke="#38bdf8"
                                strokeDasharray="2 2"
                                strokeOpacity={0.3}
                                strokeWidth={1.2}
                                dot={false}
                                activeDot={false}
                              />
                              <Line
                                type="monotone"
                                dataKey="roundaboutDelayMax"
                                name="Roundabout driver spread, upper (max / +σ)"
                                stroke="#10b981"
                                strokeDasharray="3 3"
                                strokeOpacity={0.4}
                                strokeWidth={1.5}
                                dot={false}
                                activeDot={false}
                              />
                              <Line
                                type="monotone"
                                dataKey="roundaboutDelayMin"
                                name="Roundabout driver spread, lower (min / −σ)"
                                stroke="#10b981"
                                strokeDasharray="2 2"
                                strokeOpacity={0.3}
                                strokeWidth={1.2}
                                dot={false}
                                activeDot={false}
                              />
                            </>
                          )}
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="chart-empty">
                        No telemetry data recorded
                      </div>
                    )}
                  </div>
                )}

                {/* Throughput Chart */}
                {(metricView === "all" || metricView === "throughput") && (
                  <div className="chart-card">
                    {metricView === "all" && (
                      <div className="chart-card-mini-header">
                        <span className="mini-title">🚗 Throughput</span>
                        <span className="mini-unit">completed veh</span>
                      </div>
                    )}
                    {chartData.length > 0 ? (
                      <ResponsiveContainer
                        width="100%"
                        height={metricView === "all" ? 280 : 400}
                      >
                        <LineChart
                          data={chartData}
                          margin={{ top: 16, right: 24, bottom: 12, left: 8 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke={CHART_GRID}
                          />
                          <XAxis
                            dataKey={xDataKey}
                            tick={{
                              fontSize: 12,
                              fill: "hsl(var(--muted-foreground))",
                            }}
                            tickFormatter={(v: number) => v.toString()}
                            label={{
                              value:
                                xAxisMode === "volume"
                                  ? "Hourly Volume (veh/h)"
                                  : "Arrival Rate (veh/s)",
                              position: "insideBottom",
                              offset: -6,
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 12,
                            }}
                          />
                          <YAxis
                            tick={{
                              fontSize: 12,
                              fill: "hsl(var(--muted-foreground))",
                            }}
                            label={{
                              value: "Throughput (veh)",
                              angle: -90,
                              position: "insideLeft",
                              offset: 8,
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 12,
                            }}
                          />
                          <Tooltip
                            content={
                              <CustomTooltip unit=" veh" xMode={xAxisMode} />
                            }
                          />
                          <Legend
                            wrapperStyle={{ fontSize: 13, paddingTop: 10 }}
                          />
                          {crossover && xAxisMode === "volume" && (
                            <ReferenceLine
                              x={crossover}
                              stroke="#f59e0b"
                              strokeDasharray="4 3"
                              strokeWidth={2}
                            />
                          )}
                          <Line
                            type="monotone"
                            dataKey="signalThroughput"
                            name="Fixed-Time Signal"
                            stroke="#38bdf8"
                            strokeWidth={3}
                            dot={{ r: 5, fill: "#38bdf8" }}
                            activeDot={{
                              r: 8,
                              stroke: "#7dd3fc",
                              strokeWidth: 2,
                            }}
                            animationDuration={450}
                            animationEasing="ease-out"
                          />
                          <Line
                            type="monotone"
                            dataKey="roundaboutThroughput"
                            name="Modern Roundabout"
                            stroke="#10b981"
                            strokeWidth={3}
                            dot={{ r: 5, fill: "#10b981" }}
                            activeDot={{
                              r: 8,
                              stroke: "#34d399",
                              strokeWidth: 2,
                            }}
                            animationDuration={450}
                            animationEasing="ease-out"
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="chart-empty">
                        No telemetry data recorded
                      </div>
                    )}
                  </div>
                )}

                {/* Queue Chart */}
                {(metricView === "all" || metricView === "queue") && (
                  <div className="chart-card">
                    {metricView === "all" && (
                      <div className="chart-card-mini-header">
                        <span className="mini-title">📏 Queue Length</span>
                        <span className="mini-unit">avg veh / lane</span>
                      </div>
                    )}
                    {chartData.length > 0 ? (
                      <ResponsiveContainer
                        width="100%"
                        height={metricView === "all" ? 280 : 400}
                      >
                        <LineChart
                          data={chartData}
                          margin={{ top: 16, right: 24, bottom: 12, left: 8 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke={CHART_GRID}
                          />
                          <XAxis
                            dataKey={xDataKey}
                            tick={{
                              fontSize: 12,
                              fill: "hsl(var(--muted-foreground))",
                            }}
                            tickFormatter={(v: number) => v.toString()}
                            label={{
                              value:
                                xAxisMode === "volume"
                                  ? "Hourly Volume (veh/h)"
                                  : "Arrival Rate (veh/s)",
                              position: "insideBottom",
                              offset: -6,
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 12,
                            }}
                          />
                          <YAxis
                            tick={{
                              fontSize: 12,
                              fill: "hsl(var(--muted-foreground))",
                            }}
                            label={{
                              value: "Queue (veh)",
                              angle: -90,
                              position: "insideLeft",
                              offset: 8,
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 12,
                            }}
                          />
                          <Tooltip
                            content={
                              <CustomTooltip unit=" veh" xMode={xAxisMode} />
                            }
                          />
                          <Legend
                            wrapperStyle={{ fontSize: 13, paddingTop: 10 }}
                          />
                          {crossover && xAxisMode === "volume" && (
                            <ReferenceLine
                              x={crossover}
                              stroke="#f59e0b"
                              strokeDasharray="4 3"
                              strokeWidth={2}
                            />
                          )}
                          <Line
                            type="monotone"
                            dataKey="signalQueue"
                            name="Fixed-Time Signal"
                            stroke="#38bdf8"
                            strokeWidth={3}
                            dot={{ r: 5, fill: "#38bdf8" }}
                            activeDot={{
                              r: 8,
                              stroke: "#7dd3fc",
                              strokeWidth: 2,
                            }}
                            animationDuration={450}
                            animationEasing="ease-out"
                          />
                          <Line
                            type="monotone"
                            dataKey="roundaboutQueue"
                            name="Modern Roundabout"
                            stroke="#10b981"
                            strokeWidth={3}
                            dot={{ r: 5, fill: "#10b981" }}
                            activeDot={{
                              r: 8,
                              stroke: "#34d399",
                              strokeWidth: 2,
                            }}
                            animationDuration={450}
                            animationEasing="ease-out"
                          />
                          {showUncertaintyBands && (
                            <>
                              <Line
                                type="monotone"
                                dataKey="signalQueueMax"
                                name="Signal Peak Queue"
                                stroke="#38bdf8"
                                strokeDasharray="3 3"
                                strokeOpacity={0.45}
                                strokeWidth={1.5}
                                dot={false}
                                activeDot={false}
                              />
                              <Line
                                type="monotone"
                                dataKey="roundaboutQueueMax"
                                name="Roundabout Peak Queue"
                                stroke="#10b981"
                                strokeDasharray="3 3"
                                strokeOpacity={0.45}
                                strokeWidth={1.5}
                                dot={false}
                                activeDot={false}
                              />
                            </>
                          )}
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="chart-empty">
                        No telemetry data recorded
                      </div>
                    )}
                  </div>
                )}

                {/* Optional Delta Trend Chart */}
                {showDeltaTrend && (
                  <div
                    className="chart-card chart-card-delta-trend"
                    style={{ gridColumn: "1 / -1" }}
                  >
                    <div className="chart-card-mini-header">
                      <span className="mini-title">
                        📈 Relative Performance Delta (% Difference)
                      </span>
                      <span className="mini-unit">
                        Δ % (Objective Baseline: 0% Parity)
                      </span>
                    </div>
                    {chartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart
                          data={chartData}
                          margin={{ top: 16, right: 24, bottom: 12, left: 8 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke={CHART_GRID}
                          />
                          <XAxis
                            dataKey={xDataKey}
                            tick={{
                              fontSize: 12,
                              fill: "hsl(var(--muted-foreground))",
                            }}
                            tickFormatter={(v: number) => v.toString()}
                            label={{
                              value:
                                xAxisMode === "volume"
                                  ? "Hourly Volume (veh/h)"
                                  : "Arrival Rate (veh/s)",
                              position: "insideBottom",
                              offset: -6,
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 12,
                            }}
                          />
                          <YAxis
                            tick={{
                              fontSize: 12,
                              fill: "hsl(var(--muted-foreground))",
                            }}
                            label={{
                              value: "Δ % Difference",
                              angle: -90,
                              position: "insideLeft",
                              offset: 8,
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 12,
                            }}
                          />
                          <Tooltip
                            content={
                              <CustomTooltip unit="%" xMode={xAxisMode} />
                            }
                          />
                          <Legend
                            wrapperStyle={{ fontSize: 13, paddingTop: 10 }}
                          />
                          <ReferenceLine
                            y={0}
                            stroke={CHART_AXIS}
                            strokeDasharray="4 3"
                            strokeWidth={2}
                            label={{
                              value: "Parity (0%)",
                              position: "right",
                              fill: "#94a3b8",
                              fontSize: 11,
                            }}
                          />
                          {crossover && xAxisMode === "volume" && (
                            <ReferenceLine
                              x={crossover}
                              stroke="#f59e0b"
                              strokeDasharray="4 3"
                              strokeWidth={2}
                              label={{
                                value: `Crossover (${crossover.toLocaleString()} veh/h)`,
                                position: "top",
                                fill: "#f59e0b",
                                fontSize: 11,
                              }}
                            />
                          )}
                          <Line
                            type="monotone"
                            dataKey="delayDeltaPercent"
                            name="Delay Δ % (+ = signal lower, − = roundabout lower)"
                            stroke="#8b5cf6"
                            strokeWidth={2.5}
                            dot={{ r: 4, fill: "#8b5cf6" }}
                          />
                          <Line
                            type="monotone"
                            dataKey="queueDeltaPercent"
                            name="Queue Δ % (+ = signal lower, − = roundabout lower)"
                            stroke="#f59e0b"
                            strokeWidth={2}
                            strokeDasharray="4 2"
                            dot={{ r: 3, fill: "#f59e0b" }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="chart-empty">
                        No telemetry data recorded
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── TAB 2: Head-to-Head Volume Matrix ──────── */}
          {activeTab === "matrix" && (
            <div className="sweep-summary-table-wrapper">
              <div className="table-header-controls">
                <div>
                  <h4>Volume Sweep Results: {activeSession.name}</h4>
                  <p className="table-subtitle">
                    Comparative telemetry data with side-by-side delay bars &
                    HCM Level of Service
                  </p>
                </div>
                <div className="table-filter-group">
                  <span className="filter-label">Filter:</span>
                  <button
                    type="button"
                    className={`table-filter-btn ${filterWinner === "all" ? "active" : ""}`}
                    onClick={() => {
                      setFilterWinner("all");
                    }}
                  >
                    All ({runsList.length.toString()})
                  </button>
                  <button
                    type="button"
                    className={`table-filter-btn ${filterWinner === "roundabout" ? "active" : ""}`}
                    onClick={() => {
                      setFilterWinner("roundabout");
                    }}
                  >
                    🔄 Roundabout ({roundaboutWins.toString()})
                  </button>
                  <button
                    type="button"
                    className={`table-filter-btn ${filterWinner === "signal" ? "active" : ""}`}
                    onClick={() => {
                      setFilterWinner("signal");
                    }}
                  >
                    🚦 Signal ({signalWins.toString()})
                  </button>
                  <button
                    type="button"
                    className={`table-filter-btn ${filterWinner === "tie" ? "active" : ""}`}
                    onClick={() => {
                      setFilterWinner("tie");
                    }}
                  >
                    ⚖️ About the same ({tieWins.toString()})
                  </button>
                </div>
              </div>

              <div className="table-scroll-container">
                <table className="modern-telemetry-table">
                  <thead>
                    <tr>
                      <th>Demand Tier</th>
                      <th>Delay Comparison Bar</th>
                      <th>Signal Delay & LOS</th>
                      <th>Roundabout Delay & LOS</th>
                      <th>Throughput</th>
                      <th>Queues</th>
                      <th
                        title={`Lower mean delay at this tier (one random pattern); tie when within ${tieText(activeSession.tieTolerance)}; inconclusive when a side served fewer than 20 vehicles or the vehicle limit cut demand off`}
                      >
                        Lower mean delay
                      </th>
                      <th>Δ Delay</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRuns.map((run) => {
                      const sigLOS = getLevelOfService(
                        run.signal.delay,
                        "signal",
                      );
                      const rndLOS = getLevelOfService(
                        run.roundabout.delay,
                        "roundabout",
                      );
                      const sigPct = Math.min(
                        100,
                        Math.round((run.signal.delay / maxDelayInRuns) * 100),
                      );
                      const rndPct = Math.min(
                        100,
                        Math.round(
                          (run.roundabout.delay / maxDelayInRuns) * 100,
                        ),
                      );

                      return (
                        <tr key={run.arrivalRate}>
                          <td>
                            <div className="table-tier-col">
                              <strong>
                                {run.hourlyVolumeVehPerHour.toLocaleString()}{" "}
                                veh/h
                              </strong>
                              <span className="table-tier-rate">
                                {run.arrivalRate.toFixed(2)} veh/s
                              </span>
                            </div>
                          </td>

                          {/* Visual Micro Delay Bar */}
                          <td className="delay-bar-cell">
                            <div className="dual-delay-bars">
                              <div className="bar-row">
                                <span className="bar-label">Sig</span>
                                <div className="bar-track">
                                  <div
                                    className="bar-fill sig-fill"
                                    style={{ width: `${sigPct.toString()}%` }}
                                  />
                                </div>
                              </div>
                              <div className="bar-row">
                                <span className="bar-label">Rnd</span>
                                <div className="bar-track">
                                  <div
                                    className="bar-fill rnd-fill"
                                    style={{ width: `${rndPct.toString()}%` }}
                                  />
                                </div>
                              </div>
                            </div>
                          </td>

                          {/* Signal Delay */}
                          <td>
                            <div className="delay-los-cell">
                              <span className="delay-val">
                                {run.signal.delay.toFixed(2)}s
                              </span>
                              <span
                                className="los-chip mini"
                                style={{
                                  color: sigLOS.color,
                                  background: sigLOS.bg,
                                }}
                              >
                                LOS {sigLOS.grade}
                              </span>
                            </div>
                            {run.signal.delayStdDev !== undefined && (
                              <div
                                style={{
                                  fontSize: "11px",
                                  color: "hsl(var(--muted-foreground))",
                                  marginTop: "2px",
                                }}
                              >
                                ±{run.signal.delayStdDev.toFixed(1)}s [
                                {run.signal.delayMin?.toFixed(1)}–
                                {run.signal.delayMax?.toFixed(1)}s]
                              </div>
                            )}
                          </td>

                          {/* Roundabout Delay */}
                          <td>
                            <div className="delay-los-cell">
                              <span className="delay-val">
                                {run.roundabout.delay.toFixed(2)}s
                              </span>
                              <span
                                className="los-chip mini"
                                style={{
                                  color: rndLOS.color,
                                  background: rndLOS.bg,
                                }}
                              >
                                LOS {rndLOS.grade}
                              </span>
                            </div>
                            {run.roundabout.delayStdDev !== undefined && (
                              <div
                                style={{
                                  fontSize: "11px",
                                  color: "hsl(var(--muted-foreground))",
                                  marginTop: "2px",
                                }}
                              >
                                ±{run.roundabout.delayStdDev.toFixed(1)}s [
                                {run.roundabout.delayMin?.toFixed(1)}–
                                {run.roundabout.delayMax?.toFixed(1)}s]
                              </div>
                            )}
                          </td>

                          {/* Throughput */}
                          <td>
                            <div className="table-multi-col">
                              <span>🚦 {run.signal.throughput}</span>
                              <span>🔄 {run.roundabout.throughput}</span>
                            </div>
                          </td>

                          {/* Queues */}
                          <td>
                            <div className="table-multi-col">
                              <span>
                                🚦 {run.signal.queue.toFixed(1)}
                                {run.signal.queueMax !== undefined && (
                                  <span
                                    style={{
                                      fontSize: "10.5px",
                                      opacity: 0.8,
                                      marginLeft: "3px",
                                    }}
                                  >
                                    (pk {run.signal.queueMax.toFixed(0)})
                                  </span>
                                )}
                              </span>
                              <span>
                                🔄 {run.roundabout.queue.toFixed(1)}
                                {run.roundabout.queueMax !== undefined && (
                                  <span
                                    style={{
                                      fontSize: "10.5px",
                                      opacity: 0.8,
                                      marginLeft: "3px",
                                    }}
                                  >
                                    (pk {run.roundabout.queueMax.toFixed(0)})
                                  </span>
                                )}
                              </span>
                            </div>
                          </td>

                          {/* Winner Badge */}
                          <td>
                            <span
                              className={
                                run.winner === "roundabout"
                                  ? "winner-roundabout"
                                  : run.winner === "signal"
                                    ? "winner-signal"
                                    : "winner-tie"
                              }
                              title={
                                run.inconclusiveReason ===
                                "vehicle_limit_reached"
                                  ? "Vehicle generation hit its limit, so demand was cut off at this tier"
                                  : run.inconclusiveReason === "low_sample"
                                    ? "Fewer than 20 vehicles got through on a side"
                                    : undefined
                              }
                            >
                              {run.winner === "roundabout"
                                ? "🔄 Roundabout"
                                : run.winner === "signal"
                                  ? "🚦 Signal"
                                  : run.winner === "tie"
                                    ? "⚖️ About the same"
                                    : "❔ Inconclusive"}
                            </span>
                          </td>

                          {/* Delta */}
                          <td>
                            <span
                              className="delta-pill"
                              style={{
                                color:
                                  run.delayDeltaPercent > 0
                                    ? "#38bdf8"
                                    : run.delayDeltaPercent < 0
                                      ? "#10b981"
                                      : "#94a3b8",
                                background:
                                  run.delayDeltaPercent > 0
                                    ? "rgba(56, 189, 248, 0.12)"
                                    : run.delayDeltaPercent < 0
                                      ? "rgba(16, 185, 129, 0.12)"
                                      : "rgba(148, 163, 184, 0.12)",
                              }}
                              title={
                                run.delayDeltaPercent > 0
                                  ? `+${run.delayDeltaPercent.toFixed(1)}% (signal lower)`
                                  : run.delayDeltaPercent < 0
                                    ? `${run.delayDeltaPercent.toFixed(1)}% (roundabout lower)`
                                    : "0.0% Parity"
                              }
                            >
                              {run.delayDeltaPercent > 0 ? "+" : ""}
                              {run.delayDeltaPercent.toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <TierMetrics runs={runsList} />
            </div>
          )}

          {/* ── TAB 3: How to read this sweep ─ */}
          {activeTab === "insights" && (
            <div className="engineering-insights-container">
              <div className="insights-header">
                <div>
                  <h4>📖 How to read this sweep</h4>
                  <p className="insights-subtitle">
                    What this sweep measured, what it shows, and what it cannot
                    show. Every figure here comes from this sweep; the rest
                    describes how UrbanFlow measures.
                  </p>
                </div>
              </div>
              <div className="insights-card-grid">
                <div className="insight-card-modern">
                  <div className="insight-card-top">
                    <span className="insight-card-icon">🧪</span>
                    <span className="insight-badge recommendation-badge">
                      What was run
                    </span>
                  </div>
                  <h5>Measured, not modelled in the abstract</h5>
                  <p>
                    {runsList.length.toString()} demand tiers, each simulated
                    for {activeSession.duration.toString()} s with one random
                    traffic pattern (seed {activeSession.randomSeed.toString()}
                    ). Both controls received identical arrivals at every tier.
                    {activeSession.calibration
                      ? ` ${activeSession.calibration.note}`
                      : " Whether this sweep used the calibrated one-lane configuration was not recorded."}
                  </p>
                </div>
                <div className="insight-card-modern">
                  <div className="insight-card-top">
                    <span className="insight-card-icon">📊</span>
                    <span className="insight-badge roundabout-badge">
                      What this sweep shows
                    </span>
                  </div>
                  <h5>Lower mean delay, tier by tier</h5>
                  <p>
                    {crossoverSummary(
                      runsList,
                      crossover,
                      activeSession.curves.crossoverBracketArrivalRates,
                    )}{" "}
                    Tally: roundabout {roundaboutWins.toString()}, signal{" "}
                    {signalWins.toString()}, about the same {tieWins.toString()}
                    , inconclusive {inconclusiveTiers.toString()} of{" "}
                    {totalRuns.toString()} tiers. &ldquo;About the same&rdquo;
                    means within {tieText(activeSession.tieTolerance)}.
                  </p>
                </div>
                <div className="insight-card-modern">
                  <div className="insight-card-top">
                    <span className="insight-card-icon">⚠️</span>
                    <span className="insight-badge signal-badge">
                      What it cannot show
                    </span>
                  </div>
                  <h5>Limits to keep in mind</h5>
                  <ul className="insight-list">
                    <li>
                      One random pattern per tier: a difference here may be
                      chance. The Statistical validation page repeats a scenario
                      over many patterns and tests it.
                    </li>
                    <li>
                      &ldquo;Delay&rdquo; is extra travel time against the
                      driver&apos;s own desired speed. It includes slowing to
                      enter a roundabout and is not the same as time queued, so
                      read it next to the queue chart.
                    </li>
                    <li>
                      The change in which control has the lower delay is not a
                      capacity limit or a design threshold.
                    </li>
                    <li>
                      UrbanFlow does not calculate emissions, fuel use, cost or
                      crash risk. Nothing on this page speaks to them.
                    </li>
                    {cappedTiers > 0 && (
                      <li>
                        Vehicle generation stopped at its per-run limit in{" "}
                        {cappedTiers.toString()} tier
                        {cappedTiers === 1 ? "" : "s"}, so demand there was cut
                        off; those tiers are marked inconclusive.
                      </li>
                    )}
                  </ul>
                </div>
              </div>
              {/* Level-of-service reference: one definition for the whole app */}
              <div className="hcm-los-reference-box">
                <h5>
                  📖 Indicative level-of-service bands (Highway Capacity Manual
                  delay bands, average delay in seconds)
                </h5>
                <p className="insights-subtitle">
                  Used as a reference for how large a delay is. The grades on
                  this page apply the manual&apos;s bands to simulated delay,
                  which also includes geometric slow-down, so they are an
                  indicative guide and not a level-of-service analysis. Signal:
                  signalised-intersection bands. Roundabout: the stricter
                  unsignalised bands.
                </p>
                <div className="los-grid-chips">
                  {(["A", "B", "C", "D", "E", "F"] as LosGrade[]).map(
                    (grade, i) => (
                      <div className="los-card-chip" key={grade}>
                        <span
                          className="los-badge"
                          style={{
                            color: LOS_COLORS[grade].color,
                            background: LOS_COLORS[grade].bg,
                          }}
                        >
                          LOS {grade}
                        </span>
                        {(["signal", "roundabout"] as Side[]).map((side) => {
                          const bounds = LOS_THRESHOLDS[side];
                          const lower = i === 0 ? null : bounds[i - 1];
                          const upper = i < bounds.length ? bounds[i] : null;
                          const range =
                            upper === null
                              ? `> ${(lower ?? 0).toString()} s`
                              : lower === null
                                ? `≤ ${upper.toString()} s`
                                : `${lower.toString()} – ${upper.toString()} s`;
                          return (
                            <span className="los-time" key={side}>
                              {SIDE_TITLE[side]}: {range}
                            </span>
                          );
                        })}
                        <span className="los-condition">
                          {LOS_WORDS[grade]}
                        </span>
                      </div>
                    ),
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
