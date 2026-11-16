import ast
import dataclasses
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.governance import audit as audit_mod
from src.governance import router as router_mod
from src.governance import shadow as shadow_mod
from src.governance import workflow as workflow_mod
from src.governance.audit import (
    GENESIS_HASH,
    AuditLog,
    JsonlAuditStore,
    verify_chain,
)
from src.governance.shadow import ShadowLog, ShadowRecord, shadow_report
from src.governance.workflow import (
    CommentRequiredError,
    IllegalTransitionError,
    PermissionDeniedError,
    State,
    WorkflowService,
)


def make_log(n=4):
    ticks = iter(range(1000, 2000))
    log = AuditLog(clock=lambda: float(next(ticks)))
    for i in range(n):
        log.append("alice", "act", f"s{i}", {"i": i})
    return log


# ---------- audit chain ----------


def test_chain_valid_and_deterministic():
    log = make_log()
    res = log.verify()
    assert res.ok and res.length == 4 and res.head == log.head()
    assert log.entries()[0].prev_hash == GENESIS_HASH
    assert make_log().head() == log.head()


def test_detects_edit():
    entries = make_log().entries()
    entries[1] = dataclasses.replace(entries[1], actor="mallory")
    res = verify_chain(entries)
    assert not res.ok and res.bad_seq == 1


def test_detects_delete():
    entries = make_log().entries()
    del entries[1]
    assert not verify_chain(entries).ok


def test_detects_reorder():
    entries = make_log().entries()
    entries[1], entries[2] = entries[2], entries[1]
    assert not verify_chain(entries).ok


def test_detects_truncated_tail_with_stored_head():
    log = make_log()
    head, n = log.head(), len(log.entries())
    entries = log.entries()[:-1]
    assert verify_chain(entries).ok  # a bare chain cannot see this
    assert not verify_chain(entries, expected_head=head).ok
    assert not verify_chain(entries, expected_length=n).ok
    assert verify_chain(log.entries(), expected_head=head, expected_length=n).ok


def test_jsonl_store_roundtrip_and_tamper(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(JsonlAuditStore(path, fsync=True), clock=lambda: 5.0)
    log.append("a", "x", "s", {"k": 1})
    log.append("a", "y", "s")
    reopened = AuditLog(JsonlAuditStore(path))
    assert reopened.verify().ok and len(reopened.entries()) == 2
    reopened.append("b", "z", "s")
    assert AuditLog(JsonlAuditStore(path)).verify().length == 3
    path.write_text(path.read_text().replace('"actor":"a"', '"actor":"q"', 1))
    assert not AuditLog(JsonlAuditStore(path)).verify().ok


# ---------- workflow ----------


def svc():
    return WorkflowService(AuditLog(clock=lambda: 1.0))


def new_rec(s):
    return s.create("alice", "scn-1", {"closeLinks": ["L1"]}, ["ev-1"], "r1")


def test_happy_path_and_audit():
    s = svc()
    new_rec(s)
    s.transition("r1", State.SUBMITTED, "alice")
    rec = s.transition("r1", State.APPROVED, "bob", ["approver"])
    assert rec.state is State.APPROVED and rec.decided_by == "bob"
    assert [e.action for e in s.log.entries()] == [
        "recommendation.create",
        "recommendation.submitted",
        "recommendation.approved",
    ]
    assert s.log.verify().ok


def test_self_approval_and_role_rules():
    s = svc()
    new_rec(s)
    s.transition("r1", State.SUBMITTED, "alice")
    with pytest.raises(PermissionDeniedError):
        s.transition("r1", State.APPROVED, "alice", ["approver"])
    with pytest.raises(PermissionDeniedError):
        s.transition("r1", State.APPROVED, "bob", ["author"])
    with pytest.raises(PermissionDeniedError):
        s.transition("r1", State.WITHDRAWN, "bob")
    assert s.get("r1").state is State.SUBMITTED


def test_reject_needs_comment():
    s = svc()
    new_rec(s)
    s.transition("r1", State.SUBMITTED, "alice")
    with pytest.raises(CommentRequiredError):
        s.transition("r1", State.REJECTED, "bob", ["approver"], "  ")
    rec = s.transition("r1", State.REJECTED, "bob", ["approver"], "too risky")
    assert rec.state is State.REJECTED and rec.decision_comment == "too risky"


def test_illegal_transitions_and_withdraw():
    s = svc()
    new_rec(s)
    with pytest.raises(IllegalTransitionError):
        s.transition("r1", State.APPROVED, "bob", ["approver"])  # skips submit
    s.transition("r1", State.WITHDRAWN, "alice")
    for to in State:
        with pytest.raises(IllegalTransitionError):
            s.transition("r1", to, "alice", ["approver"])


# ---------- shadow ----------


def test_shadow_metrics_hand_computed():
    recs = [
        ShadowRecord("i1", "A", {"A": 10, "B": 14}, "A", 12),
        ShadowRecord("i2", "A", {"A": 10, "B": 14}, "B", 17),
        ShadowRecord("i3", "B", {"A": 20, "B": 15}, "A", 18),
        ShadowRecord("i4", "A", {"A": 1, "B": 2}),
    ]
    rep = shadow_report(recs)
    assert rep["recorded"] == 4 and rep["withOutcome"] == 3
    assert rep["matchRate"] == pytest.approx(1 / 3)
    assert rep["meanAbsError"] == pytest.approx(7 / 3)  # |-2|,|-3|,|2|
    assert rep["meanBias"] == pytest.approx(-1.0)
    assert rep["meanRegret"] == pytest.approx(3.0)  # 0, 4, 5
    assert rep["advisoryOnly"] is True


def test_shadow_empty_and_log():
    assert shadow_report([])["matchRate"] is None
    log = ShadowLog()
    log.record("i1", "A", {"A": 1.0, "B": 3.0})
    log.observe("i1", "B", 2.5)
    rep = log.report()
    assert rep["matchRate"] == 0.0 and rep["meanRegret"] == 2.0


# ---------- advisory-only guarantees ----------

MODULES = (audit_mod, workflow_mod, shadow_mod, router_mod)
FORBIDDEN_IMPORTS = {
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "http",
    "shutil",
    "importlib",
    "ctypes",
}
FORBIDDEN_NAMES = ("apply", "execute", "deploy", "enact", "implement", "run_change")


def test_no_executing_imports_or_calls():
    for mod in MODULES:
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert node.func.id not in {"exec", "eval", "compile", "__import__"}
                continue
            assert not names & FORBIDDEN_IMPORTS, (mod.__name__, names)


def test_no_apply_style_api():
    for mod in MODULES:
        for name in dir(mod):
            assert not any(f in name.lower() for f in FORBIDDEN_NAMES), name
    for cls in (WorkflowService, AuditLog, ShadowLog):
        for name in dir(cls):
            assert not any(f in name.lower() for f in FORBIDDEN_NAMES), name


def test_approval_only_changes_state_and_logs():
    s = svc()
    change = {"closeLinks": ["L1"], "nested": {"k": [1, 2]}}
    s.create("alice", "scn", change, rec_id="r1")
    s.transition("r1", State.SUBMITTED, "alice")
    s.transition("r1", State.APPROVED, "bob", ["approver"])
    rec = s.get("r1")
    assert rec.proposed_change == change  # untouched
    assert len(s.log.entries()) == 3  # only logging happened
    assert not any(callable(v) for v in rec.to_dict().values())


# ---------- router ----------


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router_mod.router)
    service = svc()
    app.dependency_overrides[router_mod.get_service] = lambda: service
    return TestClient(app)


