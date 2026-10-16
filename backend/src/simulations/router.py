"""``/api/v1/simulations``, ``/api/simulation/new``, ``/ws/v1/stream`` and the
stateless configuration / scenario validation routes."""

import asyncio
import csv
import io
import json
import logging
import time
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.errors import iso_timestamp
from src.api.origins import close_after_stream_error, refuse_foreign_origin
from src.api.security import require_api_key
from src.api.validation import (
    check_engine_config_or_400,
    config_schema_error,
    valid_scenario_or_400,
)
from src.core.config_models import ScenarioConfiguration
from src.core.enums import SimulationStatus
from src.engine.readout import engine_metrics
from src.metrics.collector import MetricCollector
from src.scenario.config_validation import semantic_config_errors
from src.scenario.documents import STRATEGIES, compile_scenario, validate_scenario
from src.simulations.registry import (
    InvalidSimulationConfigError,
    SimulationLimitReachedError,
    register_simulation,
    simulations_db,
    simulations_lock,
)
from src.snapshot.buffer import SnapshotBuffer
from src.snapshot.builder import SnapshotBuilder

logger = logging.getLogger(__name__)

router = APIRouter()


class ControlRequest(BaseModel):
    action: str  # start, pause, resume, stop


# Scenario documents (V1.4): a portable, strategy-neutral description of a
# junction and its traffic (scenario/documents.py), compiled into an engine
# configuration once per control strategy. These endpoints only read the
# document; nothing is stored.
class ScenarioRequest(BaseModel):
    scenario: Dict[str, Any]
    # Strategies the scenario will be run with; each must accept it.
    # Omitted: the junction type the scenario names.
    strategies: list[Literal["fixed_time", "adaptive", "roundabout"]] | None = Field(
        default=None, min_length=1, max_length=3
    )


class ScenarioCompileRequest(BaseModel):
    scenario: Dict[str, Any]
    strategy: Literal["fixed_time", "adaptive", "roundabout"]


def get_simulation_or_404(sim_id: str) -> Dict[str, Any]:
    with simulations_lock:
        if sim_id not in simulations_db:
            raise HTTPException(status_code=404, detail="Simulation not found")
        return simulations_db[sim_id]


# ── Configuration and scenario validation ───────────────────────────────────
@router.post("/api/v1/configs/validate")
def validate_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    schema_error = config_schema_error(payload)
    if schema_error is not None:
        return {"valid": False, "errors": [schema_error]}
    errors = semantic_config_errors(payload)
    return {"valid": not errors, "errors": errors}


@router.post("/api/v1/scenarios/validate")
def validate_scenario_endpoint(payload: ScenarioRequest) -> Dict[str, Any]:
    """Whether a scenario can be simulated under each requested strategy.

    Always 200: ``valid`` is false and ``errors`` says why (and, for an error
    specific to one strategy, which) when it cannot. ``warnings`` lists what
    the results of a valid scenario should be read in the light of.
    """
    result = validate_scenario(
        payload.scenario, list(payload.strategies) if payload.strategies else None
    )
    result.pop("byStrategy", None)
    return result


@router.post("/api/v1/scenarios/compile")
def compile_scenario_endpoint(payload: ScenarioCompileRequest) -> Dict[str, Any]:
    """The exact engine configuration a scenario runs under one strategy."""
    document = valid_scenario_or_400(payload.scenario, [payload.strategy])
    return {
        "strategy": payload.strategy,
        "config": compile_scenario(document, payload.strategy),
    }


# ── Simulation lifecycle ────────────────────────────────────────────────────
@router.post("/api/simulation/new", dependencies=[Depends(require_api_key)])
def create_simulation_v2(payload: ScenarioConfiguration) -> Dict[str, Any]:
    config_dict = payload.model_dump(exclude_none=True)
    # Cross-field rules are checked against what the client actually sent,
    # not the defaults-filled dump: warmupTime's 30 s default must not turn a
    # short run into a rejected one (see semantic_config_errors).
    return create_registered_simulation(
        config_dict,
        semantic_source=payload.model_dump(exclude_none=True, exclude_unset=True),
    )


