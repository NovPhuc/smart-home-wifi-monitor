"""Huấn luyện RoomNet-MT — multi-task: phân loại phòng + nhận diện hoạt động.

Giữ nguyên mọi cơ chế của ``train_room.py`` (early stopping, cosine restarts,
augmentation, CenterLoss, JS temporal) và THÊM loss cho head hoạt động:
``loss = ce_room + w_center·CenterLoss + w_temporal·JS + w_activity·CE_activity``.

Nhãn hoạt động đến từ ``RoomWindowDatasetMT`` — chưng cất bộ luật
``ActivityMonitor`` trong phạm vi cửa sổ (không dùng dữ liệu test).

Kết quả ghi vào ``roomnet_mt_val_metrics.json`` gồm chỉ số phòng VÀ mức đồng
thuận của head hoạt động với nhãn luật trên tập validation.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.dataset import RoomWindowDatasetMT
from smarthome.preprocessing import RSSIPreprocessor
from smarthome.models.roomnet_lite import CenterLoss, js_divergence_from_logits
from smarthome.models.roomnet_mt import ACTIVITY_LABELS, RoomNetMT
from smarthome.metrics import room_metrics
from smarthome.utils import set_seed, save_json
from train_room import augment_batch  # cùng chiến lược augmentation


def evaluate_mt(model, loader, device, rooms):
    """Trả về (room_metrics, activity_agreement, activity_confusion)."""
    model.eval()
    ys, ps, acts, preds_act = [], [], [], []
    with torch.no_grad():
        for x, y, _stable, activity in loader:
            logits, _emb, act_logits = model(x.to(device))
            pred = logits.argmax(dim=1).cpu().numpy()
            ys.extend(y.numpy().tolist())
            ps.extend(pred.tolist())
            acts.extend(activity.numpy().tolist())
            preds_act.extend(act_logits.argmax(dim=1).cpu().numpy().tolist())
    confusion = np.zeros((len(ACTIVITY_LABELS), len(ACTIVITY_LABELS)), dtype=int)
    for t, p in zip(acts, preds_act):
        confusion[t][p] += 1
    agreement = float(np.mean(np.asarray(acts) == np.asarray(preds_act))) if acts else 0.0
    return room_metrics(ys, ps, rooms), agreement, confusion.tolist()


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
    acfg = cfg.get("activity", {})
    movement_delta = float(acfg.get("movement_rssi_delta", 4.0))
    still_delta = float(acfg.get("still_rssi_delta", 1.5))

    train_df = pd.read_csv(Path(args.processed_dir) / "room_train.csv")
    val_df = pd.read_csv(Path(args.processed_dir) / "room_val.csv")
    train_ds = RoomWindowDatasetMT(train_df, pp, rooms, w, movement_delta, still_delta)
    val_ds = RoomWindowDatasetMT(val_df, pp, rooms, w, movement_delta, still_delta)

    mcfg = cfg["room_model"]
    activity_weight = float(mcfg.get("activity_loss_weight", 0.5))
    batch = int(mcfg["batch_size"])
    train_loader = DataLoader(train_ds, batch_size=batch, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch, shuffle=False)
    model = RoomNetMT(
        pp.feature_dim, len(rooms), int(mcfg["hidden_channels"]),
        int(mcfg["embedding_dim"]), float(mcfg["dropout"]),
    ).to(device)
    center_loss = CenterLoss(len(rooms), int(mcfg["embedding_dim"])).to(device)
    opt = torch.optim.AdamW(
        list(model.parameters()) + list(center_loss.parameters()),
        lr=float(mcfg["lr"]), weight_decay=float(mcfg["weight_decay"]),
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=10, T_mult=2, eta_min=1e-5)
    ce_fn = nn.CrossEntropyLoss()
    epochs = args.epochs or int(mcfg["epochs"])
    best = -1.0
    best_summary: dict = {}
    model_path = Path(args.models_dir) / "roomnet_mt.pt"

    patience = int(mcfg.get("early_stopping_patience", 10))
    min_delta = float(mcfg.get("early_stopping_min_delta", 1e-4))
    patience_counter = 0

    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for x, y, stable, activity in train_loader:
            x, y, stable, activity = (
                x.to(device), y.to(device), stable.to(device), activity.to(device),
            )
            x = augment_batch(x, training=model.training, aug_prob=0.3, noise_std=0.015, dropout_prob=0.1)
            logits, emb, act_logits = model(x)
            ce = ce_fn(logits, y)
            c_loss = center_loss(emb, y)
            act_ce = ce_fn(act_logits, activity)

            x_shift = torch.cat([x[:, :, :1], x[:, :, :-1]], dim=2)
            prev_logits, _prev_emb, _prev_act = model(x_shift)
            js = js_divergence_from_logits(logits, prev_logits)
            t_loss = (js * stable).sum() / stable.sum().clamp_min(1.0)

            loss = (
                ce
                + float(mcfg["center_loss_weight"]) * c_loss
                + float(mcfg["temporal_loss_weight"]) * t_loss
                + activity_weight * act_ce
            )
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            losses.append(float(loss.item()))

        scheduler.step()
        metrics, agreement, confusion = evaluate_mt(model, val_loader, device, rooms)
        score = metrics["macro_f1"] + activity_weight * agreement
        print(
            f"epoch={epoch:03d} loss={np.mean(losses):.4f} "
            f"val_acc={metrics['accuracy']:.4f} val_f1={metrics['macro_f1']:.4f} "
            f"act_agree={agreement:.4f} lr={opt.param_groups[0]['lr']:.6f}"
        )
        if score > best + min_delta:
            best = score
            patience_counter = 0
            torch.save(model.state_dict(), model_path)
            best_summary = {
                "room_metrics": metrics,
                "activity_agreement": agreement,
                "activity_confusion": confusion,
                "activity_labels": list(ACTIVITY_LABELS),
                "epochs_trained": epoch,
            }
            save_json(best_summary, Path(args.models_dir) / "roomnet_mt_val_metrics.json")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {epoch} (best score={best:.4f})")
                break

    print(f"Best val score={best:.4f}; saved {model_path}")


if __name__ == "__main__":
    main()
