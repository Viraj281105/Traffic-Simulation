# Traffic Simulation Code Review Prep: Phase 4
## Vehicles: Spawning, Dynamics, & Physics

This guide details vehicle generation, physical kinematics using the Intelligent Driver Model (IDM), lane transitions, collision detection, and lane-changing behavior.

---

## 1. Vehicle Spawning Lifecycle

Vehicles are managed by the [`VehicleSpawner`](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/backend/src/vehicles/spawner.py).
1. **Spawn Decision**: At each step, a Poisson-like generator checks the arrival probability $P(\text{spawn}) = 1 - e^{-\lambda \cdot dt}$ where $\lambda$ is the configured arrival rate.
2. **Path Setup**: 
   * A vehicle is assigned a random incoming direction (e.g. `Direction.NORTH`) and a target outgoing direction.
   * Based on this, a `TurnIntent` is computed (Straight, Left, Right).
   * A full route (Incoming Lane -> Connection Lane -> Outgoing Lane) is resolved.
3. **Safety Check**: A vehicle is only spawned if there is a safe headway gap on the target entry lane (i.e. distance to the last spawned vehicle is greater than the safety limit).

---

## 2. Longitudinal Driver Physics: The Intelligent Driver Model (IDM)

The [`IntelligentDriverModel`](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/backend/src/vehicles/idm.py) calculates the acceleration $a$ for each vehicle.

### The IDM Equation
The acceleration formula is split into two components: **Free-road acceleration** and **Interaction deceleration**.

$$a = a_{\text{max}} \left[ 1 - \left( \frac{v}{v_0} \right)^\delta - \left( \frac{s^*(v, \Delta v)}{gap} \right)^2 \right]$$

* **Free-road Acceleration**: $a_{\text{free}} = a_{\text{max}} \left[ 1 - \left( \frac{v}{v_0} \right)^\delta \right]$
  * If the road is empty, the vehicle accelerates toward its desired speed $v_0$.
  * The exponent $\delta$ (typically $4$) controls how rapidly acceleration drops off as the vehicle approaches $v_0$.
* **Interaction Deceleration**: $a_{\text{interaction}} = -a_{\text{max}} \left( \frac{s^*}{gap} \right)^2$
  * Evaluated if a leading vehicle (or stop line) is detected at a distance $gap$.
  * The dynamic desired gap $s^*$ is calculated as:
    $$s^*(v, \Delta v) = s_0 + v \cdot T + \frac{v \cdot \Delta v}{2 \sqrt{a_{\text{max}} \cdot b_{\text{comfort}}}}$$

### IDM Parameters Table
| Parameter | Symbol | Code Variable | Default | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| Max Acceleration | $a_{\text{max}}$ | `_max_acceleration` | $2.0 \text{ m/s}^2$ | Acceleration on empty road |
| Comfort Deceleration | $b_{\text{comfort}}$ | `_comfort_deceleration` | $3.0 \text{ m/s}^2$ | Braking limit during normal following |
| Minimum Standstill Gap | $s_0$ | `_minimum_gap` | $2.0 \text{ m}$ | Distance kept from the leader when stopped |
| Desired Headway | $T$ | `_desired_time_headway` | $1.5 \text{ s}$ | Target safety time gap to leader |
| Acceleration Exponent | $\delta$ | `_idm_delta` | $4.0$ | Controls acceleration scaling |

### Special Edge Cases in IDM
* **`lead_speed` or `gap` is None**: Acceleration equals $a_{\text{free}}$.
* **`gap <= 0.0` (Collision/Overshoot)**: Instantly returns `-max_deceleration` (clamped to `-9.0 m/s^2`) to simulate emergency braking.

---

## 3. Position Updates & Route Progression

Inside `vehicle.update_state(acceleration, dt)`:
1. **Speed Update**: $v_{t+1} = \max(0.0, v_t + a \cdot dt)$. Speed cannot go negative.
2. **Displacement Calculation**: $d = v_{t+1} \cdot dt$.
3. **Lane Transition**:
   * If the vehicle's position plus $d$ is less than the current lane length: `position += d`.
   * If `position + d >= lane.length`, the vehicle transitions to the next lane in `self.route`:
     * It subtracts the remaining length of the old lane: `position = (position + d) - lane.length`.
     * The old lane deregisters the vehicle; the new lane registers it.
     * If there is no next lane (end of route), its state transitions to `VehicleState.EXITED`.

---

## 4. Bounding Box & Collision Detection (SAT)

For safety audit reporting, vehicles are treated as Oriented Bounding Boxes (OBBs).

### A. OBB Vertex Coordinates Calculation
Given a vehicle center $(X_c, Y_c)$, length $L$, width $W$, and heading $\theta$ (converted to radians $\phi$):
$$\text{direction\_vector} = (\sin\phi, \cos\phi)$$
$$\text{normal\_vector} = (-\cos\phi, \sin\phi)$$

The four vertices are computed by offsetting along these vectors:
$$\text{Vertex} = (X_c, Y_c) \pm \frac{L}{2} \cdot \text{direction\_vector} \pm \frac{W}{2} \cdot \text{normal\_vector}$$

### B. Separating Axis Theorem (SAT) math
To check if two bounding boxes overlap:
1. For each box, construct projection axes perpendicular to their four edges (2 unique axes per box, 4 axes total).
2. Project all vertices of both boxes onto each axis.
3. If there is **any** axis where the projected min/max intervals do not overlap, then the boxes do not overlap (a separating axis exists).
4. If the projections overlap on **all** axes, a collision is flagged.

---

## 5. Senior Reviewer Questions & Defense

### Q1: "Why do you use IDM instead of simpler linear deceleration/acceleration formulas?"
* **Defense**:
  * **Driver Realism**: IDM is a mathematically validated microscopic car-following model. It transitions smoothly from free-road cruising to stable car-following and emergency braking.
  * **Crash Prevention**: Simple linear models fail to account for closing speed differences ($\Delta v$) dynamically, causing artificial rear-end crashes when leader vehicles decelerate suddenly.

### Q2: "What is the MOBIL lane changing utility constraint?"
* **Defense**:
  * We enforce safety rules during lane changes: the deceleration of the *new* follower on the target lane must not exceed a safety threshold (e.g. $2.0 \text{ m/s}^2$).
  * This prevents vehicles from cutting off others and causing secondary pile-ups.
