from src.study.report_generator import (
    generate_study_report_csv,
    generate_study_report_json,
)
from src.study.validation import run_statistical_validation
from src.study.volume_sweep import run_volume_sweep_experiment


def test_study_report_generation(tmp_path, monkeypatch) -> None:
    test_db = str(tmp_path / "test_report.db")
    monkeypatch.setattr("src.database.db.DB_PATH", test_db)
    monkeypatch.setattr("src.study.volume_sweep.DB_PATH", test_db)

    sweep = run_volume_sweep_experiment(arrival_rates=[0.2, 0.5], duration=4.0)
    val = run_statistical_validation(num_seeds=2, duration=4.0)

    # JSON report
    report_json = generate_study_report_json(
        sweep_results=sweep, validation_results=val
    )
    assert report_json["version"] == "1.0.0"
    assert "summary" in report_json
    assert "volumeSweep" in report_json
    assert "statisticalValidation" in report_json

    # CSV report
    report_csv = generate_study_report_csv(sweep_results=sweep, validation_results=val)
    assert "=== COMPREHENSIVE TRAFFIC STUDY REPORT ===" in report_csv
    assert "=== VOLUME SWEEP RESULTS ===" in report_csv
    assert "=== STATISTICAL MONTE CARLO VALIDATION ===" in report_csv
