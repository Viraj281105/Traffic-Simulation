import { useEffect, useRef, useState } from 'react';
import type { PollingState, SingleVehicleResponse, SimulationLifecycle } from '../types/simulation';

const API_BASE = 'http://localhost:8000/api/simulation';
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
  const [status, setStatus] = useState<SimulationLifecycle>('stopped');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isPollingRef = useRef(false);

  // Poll the single-vehicle endpoint
  const pollVehicleState = async () => {
    try {
      const response = await fetch(`${API_BASE}/single-vehicle`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data: SingleVehicleResponse = await response.json();
      setVehicle(data);
      setStatus(data.simulation_status);
      setError(null);

      // Stop polling if simulation has completed
      if (data.simulation_status === 'completed') {
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
      const response = await fetch(`${API_BASE}/start`, { method: 'POST' });
      if (!response.ok) {
        throw new Error(`Failed to start simulation: HTTP ${response.status}`);
      }
      const data = await response.json();
      setStatus(data.status as SimulationLifecycle);

      // Begin polling
      isPollingRef.current = true;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      await pollVehicleState();
      pollIntervalRef.current = setInterval(pollVehicleState, POLL_INTERVAL_MS);
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
      const response = await fetch(`${API_BASE}/stop`, { method: 'POST' });
      if (!response.ok) {
        throw new Error(`Failed to stop simulation: HTTP ${response.status}`);
      }
      const data = await response.json();
      setStatus(data.status as SimulationLifecycle);
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
      const response = await fetch(`${API_BASE}/reset`, { method: 'POST' });
      if (!response.ok) {
        throw new Error(`Failed to reset simulation: HTTP ${response.status}`);
      }
      const data = await response.json();
      setStatus(data.status as SimulationLifecycle);
      setVehicle(null);
      setIsLoading(false);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setError(errorMsg);
    }
  };

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
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
