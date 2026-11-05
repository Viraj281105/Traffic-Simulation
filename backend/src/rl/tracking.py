"""MLflow tracking behind an optional import, plus a minimal model registry.

``mlflow`` is not required: without it :func:`start_run` yields a no-op run
that still collects params and metrics in memory (``run.params`` /
``run.metrics``) so callers and tests behave the same either way. With it, runs
go to a *file-based* store (``file:<dir>``, default ``./mlruns``); no server.

The registry (:class:`ModelRegistry`) is a plain directory plus a JSON index,
so it works with or without MLflow and is easy to inspect, copy and diff::

    <root>/<name>/v<N>/model.zip      the saved policy
    <root>/<name>/v<N>/meta.json      algorithm, metrics, tags, source run
    <root>/index.json                 {name: {versions: [...], stages: {...}}}
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

try:  # optional dependency
    import mlflow  # type: ignore[import-not-found,unused-ignore]
except Exception:  # pragma: no cover - exercised only when mlflow is absent
    mlflow = None

DEFAULT_TRACKING_DIR = "mlruns"
STAGES = ("none", "staging", "production", "archived")


def mlflow_available() -> bool:
    return mlflow is not None


def file_tracking_uri(directory: Union[str, Path]) -> str:
    return Path(directory).resolve().as_uri()


class TrackedRun:
    """Params/metrics sink; mirrors to MLflow when it is installed."""

    def __init__(self, active: bool) -> None:
        self.active = active
        self.params: Dict[str, Any] = {}
        self.metrics: Dict[str, List[float]] = {}
        self.run_id: Optional[str] = None

    def log_params(self, params: Dict[str, Any]) -> None:
        flat = {
            k: str(v) if not isinstance(v, (int, float, str)) else v
            for k, v in params.items()
        }
        self.params.update(flat)
        if self.active:
            mlflow.log_params(flat)

    def log_metrics(
        self, metrics: Dict[str, float], step: Optional[int] = None
    ) -> None:
        clean = {k: float(v) for k, v in metrics.items()}
        for k, v in clean.items():
            self.metrics.setdefault(k, []).append(v)
        if self.active:
            mlflow.log_metrics(clean, step=step)

    def log_artifact(self, path: Union[str, Path]) -> None:
        if self.active:
            mlflow.log_artifact(str(path))


@contextlib.contextmanager
def start_run(
    experiment: str = "rl-signal-control",
    run_name: Optional[str] = None,
    tracking_dir: Union[str, Path, None] = DEFAULT_TRACKING_DIR,
    enabled: bool = True,
) -> Iterator[TrackedRun]:
    """Open a tracked run; a no-op run when disabled or MLflow is absent."""
    if not (enabled and mlflow is not None and tracking_dir is not None):
        yield TrackedRun(active=False)
        return
    # MLflow 3 gates the file store behind this flag; a local file store is
    # exactly what is wanted here (no server), so opt in unless set already.
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri(file_tracking_uri(tracking_dir))
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name) as active:
        run = TrackedRun(active=True)
        run.run_id = active.info.run_id
        yield run


class ModelRegistry:
    """Versioned model store with stage labels (file based)."""

    def __init__(self, root: Union[str, Path]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"

    # -- index ---------------------------------------------------------
    def _load(self) -> Dict[str, Any]:
        if not self._index_path.exists():
            return {}
        with open(self._index_path, encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
        return data

    def _save(self, index: Dict[str, Any]) -> None:
        tmp = self._index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(index, f, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(self._index_path)

    # -- api -----------------------------------------------------------
    def register(
        self,
        name: str,
        model_path: Union[str, Path],
        algo: str,
        metrics: Optional[Dict[str, float]] = None,
        tags: Optional[Dict[str, str]] = None,
        run_id: Optional[str] = None,
    ) -> int:
        """Copy ``model_path`` in as the next version of ``name``; return it."""
        src = Path(model_path)
        if not src.is_file():
            raise FileNotFoundError(src)
        index = self._load()
        entry = index.setdefault(name, {"versions": [], "stages": {}})
        version = len(entry["versions"]) + 1
        target = self.root / name / f"v{version}"
        target.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(src, target / "model.zip")
        meta = {
            "name": name,
            "version": version,
            "algo": algo,
            "metrics": dict(metrics or {}),
            "tags": dict(tags or {}),
            "run_id": run_id,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(target / "meta.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, indent=2, sort_keys=True)
            f.write("\n")
        entry["versions"].append(version)
        entry["stages"][str(version)] = "none"
        self._save(index)
        return version

    def set_stage(self, name: str, version: int, stage: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}")
        index = self._load()
        if name not in index or str(version) not in index[name]["stages"]:
            raise KeyError(f"{name} v{version} is not registered")
        if stage == "production":  # one production version per model
            for v, s in index[name]["stages"].items():
                if s == "production":
                    index[name]["stages"][v] = "archived"
        index[name]["stages"][str(version)] = stage
        self._save(index)

    def versions(self, name: str) -> List[int]:
        return list(self._load().get(name, {}).get("versions", []))

    def stage_of(self, name: str, version: int) -> str:
        return str(self._load()[name]["stages"][str(version)])

    def resolve(
        self, name: str, stage_or_version: Union[str, int, None] = None
    ) -> Path:
        """Model file of a version number, a stage name, or the latest."""
        index = self._load()
        if name not in index or not index[name]["versions"]:
            raise KeyError(f"no model registered as {name!r}")
        entry = index[name]
        if stage_or_version is None or stage_or_version == "latest":
            version = entry["versions"][-1]
        elif isinstance(stage_or_version, int) or str(stage_or_version).isdigit():
            version = int(stage_or_version)
        else:
            matches = [
                int(v) for v, s in entry["stages"].items() if s == stage_or_version
            ]
            if not matches:
                raise KeyError(f"{name} has no version in stage {stage_or_version!r}")
            version = max(matches)
        path = self.root / name / f"v{version}" / "model.zip"
        if not path.is_file():
            raise KeyError(f"{name} v{version} is not registered")
        return path

    def metadata(self, name: str, version: int) -> Dict[str, Any]:
        with open(
            self.root / name / f"v{version}" / "meta.json", encoding="utf-8"
        ) as f:
            data: Dict[str, Any] = json.load(f)
        return data

    # -- additive: save/load objects, promotion (F18 W41 model registry) ----
    def stage_version(self, name: str, stage: str = "production") -> Optional[int]:
        """The version currently in ``stage`` (highest if several), or None."""
        entry = self._load().get(name)
        if not entry:
            return None
        found = [int(v) for v, s in entry["stages"].items() if s == stage]
        return max(found) if found else None

    def save_model(
        self,
        name: str,
        model: Any,
        algo: str,
        metrics: Optional[Dict[str, float]] = None,
        tags: Optional[Dict[str, str]] = None,
        run_id: Optional[str] = None,
    ) -> int:
        """Save a trained object (anything with ``.save(path)``) as the next version."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.zip"
            model.save(str(path))
            return self.register(name, path, algo, metrics, tags, run_id)

    def load_model(
        self, name: str, stage_or_version: Union[str, int, None] = None
    ) -> Any:
        """Load a registered stable-baselines3 model by version, stage or latest."""
        from src.rl.train import load_model

        path = self.resolve(name, stage_or_version)
        version = int(path.parent.name[1:])
        return load_model(self.metadata(name, version)["algo"], path)

    def update_metrics(
        self, name: str, version: int, metrics: Dict[str, float]
    ) -> None:
        """Merge evaluation metrics into a version's ``meta.json``."""
        meta = self.metadata(name, version)
        meta["metrics"] = {
            **meta.get("metrics", {}),
            **{k: float(v) for k, v in metrics.items()},
        }
        with open(
            self.root / name / f"v{version}" / "meta.json",
            "w",
            encoding="utf-8",
            newline="\n",
        ) as f:
            json.dump(meta, f, indent=2, sort_keys=True)
            f.write("\n")

    def promote(
        self, name: str, version: int, stage: str = "production", note: str = ""
    ) -> None:
        """Move ``version`` to ``stage`` (demoting any previous production) and log it."""
        self.set_stage(name, version, stage)
        index = self._load()
        index[name].setdefault("history", []).append(
            {
                "version": int(version),
                "stage": stage,
                "note": note,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        self._save(index)

    def history(self, name: str) -> List[Dict[str, Any]]:
        return list(self._load().get(name, {}).get("history", []))

    def promote_if_better(
        self,
        name: str,
        version: int,
        metric: str,
        lower_is_better: bool = True,
        stage: str = "production",
    ) -> Dict[str, Any]:
        """Promote ``version`` when it beats the incumbent on a stored metric.

        With no incumbent in ``stage`` the candidate is promoted. A candidate
        or incumbent without ``metric`` never wins (``promoted`` False).
        """
        cand = self.metadata(name, version).get("metrics", {}).get(metric)
        inc_v = self.stage_version(name, stage)
        inc = (
            None
            if inc_v is None
            else self.metadata(name, inc_v).get("metrics", {}).get(metric)
        )
        if inc_v == version:
            return {
                "promoted": False,
                "reason": "already in stage",
                "candidate": cand,
                "incumbent": inc,
            }
        if cand is None:
            return {
                "promoted": False,
                "reason": f"candidate has no {metric}",
                "candidate": None,
                "incumbent": inc,
            }
        if inc_v is not None and inc is None:
            return {
                "promoted": False,
                "reason": f"incumbent has no {metric}",
                "candidate": cand,
                "incumbent": None,
            }
        better = inc_v is None or (cand < inc if lower_is_better else cand > inc)
        if better:
            self.promote(name, version, stage, note=f"{metric}: {cand} vs {inc}")
        return {
            "promoted": bool(better),
            "reason": "better than incumbent"
            if better and inc_v is not None
            else ("no incumbent" if better else "not better than incumbent"),
            "candidate": cand,
            "incumbent": inc,
        }
