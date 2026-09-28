import { useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";

const reducedMotion = () =>
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * The app's <main>, entering with a short fade, rise and blur-to-sharp each
 * time `transitionKey` changes (a new page or guided step). Nothing waits on
 * the animation: the new content is rendered and interactive immediately,
 * and nothing is remounted — the element is only animated.
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
    const reduce = reducedMotion();
    const animation = el.animate(
      reduce
        ? [{ opacity: 0.4 }, { opacity: 1 }]
        : [
            {
              opacity: 0,
              transform: "translateY(8px)",
              filter: "blur(6px)",
            },
            { opacity: 1, transform: "none", filter: "blur(0)" },
          ],
      {
        duration: reduce ? 120 : 340,
        easing: "cubic-bezier(0.2, 0.8, 0.2, 1)",
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
