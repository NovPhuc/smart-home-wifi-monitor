from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_recall_fscore_support


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _first_json(directory: Path, name: str, fallback_dir: Path | None = None) -> dict:
    data = _read_json(directory / name)
    if not data and fallback_dir is not None and fallback_dir != directory:
        data = _read_json(fallback_dir / name)
    return data


def collect_model_metrics(home_dir: str | Path, shared_dir: str | Path | None = None) -> dict:
    """Assemble the room, anomaly and baseline metrics shown in the dashboard.

    Room metrics are specific to the home's own model. Anomaly and baseline
    metrics come from the home directory when trained there, otherwise from the
    shared ``models/`` artifacts, so the endpoints are populated instead of
    always returning empty dictionaries.
    """
    home = Path(home_dir)
    shared = Path(shared_dir) if shared_dir is not None else None
    room = _read_json(home / "room_test_metrics.json")
    anomaly = _first_json(home, "anomaly_test_metrics.json", shared)
    baselines = _first_json(home, "baseline_metrics.json", shared)
    hybrid = anomaly.get("hybrid_ae_plus_rules") or {}
    return {
        "room_model": {
            "accuracy": room.get("accuracy"),
            "macro_f1": room.get("macro_f1"),
            "mean_inference_ms": room.get("mean_inference_ms_per_sample"),
        },
        "anomaly_model": {
            "precision": hybrid.get("precision"),
            "recall": hybrid.get("recall"),
            "f1": hybrid.get("f1"),
            "threshold": anomaly.get("threshold"),
        },
        "baselines": baselines,
    }


def room_metrics(y_true, y_pred, rooms: list[str]) -> dict:
    # Chỉ định labels rõ ràng để đảm bảo report bao gồm tất cả các room dù prediction có thể thiếu một số class
    labels = list(range(len(rooms)))
    report = classification_report(y_true, y_pred, labels=labels, target_names=rooms, output_dict=True, zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "classification_report": report,
    }


def binary_anomaly_metrics(y_true, y_pred) -> dict:
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return {"precision": float(p), "recall": float(r), "f1": float(f1)}
