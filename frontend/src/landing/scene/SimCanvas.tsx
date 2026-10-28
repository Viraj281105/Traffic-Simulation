import { useEffect, useRef, type RefObject } from "react";
import { drawScene, type Camera, type SceneTheme } from "./render";
import { useSceneTheme } from "./SceneContext";
import { useOnScreen, type SimClock } from "./clock";
import { sampleRun, type SceneData, type StrategyId } from "./sceneData";

interface SimCanvasProps {
  data: SceneData;
  strategy: StrategyId;
  clock: RefObject<SimClock>;
  camera: RefObject<Camera>;
  label: string;
  className?: string;
  /** Upper bound on the canvas pixel ratio. */
  maxDpr?: number;
  /** Pin the canvas to one theme (the dark hero and finale); by default
   *  it follows the page. */
  theme?: SceneTheme;
}

/** One junction, replayed from the recorded run for `strategy`. The canvas
 *  repaints only while on screen and only when the clock or camera moved. */
export function SimCanvas({
  data,
  strategy,
  clock,
  camera,
  label,
  className,
  maxDpr = 2,
  theme: pinned,
}: SimCanvasProps) {
  const pageTheme = useSceneTheme();
  const theme = pinned ?? pageTheme;
  const ref = useRef<HTMLCanvasElement | null>(null);
  const visible = useOnScreen(ref);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const run = data.runs[strategy];
    let width = 0;
    let height = 0;
    let dpr = 1;
    let lastKey = "";
    let raf = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(maxDpr, window.devicePixelRatio || 1);
      width = Math.max(1, Math.round(rect.width));
      height = Math.max(1, Math.round(rect.height));
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      lastKey = "";
    };
    resize();
    const ro =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    ro?.observe(canvas);

    const frame = () => {
      raf = requestAnimationFrame(frame);
      if (!visible.current || document.hidden) return;
      const cam = camera.current;
      const key = `${clock.current.t.toFixed(3)}|${cam.yaw.toFixed(2)}|${cam.elev.toFixed(2)}|${cam.zoom.toFixed(3)}|${cam.shiftY.toFixed(3)}|${cam.shiftX.toFixed(3)}|${width.toString()}x${height.toString()}`;
      if (key === lastKey) return;
      lastKey = key;
      const s = sampleRun(run, data, clock.current.t);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawScene(ctx, width, height, {
        strategy,
        vehicles: s.vehicles,
        control: s.control,
        camera: cam,
        innerRadius: run.geometry.innerRadius ?? 10,
        outerRadius: run.geometry.outerRadius ?? 20,
        clock: s.clock,
        theme,
      });
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      ro?.disconnect();
    };
  }, [data, strategy, clock, camera, visible, maxDpr, theme]);

  return (
    <canvas ref={ref} className={className} role="img" aria-label={label} />
  );
}
