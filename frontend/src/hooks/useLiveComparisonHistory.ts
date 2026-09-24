import { useEffect, useRef, useState } from "react";
import type { DualSnapshot, LiveSnapshot } from "../types/simulation";
import { isInWarmup } from "../metrics/catalog";

export interface ComparisonHistoryPoint {
  /** Simulated time in seconds */
  time: number;
  timeFormatted: string;
  inWarmup: boolean;

  // ── Performance metrics ──
  signalAvgDelay: number | null;
  roundaboutAvgDelay: number | null;
  signalMedianDelay: number | null;
  roundaboutMedianDelay: number | null;
  signalP95Delay: number | null;
  roundaboutP95Delay: number | null;
  signalAvgWait: number | null;
  roundaboutAvgWait: number | null;
  signalThroughput: number;
  roundaboutThroughput: number;
  signalThroughputRate: number | null;
  roundaboutThroughputRate: number | null;
  signalSpeed: number;
  roundaboutSpeed: number;
  signalPti: number | null;
  roundaboutPti: number | null;

  // ── Flow & Queue metrics ──
  signalAvgQueue: number | null;
  roundaboutAvgQueue: number | null;
  signalActiveAvgQueue: number | null;
  roundaboutActiveAvgQueue: number | null;
  signalStopsPerVeh: number | null;
  roundaboutStopsPerVeh: number | null;
  signalTotalStops: number;
  roundaboutTotalStops: number;
  signalFairness: number | null;
  roundaboutFairness: number | null;

  // ── Safety metrics ──
  signalMinTtc: number | null;
  roundaboutMinTtc: number | null;
  signalTtcEvents: number;
  roundaboutTtcEvents: number;
  signalCollisions: number;
  roundaboutCollisions: number;
  signalMinPet: number | null;
  signalPetEvents: number;

  // ── Capacity & Demand ──
  signalUtilization: number | null;
  roundaboutUtilization: number | null;
  signalIdleLoss: number | null;
  signalActiveVehicles: number;
  roundaboutActiveVehicles: number;
  signalSpawned: number;
  roundaboutSpawned: number;
}

export interface CollisionEventRecord {
  id: string;
  time: number;
  timeFormatted: string;
  control: "signal" | "roundabout";
  newCount: number;
}

const MAX_HISTORY_POINTS = 200;

function formatSimTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m)}:${String(s).padStart(2, "0")}`;
}

export function useLiveComparisonHistory(snapshot: DualSnapshot | null) {
  const [history, setHistory] = useState<ComparisonHistoryPoint[]>([]);
  const [collisionEvents, setCollisionEvents] = useState<CollisionEventRecord[]>([]);

  const lastRecordedTimeRef = useRef<number>(-1);
  const prevCollisionsRef = useRef<{ signal: number; roundabout: number }>({
    signal: 0,
    roundabout: 0,
  });
  const prevSimIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!snapshot) {
      lastRecordedTimeRef.current = -1;
      prevCollisionsRef.current = { signal: 0, roundabout: 0 };
      prevSimIdRef.current = null;
      return;
    }

    const sig: LiveSnapshot = snapshot.signal;
    const rnd: LiveSnapshot = snapshot.roundabout;

    const t = snapshot.elapsed;
    const simId = sig.simulationId;

    const isRestart = simId !== prevSimIdRef.current || t < lastRecordedTimeRef.current - 1.0;
    if (isRestart) {
      lastRecordedTimeRef.current = -1;
      prevCollisionsRef.current = {
        signal: sig.metrics.collisionCount,
        roundabout: rnd.metrics.collisionCount,
      };
      prevSimIdRef.current = simId;
    }

    // Sample approximately once per second of simulated time
    if (!isRestart && lastRecordedTimeRef.current >= 0 && Math.abs(t - lastRecordedTimeRef.current) < 0.8) {
      return;
    }
    lastRecordedTimeRef.current = t;

    const sigWarm = isInWarmup(sig.timestamp, sig.warmupTime);
    const rndWarm = isInWarmup(rnd.timestamp, rnd.warmupTime);
    const inWarmup = sigWarm || rndWarm;

    const sigM = sig.metrics;
    const rndM = rnd.metrics;

    // Check for new collision events
    const currentSigCollisions = sigM.collisionCount;
    const currentRndCollisions = rndM.collisionCount;

    if (currentSigCollisions > prevCollisionsRef.current.signal) {
      const newEvt: CollisionEventRecord = {
        id: `sig-${t.toFixed(1)}-${String(currentSigCollisions)}`,
        time: t,
        timeFormatted: formatSimTime(t),
        control: "signal",
        newCount: currentSigCollisions,
      };
      setCollisionEvents((prev) => (isRestart ? [newEvt] : [...prev, newEvt]));
      prevCollisionsRef.current.signal = currentSigCollisions;
    } else if (isRestart) {
      setCollisionEvents([]);
    }

    if (currentRndCollisions > prevCollisionsRef.current.roundabout) {
      const newEvt: CollisionEventRecord = {
        id: `rnd-${t.toFixed(1)}-${String(currentRndCollisions)}`,
        time: t,
        timeFormatted: formatSimTime(t),
        control: "roundabout",
        newCount: currentRndCollisions,
      };
      setCollisionEvents((prev) => (isRestart ? [newEvt] : [...prev, newEvt]));
      prevCollisionsRef.current.roundabout = currentRndCollisions;
    }

    const point: ComparisonHistoryPoint = {
      time: Math.round(t * 10) / 10,
      timeFormatted: formatSimTime(t),
      inWarmup,

      // Performance
      signalAvgDelay: sigWarm ? null : sigM.averageDelay,
      roundaboutAvgDelay: rndWarm ? null : rndM.averageDelay,
      signalMedianDelay: sigWarm ? null : sigM.medianDelay,
      roundaboutMedianDelay: rndWarm ? null : rndM.medianDelay,
      signalP95Delay: sigWarm ? null : sigM.p95Delay,
      roundaboutP95Delay: rndWarm ? null : rndM.p95Delay,
      signalAvgWait: sigWarm ? null : sigM.averageWaitTime,
      roundaboutAvgWait: rndWarm ? null : rndM.averageWaitTime,
      signalThroughput: sigM.throughput,
      roundaboutThroughput: rndM.throughput,
      signalThroughputRate: sigWarm ? null : sigM.throughputRate,
      roundaboutThroughputRate: rndWarm ? null : rndM.throughputRate,
      signalSpeed: sigM.averageTravelSpeed,
      roundaboutSpeed: rndM.averageTravelSpeed,
      signalPti: sigWarm ? null : sigM.travelTimeReliability,
      roundaboutPti: rndWarm ? null : rndM.travelTimeReliability,

      // Flow
      signalAvgQueue: sigWarm ? null : sigM.averageQueueLength,
      roundaboutAvgQueue: rndWarm ? null : rndM.averageQueueLength,
      signalActiveAvgQueue: sigWarm ? null : sigM.activeAverageQueueLength,
      roundaboutActiveAvgQueue: rndWarm ? null : rndM.activeAverageQueueLength,
      signalStopsPerVeh: sigWarm ? null : sigM.averageStopsPerVehicle,
      roundaboutStopsPerVeh: rndWarm ? null : rndM.averageStopsPerVehicle,
      signalTotalStops: sigM.totalStops,
      roundaboutTotalStops: rndM.totalStops,
      signalFairness: sigWarm ? null : sigM.directionalFairnessIndex,
      roundaboutFairness: rndWarm ? null : rndM.directionalFairnessIndex,

      // Safety
      signalMinTtc: sigM.minTTC ?? null,
      roundaboutMinTtc: rndM.minTTC ?? null,
      signalTtcEvents: sigM.ttcEventCount ?? 0,
      roundaboutTtcEvents: rndM.ttcEventCount ?? 0,
      signalCollisions: currentSigCollisions,
      roundaboutCollisions: currentRndCollisions,
      signalMinPet: sigM.minPET ?? null,
      signalPetEvents: sigM.petEventCount ?? 0,

      // Capacity & Demand
      signalUtilization: sigWarm ? null : sigM.intersectionUtilization,
      roundaboutUtilization: rndWarm ? null : rndM.intersectionUtilization,
      signalIdleLoss: sigWarm ? null : sigM.idleOpportunityLoss * 100,
      signalActiveVehicles: sig.vehicleCounts.active,
      roundaboutActiveVehicles: rnd.vehicleCounts.active,
      signalSpawned: sigM.totalVehiclesSpawned,
      roundaboutSpawned: rndM.totalVehiclesSpawned,
    };

    setHistory((prev) => {
      const base = isRestart ? [] : prev;
      const next = [...base, point];
      if (next.length > MAX_HISTORY_POINTS) {
        return next.slice(next.length - MAX_HISTORY_POINTS);
      }
      return next;
    });
  }, [snapshot]);

  return {
    history: snapshot ? history : [],
    collisionEvents: snapshot ? collisionEvents : [],
  };
}
