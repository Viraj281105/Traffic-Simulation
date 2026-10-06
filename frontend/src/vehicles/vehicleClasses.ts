/**
 * Vehicle classes (V1.1): labels, colours and traffic-mix presets.
 *
 * The behaviour of each class (dimensions, acceleration, braking, headway,
 * cornering, lane changing) lives in the backend
 * (backend/src/vehicles/vehicle_types.py). The frontend only describes the
 * classes and chooses the share of arrivals each one gets.
 */

import type { VehicleClass } from "../types/simulation";

export type { VehicleClass };

/** Share of arrivals per class (0-1, summing to 1). */
export type VehicleMix = Record<VehicleClass, number>;

export interface VehicleClassInfo {
  id: VehicleClass;
  label: string;
  /** One-line description of what makes the class behave differently. */
  description: string;
  /** Body colour on the maps and swatch colour in legends. */
  color: string;
}

/** In the backend's canonical order. */
export const VEHICLE_CLASSES: VehicleClassInfo[] = [
  {
    id: "car",
    label: "Car",
    description: "The calibrated reference vehicle, 4–5 m.",
    color: "#4d96ff",
  },
  {
    id: "suv",
    label: "SUV",
    description: "Slightly longer and wider, a little slower to accelerate.",
    color: "#43aa8b",
  },
  {
    id: "bus",
    label: "Bus",
    description:
      "12 m. Gentle acceleration and braking, longer headway, slow through curves, needs a bigger gap.",
    color: "#f4b400",
  },
  {
    id: "truck",
    label: "Truck",
    description:
      "8–12 m. The slowest to accelerate and the longest headway; takes turns slowly.",
    color: "#e76f51",
  },
  {
    id: "motorcycle",
    label: "Motorcycle / bike",
    description: "2 m. Quick to accelerate, short headway, corners faster.",
    color: "#c77dff",
  },
];

export const VEHICLE_CLASS_INFO: Record<VehicleClass, VehicleClassInfo> =
  Object.fromEntries(VEHICLE_CLASSES.map((c) => [c.id, c])) as Record<
    VehicleClass,
    VehicleClassInfo
  >;

export interface MixPreset {
  id: string;
  label: string;
  description: string;
  /** null = cars only: the calibrated V1.0 population, exactly. */
  mix: VehicleMix | null;
}

export const MIX_PRESETS: MixPreset[] = [
  {
    id: "cars",
    label: "Cars only",
    description:
      "The calibrated comparison: every vehicle is the reference car.",
    mix: null,
  },
  {
    id: "city",
    label: "Typical city mix",
    description: "Mostly cars and SUVs, with some buses, trucks and bikes.",
    mix: { car: 0.6, suv: 0.2, bus: 0.05, truck: 0.05, motorcycle: 0.1 },
  },
  {
    id: "freight",
    label: "Bus & freight route",
    description: "Three in ten vehicles are buses or trucks.",
    mix: { car: 0.5, suv: 0.1, bus: 0.15, truck: 0.15, motorcycle: 0.1 },
  },
  {
    id: "two-wheeler",
    label: "Many two-wheelers",
    description: "Four in ten vehicles are motorcycles or scooters.",
    mix: { car: 0.45, suv: 0.1, bus: 0.03, truck: 0.02, motorcycle: 0.4 },
  },
];

export function emptyMix(): VehicleMix {
  return { car: 0, suv: 0, bus: 0, truck: 0, motorcycle: 0 };
}

/** Scale shares to sum to exactly 1 (3 decimals), or null if all are zero. */
export function normalizeMix(mix: VehicleMix): VehicleMix | null {
  const total = VEHICLE_CLASSES.reduce(
    (sum, c) => sum + Math.max(0, mix[c.id]),
    0,
  );
  if (!(total > 0)) return null;
  const out = emptyMix();
  let assigned = 0;
  let largest: VehicleClass = "car";
  for (const c of VEHICLE_CLASSES) {
    const share = Math.round((Math.max(0, mix[c.id]) / total) * 1000) / 1000;
    out[c.id] = share;
    assigned += share;
    if (share > out[largest]) largest = c.id;
  }
  // Put the rounding remainder on the largest share.
  out[largest] = Math.round((out[largest] + 1 - assigned) * 1000) / 1000;
  return out;
}

export function sameMix(
  a: VehicleMix | null | undefined,
  b: VehicleMix | null | undefined,
): boolean {
  if (!a || !b) return (a ?? null) === (b ?? null);
  return VEHICLE_CLASSES.every((c) => Math.abs(a[c.id] - b[c.id]) < 1e-9);
}

/** The preset a mix matches, if any. */
export function mixPresetFor(
  mix: VehicleMix | null | undefined,
): MixPreset | undefined {
  return MIX_PRESETS.find((p) => sameMix(p.mix, mix ?? null));
}

/** True when the mix includes any vehicle other than the reference car. */
export function hasMixedTraffic(mix: VehicleMix | null | undefined): boolean {
  return !!mix && VEHICLE_CLASSES.some((c) => c.id !== "car" && mix[c.id] > 0);
}

/** True when the mix includes vehicles longer than the reference car. */
export function hasLongVehicles(mix: VehicleMix | null | undefined): boolean {
  return !!mix && (mix.bus > 0 || mix.truck > 0);
}

/** "60% car, 20% SUV, …" — classes with a share, largest first. */
export function describeMix(mix: VehicleMix | null | undefined): string {
  if (!mix) return "cars only";
  return VEHICLE_CLASSES.filter((c) => mix[c.id] > 0)
    .sort((a, b) => mix[b.id] - mix[a.id])
    .map(
      (c) => `${String(Math.round(mix[c.id] * 100))}% ${c.label.toLowerCase()}`,
    )
    .join(", ");
}
