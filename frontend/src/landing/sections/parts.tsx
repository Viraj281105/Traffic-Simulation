import { useEffect, useRef, useState } from "react";
import { animate, useInView, useReducedMotion } from "framer-motion";
import type { Run } from "../scene/sceneData";

/** A number that counts up to `value` when it first scrolls into view (and
 *  again whenever `value` changes). Reduced motion shows the value at once. */
export function Counter({
  value,
  digits = 0,
  className,
}: {
  value: number | null;
  digits?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (value === null || reduced || !inView) return;
    const controls = animate(from.current, value, {
      duration: 1.1,
      ease: [0.2, 0.8, 0.2, 1],
      onUpdate: (v) => {
        from.current = v;
        setShown(v);
      },
    });
    return () => {
      controls.stop();
    };
  }, [value, inView, reduced]);
  const display = reduced ? (value ?? 0) : shown;
  return (
    <span ref={ref} className={className}>
      {value === null ? "—" : display.toFixed(digits)}
    </span>
  );
}

/** The queue over the whole recorded run, with a cursor at the replay's
 *  position. Both come straight from the engine's per-second readings. */
export function QueueSpark({
  run,
  second,
  colour,
  label,
}: {
  run: Run;
  second: number;
  colour: string;
  label: string;
}) {
  const w = 280;
  const h = 64;
  const max = Math.max(1, ...run.series.map((s) => s[1]));
  const last = run.series.length - 1;
  const pts = run.series.map(
    (s, i) =>
      `${((i / Math.max(1, last)) * w).toFixed(1)},${(h - (s[1] / max) * (h - 6) - 3).toFixed(1)}`,
  );
  const x = (Math.min(last, Math.max(0, second)) / Math.max(1, last)) * w;
  return (
    <svg
      className="spark"
      viewBox={`0 0 ${w.toString()} ${h.toString()}`}
      role="img"
      aria-label={label}
      preserveAspectRatio="none"
    >
      <polygon
        points={`0,${h.toString()} ${pts.join(" ")} ${w.toString()},${h.toString()}`}
        fill={colour}
        opacity="0.16"
      />
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke={colour}
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
      <line
        x1={x}
        x2={x}
        y1="0"
        y2={h}
        stroke="currentColor"
        strokeOpacity="0.55"
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
        style={{ transition: "all 250ms linear" }}
      />
    </svg>
  );
}
