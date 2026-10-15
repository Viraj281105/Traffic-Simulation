import { useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";
import { DURATION, EASING, canAnimate, prefersReducedMotion } from "./motion";

/**
 * A container whose height follows its content smoothly: when what is inside
 * grows or shrinks (a check result arriving, a job finishing), the box eases
 * to its new height instead of jumping, so the content below slides rather
 * than snaps. The inner element is measured; the outer one is animated and
 * clipped only while the animation runs, so focus rings and shadows are never
 * cut off at rest.
 */
export function SmoothHeight({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const outer = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const box = outer.current;
    const content = inner.current;
    if (!canAnimate(box) || !content || typeof ResizeObserver === "undefined")
      return;
    let last = content.getBoundingClientRect().height;
    let running: Animation | null = null;
    const observer = new ResizeObserver(() => {
      const next = content.getBoundingClientRect().height;
      // A running animation's current height is the honest start point.
      const from = running ? box.getBoundingClientRect().height : last;
      last = next;
      if (Math.abs(next - from) < 2 || prefersReducedMotion()) return;
      running?.cancel();
      box.style.overflow = "clip";
      const animation = box.animate(
        [{ height: `${String(from)}px` }, { height: `${String(next)}px` }],
        { duration: DURATION.slow, easing: EASING.emphasized },
      );
      running = animation;
      // Events fire asynchronously: a cancelled animation must not reset the
      // state of the one that replaced it.
      const done = () => {
        if (running !== animation) return;
        running = null;
        box.style.overflow = "";
      };
      animation.addEventListener("finish", done);
      animation.addEventListener("cancel", done);
    });
    observer.observe(content);
    return () => {
      observer.disconnect();
      running?.cancel();
    };
  }, []);

  return (
    <div ref={outer} className={className}>
      <div ref={inner} className="uf-smooth-inner">
        {children}
      </div>
    </div>
  );
}
