from __future__ import annotations
import argparse
import io
import json
import sys
from pathlib import Path
import time

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from sklearn.model_selection import KFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.preprocessing import RSSIPreprocessor
from smarthome.dataset import RoomWindowDataset
from smarthome.models import RoomNetLite, CenterLoss, js_divergence_from_logits, SimpleCNN
from smarthome.metrics import room_metrics
from smarthome.utils import set_seed, save_json


def _wrap(stream, encoding="utf-8"):
    if isinstance(stream, io.TextIOWrapper) and stream.encoding.lower() != encoding.lower():
        return io.TextIOWrapper(stream.buffer, encoding=encoding)
    return stream


def _ensure_unicode_output():
    sys.stdout = _wrap(sys.stdout)
    sys.stderr = _wrap(sys.stderr)


def evaluate(model, loader, device, rooms):
    model.eval()
    ys, ps = [], []
    with torch.no_grad():
        for x, y, _ in loader:
            logits, _ = model(x.to(device))
            pred = logits.argmax(dim=1).cpu().numpy()
            ys.extend(y.numpy().tolist())
            ps.extend(pred.tolist())
    return room_metrics(ys, ps, rooms)


def train_one_fold(train_df, val_df, pp, rooms, window_size, mcfg, device, epochs, fold_idx, model_type="roomnet"):
    train_ds = RoomWindowDataset(train_df, pp, rooms, window_size)
    val_ds = RoomWindowDataset(val_df, pp, rooms, window_size)
    batch = int(mcfg["batch_size"])
    train_loader = DataLoader(train_ds, batch_size=batch, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch, shuffle=False)

    if model_type == "roomnet":
        model = RoomNetLite(pp.feature_dim, len(rooms), int(mcfg["hidden_channels"]), int(mcfg["embedding_dim"]), float(mcfg["dropout"])).to(device)
        center_loss = CenterLoss(len(rooms), int(mcfg["embedding_dim"])).to(device)
        opt = torch.optim.AdamW(
            list(model.parameters()) + list(center_loss.parameters()),
            lr=float(mcfg["lr"]), weight_decay=float(mcfg["weight_decay"])
        )
    else:  # simple_cnn
        model = SimpleCNN(pp.feature_dim, len(rooms), int(mcfg["hidden_channels"]), int(mcfg["embedding_dim"]), float(mcfg["dropout"])).to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=float(mcfg["lr"]), weight_decay=float(mcfg["weight_decay"]))

    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=10, T_mult=2, eta_min=1e-5)
    ce_fn = torch.nn.CrossEntropyLoss()
    best = -1.0
    patience = int(mcfg.get("early_stopping_patience", 10))
    min_delta = float(mcfg.get("early_stopping_min_delta", 1e-4))
    patience_counter = 0

    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for x, y, stable in train_loader:
            x, y, stable = x.to(device), y.to(device), stable.to(device)
            logits, emb = model(x)
            ce = ce_fn(logits, y)
            if model_type == "roomnet":
                c_loss = center_loss(emb, y)
                x_shift = torch.cat([x[:, :, :1], x[:, :, :-1]], dim=2)
                prev_logits, _ = model(x_shift)
                js = js_divergence_from_logits(logits, prev_logits)
                t_loss = (js * stable).sum() / stable.sum().clamp_min(1.0)
                loss = ce + float(mcfg["center_loss_weight"]) * c_loss + float(mcfg["temporal_loss_weight"]) * t_loss
            else:
                loss = ce
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            losses.append(float(loss.item()))

        scheduler.step()
        metrics = evaluate(model, val_loader, device, rooms)
        if metrics["macro_f1"] > best + min_delta:
            best = metrics["macro_f1"]
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break
    return best


