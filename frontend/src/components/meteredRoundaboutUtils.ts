import type {
  MeteringControllerState,
  SignalDirection,
} from "../types/simulation";

export const ORDER: SignalDirection[] = ["north", "south", "east", "west"];

export const SHORT: Record<SignalDirection, string> = {
  north: "N",
  south: "S",
  east: "E",
  west: "W",
};

/**
 * The queue cap is not an arm state: the controller records it as an event and then
 * walks the ordinary yellow / all-red clearance, so no arm ever reports
 * `reason: "queue_cap"`. It is the cause of the current clearance when a queue_cap
 * event is at least as recent as the last arm opening (a cap can only fire during a
 * green) and the phase is no longer green. Returns the arms whose queue triggered it.
 */
function queueCapArmsEndingCurrentGreen(
  metering: MeteringControllerState,
): string[] {
  if (metering.color === "green") return [];
  const events = metering.recentDecisions ?? [];
  let lastOpen = -Infinity;
  for (const e of events) {
    if (e.state === "open" && typeof e.time === "number") {
      lastOpen = Math.max(lastOpen, e.time);
    }
  }
  const arms: string[] = [];
  for (const e of events) {
    if (
      e.reason === "queue_cap" &&
      typeof e.time === "number" &&
      e.time >= lastOpen &&
      typeof e.arm === "string" &&
      e.arm in SHORT
    ) {
      const label = SHORT[e.arm as SignalDirection];
      if (!arms.includes(label)) arms.push(label);
    }
  }
  return arms;
}

/**
 * Returns plain-language explanation for why an arm or phase is held (SR-28).
 */
export function meteringHoldReasonText(
  metering: MeteringControllerState,
): string {
  const spillbackArms = metering.arms
    .filter((a) => a.reason === "ring_spillback_hold")
    .map((a) => SHORT[a.direction]);
  if (spillbackArms.length > 0) {
    return `Spillback guard active: holding red on ${spillbackArms.join(", ")} to prevent circulating ring obstruction.`;
  }
  const queueCapArms = queueCapArmsEndingCurrentGreen(metering);
  if (queueCapArms.length > 0) {
    return `Queue cap: green ended early because the standing queue on ${queueCapArms.join(", ")} reached its limit.`;
  }
  if (metering.color === "yellow") {
    return "Yellow change interval: clearing approaching vehicles.";
  }
  if (metering.color === "red") {
    return "All-red clearance interval: waiting for circulating gaps.";
  }
  return "Phase running on scheduled green.";
}
