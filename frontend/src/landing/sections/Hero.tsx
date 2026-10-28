import { useEffect, useRef } from "react";
import { ArrowDownRight, ArrowRight } from "lucide-react";
import { useReducedMotion } from "framer-motion";
import { Reveal } from "../components/Reveal";
import { VIEW_ROUTES } from "../../routing";
import { useSceneData } from "../scene/SceneContext";
import { SimCanvas } from "../scene/SimCanvas";
import { HERO_CAMERA, useSimClock } from "../scene/clock";
import type { Camera } from "../scene/render";
import { formatClock } from "../scene/sceneData";
import { useHud } from "../scene/useHud";

/** First screen: the recorded fixed-time junction under pressure, in
 *  perspective, with a live readout taken from the same frames. */
export function Hero() {
  const data = useSceneData();
  const reduced = useReducedMotion() ?? false;
  const section = useRef<HTMLElement | null>(null);
  const clock = useSimClock(!reduced, 1, reduced ? 21 : 0);
  const camera = useRef<Camera>({ ...HERO_CAMERA });
  const hud = useHud(data, "fixed_time", clock);

  // Slow camera drift, pointer parallax and a pull-back as the page scrolls.
  useEffect(() => {
    const target = { x: 0, y: 0 };
    let raf = 0;
    const narrow = () => window.innerWidth < 900;
    const apply = () => {
      const el = section.current;
      const rect = el?.getBoundingClientRect();
      const span = rect ? Math.max(1, rect.height) : 1;
      const p = rect ? Math.max(0, Math.min(1, -rect.top / span)) : 0;
      const c = camera.current;
      const t = performance.now() / 1000;
      const drift = reduced ? 0 : Math.sin(t / 9) * 3;
      c.yaw = HERO_CAMERA.yaw + drift + target.x * 5 + p * 26;
      c.elev = HERO_CAMERA.elev + target.y * -3 + p * 22;
      c.zoom = (narrow() ? 0.95 : 1.42) + p * 0.3;
      c.shiftX = narrow() ? 0 : 0.17;
      c.shiftY = narrow() ? -0.26 : 0.03 - p * 0.05;
    };
    const onMove = (e: PointerEvent) => {
      target.x = (e.clientX / window.innerWidth - 0.5) * 2;
      target.y = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    const loop = () => {
      apply();
      raf = requestAnimationFrame(loop);
    };
    apply();
    if (!reduced) {
      window.addEventListener("pointermove", onMove, { passive: true });
      raf = requestAnimationFrame(loop);
    } else {
      window.addEventListener("scroll", apply, { passive: true });
      window.addEventListener("resize", apply);
    }
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("scroll", apply);
      window.removeEventListener("resize", apply);
    };
  }, [reduced]);

  return (
    <section
      className="hero-stage"
      id="top"
      data-surface="dark"
      aria-labelledby="hero-title"
      ref={section}
    >
      <div className="hero-stage__scene" aria-hidden={!data}>
        {data ? (
          <SimCanvas
            data={data}
            strategy="fixed_time"
            theme="dark"
            clock={clock}
            camera={camera}
            label="A four-arm junction under a fixed-time signal, replayed from a recorded engine run. Vehicles are coloured green when flowing, amber when slowing and red when stopped."
            className="hero-stage__canvas"
          />
        ) : null}
      </div>
      <div className="hero-stage__scrim" aria-hidden="true" />

      <div className="hero-stage__content">
        <p className="hero-stage__kicker">
          <span className="signal-dot" aria-hidden="true" /> Traffic simulation
          and evidence
        </p>
        <Reveal>
          <h1 id="hero-title" className="hero-stage__title display">
            Signal or
            <br />
            <em>roundabout?</em>
            <br />
            Run both.
          </h1>
        </Reveal>
        <Reveal delay={0.15}>
          <p className="hero-stage__sub">
            Same junction. Same cars. Four ways to control it, and the evidence
            to judge them.
          </p>
        </Reveal>
        <div className="hero-stage__actions">
          <a
            className="pb-btn pb-primary pb-lg"
            href={VIEW_ROUTES.comparative}
            data-testid="link-explore-simulation"
          >
            Launch UrbanFlow <ArrowRight size={16} />
          </a>
          <a
            className="pb-btn pb-lg hero-stage__ghost"
            href="#story"
            data-testid="link-read-method"
          >
            See it unfold <ArrowDownRight size={16} />
          </a>
        </div>
      </div>

      <div className="hero-stage__hud" aria-label="Live readout of the replay">
        <div className="hud-chip">
          <span className="hud-chip__label">Simulated time</span>
          <strong className="hud-chip__value mono">
            {formatClock(hud.clock)}
          </strong>
        </div>
        <div className="hud-chip">
          <span className="hud-chip__label">Vehicles on the network</span>
          <strong className="hud-chip__value mono">
            {hud.vehicles.toString()}
          </strong>
        </div>
        <div className="hud-chip is-warn">
          <span className="hud-chip__label">Queued at the signal</span>
          <strong className="hud-chip__value mono">
            {hud.queued.toString()}
          </strong>
        </div>
        <div className="hud-chip">
          <span className="hud-chip__label">Control strategies</span>
          <strong className="hud-chip__value mono">4</strong>
        </div>
        <p className="hero-stage__caption">
          {data
            ? `Replay of a real engine run: fixed-time signal, ${data.provenance.vehiclesPerHourPerArm.toString()} vehicles per hour on every arm, seed ${data.provenance.seed.toString()}.`
            : "Loading the recorded simulation…"}
        </p>
      </div>
    </section>
  );
}
