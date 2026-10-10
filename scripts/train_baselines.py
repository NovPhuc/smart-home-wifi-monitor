from __future__ import annotations
import argparse
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.preprocessing import RSSIPreprocessor
from smarthome.dataset import RoomWindowDataset
from smarthome.utils import save_json


def to_xy(ds):
    x = np.stack([ds[i][0].numpy().reshape(-1) for i in range(len(ds))])
    y = np.asarray([int(ds[i][1]) for i in range(len(ds))])
    return x, y


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--processed-dir", default=str(ROOT / "data/processed"))
    p.add_argument("--models-dir", default=str(ROOT / "models"))
    args = p.parse_args()
    cfg = load_config(args.config)
    rooms = cfg["rooms"]
    pp = RSSIPreprocessor.load(Path(args.models_dir) / "preprocessor.json")
    w = int(cfg["data"]["window_size"])
    train = RoomWindowDataset(pd.read_csv(Path(args.processed_dir)/"room_train.csv"), pp, rooms, w)
    test = RoomWindowDataset(pd.read_csv(Path(args.processed_dir)/"room_test.csv"), pp, rooms, w)
    xtr, ytr = to_xy(train); xte, yte = to_xy(test)

    models = {
        "kNN": KNeighborsClassifier(n_neighbors=5, weights="distance"),
        "RandomForest": RandomForestClassifier(n_estimators=250, random_state=int(cfg["seed"]), n_jobs=-1),
        "MLP": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=180, random_state=int(cfg["seed"])),
    }
    results = {}
    for name, model in models.items():
        model.fit(xtr, ytr)
        pred = model.predict(xte)
        results[name] = {
            "accuracy": float(accuracy_score(yte, pred)),
            "macro_f1": float(f1_score(yte, pred, average="macro")),
        }
        print(name, results[name])
    save_json(results, Path(args.models_dir)/"baseline_metrics.json")


if __name__ == "__main__":
    main()
