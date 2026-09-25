import { useEffect, useState } from "react";

/**
 * True once `active` has stayed true for `delayMs`. Used so a loader only
 * appears for work that is actually taking a moment: a response that
 * arrives within the delay never flashes a loader, and nothing is ever
 * held back to show one.
 */
export function useDelayedFlag(active: boolean, delayMs = 150): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!active) return;
    const timer = window.setTimeout(() => {
      setShown(true);
    }, delayMs);
    return () => {
      window.clearTimeout(timer);
      setShown(false);
    };
  }, [active, delayMs]);
  return active && shown;
}
