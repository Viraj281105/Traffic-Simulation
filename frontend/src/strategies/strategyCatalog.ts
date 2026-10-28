/**
 * The control strategies the dashboard can compare.
 *
 * Which strategies exist, and which the live comparison can run, comes from
 * the backend's strategy registry (GET /api/strategies). This module only
 * adds presentation: a short name, a plain one-line explanation, a colour
 * and a glyph per canonical id. A strategy the registry adds later still
 * appears, with its registry name and description and a spare colour, so a
 * new strategy needs no change here to be offered; adding an entry to
 * PRESENTATION only polishes how it reads.
 */
import { useEffect, useState } from "react";
import {
  listStrategies,
  type StrategyCatalogDto,
  type StrategyDescriptorDto,
} from "../services/api";

export type StrategyFamily = "signal" | "roundabout";

export interface StrategyInfo {
  /** Canonical registry id, e.g. "adaptive_signal". */
  id: string;
  /** Short name for cards, columns and legends. */
  name: string;
  /** The registry's full name. */
  fullName: string;
  /** One plain sentence on how it controls traffic. */
  summary: string;
  family: StrategyFamily;
  /** CSS colour (a series token) used for this strategy everywhere. */
  color: string;
  /** Which glyph draws it (StrategyGlyph). */
  glyph: "fixed" | "adaptive" | "roundabout" | "metered" | StrategyFamily;
  /** The live comparison can run it. */
  live: boolean;
  /** What the model does not cover for it (registry). */
  notModelled: string[];
}

interface Presentation {
  name: string;
  summary: string;
  color: string;
  glyph: StrategyInfo["glyph"];
}

const PRESENTATION: Record<string, Presentation> = {
  fixed_time_signal: {
    name: "Fixed-time signal",
    summary:
      "Greens follow a set timetable, whatever traffic is actually waiting.",
    color: "var(--series-fixed)",
    glyph: "fixed",
  },
  adaptive_signal: {
    name: "Adaptive signal",
    summary:
      "Detectors stretch a green while traffic keeps coming and end it early when the road empties.",
    color: "var(--series-adaptive)",
    glyph: "adaptive",
  },
  conventional_roundabout: {
    name: "Roundabout",
    summary:
      "No signals: drivers give way to circulating traffic and enter when there is a gap.",
    color: "var(--series-conventional)",
    glyph: "roundabout",
  },
  metered_entry_roundabout: {
    name: "Metered roundabout",
    summary:
      "Signals on the entries pace drivers onto the ring; circulating traffic keeps priority.",
    color: "var(--series-metered)",
    glyph: "metered",
  },
};

const SPARE_COLORS = [
  "var(--series-5)",
  "var(--series-6)",
  "var(--series-neutral)",
];

/** Legacy names a saved run may use for a strategy. */
const LEGACY_IDS: Record<string, string> = {
  fixed_time: "fixed_time_signal",
  adaptive: "adaptive_signal",
  roundabout: "conventional_roundabout",
  signalised_roundabout: "metered_entry_roundabout",
};

function titleCase(id: string): string {
  const words = id.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function familyOf(id: string): StrategyFamily {
  return id.includes("roundabout") ? "roundabout" : "signal";
}

/** Presentation for a strategy id, from the built-in table or derived from
 *  the registry entry (or, with neither, from the id itself). */
export function strategyInfo(
  rawId: string,
  descriptor?: StrategyDescriptorDto,
  spareIndex = 0,
): StrategyInfo {
  const id = LEGACY_IDS[rawId] ?? rawId;
  const known = PRESENTATION[id] as Presentation | undefined;
  const family = descriptor?.family ?? familyOf(id);
  return {
    id,
    name: known?.name ?? descriptor?.name ?? titleCase(id),
    fullName: descriptor?.name ?? known?.name ?? titleCase(id),
    summary: known?.summary ?? descriptor?.description ?? "",
    family,
    color: known?.color ?? SPARE_COLORS[spareIndex % SPARE_COLORS.length],
    glyph: known?.glyph ?? family,
    live: descriptor?.liveComparison ?? false,
    notModelled: descriptor?.notModelled ?? [],
  };
}

/** Short display name for a strategy id (saved runs, CSV headers). */
export function strategyName(id: string): string {
  return strategyInfo(id).name;
}

export interface StrategyCatalog {
  /** Every live-comparable strategy, in registry order. */
  strategies: StrategyInfo[];
  defaultSelection: string[];
  maxStrategies: number;
}

export function catalogFrom(dto: StrategyCatalogDto): StrategyCatalog {
  let spare = 0;
  const strategies = dto.strategies
    .filter((d) => d.liveComparison)
    .map((d) => strategyInfo(d.id, d, d.id in PRESENTATION ? 0 : spare++));
  const ids = new Set(strategies.map((s) => s.id));
  return {
    strategies,
    defaultSelection: dto.liveComparison.defaultSelection.filter((id) =>
      ids.has(id),
    ),
    maxStrategies: dto.liveComparison.maxStrategies,
  };
}

export type CatalogState =
  | { status: "loading" }
  | { status: "ready"; catalog: StrategyCatalog }
  | { status: "error"; message: string };

// One request per page load: the registry does not change while it runs.
let cached: Promise<StrategyCatalog> | null = null;

function loadCatalog(): Promise<StrategyCatalog> {
  cached ??= listStrategies()
    .then(catalogFrom)
    .catch((err: unknown) => {
      cached = null;
      throw err;
    });
  return cached;
}

/** Test hook: forget the cached catalog. */
export function resetStrategyCatalog(): void {
  cached = null;
}

/** The strategies the live comparison offers, loaded once per page. */
export function useStrategyCatalog(): CatalogState & { retry: () => void } {
  const [state, setState] = useState<CatalogState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    loadCatalog()
      .then((catalog) => {
        if (live) setState({ status: "ready", catalog });
      })
      .catch(() => {
        if (live)
          setState({
            status: "error",
            message:
              "The list of strategies could not be loaded. Is the backend reachable?",
          });
      });
    return () => {
      live = false;
    };
  }, [attempt]);
  return {
    ...state,
    retry: () => {
      setState({ status: "loading" });
      setAttempt((n) => n + 1);
    },
  };
}

/** The strategies a configuration compares, in order: its own choice (even
 *  an empty one, which nothing can run), or, when it has made none, the
 *  catalog's default selection. */
export function selectedStrategies(
  chosen: string[] | undefined,
  catalog: StrategyCatalog | null,
): string[] {
  if (chosen !== undefined) return chosen;
  return catalog?.defaultSelection ?? [];
}
