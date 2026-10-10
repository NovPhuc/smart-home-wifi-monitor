from __future__ import annotations
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_recall_fscore_support


def room_metrics(y_true, y_pred, rooms: list[str]) -> dict:
    # Chỉ định labels rõ ràng để đảm bảo report bao gồm tất cả các room dù prediction có thể thiếu một số class
    labels = list(range(len(rooms)))
    report = classification_report(y_true, y_pred, labels=labels, target_names=rooms, output_dict=True, zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "classification_report": report,
    }


def binary_anomaly_metrics(y_true, y_pred) -> dict:
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return {"precision": float(p), "recall": float(r), "f1": float(f1)}
