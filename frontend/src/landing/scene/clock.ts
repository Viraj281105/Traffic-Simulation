import { useEffect, useRef, type RefObject } from "react";
import type { Camera } from "./render";

export interface SimClock {
  /** Seconds into the replayed window. */
  t: number;
}

export const HERO_CAMERA: Camera = {
  yaw: -32,
  elev: 36,
  zoom: 1,
  shiftY: 0.04,
  shiftX: 0,
};

/** Whether `ref`'s element is on screen. Read `.current` inside loops. */
export function useOnScreen(
  ref: RefObject<Element | null>,
  margin = "120px",
): RefObject<boolean> {
  const visible = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) visible.current = entry.isIntersecting;
      },
      { rootMargin: margin },
    );
    io.observe(el);
    return () => {
      io.disconnect();
    };
  }, [ref, margin]);
  return visible;
}

/** Advances a shared replay clock while `playing` and the tab is visible. */
export function useSimClock(
  playing: boolean,
  speed = 1,
  start = 0,
): RefObject<SimClock> {
  const clock = useRef<SimClock>({ t: start });
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const loop = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      if (!document.hidden) clock.current.t += dt * speed;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
    };
  }, [playing, speed]);
  return clock;
}

/** Moves a replay clock to `t` seconds (the scrubber). */
export function seekClock(clock: RefObject<SimClock>, t: number): void {
  clock.current.t = t;
}
