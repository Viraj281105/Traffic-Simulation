# Traffic Simulation Code Review Prep: Phase 5
## Intersection & Roundabout Controllers

This guide explains how intersection traffic controllers coordinate movement, control signals, and calculate yield conditions.

---

## 1. Fixed-Time Signal Controller ([`FixedTimeSignalController`](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/backend/src/controllers/fixed_time_signal.py))

The signal controller runs a cyclic schedule. It alternates green phases for each direction to prevent crossing traffic conflicts.

### A. Cycle Phase Structure (Per Direction)
For each approach direction (North -> South -> East -> West), the cycle contains:
1. **Straight + Right Green**: Straight and Right-turn lanes proceed.
2. **Left-Turn Protected Green**: Dedicated phase for left-turning vehicles since they must cross oncoming traffic.
3. **Yellow Transition**: Warns vehicles that the phase is ending.
4. **All-Red Clearance**: All directions are red, allowing cars inside the intersection box to clear.

```
Cycle Phase Timeline (N -> S -> E -> W):
┌──────────────────────────┬───────────────────────┬────────────┬─────────┐
│ 1. Straight/Right Green  │ 2. Left-Protect Green │ 3. Yellow  │ 4. Red  │
│         (25s)            │         (10s)         │    (4s)    │  (2s)   │
└──────────────────────────┴───────────────────────┴────────────┴─────────┘
```

### B. Lane Tagging by Turn Intent
Depending on the number of lanes on the incoming approach, lanes are mapped as follows:
* **1 Lane**: All turn intents share the single lane.
* **2 Lanes**: Lane 0 (leftmost) is reserved for Left turns. Lane 1 is for Straight and Right turns.
* **3+ Lanes**: Lane 0 is Left turns; Middle lanes are Straight; Outermost (rightmost) lane is Right turns.

### C. Stopping Mechanism: Virtual Obstacles
* Instead of overriding vehicle speed directly, when a signal changes to Red or Yellow, the controller registers a [`VirtualObstacle`](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/backend/src/controllers/fixed_time_signal.py) at the end of the incoming lane (position = `lane.length`).
* The [`VirtualObstacle`](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/backend/src/controllers/fixed_time_signal.py) mimics a stationary vehicle (speed = `0.0 m/s`, length = `0.0 m`).
* The IDM physics model detects this obstacle as the leader vehicle and decelerates the approaching vehicle naturally to a stop at the stop line.

---

## 2. Roundabout Yield Controller ([`RoundaboutController`](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/backend/src/controllers/roundabout.py))

Unsignalized roundabouts rely on **priority-to-circulating-traffic** yield logic.

### A. Entry Merge Yielding Rules
Approaching vehicles on an incoming lane must yield to circulating vehicles inside the roundabout ring:
1. Identify all vehicles on circulating lanes (lanes with prefix `conn_`).
2. Map the coordinate positions of the approaching lane's merge point (at `lane.end_coords`).
3. Compute the angular coordinate ($\theta_{\text{entry}}$) of this entry point:
   $$\theta_{\text{entry}} = \arctan2(y_{\text{entry}}, x_{\text{entry}})$$
4. Check if any circulating vehicle is approaching the merge point within a safe gap threshold:
   $$\text{threshold} = \max(15.0, T_{\text{critical}} \cdot v_{\text{circulating}})$$
   Where $T_{\text{critical}}$ is the configured `criticalGap` (default `2.5 s`).

```
Roundabout Yield Check:
                        Entering Vehicle (Incoming Lane)
                                   │
                                   ▼
                            Yield Line
                      ┌────────────────────┐
                      │    Circular Ring   │
                      │ ◄── [Circulating]  │  ◄── Yield if within criticalGap (2.5s)
                      └────────────────────┘
```

---

## 3. Senior Reviewer Questions & Defense

### Q1: "Why do you use a `VirtualObstacle` model instead of setting vehicle speed to 0 directly?"
* **Defense**:
  * **Physical Realism**: Forcing a vehicle's speed to 0 directly creates an infinite deceleration spike ($a \to -\infty$), which is physically impossible and causes jittering/teleportation artifacts in the visual playback.
  * **Model Uniformity**: By mapping signal states to a zero-speed virtual leader, the vehicle continues to run the *same* IDM physics equation. This maintains acceleration continuity and simplifies our update loop.

### Q2: "How does the All-Red phase prevent gridlock inside the intersection box?"
* **Defense**:
  * When a green phase ends, vehicles traveling at speed need time to exit the intersection box. The yellow phase slows approaching vehicles, and the **All-Red Clearance** phase (typically `2s`) ensures that vehicles already inside the intersection box can safely complete their turns and clear the intersection before the perpendicular flow starts.
