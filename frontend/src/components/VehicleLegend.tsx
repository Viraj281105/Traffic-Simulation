import type { LiveSnapshot, VehicleClass } from "../types/simulation";
import {
  VEHICLE_CLASSES,
  VEHICLE_CLASS_INFO,
  type VehicleMix,
} from "../vehicles/vehicleClasses";
import "./VehicleLegend.css";

/** Proportional bar of a traffic mix (cars only when ``mix`` is null). */
export function VehicleMixBar({ mix }: { mix: VehicleMix | null | undefined }) {
  const parts = mix
    ? VEHICLE_CLASSES.filter((c) => mix[c.id] > 0)
    : [VEHICLE_CLASS_INFO.car];
  const label = parts
    .map(
      (c) =>
        `${String(Math.round((mix ? mix[c.id] : 1) * 100))}% ${c.label.toLowerCase()}`,
    )
    .join(", ");
  return (
    <span className="vehicle-mix-bar" role="img" aria-label={label}>
      {parts.map((c) => (
        <span
          key={c.id}
          className="vehicle-mix-bar__part"
          style={{
            flexGrow: mix ? mix[c.id] : 1,
            background: c.color,
          }}
          title={`${c.label}: ${String(Math.round((mix ? mix[c.id] : 1) * 100))}%`}
        />
      ))}
    </span>
  );
}

/**
 * Map legend: which vehicle classes are on the road right now, and how many.
 * Hidden for cars-only traffic, so the calibrated comparison looks exactly
 * as it always has. Also explains the lane-change indicator when vehicles
 * are changing lanes.
 */
export function VehicleLegend({
  snapshot,
}: {
  snapshot: LiveSnapshot | null | undefined;
}) {
  if (!snapshot) return null;
  const counts = new Map<VehicleClass, number>();
  for (const v of snapshot.vehicles) {
    if (v.state === "exited") continue;
    const cls = v.vehicleType ?? "car";
    counts.set(cls, (counts.get(cls) ?? 0) + 1);
  }
  const mixed = [...counts.keys()].some((c) => c !== "car");
  const changing = snapshot.laneModel?.laneChangesInProgress ?? 0;
  if (!mixed && changing === 0) return null;
  return (
    <div className="vehicle-legend" aria-label="Map legend">
      {mixed &&
        VEHICLE_CLASSES.filter((c) => counts.has(c.id)).map((c) => (
          <span key={c.id} className="vehicle-legend__item">
            <span
              className={`vehicle-legend__swatch is-${c.id}`}
              style={{ background: c.color }}
              aria-hidden="true"
            />
            {c.label}
            <span className="vehicle-legend__count">
              {String(counts.get(c.id) ?? 0)}
            </span>
          </span>
        ))}
      {changing > 0 && (
        <span className="vehicle-legend__item">
          <span className="vehicle-legend__blink" aria-hidden="true" />
          Changing lanes
          <span className="vehicle-legend__count">{String(changing)}</span>
        </span>
      )}
    </div>
  );
}
