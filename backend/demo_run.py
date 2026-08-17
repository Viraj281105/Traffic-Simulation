import os
import sys
import time

# Reconfigure stdout to use UTF-8 to support emojis and arrows on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add the backend src directory to path to allow correct imports
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
sys.path.append(os.path.dirname(__file__))

from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import Direction


def draw_cli_dashboard(elapsed, active_vehicles, exited_vehicles, signals_state, phase_name, remaining, logs):
    """Renders a complete, high-fidelity ASCII dashboard in the terminal."""
    ROWS = 21  # noqa: N806
    COLS = 61  # noqa: N806
    boundary = 7.0  # 2 lanes * 3.5m

    # Initialize empty grid
    grid = [[" " for _ in range(COLS)] for _ in range(ROWS)]

    # Draw roads
    for r in range(ROWS):
        for c in range(COLS):
            # Map grid index to coordinates (x, y)
            x = (c - 30) * 4.0
            y = (10 - r) * 10.0

            is_vert_road = (abs(x) <= boundary)
            is_horiz_road = (abs(y) <= boundary)

            if is_vert_road and is_horiz_road:
                grid[r][c] = " "
            elif is_vert_road:
                if abs(x) <= 0.5:
                    grid[r][c] = ":"  # lane divider
                elif abs(abs(x) - boundary) <= 1.0:
                    grid[r][c] = "|"  # border
                else:
                    grid[r][c] = "."
            elif is_horiz_road:
                if abs(y) <= 0.5:
                    grid[r][c] = "="  # lane divider
                elif abs(abs(y) - boundary) <= 1.0:
                    grid[r][c] = "-"  # border
                else:
                    grid[r][c] = "."

    # Put signal indicators at entry lines
    ns_sig = signals_state.get(Direction.NORTH, "red").upper()
    ew_sig = signals_state.get(Direction.EAST, "red").upper()

    ns_color = "\033[92m" if ns_sig == "GREEN" else "\033[93m" if ns_sig == "YELLOW" else "\033[91m"
    ew_color = "\033[92m" if ew_sig == "GREEN" else "\033[93m" if ew_sig == "YELLOW" else "\033[91m"
    reset = "\033[0m"

    # North entry stop-line: x=-3.5 (left lane), y=boundary
    # South entry stop-line: x=3.5 (right lane), y=-boundary
    # East entry stop-line: x=boundary, y=3.5
    # West entry stop-line: x=-boundary, y=-3.5
    grid[8][29] = f"{ns_color}🚦{reset}"
    grid[12][31] = f"{ns_color}🚦{reset}"
    grid[10][32] = f"{ew_color}🚦{reset}"
    grid[10][28] = f"{ew_color}🚦{reset}"

    # Place vehicles on the grid
    for v in active_vehicles:
        if v.lane is None:
            continue
        cx, cy = v.coords

        # Map to grid
        c = 30 + int(cx / 4.0)
        r = 10 - int(cy / 10.0)

        if 0 <= r < ROWS and 0 <= c < COLS:
            # Determine direction arrow based on heading (0=Up, 90=Right, 180=Down, 270=Left)
            # Map heading degrees to arrow
            h = v.heading % 360
            if 45 <= h < 135:
                arrow = "▶"
            elif 135 <= h < 225:
                arrow = "▼"
            elif 225 <= h < 315:
                arrow = "◀"
            else:
                arrow = "▲"

            # Color vehicle by speed/state
            if v.speed < 0.1:
                v_color = "\033[91m"  # Stopped (Red)
            elif v.speed < 5.0:
                v_color = "\033[93m"  # Slow/Yielding (Yellow)
            else:
                v_color = "\033[92m"  # Moving (Green)

            grid[r][c] = f"{v_color}{arrow}{reset}"

    # Generate visual string
    out = []
    out.append("\033[H")  # Move cursor to top-left to avoid flicker
    out.append("=" * 80)
    out.append(" 🚦 \033[1mTRAFFIC COMPARISON FRAMEWORK (BACKEND ENGINE DEMO)\033[0m 🚦")
    out.append("=" * 80)
    out.append(f" Time: {elapsed:5.1f}s | Active: {len(active_vehicles):2d} | Exited: {len(exited_vehicles):2d}")
    out.append(f" Phase: {phase_name:<12} | Time Left: {remaining:.1f}s")
    out.append("-" * 80)

    # Add the grid with border
    for r in range(ROWS):
        row_str = "".join(grid[r])
        out.append(f"  {row_str}")

    out.append("-" * 80)
    out.append(" \033[1mRECENT SIMULATION EVENTS:\033[0m")
    for log in logs[-5:]:
        out.append(f"  {log}")
    # fill up empty logs space
    for _ in range(5 - len(logs[-5:])):
        out.append("")
    out.append("=" * 80)

    # Compute stats
    if exited_vehicles:
        avg_wait = sum(v.wait_time for v in exited_vehicles) / len(exited_vehicles)
        avg_stops = sum(v.stop_count for v in exited_vehicles) / len(exited_vehicles)
        out.append(f" Average Delay (Wait): {avg_wait:4.2f}s | Average Stop Count: {avg_stops:4.2f} stops")
    else:
        out.append(" Average Delay (Wait): N/A   | Average Stop Count: N/A")
    out.append("=" * 80)

    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def run_demo(intersection_type: str = "fixed_time_signal"):
    config = {
        "simulation": {
            "duration": 60,
            "timeStep": 0.1,
            "warmupTime": 5,
            "randomSeed": 42
        },
        "traffic": {
            "totalVehicles": 60,
            "arrivalRate": 1.5,
            "arrivalDistribution": "poisson",
            "directionalSplit": {"north": 0.25, "south": 0.25, "east": 0.25, "west": 0.25},
            "turnProbabilities": {"left": 0.2, "straight": 0.6, "right": 0.2}
        },
        "geometry": {
            "intersectionType": intersection_type,
            "intersectionCenter": {"x": 0.0, "y": 0.0}
        },
        "roads": {
            "approachLength": 150.0,
            "laneWidth": 3.5,
            "lanesPerApproach": 2,
            "speedLimit": 13.89
        },
        "vehicleGeneration": {
            "vehicleLength": {"min": 4.0, "max": 5.0},
            "vehicleWidth": {"min": 1.8, "max": 2.2},
            "desiredSpeed": {"min": 11.0, "max": 15.0},
            "maxAcceleration": 2.0,
            "comfortDeceleration": 3.0,
            "desiredTimeHeadway": 1.5,
            "minimumGap": 2.0,
            "idmDelta": 4.0
        }
    }

    clock = Clock(time_step=config["simulation"]["timeStep"])
    engine = SimulationEngine(clock, duration=config["simulation"]["duration"], config=config)

    if intersection_type == "fixed_time_signal":
        controller = FixedTimeSignalController(config, engine.network)
    else:
        controller = RoundaboutController(config, engine.network)

    dt = clock.time_step
    sim_duration = config["simulation"]["duration"]
    total_steps = int(sim_duration / dt)

    # Setup terminal screen
    os.system('cls' if os.name == 'nt' else 'clear')

    logs = ["Simulation initialized. Spawner and IDM ready."]
    spawned_ids = set()
    exited_ids = set()

    for step in range(1, total_steps + 1):
        elapsed = step * dt

        # Update controller
        controller.update(dt, engine.pool.active_vehicles)

        # Get signals state
        signals_state = {}
        state = controller.get_state()
        if state["type"] == "fixed_time_signal":
            for sig in state.get("signals", []):
                dir_enum = getattr(Direction, sig["direction"].upper())
                signals_state[dir_enum] = sig["color"]
            phase_name = state["currentPhase"]
            phase_remaining = state["phaseTimeRemaining"]
        else:
            for d in Direction:
                signals_state[d] = "green"
            phase_name = "circulating (roundabout)"
            phase_remaining = 0.0

        # Step the engine
        engine.step()

        # Check spawns
        active_ids = set(v.vehicle_id for v in engine.pool.active_vehicles)
        new_spawns = active_ids - spawned_ids
        for vid in new_spawns:
            spawned_ids.add(vid)
            v = next((x for x in engine.pool.active_vehicles if x.vehicle_id == vid), None)
            if v and v.route:
                start_dir = v.route[0].lane_id.split("_")[0].upper()
                end_dir = v.route[-1].lane_id.split("_")[0].upper()
                logs.append(f"🆕 Vehicle \033[94m{vid}\033[0m entered from {start_dir} heading to {end_dir}")

        # Check exits
        all_exited = set(v.vehicle_id for v in engine.pool.exited_vehicles)
        new_exits = all_exited - exited_ids
        for vid in new_exits:
            exited_ids.add(vid)
            v = next((x for x in engine.pool.exited_vehicles if x.vehicle_id == vid), None)
            if v:
                logs.append(f"✅ Vehicle \033[92m{vid}\033[0m exited. Delay: {v.wait_time:.1f}s, Stops: {v.stop_count}")

        # Draw frame at 10Hz simulation rate (every step is 0.1s, so draw every tick!)
        # We add a small sleep to simulate running at 1x real-time speed
        draw_cli_dashboard(
            elapsed, 
            engine.pool.active_vehicles, 
            engine.pool.exited_vehicles, 
            signals_state, 
            phase_name, 
            phase_remaining, 
            logs
        )
        time.sleep(0.04)  # ~2.5x real time speed for presentation snappy feeling

    # Pause at the end to let them read the final stats
    input("\nSimulation complete. Press Enter to exit demo...")


if __name__ == "__main__":
    mode = "fixed_time_signal"
    if len(sys.argv) > 1:
        if sys.argv[1] in ("signal", "fixed_time_signal"):
            mode = "fixed_time_signal"
        elif sys.argv[1] in ("roundabout", "yield"):
            mode = "roundabout"
    run_demo(mode)
