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
  const queueCapArms = metering.arms
    .filter((a) => a.reason === "queue_cap")
    .map((a) => SHORT[a.direction]);
  if (queueCapArms.length > 0) {
    return `Queue cap active: red ended early on ${queueCapArms.join(", ")} due to standing approach queue.`;
  }
  if (metering.color === "yellow") {
    return "Yellow change interval: clearing approaching vehicles.";
  }
  if (metering.color === "red") {
    return "All-red clearance interval: waiting for circulating gaps.";
  }
  return "Phase running on scheduled green.";
}