@router.post(
    "/api/v1/simulations",
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
def create_simulation(config: Dict[str, Any]) -> Dict[str, Any]:
    # V1.4: {"scenario": <scenario document>, "strategy": ...} runs a scenario
    # document under one strategy; anything else is an engine configuration,
    # exactly as before. An engine configuration never has a top-level
    # "strategy", so the two cannot be confused.
    if "strategy" in config and isinstance(config.get("scenario"), dict):
        strategy = config["strategy"]
        if strategy not in STRATEGIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid strategy {strategy!r}: must be one of "
                f"{', '.join(STRATEGIES)}",
            )
        document = valid_scenario_or_400(config["scenario"], [strategy])
        config = compile_scenario(document, strategy)
    return create_registered_simulation(config, semantic_source=config)


def create_registered_simulation(
    config: Dict[str, Any], semantic_source: Dict[str, Any]
) -> Dict[str, Any]:
    # Schema-level shape/bounds, then the contract's cross-field rules, which
    # the schema cannot express.
    check_engine_config_or_400(config, semantic_source)
    # Building the engine can still reject a config that passed both (e.g.
    # duration <= 0, an unsupported phaseSequence entry) — surface those as
    # 400s, not a raw 500, since they are still the client's fault.
    try:
        entry = register_simulation(config)
    except InvalidSimulationConfigError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid configuration: {exc}"
        ) from exc
    except SimulationLimitReachedError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    return {
        "simulationId": entry["sim_id"],
        "configId": entry["config_id"],
        "status": entry["engine"].status.value.lower(),
        "createdAt": iso_timestamp(entry["created_at"]),
        "config": config,
    }


@router.delete("/api/v1/simulations/{sim_id}", dependencies=[Depends(require_api_key)])
def delete_simulation(sim_id: str) -> Dict[str, Any]:
    """Explicitly removes a simulation from the in-memory registry.

    Refuses to delete a RUNNING/PAUSED simulation — stop it first.
    """
    with simulations_lock:
        if sim_id not in simulations_db:
            raise HTTPException(status_code=404, detail="Simulation not found")
        sim = simulations_db[sim_id]
        engine = sim["engine"]
        if engine.status in (SimulationStatus.RUNNING, SimulationStatus.PAUSED):
            raise HTTPException(
                status_code=400,
                detail="Cannot delete a running or paused simulation; stop it first.",
            )
        del simulations_db[sim_id]
    return {"status": "deleted", "simulationId": sim_id}


@router.post(
    "/api/v1/simulations/{sim_id}/control", dependencies=[Depends(require_api_key)]
)
def control_simulation(sim_id: str, payload: ControlRequest) -> Dict[str, Any]:
    sim = get_simulation_or_404(sim_id)
    engine = sim["engine"]
    action = payload.action.lower()

    if action not in ("start", "pause", "resume", "stop"):
        raise HTTPException(status_code=400, detail="Invalid action")

    # Captured before the transition so it reflects the actual prior state,
    # not a value re-derived after engine.status has already changed.
    previous_status = engine.status.value.lower()

    try:
        if action == "start":
            engine.start()
        elif action == "pause":
            engine.pause()
        elif action == "resume":
            engine.resume()
        elif action == "stop":
            engine.stop()
    except RuntimeError as exc:
        # engine.start() raises RuntimeError for an invalid transition
        # (e.g. "start" on an already-running/completed simulation) —
        # surface that as the documented 409 INVALID_STATE_TRANSITION
        # (docs/architecture/08-communication-contract.md §6.2), not an
        # unhandled 500. pause()/resume()/stop() have no invalid-transition
        # case to catch here: they are documented no-ops outside their
        # applicable state (see SimulationEngine). Nothing is returned on
        # this path, so a failed transition can never produce a payload
        # that looks like a successful one.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    current_status = engine.status.value.lower()
    return {
        "status": current_status,
        "simulationId": sim_id,
        "previousStatus": previous_status,
        "currentStatus": current_status,
        "timestamp": iso_timestamp(time.time()),
    }


@router.get("/api/v1/simulations/{sim_id}")
def get_simulation(sim_id: str) -> Dict[str, Any]:
    sim = get_simulation_or_404(sim_id)
    engine = sim["engine"]
    return {
        "simulationId": sim_id,
        "status": engine.status.value.lower(),
        "elapsed": round(engine.clock.get_elapsed_time(), 2),
        "tick": engine.clock.get_tick_count(),
    }