def train_one_fold_simple(train_df, val_df, pp, rooms, window_size, mcfg, device, epochs):
    """Simpler version without center loss and temporal loss for SimpleCNN."""
    train_ds = RoomWindowDataset(train_df, pp, rooms, window_size)
    val_ds = RoomWindowDataset(val_df, pp, rooms, window_size)
    batch = int(mcfg["batch_size"])
    train_loader = DataLoader(train_ds, batch_size=batch, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch, shuffle=False)
    model = SimpleCNN(pp.feature_dim, len(rooms), int(mcfg["hidden_channels"]), int(mcfg["embedding_dim"]), float(mcfg["dropout"])).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(mcfg["lr"]), weight_decay=float(mcfg["weight_decay"]))
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=10, T_mult=2, eta_min=1e-5)
    ce_fn = torch.nn.CrossEntropyLoss()
    best = -1.0
    patience = int(mcfg.get("early_stopping_patience", 10))
    min_delta = float(mcfg.get("early_stopping_min_delta", 1e-4))
    patience_counter = 0

    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for x, y, _ in train_loader:
            x, y = x.to(device), y.to(device)
            logits, _ = model(x)
            loss = ce_fn(logits, y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            losses.append(float(loss.item()))

        scheduler.step()
        metrics = evaluate(model, val_loader, device, rooms)
        if metrics["macro_f1"] > best + min_delta:
            best = metrics["macro_f1"]
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break
    return best


def main():
    _ensure_unicode_output()

    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--processed-dir", default=str(ROOT / "data/processed"))
    p.add_argument("--models-dir", default=str(ROOT / "models"))
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--model", choices=["roomnet", "simple"], default="roomnet", help="Model type for K-fold CV")
    args = p.parse_args()

    cfg = load_config(args.config)
    set_seed(int(cfg["seed"]))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rooms = cfg["rooms"]
    pp = RSSIPreprocessor.load(Path(args.models_dir) / "preprocessor.json")
    w = int(cfg["data"]["window_size"])

    # Load all training data (train + val)
    train_df = pd.read_csv(Path(args.processed_dir) / "room_train.csv")
    val_df = pd.read_csv(Path(args.processed_dir) / "room_val.csv")
    full_train_df = pd.concat([train_df, val_df], ignore_index=True)

    sessions = list(dict.fromkeys(full_train_df["session_id"].tolist()))
    print(f"Total sessions for K-fold: {sessions}")

    mcfg = cfg["room_model"]
    epochs = int(mcfg["epochs"])
    n_folds = min(args.folds, len(sessions))

    kfold = KFold(n_splits=n_folds, shuffle=True, random_state=int(cfg["seed"]))
    fold_results = []

    for fold_idx, (train_idx, val_idx) in enumerate(kfold.split(sessions)):
        train_sessions = [sessions[i] for i in train_idx]
        val_sessions = [sessions[i] for i in val_idx]
        print(f"\n=== Fold {fold_idx + 1}/{n_folds} ===")
        print(f"  Train sessions: {train_sessions}")
        print(f"  Val sessions: {val_sessions}")

        fold_train_df = full_train_df[full_train_df.session_id.isin(train_sessions)].copy()
        fold_val_df = full_train_df[full_train_df.session_id.isin(val_sessions)].copy()

        if args.model == "roomnet":
            best_f1 = train_one_fold(fold_train_df, fold_val_df, pp, rooms, w, mcfg, device, epochs, fold_idx, "roomnet")
        else:
            best_f1 = train_one_fold_simple(fold_train_df, fold_val_df, pp, rooms, w, mcfg, device, epochs)
        fold_results.append(best_f1)
        print(f"  Fold {fold_idx + 1} best macro-F1: {best_f1:.4f}")

    fold_results = np.array(fold_results)
    print(f"\n=== K-Fold Cross-Validation Results ({n_folds}-fold) [{args.model}] ===")
    print(f"Per-fold macro-F1: {fold_results}")
    print(f"Mean macro-F1: {fold_results.mean():.4f} ± {fold_results.std():.4f}")
    print(f"95% CI: [{fold_results.mean() - 1.96 * fold_results.std() / np.sqrt(n_folds):.4f}, {fold_results.mean() + 1.96 * fold_results.std() / np.sqrt(n_folds):.4f}]")

    suffix = "roomnet" if args.model == "roomnet" else "simple"
    save_json({
        "model": args.model,
        "k_fold": n_folds,
        "per_fold_macro_f1": fold_results.tolist(),
        "mean_macro_f1": float(fold_results.mean()),
        "std_macro_f1": float(fold_results.std()),
        "ci_95_lower": float(fold_results.mean() - 1.96 * fold_results.std() / np.sqrt(n_folds)),
        "ci_95_upper": float(fold_results.mean() + 1.96 * fold_results.std() / np.sqrt(n_folds)),
    }, Path(args.models_dir) / f"kfold_metrics_{suffix}.json")


if __name__ == "__main__":
    main()