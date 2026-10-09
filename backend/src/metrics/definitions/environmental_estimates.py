"""Simplified kinematic fuel and CO2 emission estimates.

IMPORTANT: These are ESTIMATES, not measurements.
============================================================
This module implements a simplified kinematic fuel consumption model to
provide indicative environmental impact figures alongside other simulation
metrics. It is NOT a calibrated or validated model for any specific vehicle
type, engine, or road environment.

Model description
-----------------
Fuel consumption is approximated using a three-term linear model based on
instantaneous speed (v, m/s) and positive acceleration (a, m/s^2):

    fuel_rate (L/s) = a0 + a1 * |v| + a2 * max(a, 0)

where:
    a0 = 0.00060   -- baseline idle consumption (~2.16 L/hour)
    a1 = 0.000045  -- speed-dependent term (~12 L/100 km at 60 km/h cruise)
    a2 = 0.00025   -- acceleration penalty (extra fuel for positive accel)

Deceleration (a < 0) is assumed to incur only the idle rate (engine braking /
fuel cut-off), so the a2 term is clamped to zero for decelerating vehicles.

Assumptions and limitations
-----------------------------
* All vehicles are treated as identical petrol passenger cars with no
  differentiation by vehicle class, weight, or engine type.
* The constants were chosen to produce plausible per-vehicle fuel economy
  figures for a generic petrol car (roughly 8--12 L/100 km at urban speeds);
  they have NOT been validated against real-world measurements or calibrated
  to the simulated vehicles' specific parameters.
* CO2 conversion uses 2.31 kg CO2 per litre of petrol (well-to-exhaust
  emission factor; UK BEIS 2023 / IPCC AR6 range 2.28-2.35 kg/L).
* The model does not account for: engine warming, aerodynamic drag at high
  speeds, road grade, tyre rolling resistance, or hybrid/electric vehicles.
* Results should always be labelled as "Estimated" in any output or report.
  The key ``environmentalMetricsAreEstimates`` is always True in the metrics
  output -- it must never be removed or set to False.

Unit summary
------------
    fuel_rate:    litres per second (L/s)
    fuel_total:   litres (L)
    co2_rate:     kg CO2 per second (kg/s)
    co2_total:    kg CO2 (kg)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Model constants  (see module docstring for units and assumptions)
# ---------------------------------------------------------------------------

# Idle fuel rate (L/s): a vehicle at rest with engine running.
# 0.00060 L/s ≈ 2.16 L/hour, a typical petrol idle figure.
_IDLE_FUEL_RATE: float = 0.00060

# Speed coefficient (L/s per m/s). Tuned so that at 60 km/h (16.67 m/s)
# the speed term alone gives ~0.75 L/s * 3600 = 2.70 L/h, totalling
# ~0.45 + 2.70 + 0 = 3.15 L/h at steady cruise, within the ~8-12 L/100 km
# (3-4.5 L/h at 60 km/h) ballpark for a compact petrol car.
_SPEED_COEFF: float = 0.000045

# Acceleration penalty (L/s per m/s^2). Only applied for positive
# accelerations; represents the additional fuel needed to accelerate.
_ACCEL_COEFF: float = 0.00025

# CO2 conversion: kg of CO2 per litre of petrol (exhaust only).
# Source: UK BEIS 2023 greenhouse gas conversion factors;
# cross-checked against IPCC AR6 Table 7.SM.7 (2.28-2.35 kg/L range).
_CO2_KG_PER_LITRE_PETROL: float = 2.31


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def estimate_fuel_liters_per_vehicle_per_tick(
    speed: float,
    acceleration: float,
    time_step: float,
) -> float:
    """Estimate fuel consumed by a single vehicle during one simulation tick.

    Args:
        speed:        Vehicle speed at this tick, in m/s. Clamped to >= 0.
        acceleration: Vehicle acceleration at this tick, in m/s^2. Negative
                      values (braking) contribute only the idle term.
        time_step:    Simulated tick duration in seconds (e.g. 0.1 for a
                      10 Hz simulation).

    Returns:
        Estimated fuel consumed in litres (L) during this tick.
        Always >= 0. Returns 0.0 when time_step <= 0.
    """
    if time_step <= 0.0:
        return 0.0
    v = max(0.0, speed)
    a_pos = max(0.0, acceleration)  # braking = no extra fuel above idle
    fuel_rate = _IDLE_FUEL_RATE + _SPEED_COEFF * v + _ACCEL_COEFF * a_pos
    return fuel_rate * time_step


def estimate_co2_kg(fuel_liters: float) -> float:
    """Convert fuel volume (litres) to estimated CO2 mass (kg).

    Uses the petrol CO2 conversion factor (see module docstring).

    Args:
        fuel_liters: Estimated fuel consumed in litres. Clamped to >= 0.

    Returns:
        Estimated CO2 emitted in kg.
    """
    return max(0.0, fuel_liters) * _CO2_KG_PER_LITRE_PETROL
