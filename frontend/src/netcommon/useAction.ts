import { useCallback, useRef, useState } from "react";
import { errorText } from "./api";

export type Action<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

/**
 * A request that starts when the person presses a button (the network screens
 * run a simulation on demand; nothing loads by itself). A newer run replaces
 * an older one, and a stale answer is ignored.
 */
export function useAction<T>(
  failure: string,
): [Action<T>, (run: () => Promise<T>) => void, () => void] {
  const [state, setState] = useState<Action<T>>({ status: "idle" });
  const latest = useRef(0);

  const start = useCallback(
    (run: () => Promise<T>) => {
      const mine = ++latest.current;
      setState({ status: "loading" });
      run().then(
        (data) => {
          if (latest.current === mine) setState({ status: "ready", data });
        },
        (err: unknown) => {
          if (latest.current === mine) {
            setState({ status: "error", message: errorText(err, failure) });
          }
        },
      );
    },
    [failure],
  );

  const reset = useCallback(() => {
    latest.current += 1;
    setState({ status: "idle" });
  }, []);

  return [state, start, reset];
}
