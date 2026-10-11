from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.dataset import AnomalyFeatureBuilder, SequenceDataset
from smarthome.models import GRUAutoencoder, reconstruction_loss, per_sequence_reconstruction_score
from smarthome.utils import set_seed, save_json


def collect_scores(model, loader, device, room_dim, rw, cw):
    scores = []
    model.eval()
    with torch.no_grad():
        for x in loader:
            x = x.to(device)
            recon = model(x)
            s = per_sequence_reconstruction_score(recon, x, room_dim, rw, cw)
            scores.extend(s.cpu().numpy().tolist())
    return np.asarray(scores, dtype=np.float64)


def find_best_threshold(val_scores_normal: np.ndarray, val_scores_anomaly: np.ndarray | None,
                         quantiles: list[float] = [0.90, 0.95, 0.97, 0.99, 0.995]) -> tuple[float, float, dict]:
    """Grid search for best quantile threshold based on validation data.
    If anomaly validation data available, optimize F1. Otherwise use quantile on normal.
    """
    results = {}
    if val_scores_anomaly is not None and len(val_scores_anomaly) > 0:
        # Optimize F1 on validation set with anomalies
        best_f1 = -1.0
        best_q = quantiles[0]
        best_thresh = 0.0
        for q in quantiles:
            thresh = float(np.quantile(val_scores_normal, q))
            y_true = np.concatenate([np.zeros(len(val_scores_normal)), np.ones(len(val_scores_anomaly))])
            y_pred = np.concatenate([
                (val_scores_normal > thresh).astype(int),
                (val_scores_anomaly > thresh).astype(int)
            ])
            if y_pred.sum() == 0:
                f1 = 0.0
            else:
                tp = ((y_pred == 1) & (y_true == 1)).sum()
                fp = ((y_pred == 1) & (y_true == 0)).sum()
                fn = ((y_pred == 0) & (y_true == 1)).sum()
                prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            results[q] = {"threshold": thresh, "f1": f1, "precision": prec, "recall": rec}
            if f1 > best_f1:
                best_f1 = f1
                best_q = q
                best_thresh = thresh
        return best_thresh, best_q, results
    else:
        # No anomaly validation data - use default quantile
        q = float(quantiles[-2])  # 0.99 default
        thresh = float(np.quantile(val_scores_normal, q))
        return thresh, q, {q: {"threshold": thresh}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--input", default=str(ROOT / "data/anomaly/location_events.csv"))
    p.add_argument("--models-dir", default=str(ROOT / "models"))
    p.add_argument("--epochs", type=int, default=None)
    args = p.parse_args()

    cfg = load_config(args.config)
    set_seed(int(cfg["seed"]))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    df = pd.read_csv(args.input)
    normal = df[df["is_anomaly"] == 0].copy()
    anomaly = df[df["is_anomaly"] == 1].copy()
    days = list(dict.fromkeys(normal["day_id"].tolist()))
    anomaly_days = list(dict.fromkeys(anomaly["day_id"].tolist()))
    # Fix A (lỗi rò rỉ #8): tách 3 phần KHÔNG giao nhau theo ngày —
    #   train:     ~70% ngày đầu  -> huấn luyện AE (chỉ sự kiện normal)
    #   threshold: 2 ngày kế tiếp -> early stopping + chọn ngưỡng (normal + anomaly)
    #   test:      các ngày cuối  -> CHỈ dùng để đánh giá trong evaluate_anomaly.py
    # Trước đây các ngày dùng chọn ngưỡng (D13–D14) nằm trong tập đánh giá.
    n_days = len(days)
    n_train = max(1, int(n_days * 0.7) + 1)
    n_threshold = 2
    train_days = set(days[:n_train])
    val_days = set(days[n_train:n_train + n_threshold]) or {days[-1]}
    test_days = [d for d in days[n_train + n_threshold:]]
    val_anomaly_days = set(anomaly_days[:n_threshold]) or set()

    builder = AnomalyFeatureBuilder(cfg["rooms"], float(cfg["data"].get("anomaly_feature_max_dwell_minutes", 180)))
    seq_len = int(cfg["data"]["anomaly_sequence_length"])

    def make_ds(day_set, df_source=normal):
        sequences = []
        for _, g in df_source[df_source.day_id.isin(day_set)].groupby("day_id"):
            feat = builder.from_event_frame(g.sort_values("timestamp"))
            ds = SequenceDataset(feat, seq_len)
            sequences.extend(ds.sequences)
        class _DS(torch.utils.data.Dataset):
            def __len__(self): return len(sequences)
            def __getitem__(self, i): return torch.from_numpy(sequences[i])
        return _DS()

    train_ds = make_ds(train_days)
    val_ds = make_ds(val_days)
    val_anomaly_ds = make_ds(val_anomaly_days, anomaly) if val_anomaly_days else None
    if len(train_ds) == 0 or len(val_ds) == 0:
        raise ValueError("Not enough normal trajectory data for anomaly sequence training.")

    acfg = cfg["anomaly_model"]
    train_loader = DataLoader(train_ds, batch_size=int(acfg["batch_size"]), shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=int(acfg["batch_size"]), shuffle=False)
    val_anomaly_loader = DataLoader(val_anomaly_ds, batch_size=int(acfg["batch_size"]), shuffle=False) if val_anomaly_ds else None
    model = GRUAutoencoder(builder.feature_dim, int(acfg["hidden_size"]), int(acfg["latent_size"]), int(acfg["num_layers"])).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(acfg["lr"]), weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=10, T_mult=2, eta_min=1e-5)
    rw, cw = float(acfg["room_loss_weight"]), float(acfg["continuous_loss_weight"])
    epochs = args.epochs or int(acfg["epochs"])
    best = float("inf")
    path = Path(args.models_dir) / "gru_autoencoder.pt"

    # Early stopping
    patience = int(acfg.get("early_stopping_patience", 15))
    min_delta = float(acfg.get("early_stopping_min_delta", 1e-4))
    patience_counter = 0

    for epoch in range(1, epochs + 1):
        model.train(); losses = []
        for x in train_loader:
            x = x.to(device)
            recon = model(x)
            loss = reconstruction_loss(recon, x, builder.room_dim, rw, cw)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            losses.append(float(loss.item()))
        scheduler.step()
        scores = collect_scores(model, val_loader, device, builder.room_dim, rw, cw)
        val_mean = float(scores.mean())
        print(f"epoch={epoch:03d} train_loss={np.mean(losses):.4f} val_score={val_mean:.4f} lr={opt.param_groups[0]['lr']:.6f}")
        if val_mean < best - min_delta:
            best = val_mean
            patience_counter = 0
            torch.save(model.state_dict(), path)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {epoch} (best val_score={best:.4f})")
                break

    model.load_state_dict(torch.load(path, map_location=device))
    val_scores_normal = collect_scores(model, val_loader, device, builder.room_dim, rw, cw)
    val_scores_anomaly = collect_scores(model, val_anomaly_loader, device, builder.room_dim, rw, cw) if val_anomaly_loader else None

    # Grid search for best threshold quantile
    quantiles = [0.90, 0.95, 0.97, 0.99, 0.995]
    threshold, best_q, threshold_results = find_best_threshold(val_scores_normal, val_scores_anomaly, quantiles)

    save_json({
        "threshold": threshold,
        "quantile": best_q,
        "normal_val_mean": float(val_scores_normal.mean()),
        "normal_val_std": float(val_scores_normal.std()),
        "sequence_length": seq_len,
        "threshold_grid_search": threshold_results,
        "train_days": sorted(train_days),
        "threshold_days": sorted(val_days),
        "test_days": sorted(test_days),
    }, Path(args.models_dir) / "anomaly_threshold.json")
    print(f"Saved anomaly model and threshold={threshold:.5f} (quantile={best_q})")


if __name__ == "__main__":
    main()
