export interface SimulationConfigValues {
  lanes: number;
  laneWidth: number;
  arrivalRate: number;
  duration: number;
  randomSeed: number;
  greenDuration: number;
  yellowDuration: number;
  allRedDuration: number;
  criticalGap: number;
  followUpTime: number;
}

export const DEFAULT_CONFIG_VALUES: SimulationConfigValues = {
  lanes: 2,
  laneWidth: 3.5,
  arrivalRate: 0.3,
  duration: 300,
  randomSeed: 42,
  greenDuration: 15,
  yellowDuration: 3,
  allRedDuration: 2,
  criticalGap: 4.0,
  followUpTime: 2.5,
};
