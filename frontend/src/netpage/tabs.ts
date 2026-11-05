export const TABS = [
  { id: "map", label: "Map" },
  { id: "congestion", label: "Congestion" },
  { id: "metrics", label: "Metrics" },
  { id: "calibration", label: "Calibration" },
  { id: "rl", label: "RL" },
  { id: "twin", label: "Twin" },
  { id: "loadtests", label: "Load tests" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

export function isTab(value: string | null): value is TabId {
  return TABS.some((t) => t.id === value);
}
