import pytest

from src.database.dao import ScenarioSuiteDAO
from src.database.db import init_db


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """A connection to a fresh database built by the real init_db().

    The schema used to be re-typed here by hand, so these tests checked the
    DAO against a copy that could drift from production; and DB_PATH was
    reassigned to ":memory:" without being restored, leaking into every
    later test that opened the database.
    """
    import src.database.db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "suites.db"))
    init_db()
    with db_module.get_db_connection() as conn:
        yield conn


def test_save_and_get_suite(test_db):
    suite_id = "suite-123"
    run_ids = ["run-1", "run-2"]

    # Need to insert runs first because of schema logic, though there's no FK constraint yet
    for r in run_ids:
        test_db.execute(
            "INSERT INTO simulation_runs (id, status, elapsed) VALUES (?, 'COMPLETED', 1.0)",
            (r,),
        )

    ScenarioSuiteDAO.save(
        test_db,
        suite_id=suite_id,
        name="Test Suite",
        description="A test suite",
        run_ids=run_ids,
        config_variations={"run-1": "base", "run-2": "variant"},
    )

    suite = ScenarioSuiteDAO.get(test_db, suite_id)
    assert suite is not None
    assert suite["id"] == suite_id
    assert suite["name"] == "Test Suite"
    assert suite["description"] == "A test suite"
    assert suite["run_ids"] == run_ids
    assert suite["config_variations"]["run-1"] == "base"

    # Verify the suite_id was updated on the runs
    cursor = test_db.cursor()
    cursor.execute("SELECT id, suite_id FROM simulation_runs;")
    runs = cursor.fetchall()
    assert len(runs) == 2
    for r in runs:
        assert r["suite_id"] == suite_id


def test_list_suites(test_db):
    import time

    ScenarioSuiteDAO.save(test_db, "s1", "Suite 1", "", [], {}, user_id="alice")
    time.sleep(1.0)
    ScenarioSuiteDAO.save(test_db, "s2", "Suite 2", "", [], {}, user_id="alice")
    ScenarioSuiteDAO.save(test_db, "s3", "Bob's", "", [], {}, user_id="bob")

    suites = ScenarioSuiteDAO.list_suites(test_db, user_id="alice")
    assert len(suites) == 2
    # newest first
    assert suites[0]["id"] == "s2"
    assert suites[1]["id"] == "s1"

    # Suites are private: never everything by default, everything for an admin.
    assert ScenarioSuiteDAO.list_suites(test_db) == []
    assert {s["id"] for s in ScenarioSuiteDAO.list_suites(test_db, user_id="bob")} == {
        "s3"
    }
    assert len(ScenarioSuiteDAO.list_suites(test_db, is_admin=True)) == 3


def test_add_runs_keeps_existing_and_tags_new_runs(test_db):
    for r in ("run-1", "run-2", "run-3"):
        test_db.execute(
            "INSERT INTO simulation_runs (id, status, elapsed) VALUES (?, 'COMPLETED', 1.0)",
            (r,),
        )
    ScenarioSuiteDAO.save(test_db, "s1", "Suite", "", ["run-1"], {})

    ScenarioSuiteDAO.add_runs(test_db, "s1", ["run-2", "run-3", "run-1"], commit=True)

    suite = ScenarioSuiteDAO.get(test_db, "s1")
    assert suite is not None
    assert suite["run_ids"] == ["run-1", "run-2", "run-3"]
    cursor = test_db.execute("SELECT id FROM simulation_runs WHERE suite_id = 's1';")
    assert {row["id"] for row in cursor.fetchall()} == {"run-1", "run-2", "run-3"}


def test_add_runs_unknown_suite_raises(test_db):
    with pytest.raises(ValueError):
        ScenarioSuiteDAO.add_runs(test_db, "missing", ["run-1"])
