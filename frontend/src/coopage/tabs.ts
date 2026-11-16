export const TABS = [
  { id: "platoons", label: "Platoons" },
  { id: "signal-free", label: "Signal-free" },
  { id: "governance", label: "Governance" },
  { id: "cost", label: "Cost" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

export function isTab(value: string | null): value is TabId {
  return TABS.some((t) => t.id === value);
}
