import { useEffect, useState } from "react";
import { InsightsApiError, errorText } from "../netcommon/api";

export type Load<T> =
  | { status: "loading" }
  | { status: "error"; message: string; httpStatus: number | null }
  | { status: "ready"; data: T };

/** Run `fetcher` once when the component mounts. */
export function useLoad<T>(
  fetcher: () => Promise<T>,
  failure: string,
): Load<T> {
  const [state, setState] = useState<Load<T>>({ status: "loading" });
  useEffect(() => {
    let live = true;
    fetcher().then(
      (data) => {
        if (live) setState({ status: "ready", data });
      },
      (err: unknown) => {
        if (!live) return;
        const httpStatus = err instanceof InsightsApiError ? err.status : null;
        setState({
          status: "error",
          message: errorText(err, failure),
          httpStatus,
        });
      },
    );
    return () => {
      live = false;
    };
    // The request runs once per mount, whatever the closure holds.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return state;
}
