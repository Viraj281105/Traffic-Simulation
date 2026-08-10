# Project Future Scope (Deferred Features)

This document outlines the deferred features, enhancements, and research dimensions for the Traffic Simulation Project. These items are deliberately excluded from the core 2-month timeline to prioritize stability, accuracy, and comparison integrity.

---

## 1. Advanced Intersection Control Strategies
### A. Hybrid/Actuated Signal Control (3rd Comparison Column)
- **Concept**: Implement a semi-actuated or fully-actuated signal controller that adjusts phase lengths dynamically based on real-time vehicle queue lengths or loop-detector arrivals (e.g., using NEMA standard controller logic or simple threshold queue clearing).
- **Compelling Value**: Compares roundabouts not just against a rigid, inefficient clock (fixed-time) but against a modern signal that "reacts" to traffic.
- **De-prioritization Reason**: Adding a third controller introduces a substantial design and verification burden. The core two-way (Fixed vs. Roundabout) study must be mathematically solid first.

### B. Adaptive Roundabout Entry Controls (Metered Roundabouts)
- **Concept**: Implement roundabout metering signals on approaches with heavy circulating conflicts. The meter temporarily stops entry from one approach when circulating flow exceeds a safety threshold.
- **Compelling Value**: Restores capacity balance in highly asymmetric traffic conditions where one approach is starved.
- **De-prioritization Reason**: Adds complex control variables that require localized calibrations.

---

## 2. Natural-Language Configuration Interface (NL Input)
- **Concept**: Allow users to configure simulation parameters using natural language prompts (e.g., *"Set up a heavy morning rush hour from the North leg with a 3-lane roundabout"*).
- **Compelling Value**: Lowers the barrier to entry for non-technical users or managers who want to explore scenarios.
- **De-prioritization Reason**: This is a pure usability wrapper. The primary exploration requirement is fully satisfied by GUI sliders and configuration text inputs.

---

## 3. High-Fidelity Environmental & Vehicle Physics
### A. Multi-Modal Traffic Conflicts (Pedestrians, Cyclists, Buses)
- **Concept**: Introduce crosswalks, pedestrian signals, and dedicated bike lanes. Pedestrians would cross approaches dynamically, interrupting both vehicle streams and signal phases.
- **Compelling Value**: Reflects urban settings more accurately.
- **De-prioritization Reason**: High complexity. Multi-agent path conflicts complicate metrics calculations without altering the core motor-vehicle comparison.

### B. Microscopic Driver Behavior Models (Driver Psychology)
- **Concept**: Parameterize driver behavior variables like aggressiveness (smaller critical gaps/headways), inattentiveness (reaction delay times), and lane-changing behavior (mobil/minim models).
- **Compelling Value**: Evaluates how human factors alter intersection capacity.
- **De-prioritization Reason**: High variance makes findings hard to reproduce and complicates comparative validation.

---

## 4. Environmental & Safety Metrics
### A. Emissions & Fuel Consumption Modeling
- **Concept**: Integrate mathematical models (like the VT-Micro model or COPERT model) estimating instantaneous fuel consumption and exhaust ($CO_2, NO_x, PM_{10}$) based on vehicle speed and acceleration.
- **Compelling Value**: Signals generally cause more stop-and-go (accelerating from standstill consumes the most fuel), so roundabouts usually win on emissions. Quantifying this would expand the study's scope.
- **De-prioritization Reason**: Requires research-grade validation and calibration data.

### B. Conflict-Point Safety Counts (Surrogate Safety Measures)
- **Concept**: Track surrogate safety measures like Time-To-Collision (TTC) and Post-Encroachment Time (PET) between conflicting movements to count potential near-misses.
- **Compelling Value**: Complements efficiency metrics with quantitative safety comparisons.
- **De-prioritization Reason**: Incurs massive geometric collision checking overhead.

---

## 5. Stress Testing & Multi-Intersection Corridors
### A. Asymmetric Demand & Peak Hours
- **Concept**: Stress test both controllers under heavily unbalanced flows (e.g., 90% traffic going North-to-South, 10% East-to-West).
- **Compelling Value**: Reveals boundary conditions where fixed signal timing outperforms roundabouts (due to roundabout locking).
- **De-prioritization Reason**: Light-to-heavy symmetrical sweeps are sufficient to establish the primary comparisons.

### B. Multi-Intersection Corridor Optimization
- **Concept**: Link multiple intersections in a grid or line, enabling green-wave synchronization (coordination) for the signals and corridor travel times.
- **Compelling Value**: High-value study for city planners.
- **De-prioritization Reason**: Changes the problem definition entirely from an isolated intersection to a networks problem.
