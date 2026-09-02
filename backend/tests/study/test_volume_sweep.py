import sqlite3

from src.database.dao import SweepSessionDAO
from src.database.db import init_db
from src.study.volume_sweep import run_volume_sweep_experiment


def test_volume_sweep_execution(tmp_path, monkeypatch) -> None:
    test_db = str(tmp_path / "test_sweep_run.db")
    monkeypatch.setattr("src.database.db.DB_PATH", test_db)
    monkeypatch.setattr("src.database.sweep_runner.DB_PATH", test_db)
    monkeypatch.setattr("src.study.volume_sweep.DB_PATH", test_db)

    init_db()

    # Run a fast 2-point volume sweep
    rates = [0.2, 0.6]
    res = run_volume_sweep_experiment(
        arrival_rates=rates,
        duration=5.0,
        time_step=0.1,
        random_seed=123,
        name="Test Fast Sweep",
    )

    assert res["name"] == "Test Fast Sweep"
    assert "sessionId" in res
    assert len(res["runs"]) == 2

    # Check curve outputs
    curves = res["curves"]
    assert curves["rates"] == rates
    assert len(curves["signal"]["delays"]) == 2
    assert len(curves["roundabout"]["delays"]) == 2
    assert len(curves["signal"]["throughputs"]) == 2
    assert len(curves["roundabout"]["throughputs"]) == 2

    # Check database persistence
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    try:
        session = SweepSessionDAO.get(conn, res["sessionId"])
        assert session is not None
        assert session["name"] == "Test Fast Sweep"
        assert len(session["results"]["runs"]) == 2
    finally:
        conn.close()
