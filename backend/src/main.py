"""The FastAPI application: the composition root.

Creates the app, installs middleware and the error envelope, initialises the
database, and mounts every resource's router. No route is defined here; see
docs/architecture/02-backend-architecture.md for which package owns which
routes.
"""

import contextlib
import logging
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api import meta
from src.api.auth import get_current_user_id, get_current_user_is_admin
from src.api.errors import http_exception_handler
from src.api.origins import CORS_ALLOW_CREDENTIALS, CORS_ORIGINS
from src.api.request_limits import BodySizeLimitMiddleware, compute_slot
from src.api.security import require_api_key
from src.calibration import api as calibration_api
from src.database.db import init_db
from src.experiments.router import create_router as build_experiments_router
from src.history import router as history_router
from src.live import router as live_router
from src.live.sessions import live_session_middleware
from src.networks.api import router as networks_router
from src.planning.router import create_router as build_planning_router
from src.replays import router as replays_router
from src.simulations import router as simulations_router
from src.study import router as study_router
from src.study.runner import shutdown_pool
from src.suites import router as suites_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    # Stop the study worker processes (study/runner.py) with the server.
    shutdown_pool()


app = FastAPI(
    title="Traffic Simulation Framework API", version="1.0.0", lifespan=_lifespan
)

# Middleware runs outermost-last-added: the live-session middleware sees each
# request first, then the body-size cap, then CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 1 MiB cap on the stateless /api/v2 compute endpoints (src/api/request_limits.py).
app.add_middleware(BodySizeLimitMiddleware)
# Resolves each /api/simulation/* request's live session (src/live/sessions.py).
app.middleware("http")(live_session_middleware)

app.exception_handler(HTTPException)(http_exception_handler)

# Every /api/v2 and /api/v3 route needs the API key AND a signed-in user
# (src/api/security.py); tests/api/test_v2_route_auth.py checks every route.

# V1.9 /api/v2/networks (src/networks/api.py): stateless, nothing stored.
app.include_router(
    networks_router,
    dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
)

# V1.8 /api/v2/calibration (src/calibration/api.py): runs belong to their creator.
app.include_router(calibration_api.router)

# V2.0 /api/v2/planning (src/planning/router.py).
app.include_router(
    build_planning_router(
        user_dependency=get_current_user_id,
        admin_dependency=get_current_user_is_admin,
        dependencies=[Depends(require_api_key)],
        run_dependencies=[Depends(compute_slot)],
    )
)

# V3.0 /api/v3 (src/experiments/router.py): Robustness Lab experiments and capabilities.
# Same guards as /api/v2 (API key AND a signed-in user); every resource is private to its owner.
app.include_router(
    build_experiments_router(
        user_dependency=get_current_user_id,
        dependencies=[Depends(require_api_key)],
    )
)

# V1.1 /api/v1/study/history/runs (src/history/router.py): stored runs; a
# signed-in user's runs are theirs, unowned study runs stay public.
app.include_router(history_router.router)

# Initialize Database
try:
    init_db()
    logger.info("Database initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")

# /health, /api/version, /api/me, /api/users (src/api/meta.py).
app.include_router(meta.router)
# /api/simulation/* and /ws/simulation/*: the live dashboard (src/live/router.py).
app.include_router(live_router.router)
# /api/v1/simulations, /api/simulation/new, /ws/v1/stream and config/scenario
# validation (src/simulations/router.py).
app.include_router(simulations_router.router)
# /api/v1/study/*: sweeps, validation, control comparison (src/study/router.py).
app.include_router(study_router.router)
# /api/v1/replays (src/replays/router.py).
app.include_router(replays_router.router)
# /api/suites (src/suites/router.py).
app.include_router(suites_router.router)
