import { useEffect, useState } from "react";
import { errorText, isNotFound } from "./http";

export type Remote<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "notFound" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

type Settled<T> =
  | { status: "notFound" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

/**
 * Loads once per `load` function. Pass a memoised loader (useMemo) or null to
 * stay idle; a new loader starts a new request and a stale answer is ignored.
 * "Loading" is derived (the settled answer belongs to another loader), so no
 * state is set synchronously inside the effect.
 */
export function useRemote<T>(
  load: (() => Promise<T>) | null,
  failure = "This could not be loaded.",
): Remote<T> {
  const [settled, setSettled] = useState<{
    source: unknown;
    value: Settled<T>;
  } | null>(null);

  useEffect(() => {
    if (!load) return;
    let live = true;
    load().then(
      (data) => {
        if (live)
          setSettled({ source: load, value: { status: "ready", data } });
      },
      (err: unknown) => {
        if (!live) return;
        setSettled({
          source: load,
          value: isNotFound(err)
            ? { status: "notFound" }
            : { status: "error", message: errorText(err, failure) },
        });
      },
    );
    return () => {
      live = false;
    };
  }, [load, failure]);

  if (!load) return { status: "idle" };
  if (settled?.source !== load) return { status: "loading" };
  return settled.value;
}
