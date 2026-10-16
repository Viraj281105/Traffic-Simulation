"""``/api/v1/replays``: save, list, read and delete saved replays."""

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.api.security import require_api_key
from src.auth import get_current_user_email, get_current_user_id
from src.core.provenance import build_run_provenance
from src.database.dao import SimulationRunDAO, describe_reproducibility
from src.database.db import ensure_db_initialized, get_db_connection
from src.database.replay_dao import ReplayDAO
from src.live.capture import capture_engine_run
from src.live.sessions import find_live_session
from src.request_limits import PageLimit, PageOffset

router = APIRouter()


class SaveReplayRequest(BaseModel):
    name: str
    config: Dict[str, Any]
    metrics: Dict[str, Any]
    # "dual" for a signal-vs-roundabout comparison. Optional for older
    # clients: inferred from the metrics shape ({signal, roundabout}).
    mode: Optional[Literal["single", "dual"]] = None


def _with_reproducibility(
    replays: list[Dict[str, Any]], conn: Any
) -> list[Dict[str, Any]]:
    """Attaches each saved replay's compact reproducibility summary from its
    simulation_runs row (same id); None where no such row exists."""
    runs = SimulationRunDAO.get_many(conn, [r["id"] for r in replays])
    for replay in replays:
        run = runs.get(replay["id"])
        replay["reproducibility"] = (
            describe_reproducibility(run, include_payload=False) if run else None
        )
    return replays


@router.post("/api/v1/replays", dependencies=[Depends(require_api_key)])
def save_replay(
    payload: SaveReplayRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    email: str = Depends(get_current_user_email),
) -> Dict[str, Any]:
    ensure_db_initialized()
    mode = payload.mode or (
        "dual"
        if "signal" in payload.metrics and "roundabout" in payload.metrics
        else "single"
    )
    client_sim = payload.config.get("simulation", {})
    # /api/v1/replays is outside the live-session middleware's prefix, so the
    # caller's session is looked up from its cookie, never created.
    captured = capture_engine_run(
        find_live_session(request), mode, client_sim.get("randomSeed")
    )
    metrics = payload.metrics
    if captured is not None:
        run_config = captured["config"]
        metrics = captured["metrics"]
        seed = captured["seed"]
        duration = captured["duration"]
        elapsed = captured["elapsed"]
        provenance = build_run_provenance(
            config_source="engine",
            run_mode=mode,
            time_step=captured["timeStep"],
            duration=duration,
            warmup_time=captured["warmupTime"],
        )
    else:
        # No engine to read from: keep the client's summary, as before, and
        # say so in the provenance rather than presenting it as exact.
        run_config = payload.config
        seed = client_sim.get("randomSeed")
        duration = client_sim.get("duration", 60.0)
        elapsed = client_sim.get("elapsed", duration)
        provenance = build_run_provenance(
            config_source="client",
            run_mode=mode,
            time_step=client_sim.get("timeStep"),
            duration=client_sim.get("duration"),
            warmup_time=client_sim.get("warmupTime"),
        )
    itype = (
        "comparative"
        if mode == "dual"
        else run_config.get("geometry", {}).get("intersectionType", "unknown")
    )
    arr_rate = run_config.get("traffic", {}).get("arrivalRate", 0.5)
    with get_db_connection() as conn:
        replay_id = ReplayDAO.save(
            conn, payload.name, payload.config, metrics, user_id=user_id, email=email
        )
        # Also persist to simulation_runs (same id) for history, reproducible
        # comparison and the reproducibility record.
        SimulationRunDAO.save(
            conn,
            replay_id,
            "completed",
            elapsed,
            intersection_type=itype,
            random_seed=seed,
            arrival_rate=arr_rate,
            duration=duration,
            batch_id="replay",
            config=run_config,
            summary_metrics=metrics,
            provenance=provenance,
            # Same fallback as ReplayDAO.save, so both tables agree.
            name=(payload.name or "").strip() or "Saved Replay",
            user_id=user_id,
            email=email,
        )
        conn.commit()
        run = SimulationRunDAO.get(conn, replay_id)
        return {
            "status": "ok",
            "replay_id": replay_id,
            "runId": replay_id,
            "reproducibility": (
                describe_reproducibility(run, include_payload=False) if run else None
            ),
        }
    raise HTTPException(status_code=500, detail="Database connection error")


@router.get("/api/v1/replays")
def list_replays(
    limit: PageLimit = 50,
    offset: PageOffset = 0,
    user_id: str = Depends(get_current_user_id),
) -> list[Dict[str, Any]]:
    ensure_db_initialized()
    with get_db_connection() as conn:
        return _with_reproducibility(
            ReplayDAO.list_all(conn, limit=limit, offset=offset, user_id=user_id), conn
        )
    return []


@router.get("/api/v1/replays/{replay_id}")
def get_replay(
    replay_id: str, user_id: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    ensure_db_initialized()
    with get_db_connection() as conn:
        replay = ReplayDAO.get(conn, replay_id)
        if not replay:
            raise HTTPException(status_code=404, detail="Replay not found")
        # Ensure user owns this replay
        exists, owner = ReplayDAO.owner_of(conn, replay_id)
        if exists and owner and owner != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return _with_reproducibility([replay], conn)[0]
    raise HTTPException(status_code=500, detail="Database connection error")


@router.delete("/api/v1/replays/{replay_id}", dependencies=[Depends(require_api_key)])
def delete_replay(
    replay_id: str, user_id: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    ensure_db_initialized()
    with get_db_connection() as conn:
        exists, owner = ReplayDAO.owner_of(conn, replay_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Replay not found")
        if owner and owner != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        success = ReplayDAO.delete(conn, replay_id)
        if not success:
            raise HTTPException(status_code=404, detail="Replay not found")
        # The replay and its simulation_runs record are one saved experiment
        # (same id): remove both, so "deleted" also means its run page and
        # exports are gone rather than lingering as an orphan record.
        SimulationRunDAO.delete(conn, replay_id)
        return {"status": "ok"}
    raise HTTPException(status_code=500, detail="Database connection error")
