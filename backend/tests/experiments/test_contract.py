"""The checked-in ``/api/v3`` contract files are current (ADR-013 decision 7).

If one fails, regenerate with ``cd backend && python -m src.experiments.export_schemas`` and review the
diff: it is the contract change."""

import json

import pytest

from src.experiments import export_schemas as export
from src.experiments.models import ExperimentStatus
from src.main import app

from .conftest import as_user, build_client, experiment, wait_for


def _read(name: str):
    return json.loads((export.OUT / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", [n for n, _ in export.MODELS])
def test_checked_in_json_schemas_match_the_models(name):
    assert _read(f"{name}.schema.json") == export.schemas()[name], (
        f"{name}.schema.json is stale; run python -m src.experiments.export_schemas"
    )


def test_checked_in_openapi_snapshot_matches_the_app():
    assert _read(export.OPENAPI_FILE) == export.snapshot(), (
        "the /api/v3 OpenAPI snapshot is stale; run python -m src.experiments.export_schemas"
    )


def test_snapshot_holds_only_v3_and_the_expected_operations():
    paths = _read(export.OPENAPI_FILE)["paths"]
    assert all(p.startswith("/api/v3/") for p in paths)
    operations = {(m.upper(), p) for p, ops in paths.items() for m in ops}
    assert operations == {
        ("GET", "/api/v3/capabilities"),
        ("POST", "/api/v3/experiments"),
        ("GET", "/api/v3/experiments"),
        ("POST", "/api/v3/experiments/validate"),
        ("GET", "/api/v3/experiments/{experiment_id}"),
        ("DELETE", "/api/v3/experiments/{experiment_id}"),
        ("GET", "/api/v3/experiments/{experiment_id}/result"),
        ("POST", "/api/v3/tokens"),
        ("GET", "/api/v3/tokens"),
        ("DELETE", "/api/v3/tokens/{token_id}"),
        ("POST", "/api/v3/experiments/{experiment_id}/cancel"),
        ("POST", "/api/v3/experiments/{experiment_id}/resume"),
        ("GET", "/api/v3/experiments/{experiment_id}/package"),
        ("POST", "/api/v3/packages/verify"),
    }


def test_the_frozen_v2_paths_are_still_mounted_beside_v3():
    paths = app.openapi()["paths"]
    assert "/api/v2/planning/run" in paths and "/api/v2/networks/validate" in paths
    assert "/api/v3/experiments" in paths


def test_status_shape_tolerates_null_fields_and_matches_what_the_server_sends(
    make_service,
):
    # Every consumer of the status shape must tolerate null counts, error, progress and fingerprint.
    ExperimentStatus.model_validate(
        {
            "id": "x",
            "name": "n",
            "status": "queued",
            "error": None,
            "createdAt": "t",
            "counts": None,
            "specFingerprint": None,
            "resultAvailable": False,
            "progress": None,
        }
    )
    client = build_client(make_service())
    body = client.post(
        "/api/v3/experiments", json=experiment(), headers=as_user("alice")
    ).json()
    ExperimentStatus.model_validate(body)
    wait_for(client, body["id"])


def test_optional_request_fields_accept_null(make_service):
    client = build_client(make_service())
    body = experiment(alternatives=None, baseline=None)
    check = client.post(
        "/api/v3/experiments/validate", json=body, headers=as_user("alice")
    ).json()
    assert check["valid"] is True and check["counts"]["alternatives"] == 3
