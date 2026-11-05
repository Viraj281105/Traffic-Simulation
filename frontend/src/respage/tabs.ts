export const TABS = [
  { id: "incidents", label: "Incidents" },
  { id: "resilience", label: "Resilience" },
  { id: "priority", label: "Priority" },
  { id: "cooperation", label: "Cooperation" },
  { id: "account", label: "Account" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

export function isTab(value: string | null): value is TabId {
  return TABS.some((t) => t.id === value);
}
