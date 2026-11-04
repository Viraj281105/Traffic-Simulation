export const TABS = [
  { id: "results", label: "Results" },
  { id: "runs", label: "Compare runs" },
  { id: "nightly", label: "Nightly checks" },
  { id: "report", label: "Report" },
  { id: "rl", label: "RL vs fixed-time" },
  { id: "network", label: "Networks" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

export function isTab(value: string | null): value is TabId {
  return TABS.some((t) => t.id === value);
}
