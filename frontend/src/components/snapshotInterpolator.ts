import type { LiveSnapshot, SnapshotVehicle } from "../types/simulation";

/** A vehicle's interpolated pose for one rendered frame. */
export interface VehiclePose {
  vehicle: SnapshotVehicle;
  x: number;
  y: number;
  heading: number;
}

export interface InterpolatedFrame {
  /** Newest snapshot received: the source of controller/HUD state. */
  snapshot: LiveSnapshot;
  vehicles: VehiclePose[];
  /** False when nothing visible changed since the previous sample, so the
   *  caller may skip redrawing. */
  changed: boolean;
}

/** Snapshots kept for interpolation (~0.8 s at 10 Hz). */
const BUFFER_SIZE = 8;

/** How far (in simulation ticks) playback trails the newest snapshot. The
 *  longest routine gap between new ticks is one missed message (~220 ms, two
 *  ticks); two and a half ticks rides that out with margin instead of
 *  stalling. */
const PLAYBACK_DELAY_TICKS = 2.5;

/** Smoothing factor for the measured simulation rate (sim s per wall s). */
const RATE_SMOOTHING = 0.2;

/** Rate (1/s) at which playback time converges onto its target. */
const CONVERGENCE_RATE = 3;

/** Beyond this gap (s) playback jumps to its target instead of easing. */
const RESYNC_THRESHOLD_S = 0.5;

/**
 * Turns the irregular snapshot stream into smooth per-frame vehicle poses.
 *
 * The backend steps the simulation and sends snapshots on two independent
 * ~10 Hz loops, so consecutive messages advance 0, 1 or 2 ticks and arrive
 * every ~100-120 ms. Interpolating "previous -> current over a fixed 100 ms
 * from arrival" therefore froze every vehicle whenever a message repeated a
 * tick, and doubled their speed whenever one skipped a tick.
 *
 * This instead keeps a short buffer and plays it back on the simulation's
 * own clock (snapshot timestamps), slightly behind the newest snapshot. At
 * each snapshot's timestamp the rendered poses equal that snapshot's exactly;
 * between them positions are linearly interpolated. Paused, stopped and
 * completed simulations show the newest snapshot as-is.
 */
export class SnapshotInterpolator {
  private buffer: LiveSnapshot[] = [];
  private playbackTime = 0;
  private newestArrival = 0;
  /** Simulation seconds advanced per wall-clock second, measured from
   *  arrivals: the backend steps a little slower than real time. */
  private rate = 1;
  private lastSample: number | null = null;
  private dirty = true;
  private readonly exactCache = new WeakMap<LiveSnapshot, VehiclePose[]>();
  private readonly indexCache = new WeakMap<
    LiveSnapshot,
    Map<string, SnapshotVehicle>
  >();

  push(snapshot: LiveSnapshot | null, now: number): void {
    if (!snapshot) {
      if (this.buffer.length) this.dirty = true;
      this.buffer = [];
      return;
    }
    const newest = this.buffer[this.buffer.length - 1] as
      LiveSnapshot | undefined;
    if (snapshot === newest) return;
    this.dirty = true;

    if (
      newest &&
      (snapshot.timestamp < newest.timestamp ||
        snapshot.simulationId !== newest.simulationId ||
        snapshot.configId !== newest.configId)
    ) {
      // A reset, restart or reconfiguration: the old run's poses are not a
      // valid starting point for the new one.
      this.buffer = [];
    } else if (newest && snapshot.timestamp === newest.timestamp) {
      // Same simulation instant (e.g. only the status changed).
      this.buffer[this.buffer.length - 1] = snapshot;
      return;
    }

    if (newest && now > this.newestArrival) {
      const measured =
        (snapshot.timestamp - newest.timestamp) /
        ((now - this.newestArrival) / 1000);
      this.rate += (measured - this.rate) * RATE_SMOOTHING;
      this.rate = Math.min(2, Math.max(0.25, this.rate));
    }
    this.buffer.push(snapshot);
    if (this.buffer.length > BUFFER_SIZE) this.buffer.shift();
    this.newestArrival = now;
  }

