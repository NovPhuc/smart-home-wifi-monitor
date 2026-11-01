"""Ensemble meta-learning: đánh giá nhiều ứng viên trên VALIDATION, chọn best.

Ứng viên:
- Torch (nếu artifact tồn tại trong --models-dir): RoomNetLite, SimpleCNN,
  RoomNetMT — đánh giá lại trên cùng loader để so sánh công bằng.
- Sklearn: kNN, RandomForest, MLP — huấn luyện trên cửa sổ duỗi phẳng của tập
  TRAIN, lưu joblib ``model_<tên>.joblib``.

Kết quả: ``ensemble_val_metrics.json`` (chỉ số từng ứng viên trên val) và
``model_choice.json`` (người thắng + kiểu đầu vào). Tập test KHÔNG bị đụng tới.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from sklearn.metrics import accuracy_score, f1_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.preprocessing import RSSIPreprocessor
from smarthome.dataset import RoomWindowDataset
from smarthome.models import RoomNetLite, RoomNetMT, SimpleCNN
from smarthome.ensemble import candidate_feature_kind, select_best_candidate
from smarthome.utils import save_json

TORCH_CANDIDATES = {
    "RoomNetLite": ("roomnet_lite.pt", RoomNetLite),
    "SimpleCNN": ("simple_cnn.pt", SimpleCNN),
    "RoomNetMT": ("roomnet_mt.pt", RoomNetMT),
}
SKLEARN_CANDIDATES = {
    "kNN": lambda seed: KNeighborsClassifier(n_neighbors=5, weights="distance"),
    "RandomForest": lambda seed: RandomForestClassifier(n_estimators=250, random_state=seed, n_jobs=-1),
    "MLP": lambda seed: MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=180, random_state=seed),
}


def to_xy(ds):
    x = np.stack([ds[i][0].numpy().reshape(-1) for i in range(len(ds))])
    y = np.asarray([int(ds[i][1]) for i in range(len(ds))])
    return x, y


def evaluate_torch_candidate(model_path: Path, model_cls, loader, device, rooms) -> dict:
    model = model_cls(
        in_channels=loader.dataset.preprocessor.feature_dim,
        num_rooms=len(rooms),
    ).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    ys, ps = [], []
    with torch.no_grad():
        for batch in loader:
            x, y = batch[0].to(device), batch[1]
            logits = model(x)[0]
            ys.extend(y.numpy().tolist())
            ps.extend(logits.argmax(dim=1).cpu().numpy().tolist())
    return room_metrics_dict(ys, ps, rooms)


def room_metrics_dict(ys, ps, rooms) -> dict:
    from smarthome.metrics import room_metrics

    return room_metrics(ys, ps, rooms)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--processed-dir", default=str(ROOT / "data/processed"))
    p.add_argument("--models-dir", default=str(ROOT / "models"))
    args = p.parse_args()

    cfg = load_config(args.config)
    seed = int(cfg["seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rooms = cfg["rooms"]
    models_dir = Path(args.models_dir)
    pp = RSSIPreprocessor.load(models_dir / "preprocessor.json")
    w = int(cfg["data"]["window_size"])

    val_ds = RoomWindowDataset(pd.read_csv(Path(args.processed_dir) / "room_val.csv"), pp, rooms, w)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)

    candidates: dict[str, dict] = {}

    # --- Torch: đánh giá artifact đã huấn luyện trên cùng tập validation ---
    for name, (artifact, model_cls) in TORCH_CANDIDATES.items():
        model_path = models_dir / artifact
        if not model_path.exists():
            print(f"[ensemble] bo qua {name} (khong co {artifact})")
            continue
        metrics = evaluate_torch_candidate(model_path, model_cls, val_loader, device, rooms)
        candidates[name] = metrics
        print(f"[ensemble] {name}: acc={metrics['accuracy']:.4f} f1={metrics['macro_f1']:.4f}")

    # --- Sklearn: huấn luyện trên train, đánh giá trên val ---
    train_ds = RoomWindowDataset(pd.read_csv(Path(args.processed_dir) / "room_train.csv"), pp, rooms, w)
    xtr, ytr = to_xy(train_ds)
    xva, yva = to_xy(val_ds)
    for name, factory in SKLEARN_CANDIDATES.items():
        model = factory(seed)
        model.fit(xtr, ytr)
        pred = model.predict(xva)
        candidates[name] = {
            "accuracy": float(accuracy_score(yva, pred)),
            "macro_f1": float(f1_score(yva, pred, average="macro")),
        }
        joblib.dump(model, models_dir / f"model_{name}.joblib")
        print(f"[ensemble] {name}: acc={candidates[name]['accuracy']:.4f} f1={candidates[name]['macro_f1']:.4f}")

    chosen, best = select_best_candidate(candidates)
    save_json(
        {"candidates": candidates, "chosen": chosen, "selected_on": "validation"},
        models_dir / "ensemble_val_metrics.json",
    )
    save_json(
        {
            "chosen": chosen,
            "feature": candidate_feature_kind(chosen),
            "val_macro_f1": best["macro_f1"],
            "val_accuracy": best["accuracy"],
        },
        models_dir / "model_choice.json",
    )
    print(f"[ensemble] CHON: {chosen} (val f1={best['macro_f1']:.4f})")


if __name__ == "__main__":
    main()
