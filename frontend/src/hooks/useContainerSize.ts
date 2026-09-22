import { useCallback, useEffect, useRef, useState } from "react";

/**
 * useContainerSize – Returns the live pixel dimensions of the element
 * attached via the returned ref. Recalculates on every ResizeObserver entry.
 *
 * The ref is a callback ref so the observer follows the element: containers
 * that mount later (e.g. only when their view is shown) or remount are
 * measured too. A plain ref observed once on mount missed them, leaving their
 * canvases at a fallback size that CSS then stretched out of proportion.
 */
export function useContainerSize(): [
  (node: HTMLElement | null) => void,
  { width: number; height: number },
] {
  const [size, setSize] = useState({ width: 0, height: 0 });
  const observerRef = useRef<ResizeObserver | null>(null);

  const ref = useCallback((node: HTMLElement | null) => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (!node) return;

    const measure = () => {
      const { clientWidth: width, clientHeight: height } = node;
      if (width > 0 && height > 0) {
        setSize((prev) =>
          prev.width === width && prev.height === height
            ? prev
            : { width, height },
        );
      }
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    observerRef.current = ro;
  }, []);

  useEffect(
    () => () => {
      observerRef.current?.disconnect();
    },
    [],
  );

  return [ref, size];
}