  sample(now: number): InterpolatedFrame | null {
    const dt =
      this.lastSample === null
        ? 0
        : Math.max(0, (now - this.lastSample) / 1000);
    this.lastSample = now;

    const newest = this.buffer[this.buffer.length - 1] as
      LiveSnapshot | undefined;
    if (!newest) return null;

    if (newest.simulationStatus !== "running" || this.buffer.length === 1) {
      const changed = this.dirty;
      this.dirty = false;
      this.playbackTime = newest.timestamp;
      return { snapshot: newest, vehicles: this.exactPoses(newest), changed };
    }
    this.dirty = false;

    const step = newest.deltaTime > 0 ? newest.deltaTime : 0.1;
    // Estimated simulation time "now", minus the playback delay.
    const target =
      newest.timestamp +
      (this.rate * (now - this.newestArrival)) / 1000 -
      PLAYBACK_DELAY_TICKS * step;

    if (Math.abs(target - this.playbackTime) > RESYNC_THRESHOLD_S) {
      this.playbackTime = target;
    } else {
      this.playbackTime += this.rate * dt;
      this.playbackTime +=
        (target - this.playbackTime) * Math.min(1, dt * CONVERGENCE_RATE);
    }
    const oldest = this.buffer[0];
    this.playbackTime = Math.min(
      newest.timestamp,
      Math.max(oldest.timestamp, this.playbackTime),
    );

    // Bracketing pair a.timestamp <= playbackTime <= b.timestamp.
    let i = this.buffer.length - 1;
    while (i > 0 && this.buffer[i - 1].timestamp > this.playbackTime) i -= 1;
    const b = this.buffer[i];
    const a = i > 0 ? this.buffer[i - 1] : b;
    const span = b.timestamp - a.timestamp;
    const alpha = span > 0 ? (this.playbackTime - a.timestamp) / span : 1;

    return {
      snapshot: newest,
      vehicles: this.interpolate(a, b, alpha),
      changed: true,
    };
  }

  private interpolate(
    a: LiveSnapshot,
    b: LiveSnapshot,
    alpha: number,
  ): VehiclePose[] {
    if (a === b || alpha >= 1) return this.exactPoses(b);
    const previous = this.index(a);
    const poses: VehiclePose[] = [];
    for (const vehicle of b.vehicles) {
      if (vehicle.state === "exited") continue;
      const prev = previous.get(vehicle.id);
      if (!prev) {
        poses.push({
          vehicle,
          x: vehicle.x,
          y: vehicle.y,
          heading: vehicle.heading,
        });
        continue;
      }
      // Heading along the shortest angular path.
      let diff = vehicle.heading - prev.heading;
      while (diff < -180) diff += 360;
      while (diff > 180) diff -= 360;
      poses.push({
        vehicle,
        x: prev.x + alpha * (vehicle.x - prev.x),
        y: prev.y + alpha * (vehicle.y - prev.y),
        heading: (prev.heading + alpha * diff + 360) % 360,
      });
    }
    return poses;
  }

  private exactPoses(snapshot: LiveSnapshot): VehiclePose[] {
    let poses = this.exactCache.get(snapshot);
    if (!poses) {
      poses = [];
      for (const vehicle of snapshot.vehicles) {
        if (vehicle.state === "exited") continue;
        poses.push({
          vehicle,
          x: vehicle.x,
          y: vehicle.y,
          heading: vehicle.heading,
        });
      }
      this.exactCache.set(snapshot, poses);
    }
    return poses;
  }

  private index(snapshot: LiveSnapshot): Map<string, SnapshotVehicle> {
    let map = this.indexCache.get(snapshot);
    if (!map) {
      map = new Map(snapshot.vehicles.map((v) => [v.id, v]));
      this.indexCache.set(snapshot, map);
    }
    return map;
  }
}
