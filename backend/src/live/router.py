"""``/api/simulation/*`` and ``/ws/simulation/*``: the live dashboard.

Every route resolves the caller's live session (``live/sessions.py``) and
drives its single live simulation or its signal-vs-roundabout comparison.
The single-vehicle routes are the Sprint 2 polling mode kept for
compatibility.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.api.origins import close_after_stream_error, refuse_foreign_origin
from src.api.security import require_api_key
from src.core.enums import SimulationStatus
from src.live.dashboard_config import (
    VALID_INTERSECTION_TYPES,
    compile_dashboard_config,
    generate_random_seed,
)
from src.live.sessions import (
    DEFAULT_SESSION_KEY,
    LIVE_SESSION_COOKIE,
    current_session,
    get_or_create_dual_orchestrator,
    get_or_create_live_simulation,
    get_or_create_session,
    live_session_var,
    reseed_unless_user_pinned,
)
from src.live.single_vehicle import single_veh

logger = logging.getLogger(__name__)

router = APIRouter()


class SpeedRequest(BaseModel):
    # The engines' run loops divide the tick period by this value. Zero used
    # to raise ZeroDivisionError in the background thread, killing it while
    # the engine still reported RUNNING (so its session was never reclaimed);
    # a negative value silently meant "flat out". Bounded like timeScale
    # (SimulationSection, le=10); the dashboard offers 1x, 2x and 4x.
    multiplier: float = Field(gt=0, le=10.0)


# ── Single-vehicle endpoints (Sprint 2/3 compatibility) ─────────────────────
@router.get("/api/simulation/status")
def get_simulation_status() -> Dict[str, Any]:
    return {
        "status": single_veh.status,
        "sim_time": round(single_veh.sim_time, 2),
        "tick": single_veh.tick,
        "vehicle_state": single_veh.state,
        "message": "Ready" if single_veh.status == "stopped" else "Running",
    }


@router.post("/api/simulation/start", dependencies=[Depends(require_api_key)])
def start_simulation() -> Dict[str, Any]:
    single_veh.status = "running"
    return {"status": "running", "message": "Simulation started"}


@router.post("/api/simulation/stop", dependencies=[Depends(require_api_key)])
def stop_simulation() -> Dict[str, Any]:
    single_veh.status = "stopped"
    sim = get_or_create_live_simulation()
    engine = sim.get("engine")
    if engine is not None:
        try:
            engine.stop()
        except Exception as e:
            logger.error(f"Error stopping live engine: {e}")
    return {"status": "stopped", "message": "Simulation stopped"}


@router.post("/api/simulation/reset", dependencies=[Depends(require_api_key)])
def reset_simulation() -> Dict[str, Any]:
    single_veh.reset()
    return {"status": "stopped", "message": "Simulation reset"}


@router.get("/api/simulation/single-vehicle")
def get_single_vehicle() -> Dict[str, Any]:
    if single_veh.status == "running":
        # Advance vehicle state
        dt = 0.1
        single_veh.tick += 1
        single_veh.sim_time += dt
        single_veh.position += single_veh.speed * dt
        single_veh.x += single_veh.speed * dt

        # Wrap around route for visual testing
        if single_veh.position > 300.0:
            single_veh.position = 0.0
            single_veh.x = -150.0

    return {
        "vehicle_id": single_veh.vehicle_id,
        "position": round(single_veh.position, 2),
        "speed": round(single_veh.speed, 2),
        "acceleration": round(single_veh.acceleration, 2),
        "x": round(single_veh.x, 2),
        "y": round(single_veh.y, 2),
        "heading": round(single_veh.heading, 1),
        "state": single_veh.state,
        "lane_id": single_veh.lane_id,
        "wait_time": round(single_veh.wait_time, 2),
        "stop_count": single_veh.stop_count,
        "sim_time": round(single_veh.sim_time, 2),
        "tick": single_veh.tick,
        "simulation_status": single_veh.status,
    }


@router.get("/api/simulation/active-vehicles")
def get_active_vehicles() -> list[dict[str, Any]]:
    sim = get_or_create_live_simulation()
    builder = sim["builder"]
    snapshot = builder.build()
    return [v for v in snapshot["vehicles"] if v["state"] != "exited"]


# ── Live simulation ─────────────────────────────────────────────────────────
@router.post("/api/simulation/config", dependencies=[Depends(require_api_key)])
def update_simulation_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Unlike /api/v1/simulations and /api/simulation/new, this endpoint
    # builds its config dict directly from the raw payload without ever
    # running it through CONFIG_SCHEMA or a Pydantic model. An unrecognized
    # intersectionType previously passed through silently: the controller
    # dict is shaped by `== "fixed_time_signal"` (so any other value,
    # typo or not, gets the roundabout-shaped controller dict), while
    # create_controller() separately checks `== "roundabout"` (so anything
    # else, including that same typo, builds a FixedTimeSignalController) —
    # the two checks disagree for any value that is neither, so a typo
    # silently ignored the user's submitted signal-timing parameters
    # instead of failing. Reject it up front instead, consistent with how
    # the versioned creation endpoints already validate this field.
    intersection_type = payload.get("intersectionType")
    if (
        intersection_type is not None
        and intersection_type not in VALID_INTERSECTION_TYPES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid intersectionType '{intersection_type}'. "
                f"Must be one of: {', '.join(VALID_INTERSECTION_TYPES)}."
            ),
        )

    session = current_session()

    # Determine randomSeed (preserve user-provided seed explicitly). A
    # scenario document (V1.4) always carries its own seed.
    raw_seed = payload.get("randomSeed")
    scenario_doc = payload.get("scenario")
    if isinstance(scenario_doc, dict):
        raw_seed = (scenario_doc.get("simulation") or {}).get("seed", 42)
    if raw_seed is not None and str(raw_seed).strip() != "":
        try:
            seed_val = int(raw_seed)
            session.is_user_defined_seed = True
        except (ValueError, TypeError):
            seed_val = generate_random_seed()
            session.is_user_defined_seed = False
    else:
        seed_val = generate_random_seed()
        session.is_user_defined_seed = False

    # Leave the session on its previous (valid) config — and its runs
    # untouched — if this one is rejected: the compile raises before
    # anything is assigned.
    new_config = compile_dashboard_config(payload, seed_val)
    if session.current_live_config == new_config:
        return {
            "status": "ok",
            "message": "Simulation configuration unchanged",
            "randomSeed": seed_val,
        }
    session.current_live_config = new_config

    # Only now tear down the old runs. The dual stream recreates a missing
    # orchestrator from current_live_config on its next frame (see
    # websocket_dual_stream), so clearing it while the old config was still
    # in place let the stream rebuild the previous scenario, and the next
    # Play ran that instead of the one just configured.
    if session.live_sim_data["engine"] is not None:
        try:
            session.live_sim_data["engine"].stop()
        except Exception:
            pass
        session.live_sim_data["engine"] = None

    if session.dual_sim_orchestrator is not None:
        try:
            session.dual_sim_orchestrator.stop()
        except Exception:
            pass
        session.dual_sim_orchestrator = None

    # Reset live simulation cache
    session.live_sim_data["engine"] = None
    session.live_sim_data["collector"] = None
    session.live_sim_data["controller"] = None
    session.live_sim_data["builder"] = None
    session.live_sim_data["config_id"] = None

    # Pre-create the simulation with new configuration parameters
    get_or_create_live_simulation()

    return {
        "status": "ok",
        "message": "Simulation configuration updated successfully",
        "randomSeed": seed_val,
    }


@router.post("/api/simulation/play", dependencies=[Depends(require_api_key)])
def play_live_simulation() -> Dict[str, Any]:
    session = current_session()
    sim = get_or_create_live_simulation()
    engine = sim["engine"]
    if engine.status == SimulationStatus.COMPLETED:
        # Re-randomize seed for the new run only if not explicitly user-defined
        reseed_unless_user_pinned(session)
        session.live_sim_data["engine"] = None
        sim = get_or_create_live_simulation()
        engine = sim["engine"]
        engine.start()
    elif engine.status == SimulationStatus.INITIALIZED:
        engine.start()
    elif engine.status == SimulationStatus.PAUSED:
        engine.resume()
    return {
        "status": sim["engine"].status.value.lower(),
        "message": "Live simulation started/resumed",
        "randomSeed": session.current_live_config["simulation"].get("randomSeed"),
    }


@router.post("/api/simulation/pause", dependencies=[Depends(require_api_key)])
def pause_live_simulation() -> Dict[str, Any]:
    sim = get_or_create_live_simulation()
    sim["engine"].pause()
    return {
        "status": sim["engine"].status.value.lower(),
        "message": "Live simulation paused",
    }


@router.post("/api/simulation/speed", dependencies=[Depends(require_api_key)])
def set_live_simulation_speed(req: SpeedRequest) -> Dict[str, Any]:
    sim = get_or_create_live_simulation()
    sim["engine"].speed_multiplier = req.multiplier
    return {"message": f"Speed set to {req.multiplier}x"}


def frame_changed(
    frame: tuple[Any, ...], last_frame: Optional[tuple[Any, ...]]
) -> bool:
    """Whether a live stream has something new to show: a different engine
    (replaced by a config change or reset), a new status, or simulated time
    that moved on. A paused, finished or idle simulation otherwise had an
    identical snapshot rebuilt and resent ten times a second per viewer; it
    now gets the one-per-second heartbeat only. The engine is compared by
    identity, and held, so a new one can never be mistaken for the old."""
    return (
        last_frame is None
        or frame[0] is not last_frame[0]
        or frame[1:] != last_frame[1:]
    )


@router.websocket("/ws/simulation/live")
async def websocket_live_stream(websocket: WebSocket) -> None:
    if await refuse_foreign_origin(websocket):
        return
    await websocket.accept()
    session_key = websocket.cookies.get(LIVE_SESSION_COOKIE) or DEFAULT_SESSION_KEY
    token = live_session_var.set(get_or_create_session(session_key))
    last_frame: Optional[tuple[Any, ...]] = None
    last_sent_time = 0.0

    try:
        while True:
            # An open stream is proof the client is still there, so keep the
            # session fresh. Without this a viewer watching a finished run for
            # longer than the idle TTL could have their session reclaimed out
            # from under them (a completed engine does not count as active).
            current_session().touch()

            sim = get_or_create_live_simulation()
            engine = sim.get("engine")
            builder = sim.get("builder")
            if builder is not None and engine is not None:
                frame = (engine, engine.status, engine.clock.get_elapsed_time())
                now = time.time()
                if frame_changed(frame, last_frame) or now - last_sent_time >= 1.0:
                    # Off the event loop: build() waits on the engine lock
                    # for any tick in progress, and every other request and
                    # stream would otherwise wait with it.
                    snapshot = await asyncio.to_thread(builder.build)
                    await websocket.send_json(snapshot)
                    last_frame = frame
                    last_sent_time = now

            # Sleep 100ms for 10Hz frequency
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Live simulation websocket failed")
        await close_after_stream_error(websocket)
    finally:
        live_session_var.reset(token)


# ── Dual (signal vs roundabout) comparison ──────────────────────────────────
@router.post("/api/simulation/dual/play", dependencies=[Depends(require_api_key)])
def play_dual_simulation() -> Dict[str, Any]:
    session = current_session()
    orch = get_or_create_dual_orchestrator()
    status = orch.engine_signal.status
    if status == SimulationStatus.COMPLETED:
        # Re-randomize shared seed for next dual comparison run only if not user-defined
        if session.dual_sim_orchestrator is not None:
            try:
                session.dual_sim_orchestrator.stop()
            except Exception:
                pass
        session.dual_sim_orchestrator = None
        reseed_unless_user_pinned(session)
        orch = get_or_create_dual_orchestrator()
        orch.start()
    elif status == SimulationStatus.INITIALIZED:
        orch.start()
    elif status == SimulationStatus.PAUSED:
        orch.resume()
    return {
        "status": orch.get_status(),
        "message": "Dual simulation started/resumed",
        "randomSeed": session.current_live_config["simulation"].get("randomSeed"),
    }


@router.post("/api/simulation/dual/pause", dependencies=[Depends(require_api_key)])
def pause_dual_simulation() -> Dict[str, Any]:
    orch = get_or_create_dual_orchestrator()
    orch.pause()
    return {"status": orch.get_status(), "message": "Dual simulation paused"}


@router.post("/api/simulation/dual/speed", dependencies=[Depends(require_api_key)])
def set_dual_simulation_speed(req: SpeedRequest) -> Dict[str, Any]:
    orch = get_or_create_dual_orchestrator()
    orch.speed_multiplier = req.multiplier
    return {"message": f"Dual speed set to {req.multiplier}x"}


@router.post("/api/simulation/dual/reset", dependencies=[Depends(require_api_key)])
def reset_dual_simulation() -> Dict[str, Any]:
    session = current_session()
    if session.dual_sim_orchestrator is not None:
        try:
            session.dual_sim_orchestrator.stop()
        except Exception:
            pass
    session.dual_sim_orchestrator = None
    # Generate a fresh shared random seed only if not user-defined
    reseed_unless_user_pinned(session)
    orch = get_or_create_dual_orchestrator()
    return {
        "status": orch.get_status(),
        "message": "Dual simulation reset",
        "randomSeed": session.current_live_config["simulation"].get("randomSeed"),
    }


@router.get("/api/simulation/dual/status")
def get_dual_simulation_status() -> Dict[str, Any]:
    orch = get_or_create_dual_orchestrator()
    return {
        "status": orch.get_status(),
        "elapsed": round(orch.clock_signal.get_elapsed_time(), 2),
        "tick": orch.clock_signal.get_tick_count(),
    }


@router.websocket("/ws/simulation/dual")
async def websocket_dual_stream(websocket: WebSocket) -> None:
    if await refuse_foreign_origin(websocket):
        return
    await websocket.accept()
    session_key = websocket.cookies.get(LIVE_SESSION_COOKIE) or DEFAULT_SESSION_KEY
    token = live_session_var.set(get_or_create_session(session_key))
    last_frame: Optional[tuple[Any, ...]] = None
    last_sent_time = 0.0

    try:
        while True:
            # See the live stream above: an open stream keeps the session alive.
            current_session().touch()

            # Re-fetch orchestrator each frame so config changes are reflected
            orch = get_or_create_dual_orchestrator()
            frame = (
                orch,
                orch.get_status(),
                orch.clock_signal.get_elapsed_time(),
                orch.clock_roundabout.get_elapsed_time(),
            )
            now = time.time()
            if frame_changed(frame, last_frame) or now - last_sent_time >= 1.0:
                snapshot = await asyncio.to_thread(orch.get_dual_snapshot)
                await websocket.send_json(snapshot)
                last_frame = frame
                last_sent_time = now

            # Sleep 100ms for 10Hz frequency
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Dual simulation websocket failed")
        await close_after_stream_error(websocket)
    finally:
        live_session_var.reset(token)
