from __future__ import annotations
import argparse
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.dataset import RoomWindowDataset
from smarthome.preprocessing import RSSIPreprocessor
from smarthome.models import RoomNetLite, CenterLoss, js_divergence_from_logits
from smarthome.metrics import room_metrics
from smarthome.utils import set_seed, save_json


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


def augment_batch(x: torch.Tensor, training: bool = True, aug_prob: float = 0.5, noise_std: float = 0.02, dropout_prob: float = 0.1) -> torch.Tensor:
    """Data augmentation for RSSI windows: Gaussian noise + random AP dropout."""
    if not training:
        return x
    b, c, t = x.shape
    # Gaussian noise on features
    if np.random.random() < aug_prob:
        noise = torch.randn_like(x) * noise_std
        x = x + noise
    # Random AP dropout (set random APs to missing value pattern)
    if np.random.random() < aug_prob:
        # x shape: [B, 3*n_aps, T] - absolute, relative, mask
        n_aps = c // 3
        for b_idx in range(b):
            # Drop 1-2 APs randomly
            n_drop = np.random.randint(1, 3)
            drop_aps = np.random.choice(n_aps, size=n_drop, replace=False)
            for ap in drop_aps:
                # Set absolute to 0 (normalized missing), relative to -1, mask to 0
                x[b_idx, ap, :] = 0.0
                x[b_idx, n_aps + ap, :] = -1.0
                x[b_idx, 2 * n_aps + ap, :] = 0.0
    return x


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--processed-dir", default=str(ROOT / "data/processed"))
    p.add_argument("--models-dir", default=str(ROOT / "models"))
    p.add_argument("--epochs", type=int, default=None)
    args = p.parse_args()

    cfg = load_config(args.config)
    set_seed(int(cfg["seed"]))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rooms = cfg["rooms"]
    pp = RSSIPreprocessor.load(Path(args.models_dir) / "preprocessor.json")
    w = int(cfg["data"]["window_size"])
    train_df = pd.read_csv(Path(args.processed_dir) / "room_train.csv")
    val_df = pd.read_csv(Path(args.processed_dir) / "room_val.csv")
    train_ds = RoomWindowDataset(train_df, pp, rooms, w)
    val_ds = RoomWindowDataset(val_df, pp, rooms, w)

    mcfg = cfg["room_model"]
    batch = int(mcfg["batch_size"])
    train_loader = DataLoader(train_ds, batch_size=batch, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch, shuffle=False)
    model = RoomNetLite(pp.feature_dim, len(rooms), int(mcfg["hidden_channels"]), int(mcfg["embedding_dim"]), float(mcfg["dropout"])).to(device)
    center_loss = CenterLoss(len(rooms), int(mcfg["embedding_dim"])).to(device)
    opt = torch.optim.AdamW(
        list(model.parameters()) + list(center_loss.parameters()),
        lr=float(mcfg["lr"]), weight_decay=float(mcfg["weight_decay"])
    )
    # LR scheduler: cosine annealing with warm restarts
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=10, T_mult=2, eta_min=1e-5)
    ce_fn = nn.CrossEntropyLoss()
    epochs = args.epochs or int(mcfg["epochs"])
    best = -1.0
    model_path = Path(args.models_dir) / "roomnet_lite.pt"

    # Early stopping
    patience = int(mcfg.get("early_stopping_patience", 10))
    min_delta = float(mcfg.get("early_stopping_min_delta", 1e-4))
    patience_counter = 0

    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for x, y, stable in train_loader:
            x, y, stable = x.to(device), y.to(device), stable.to(device)
            # Data augmentation
            x = augment_batch(x, training=model.training, aug_prob=0.3, noise_std=0.015, dropout_prob=0.1)
            logits, emb = model(x)
            ce = ce_fn(logits, y)
            c_loss = center_loss(emb, y)

            # Self-consistency regularizer: shifted temporal context should agree for stable windows.
            x_shift = torch.cat([x[:, :, :1], x[:, :, :-1]], dim=2)
            prev_logits, _ = model(x_shift)
            js = js_divergence_from_logits(logits, prev_logits)
            t_loss = (js * stable).sum() / stable.sum().clamp_min(1.0)

            loss = ce + float(mcfg["center_loss_weight"]) * c_loss + float(mcfg["temporal_loss_weight"]) * t_loss
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            losses.append(float(loss.item()))

        scheduler.step()
        metrics = evaluate(model, val_loader, device, rooms)
        print(f"epoch={epoch:03d} loss={np.mean(losses):.4f} val_acc={metrics['accuracy']:.4f} val_f1={metrics['macro_f1']:.4f} lr={opt.param_groups[0]['lr']:.6f}")
        if metrics["macro_f1"] > best + min_delta:
            best = metrics["macro_f1"]
            patience_counter = 0
            torch.save(model.state_dict(), model_path)
            save_json(metrics, Path(args.models_dir) / "room_val_metrics.json")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {epoch} (best macro-F1={best:.4f})")
                break

    print(f"Best val macro-F1={best:.4f}; saved {model_path}")


if __name__ == "__main__":
    main()
