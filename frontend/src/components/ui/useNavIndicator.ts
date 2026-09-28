import { useLayoutEffect, useRef } from "react";

const ACTIVE = '[aria-current="page"], [aria-current="step"]';

/**
 * Positions a nav's sliding active indicator. Sets --ind-x / --ind-w / --ind-o
 * on the nav element (its ::after draws the indicator, see App.css) from the
 * current item, and re-measures when the nav or its items resize (fonts
 * loading, viewport changes). The indicator only animates once it has been
 * placed, so it never sweeps in from the left edge on first paint.
 */
export function useNavIndicator<T extends HTMLElement>(activeKey: string) {
  const ref = useRef<T>(null);

  useLayoutEffect(() => {
    const nav = ref.current;
    if (!nav) return;
    const place = () => {
      const active = nav.querySelector<HTMLElement>(ACTIVE);
      if (!active) {
        nav.style.setProperty("--ind-o", "0");
        return;
      }
      nav.style.setProperty("--ind-x", `${String(active.offsetLeft)}px`);
      nav.style.setProperty("--ind-y", `${String(active.offsetTop)}px`);
      nav.style.setProperty("--ind-w", `${String(active.offsetWidth)}px`);
      nav.style.setProperty("--ind-h", `${String(active.offsetHeight)}px`);
      nav.style.setProperty("--ind-o", "1");
    };
    place();
    const frame = requestAnimationFrame(() => {
      nav.dataset.indReady = "true";
    });
    if (typeof ResizeObserver === "undefined") {
      return () => {
        cancelAnimationFrame(frame);
      };
    }
    const observer = new ResizeObserver(place);
    observer.observe(nav);
    for (const item of nav.querySelectorAll("a, button"))
      observer.observe(item);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [activeKey]);

  return ref;
}
