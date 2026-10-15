import { useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";
import { DURATION, EASING, prefersReducedMotion } from "./motion";

/**
 * The app's <main>, entering with a short fade and rise each time
 * `transitionKey` changes (a new page or guided step). Only opacity and
 * transform animate — both run on the compositor, so a long page (the
 * planner, a results report) enters as smoothly as a short one; a blur on
 * the whole page would repaint every frame. Nothing waits on the animation:
 * the new content is rendered and interactive immediately, and nothing is
 * remounted — the element is only animated.
 *
 * Signals the change on <html data-route-busy> for the header's route
 * progress bar (App.css) for as long as the entrance runs.
 */
export function PageTransition({
  transitionKey,
  className,
  children,
}: {
  transitionKey: string;
  className?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof el.animate !== "function") return;
    const reduce = prefersReducedMotion();
    const animation = el.animate(
      reduce
        ? [{ opacity: 0.4 }, { opacity: 1 }]
        : [
            { opacity: 0, transform: "translateY(6px)" },
            { opacity: 1, transform: "none" },
          ],
      {
        duration: reduce ? 120 : DURATION.page,
        easing: EASING.emphasized,
      },
    );
    const root = document.documentElement;
    root.dataset.routeBusy = "true";
    const done = () => {
      delete root.dataset.routeBusy;
    };
    animation.addEventListener("finish", done);
    animation.addEventListener("cancel", done);
    return () => {
      animation.cancel();
    };
  }, [transitionKey]);

  return (
    <main ref={ref} className={className}>
      {children}
    </main>
  );
}