BASE = "/api/v2/governance"


def test_router_flow(client):
    body = {
        "actor": "alice",
        "id": "r1",
        "scenarioRef": "scn",
        "proposedChange": {"demandScale": 0.9},
        "evidenceRefs": ["e1"],
    }
    r = client.post(f"{BASE}/recommendations", json=body)
    assert r.status_code == 201 and r.json()["state"] == "draft"
    assert client.post(f"{BASE}/recommendations", json=body).status_code == 409
    t = f"{BASE}/recommendations/r1/transition"
    assert client.post(t, json={"actor": "alice", "to": "submitted"}).status_code == 200
    assert (
        client.post(
            t, json={"actor": "alice", "roles": ["approver"], "to": "approved"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            t, json={"actor": "bob", "roles": ["approver"], "to": "rejected"}
        ).status_code
        == 422
    )
    ok = client.post(t, json={"actor": "bob", "roles": ["approver"], "to": "approved"})
    assert ok.json()["state"] == "approved"
    assert client.post(t, json={"actor": "bob", "to": "submitted"}).status_code == 409
    assert (
        client.post(
            f"{BASE}/recommendations/nope/transition",
            json={"actor": "a", "to": "submitted"},
        ).status_code
        == 404
    )
    listed = client.get(f"{BASE}/recommendations", params={"state": "approved"}).json()
    assert [i["id"] for i in listed["items"]] == ["r1"]


def test_router_audit_and_verify(client):
    client.post(
        f"{BASE}/recommendations",
        json={"actor": "a", "scenarioRef": "s", "proposedChange": {}},
    )
    audit = client.get(f"{BASE}/audit").json()
    assert (
        audit["total"] == 1 and audit["entries"][0]["action"] == "recommendation.create"
    )
    v = client.get(
        f"{BASE}/audit/verify", params={"expectedHead": audit["head"]}
    ).json()
    assert v["ok"] is True
    bad = client.get(f"{BASE}/audit/verify", params={"expectedLength": 5}).json()
    assert bad["ok"] is False


def test_router_shadow_report(client):
    r = client.post(
        f"{BASE}/shadow/report",
        json={
            "records": [
                {
                    "interval": "i1",
                    "recommended": "A",
                    "predictedCosts": {"A": 10, "B": 14},
                    "chosen": "B",
                    "observedCost": 17,
                }
            ]
        },
    )
    j = r.json()
    assert r.status_code == 200 and j["meanRegret"] == 4.0 and j["meanBias"] == -3.0
