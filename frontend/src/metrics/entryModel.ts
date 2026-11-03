import type { RunningMetrics } from "../types/simulation";

/** The entry model a study's runs used, as study outputs report it (backend
 *  study/control_comparison._entry_model; metric contract 7.10a). */
export interface EntryModelUsed {
  model: "suspend" | "queue";
  capacity: number | null;
}

/** One sentence naming the entry model of a study's runs, or null for the
 *  default, which every earlier result also used. */
export function entryModelSentence(
  used: EntryModelUsed | undefined,
  /** How this page treats the wait outside: shown in its own column
   *  (studies), counted in the delay objective (Discovery), or not shown
   *  (Stress Lab). */
  wait: "column" | "objective" | "not-shown" = "column",
): string | null {
  if (used?.model !== "queue") return null;
  const limit =
    used.capacity === null
      ? ""
      : ` (at most ${String(used.capacity)} per road; more were rejected)`;
  const reading = {
    column:
      'Delay is measured from entry; the wait before it is shown separately as "wait to enter".',
    objective:
      "The delay objective here includes that wait (delay from arrival), so no option gains by keeping traffic out.",
    "not-shown":
      "Delays here are measured from entry and do not include that wait.",
  }[wait];
  return `Arrivals that could not enter waited in a queue outside the map${limit}. ${reading}`;
}

/** The two entry models (backend vehicles/spawner.py, metric contract
 *  §7.10a), in the words the setup screens use. */
export const ENTRY_MODEL_INFO = {
  suspend: {
    label: "Hold arrivals back",
    summary:
      "A vehicle that cannot enter waits at the edge of the map, and no further vehicle arrives on that road until it gets in. The default; every earlier result used it.",
  },
  queue: {
    label: "Queue outside the map",
    summary:
      "Vehicles keep arriving at the configured rate and line up outside the modelled roads until there is room. Their wait is reported as “Wait to enter”. Suits busy and overloaded studies.",
  },
} as const;

/** How the five vehicle counts relate, so a reader can tell admitted,
 *  exited and waiting vehicles apart. */
export const ENTRY_POPULATIONS: readonly { term: string; meaning: string }[] = [
  {
    term: "Waiting outside",
    meaning:
      "Arrived but not yet on the map. Not counted as vehicles in the network, and not in delay.",
  },
  {
    term: "Admitted",
    meaning: "Entered the modelled roads.",
  },
  {
    term: "Exited",
    meaning:
      "Admitted and left the junction. Delay and throughput are measured on these.",
  },
  {
    term: "Still in the network",
    meaning:
      "Admitted but not out when the run ends; reported as the unfinished share.",
  },
  {
    term: "Rejected",
    meaning:
      "Turned away because a road's queue was at its limit. Only with a queue limit; always 0 otherwise.",
  },
];

/** Under the point queue: the arrivals still outside the map and, with a
 *  queue limit, those turned away. Neither is in the network, so neither
 *  is in "admitted" or "in network". Null under the default model. */
export function outsideNetworkText(
  m: RunningMetrics | undefined | null,
): string | null {
  const acc = m?.demandAccounting;
  if (!acc || acc.entryModel !== "queue") return null;
  const parts = [`${String(acc.waitingAtEntry)} waiting outside`];
  if (acc.rejected > 0) parts.push(`${String(acc.rejected)} rejected`);
  return parts.join(", ");
}

/** The entry-model chip for a comparison's results, or null for the default.
 *
 *  Read from what the engines report (`demandAccounting.entryModel` in each
 *  run's metrics), so the page states the model that actually ran; the
 *  requested setting is used only until the first metrics arrive. A run that
 *  reports a different model from the one requested, or runs that disagree,
 *  are flagged rather than labelled. */
export function entryModelChip(
  requested: { enabled: boolean; capacity?: number | null } | null | undefined,
  reported: ("suspend" | "queue" | undefined)[],
): { text: string; caution: boolean } | null {
  const seen = reported.filter(
    (m): m is "suspend" | "queue" => m !== undefined,
  );
  const wanted = requested?.enabled === true ? "queue" : "suspend";
  const limit = requested?.capacity
    ? ` (at most ${String(requested.capacity)} per road)`
    : "";
  if (seen.length && new Set(seen).size > 1) {
    return {
      text: "Strategies ran different entry models: not comparable",
      caution: true,
    };
  }
  const ran = seen[0] ?? wanted;
  if (ran !== wanted) {
    return {
      text:
        ran === "queue"
          ? "Ran with arrivals queued outside the map, not as requested"
          : "Queue outside the map was requested, but arrivals were held back",
      caution: true,
    };
  }
  return ran === "queue"
    ? { text: `Arrivals queue outside the map${limit}`, caution: false }
    : null;
}
