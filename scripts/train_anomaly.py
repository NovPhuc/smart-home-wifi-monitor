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
    days = list(dict.fromkeys(normal["day_id"].tolist()))
    split = max(1, int(len(days) * 0.8))
    train_days = set(days[:split])
    val_days = set(days[split:]) or {days[-1]}

    builder = AnomalyFeatureBuilder(cfg["rooms"], float(cfg["data"].get("anomaly_feature_max_dwell_minutes", 180)))
    seq_len = int(cfg["data"]["anomaly_sequence_length"])

    def make_ds(day_set):
        sequences = []
        for _, g in normal[normal.day_id.isin(day_set)].groupby("day_id"):
            feat = builder.from_event_frame(g.sort_values("timestamp"))
            ds = SequenceDataset(feat, seq_len)
            sequences.extend(ds.sequences)
        class _DS(torch.utils.data.Dataset):
            def __len__(self): return len(sequences)
            def __getitem__(self, i): return torch.from_numpy(sequences[i])
        return _DS()

    train_ds = make_ds(train_days)
    val_ds = make_ds(val_days)
    if len(train_ds) == 0 or len(val_ds) == 0:
        raise ValueError("Not enough normal trajectory data for anomaly sequence training.")

    acfg = cfg["anomaly_model"]
    train_loader = DataLoader(train_ds, batch_size=int(acfg["batch_size"]), shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=int(acfg["batch_size"]), shuffle=False)
    model = GRUAutoencoder(builder.feature_dim, int(acfg["hidden_size"]), int(acfg["latent_size"]), int(acfg["num_layers"])).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(acfg["lr"]), weight_decay=1e-4)
    rw, cw = float(acfg["room_loss_weight"]), float(acfg["continuous_loss_weight"])
    epochs = args.epochs or int(acfg["epochs"])
    best = float("inf")
    path = Path(args.models_dir) / "gru_autoencoder.pt"

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
        scores = collect_scores(model, val_loader, device, builder.room_dim, rw, cw)
        val_mean = float(scores.mean())
        print(f"epoch={epoch:03d} train_loss={np.mean(losses):.4f} val_score={val_mean:.4f}")
        if val_mean < best:
            best = val_mean
            torch.save(model.state_dict(), path)

    model.load_state_dict(torch.load(path, map_location=device))
    scores = collect_scores(model, val_loader, device, builder.room_dim, rw, cw)
    q = float(acfg["threshold_quantile"])
    threshold = float(np.quantile(scores, q))
    save_json({
        "threshold": threshold,
        "quantile": q,
        "normal_val_mean": float(scores.mean()),
        "normal_val_std": float(scores.std()),
        "sequence_length": seq_len,
    }, Path(args.models_dir) / "anomaly_threshold.json")
    print(f"Saved anomaly model and threshold={threshold:.5f}")


if __name__ == "__main__":
    main()
