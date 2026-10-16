import { useEffect, useRef, useState } from "react";
import type {
  PollingState,
  SingleVehicleResponse,
  SimulationLifecycle,
} from "../types/simulation";
import {
  getSingleVehicle,
  getSingleVehicleStatus,
  resetSingleVehicle,
  startSingleVehicle,
  stopSingleVehicle,
} from "../services/singleVehicle";

const POLL_INTERVAL_MS = 100; // Poll every 100ms for 10 Hz simulation

/**
 * Hook that manages polling the backend single-vehicle API.
 * Handles start/stop/reset and maintains the polling interval.
 */
export function useSimulationPolling(): PollingState & {
  start: () => Promise<void>;
  stop: () => Promise<void>;
  reset: () => Promise<void>;
} {
  const [vehicle, setVehicle] = useState<SingleVehicleResponse | null>(null);
  const [status, setStatus] = useState<SimulationLifecycle>("stopped");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isPollingRef = useRef(false);

  // Poll the single-vehicle endpoint
  const pollVehicleState = async () => {
    try {
      const data = await getSingleVehicle();
      setVehicle(data);
      setStatus(data.simulation_status);
      setError(null);

      // Stop polling if simulation has completed
      if (data.simulation_status === "completed") {
        isPollingRef.current = false;
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setError(`Failed to fetch vehicle state: ${errorMsg}`);
      setIsLoading(false);
    }
  };

  // Start simulation
  const start = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await startSingleVehicle();
      setStatus(data.status);

      // Begin polling
      isPollingRef.current = true;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      await pollVehicleState();
      pollIntervalRef.current = setInterval(() => {
        void pollVehicleState();
      }, POLL_INTERVAL_MS);
      setIsLoading(false);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setError(errorMsg);
      setIsLoading(false);
      isPollingRef.current = false;
    }
  };

  // Stop simulation
  const stop = async () => {
    try {
      setError(null);
      isPollingRef.current = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      const data = await stopSingleVehicle();
      setStatus(data.status);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setError(errorMsg);
    }
  };

  // Reset simulation
  const reset = async () => {
    try {
      setError(null);
      isPollingRef.current = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      const data = await resetSingleVehicle();
      setStatus(data.status);
      setVehicle(null);
      setIsLoading(false);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setError(errorMsg);
    }
  };

  // Fetch initial status and cleanup interval on unmount
  useEffect(() => {
    let active = true;

    const fetchInitialStatus = async () => {
      try {
        const data = await getSingleVehicleStatus();
        if (active) {
          setStatus(data.status);
          setError(null);
          // If already running, start polling
          if (data.status === "running") {
            isPollingRef.current = true;
            await pollVehicleState();
            pollIntervalRef.current = setInterval(() => {
              void pollVehicleState();
            }, POLL_INTERVAL_MS);
          }
        }
      } catch (err) {
        if (active) {
          const errorMsg = err instanceof Error ? err.message : String(err);
          setError(`Failed to fetch initial status: ${errorMsg}`);
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    };

    fetchInitialStatus().catch(console.error);

    return () => {
      active = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  return {
    vehicle,
    status,
    isLoading,
    error,
    start,
    stop,
    reset,
  };
}
