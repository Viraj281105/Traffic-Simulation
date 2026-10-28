import {
  Bookmark,
  Braces,
  FlaskConical,
  Gauge,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { RoutedView } from "../../routing";

/** Every view the dashboard can show: a routed view, or the legacy
 *  single-vehicle polling view. */
export type ViewMode = RoutedView | "single";

/** Views that drive the live simulation stream. */
export const SIMULATION_VIEWS: ReadonlySet<ViewMode> = new Set([
  "signal",
  "roundabout",
  "comparative",
  "single",
]);

/** Single-control views: specialist tools with the full live metric panel,
 *  display toggles and scenario settings in the header. */
export const SINGLE_VIEWS: ReadonlySet<ViewMode> = new Set([
  "signal",
  "roundabout",
  "single",
]);

/** The places in the product. Simulate is the guided path everyone starts
 *  on; the Research lab holds the method studies; Experiments holds the
 *  planning and experiment tools; Saved holds kept runs. Developer and Admin
 *  are utilities, shown apart from the workflows. */
export type Section =
  "simulate" | "research" | "experiments" | "saved" | "developer" | "admin";

export interface NavItem {
  view: RoutedView;
  label: string;
  /** One line on what the page is for: the tab's tooltip and the text of
   *  its related-tools card. */
  description: string;
}

export interface NavGroup {
  /** Shown before the group in the sub-navigation; omitted for a lone
   *  leading item such as an overview. */
  label?: string;
  items: NavItem[];
}

export interface SectionDef {
  id: Section;
  label: string;
  icon: LucideIcon;
  /** Where the section's tab leads. */
  home: RoutedView;
  /** Signed-out visitors are asked to sign in before it opens. */
  requiresAuth: boolean;
  /** The section's own pages, for its sub-navigation. A section with one
   *  page has none. */
  groups: NavGroup[];
  /** Views that belong to the section without a tab of their own. */
  alsoContains?: ViewMode[];
}

const RESEARCH: SectionDef = {
  id: "research",
  label: "Research lab",
  icon: FlaskConical,
  home: "research",
  requiresAuth: true,
  groups: [
    {
      items: [
        {
          view: "research",
          label: "Overview",
          description:
            "How UrbanFlow compares traffic control, and what each study is for.",
        },
      ],
    },
    {
      label: "Studies",
      items: [
        {
          view: "junction",
          label: "Custom junction study",
          description:
            "Build or import a junction and compare the controls on it over matched seeds.",
        },
        {
          view: "threeWay",
          label: "Three-way study",
          description:
            "Fixed-time, adaptive and roundabout on matched seeds, with the exact method.",
        },
        {
          view: "validation",
          label: "Statistical validation",
          description:
            "Monte Carlo study of signal against roundabout, with formal tests.",
        },
        {
          view: "volume",
          label: "Traffic-level sweep",
          description:
            "Both controls across a range of demand levels, to see where the comparison changes.",
        },
      ],
    },
    {
      label: "Single control",
      items: [
        {
          view: "signal",
          label: "Signal on its own",
          description:
            "A fixed-time or adaptive signal live, with its full metrics and phase state.",
        },
        {
          view: "roundabout",
          label: "Roundabout on its own",
          description:
            "One roundabout live, with its full metrics and circulating counts.",
        },
      ],
    },
  ],
  alsoContains: ["single"],
};

const EXPERIMENTS: SectionDef = {
  id: "experiments",
  label: "Experiments",
  icon: Waypoints,
  home: "planner",
  requiresAuth: true,
  groups: [
    {
      items: [
        {
          view: "planner",
          label: "Planner",
          description:
            "Compare named control alternatives for one junction, with their uncertainty.",
        },
        {
          view: "scenarios",
          label: "Scenario planning",
          description:
            "Baseline and intervention scenarios as batch runs, compared on KPIs.",
        },
        {
          view: "copilot",
          label: "Experiment Copilot",
          description:
            "Describe a question in words and get a checked experiment to confirm.",
        },
        {
          view: "discovery",
          label: "Discovery Lab",
          description:
            "Search the strategies' parameters for one traffic regime you declare.",
        },
        {
          view: "stress",
          label: "Stress Lab",
          description:
            "Hard generated scenarios and the points where the best strategy changes.",
        },
      ],
    },
  ],
};

export const SECTIONS: Record<Section, SectionDef> = {
  simulate: {
    id: "simulate",
    label: "Simulate",
    icon: Gauge,
    home: "comparative",
    requiresAuth: false,
    groups: [],
  },
  research: RESEARCH,
  experiments: EXPERIMENTS,
  saved: {
    id: "saved",
    label: "Saved",
    icon: Bookmark,
    home: "history",
    requiresAuth: false,
    groups: [],
  },
  developer: {
    id: "developer",
    label: "Developer",
    icon: Braces,
    home: "tokens",
    requiresAuth: true,
    groups: [],
  },
  admin: {
    id: "admin",
    label: "Admin",
    icon: ShieldCheck,
    home: "admin",
    requiresAuth: true,
    groups: [],
  },
};

/** The workflows, in header order. */
export const PRIMARY_SECTIONS: Section[] = [
  "simulate",
  "research",
  "experiments",
  "saved",
];

const OWNER = new Map<ViewMode, Section>();
for (const def of Object.values(SECTIONS)) {
  OWNER.set(def.home, def.id);
  for (const group of def.groups) {
    for (const item of group.items) OWNER.set(item.view, def.id);
  }
  for (const view of def.alsoContains ?? []) OWNER.set(view, def.id);
}

export function sectionOf(view: ViewMode): Section {
  return OWNER.get(view) ?? "simulate";
}

/** Every page with a tab in a section's sub-navigation, in order. */
export function sectionItems(section: Section): NavItem[] {
  return SECTIONS[section].groups.flatMap((g) => g.items);
}
