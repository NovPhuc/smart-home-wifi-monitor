from __future__ import annotations
import argparse
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.dataset import AnomalyFeatureBuilder
from smarthome.models import GRUAutoencoder, per_sequence_reconstruction_score
from smarthome.metrics import binary_anomaly_metrics
from smarthome.anomaly import RuleEngine
from smarthome.utils import save_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--input", default=str(ROOT / "data/anomaly/location_events.csv"))
    p.add_argument("--models-dir", default=str(ROOT / "models"))
    args = p.parse_args()
    cfg = load_config(args.config)
    df = pd.read_csv(args.input).sort_values(["day_id", "timestamp"])
    builder = AnomalyFeatureBuilder(cfg["rooms"], float(cfg["data"].get("anomaly_feature_max_dwell_minutes", 180)))
    acfg = cfg["anomaly_model"]
    seq_len = int(cfg["data"]["anomaly_sequence_length"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = GRUAutoencoder(builder.feature_dim, int(acfg["hidden_size"]), int(acfg["latent_size"]), int(acfg["num_layers"])).to(device)
    model.load_state_dict(torch.load(Path(args.models_dir) / "gru_autoencoder.pt", map_location=device))
    model.eval()
    with (Path(args.models_dir) / "anomaly_threshold.json").open() as f:
        threshold_info = json.load(f)
    threshold = float(threshold_info["threshold"])
    # Fix A (lỗi rò rỉ #8): chỉ đánh giá trên các ngày test đã được tách riêng
    # khi huấn luyện (train_anomaly.py ghi "test_days" vào threshold JSON).
    # JSON cũ không có khóa này -> giữ hành vi cũ (đánh giá mọi ngày).
    test_days = threshold_info.get("test_days")
    if test_days:
        df = df[df["day_id"].isin(set(test_days))].copy()

    y_true, ae_pred, hybrid_pred, scores = [], [], [], []
    with torch.no_grad():
        for _, g in df.groupby("day_id"):
            g = g.reset_index(drop=True)
            feats = builder.from_event_frame(g)
            rule_engine = RuleEngine(cfg["rooms"], cfg["room_topology"], cfg["rules"])
            rule_flags = []
            prev = None
            for _, row in g.iterrows():
                reasons = rule_engine.evaluate(
                    str(row["room"]), prev, float(row["dwell_minutes"]), float(row["hour"])
                )
                rule_flags.append(bool(reasons))
                prev = str(row["room"])

            for end in range(seq_len - 1, len(g)):
                start = end - seq_len + 1
                x = torch.tensor(feats[start:end+1], dtype=torch.float32, device=device).unsqueeze(0)
                recon = model(x)
                score = float(per_sequence_reconstruction_score(
                    recon, x, builder.room_dim,
                    float(acfg["room_loss_weight"]), float(acfg["continuous_loss_weight"])
                ).item())
                label = int(g.loc[start:end, "is_anomaly"].max())
                deep = int(score > threshold)
                rule = int(any(rule_flags[start:end+1]))
                y_true.append(label)
                ae_pred.append(deep)
                hybrid_pred.append(int(deep or rule))
                scores.append(score)

    metrics = {
        "ae_only": binary_anomaly_metrics(y_true, ae_pred),
        "hybrid_ae_plus_rules": binary_anomaly_metrics(y_true, hybrid_pred),
        "threshold": threshold,
        "samples": len(y_true),
        "mean_score": float(np.mean(scores)),
    }
    save_json(metrics, Path(args.models_dir) / "anomaly_test_metrics.json")
    print(metrics)


if __name__ == "__main__":
    main()
