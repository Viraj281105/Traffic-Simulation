import { useEffect, useRef } from "react";
import { dashboardPayload, type SimulationConfigValues } from "../types/config";
import { updateSimulationConfig } from "../services/api";

/**
 * Keeps the backend's live session on the dashboard's configuration: every
 * change is sent (debounced by 50 ms) to /api/simulation/config, which
 * resets the live simulation and the comparison with it.
 *
 * A guided "Run the comparison" changes the config and must start playing
 * only once the backend holds it: a config update resets the simulation, so
 * playing first would run (and then lose) the old scenario. `playAfterSync`
 * asks for exactly that: the next successful sync plays.
 */
export function useLiveConfigSync(
  viewMode: string,
  configValues: SimulationConfigValues,
  play: () => Promise<void>,
) {
  const syncVersion = useRef(0);
  const playAfterSync = useRef(false);
  const playRef = useRef(play);
  useEffect(() => {
    playRef.current = play;
  });

  const {
    lanes,
    laneWidth,
    arrivalRate,
    duration,
    randomSeed,
    greenDuration,
    yellowDuration,
    allRedDuration,
    criticalGap,
    followUpTime,
    nsGreenDuration,
    ewGreenDuration,
    vehicleMix,
    laneChanging,
    lanesEastWest,
    signalControl,
    adaptive,
    scenario,
    unstructuredTraffic,
    aggressiveTwoWheelers,
  } = configValues;
  // Object-valued: compared by content in the sync effect below.
  const vehicleMixKey = JSON.stringify(vehicleMix ?? null);
  const adaptiveKey = JSON.stringify(adaptive ?? null);
  const scenarioKey = JSON.stringify(scenario ?? null);

  useEffect(() => {
    const intersectionType =
      viewMode === "roundabout" ? "roundabout" : "fixed_time_signal";
    const version = ++syncVersion.current;
    const timeoutId = setTimeout(() => {
      updateSimulationConfig(
        dashboardPayload(
          {
            lanes,
            laneWidth,
            arrivalRate,
            duration,
            randomSeed,
            greenDuration,
            yellowDuration,
            allRedDuration,
            criticalGap,
            followUpTime,
            nsGreenDuration,
            ewGreenDuration,
            vehicleMix: JSON.parse(vehicleMixKey) as typeof vehicleMix,
            laneChanging,
            lanesEastWest,
            signalControl,
            adaptive: JSON.parse(adaptiveKey) as typeof adaptive,
            scenario: JSON.parse(scenarioKey) as typeof scenario,
            unstructuredTraffic,
            aggressiveTwoWheelers,
          },
          intersectionType,
          viewMode === "signal",
        ),
      )
        .then(() => {
          if (version === syncVersion.current && playAfterSync.current) {
            playAfterSync.current = false;
            playRef.current().catch(() => {});
          }
        })
        .catch((err: unknown) => {
          playAfterSync.current = false;
          console.error("Failed to update backend config:", err);
        });
    }, 50);

    return () => {
      clearTimeout(timeoutId);
    };
  }, [
    viewMode,
    lanes,
    laneWidth,
    arrivalRate,
    duration,
    randomSeed,
    greenDuration,
    yellowDuration,
    allRedDuration,
    criticalGap,
    followUpTime,
    nsGreenDuration,
    ewGreenDuration,
    vehicleMixKey,
    laneChanging,
    lanesEastWest,
    signalControl,
    adaptiveKey,
    scenarioKey,
    unstructuredTraffic,
    aggressiveTwoWheelers,
  ]);

  return {
    /** The next successful sync starts playback. */
    playAfterSync: () => {
      playAfterSync.current = true;
    },
  };
}