@router.get("/api/v1/simulations/{sim_id}/metrics")
def get_simulation_metrics(sim_id: str) -> Dict[str, Any]:
    sim = get_simulation_or_404(sim_id)
    collector: MetricCollector = sim["collector"]
    # Under the engine's lock, so this doesn't race the background simulation
    # thread mutating pool.active_vehicles/exited_vehicles mid-tick.
    metrics: Dict[str, Any] = engine_metrics(sim["engine"], collector)
    return metrics


@router.get("/api/v1/simulations/{sim_id}/history")
def get_simulation_history(sim_id: str) -> list[dict[str, Any]]:
    sim = get_simulation_or_404(sim_id)
    buffer: SnapshotBuffer = sim["buffer"]
    return buffer.get_all()


@router.get("/api/v1/simulations/{sim_id}/history/{tick}")
def get_simulation_history_tick(sim_id: str, tick: int) -> dict[str, Any]:
    sim = get_simulation_or_404(sim_id)
    buffer: SnapshotBuffer = sim["buffer"]
    frame = buffer.get_frame(tick)
    if frame is None:
        raise HTTPException(
            status_code=404, detail=f"Frame at tick {tick} not found in buffer"
        )
    return frame


@router.get("/api/v1/simulations/{sim_id}/report")
def get_simulation_report(sim_id: str, format: str = "csv") -> Any:  # noqa: A002
    sim = get_simulation_or_404(sim_id)
    engine = sim["engine"]

    # Final metrics, read under the engine's lock so this doesn't race the
    # background simulation thread mutating the vehicle lists mid-tick.
    final_metrics: Dict[str, Any] = engine_metrics(engine, sim["collector"])

    if format == "json":
        return {
            "simulationId": sim_id,
            "finalMetrics": final_metrics,
            "ticksCount": engine.clock.get_tick_count(),
        }

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(["Metric Name", "Value"])
    for key, value in final_metrics.items():
        if isinstance(value, dict):
            writer.writerow([key, json.dumps(value)])
        else:
            writer.writerow([key, value])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=simulation_{sim_id}_report.csv"
        },
    )


def resolve_snapshot_interval(config: Dict[str, Any]) -> float:
    """Resolves the WS streaming sleep interval from simulation.snapshotFrequency.

    docs/architecture/08-communication-contract.md §5.1: snapshot frequency
    is configurable via simulation.snapshotFrequency (default 10Hz),
    hard-limited to [1, 60]Hz. CONFIG_SCHEMA/ScenarioConfiguration already
    enforce that range on the way in; the clamp here is just a defensive
    fallback for configs that bypassed that validation.
    """
    snapshot_frequency = config.get("simulation", {}).get("snapshotFrequency", 10.0)
    try:
        snapshot_frequency = float(snapshot_frequency)
    except (TypeError, ValueError):
        snapshot_frequency = 10.0
    snapshot_frequency = min(max(snapshot_frequency, 1.0), 60.0)
    return 1.0 / snapshot_frequency


@router.websocket("/ws/v1/stream")
async def websocket_stream(websocket: WebSocket, simulationId: str) -> None:  # noqa: N803
    if await refuse_foreign_origin(websocket):
        return
    await websocket.accept()
    try:
        sim = get_simulation_or_404(simulationId)
    except HTTPException:
        await websocket.close(code=1008, reason="Simulation not found")
        return

    engine = sim["engine"]
    collector = sim["collector"]
    controller = sim["controller"]
    config_id = sim["config_id"]

    builder = SnapshotBuilder(simulationId, config_id, engine, collector, controller)
    snapshot_interval = resolve_snapshot_interval(engine.config)

    try:
        while True:
            # Generate and send state snapshot
            snapshot = await asyncio.to_thread(builder.build)
            await websocket.send_json(snapshot)

            # Check if simulation complete
            if snapshot["simulationStatus"] in ("completed", "error"):
                break

            await asyncio.sleep(snapshot_interval)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Simulation stream %s failed", simulationId)
        await close_after_stream_error(websocket)
