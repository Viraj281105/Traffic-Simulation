/**
 * The dashboard's motion system for script-driven animation (the Web
 * Animations API). CSS reads the same values from styles/tokens.css
 * (--dur-*, --ease-*); keep the two in step.
 *
 * Rules: animate transform and opacity (height only where content really
 * grows, and only inside a clipped wrapper); never delay interaction; exits
 * are shorter than entrances; under prefers-reduced-motion, spatial movement
 * is dropped and state changes happen at once.
 */
import { useCallback, useLayoutEffect, useRef } from "react";

export const DURATION = {
  instant: 90,
  fast: 150,
  base: 220,
  slow: 360,
  page: 300,
  exit: 160,
} as const;

export const EASING = {
  out: "cubic-bezier(0.2, 0.8, 0.2, 1)",
  emphasized: "cubic-bezier(0.2, 0, 0, 1)",
  exit: "cubic-bezier(0.4, 0, 1, 1)",
} as const;

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function canAnimate(el: Element | null): el is HTMLElement {
  return !!el && typeof (el as HTMLElement).animate === "function";
}

export const EXIT = {
  dialog: [
    { opacity: 1, transform: "none" },
    { opacity: 0, transform: "translateY(6px) scale(0.985)" },
  ],
  drawer: [
    { opacity: 1, transform: "none" },
    { opacity: 0, transform: "translateX(28px)" },
  ],
  scrim: [{ opacity: 1 }, { opacity: 0 }],
} satisfies Record<string, Keyframe[]>;

/**
 * Gives a dialog or drawer an exit. Attach `overlay` to the scrim and
 * `panel` to the surface, and call `close` wherever the dialog closes
 * (close button, Escape, backdrop): the two play a short exit — quicker than
 * their entrance — and then the real `onClose` runs. Repeated calls during
 * the exit are ignored. Nothing can animate (reduced motion, tests): it
 * closes at once.
 */
export function useExitTransition(
  onClose: () => void,
  panelExit: Keyframe[] = EXIT.dialog,
) {
  const overlay = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const closing = useRef(false);
  const onCloseRef = useRef(onClose);
  const exitRef = useRef(panelExit);
  useLayoutEffect(() => {
    onCloseRef.current = onClose;
    exitRef.current = panelExit;
  });

  const close = useCallback(() => {
    if (closing.current) return;
    const targets = [panel.current, overlay.current].filter(
      (el): el is HTMLDivElement => canAnimate(el),
    );
    if (targets.length === 0 || prefersReducedMotion()) {
      onCloseRef.current();
      return;
    }
    closing.current = true;
    const animations = targets.map((el) =>
      el.animate(el === panel.current ? exitRef.current : EXIT.scrim, {
        duration: DURATION.exit,
        easing: EASING.exit,
        fill: "forwards",
      }),
    );
    // Closing never depends on the animation finishing: a page that is not
    // painting (a background tab, a hidden pane) has a frozen animation
    // clock, so a timer closes it on schedule regardless.
    const finished = Promise.all(
      animations.map((a) => a.finished.catch(() => undefined)),
    );
    const deadline = new Promise<void>((resolve) => {
      setTimeout(resolve, DURATION.exit + 60);
    });
    void Promise.race([finished, deadline]).then(() => {
      closing.current = false;
      onCloseRef.current();
      // If the parent keeps the element mounted, do not leave it faded out.
      // A timer, not requestAnimationFrame, which also pauses off-screen.
      setTimeout(() => {
        for (const a of animations) a.cancel();
      }, DURATION.fast);
    });
  }, []);

  return { overlay, panel, close };
}

/**
 * FLIP for a reorderable list: children marked `data-flip-key` glide from
 * their previous position to their new one when `orderKey` changes (a row
 * made the baseline, a row removed), instead of jumping. Positions are taken
 * relative to the container, so scrolling between renders is not mistaken
 * for movement.
 */
export function useFlipList<T extends HTMLElement>(orderKey: string) {
  const ref = useRef<T>(null);
  const last = useRef(new Map<string, number>());

  useLayoutEffect(() => {
    const list = ref.current;
    if (!list) return;
    const origin = list.getBoundingClientRect().top;
    const next = new Map<string, number>();
    const reduce = prefersReducedMotion();
    for (const item of list.querySelectorAll<HTMLElement>("[data-flip-key]")) {
      const key = item.dataset.flipKey ?? "";
      const top = item.getBoundingClientRect().top - origin;
      next.set(key, top);
      const previous = last.current.get(key);
      if (
        previous !== undefined &&
        Math.abs(previous - top) > 1 &&
        !reduce &&
        canAnimate(item)
      ) {
        item.animate(
          [
            { transform: `translateY(${String(previous - top)}px)` },
            { transform: "none" },
          ],
          { duration: DURATION.slow, easing: EASING.emphasized },
        );
      }
    }
    last.current = next;
  }, [orderKey]);

  return ref;
}
