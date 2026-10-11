from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from sklearn.metrics import classification_report

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.preprocessing import RSSIPreprocessor
from smarthome.dataset import RoomWindowDataset
from smarthome.models import RoomNetLite
from smarthome.topology import TopologyFilter
from smarthome.metrics import room_metrics
from smarthome.utils import save_json


def _wrap(stream, encoding="utf-8"):
    if isinstance(stream, io.TextIOWrapper) and stream.encoding.lower() != encoding.lower():
        return io.TextIOWrapper(stream.buffer, encoding=encoding)
    return stream


def _ensure_unicode_output():
    sys.stdout = _wrap(sys.stdout)
    sys.stderr = _wrap(sys.stderr)


def main():
    _ensure_unicode_output()

    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--processed-dir", default=str(ROOT / "data/processed"))
    p.add_argument("--models-dir", default=str(ROOT / "models"))
    args = p.parse_args()

    cfg = load_config(args.config)
    rooms = cfg["rooms"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    pp = RSSIPreprocessor.load(Path(args.models_dir) / "preprocessor.json")
    df = pd.read_csv(Path(args.processed_dir) / "room_test.csv")
    ds = RoomWindowDataset(df, pp, rooms, int(cfg["data"]["window_size"]))
    loader = DataLoader(ds, batch_size=128, shuffle=False)
    mcfg = cfg["room_model"]
    model = RoomNetLite(
        pp.feature_dim,
        len(rooms),
        int(mcfg["hidden_channels"]),
        int(mcfg["embedding_dim"]),
        float(mcfg["dropout"]),
    ).to(device)
    model.load_state_dict(
        torch.load(Path(args.models_dir) / "roomnet_lite.pt", map_location=device)
    )
    model.eval()

    # Topology filter for end-to-end latency measurement
    topo_filter = TopologyFilter(rooms, cfg["room_topology"])

    ys, ps = [], []
    latencies_model = []
    latencies_e2e = []
    with torch.no_grad():
        for x, y, _ in loader:
            # Model-only latency
            x = x.to(device)
            t0 = time.perf_counter()
            logits, _ = model(x)
            if device == "cuda":
                torch.cuda.synchronize()
            latencies_model.append((time.perf_counter() - t0) * 1000.0 / x.shape[0])
            
            # End-to-end latency (softmax + topology filter) - per sample
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            t0_e2e = time.perf_counter()
            for i in range(probs.shape[0]):
                topo_filter.update(probs[i])
            latencies_e2e.append((time.perf_counter() - t0_e2e) * 1000.0 / x.shape[0])
            # Reset topology filter for next batch
            topo_filter.reset()
            
            ys.extend(y.numpy().tolist())
            ps.extend(logits.argmax(1).cpu().numpy().tolist())

    # When the test split contains only one observed class, sklearn raises:
    #   ValueError: Number of classes, 1, does not match size of target_names, N
    # Handle it by calling classification_report with an explicit labels list that
    # covers every known room index, so the report always normalises across the full
    # room set regardless of which classes happen to appear in the split.
    try:
        result = room_metrics(ys, ps, rooms)
    except ValueError as exc:
        if ("Number of classes" in str(exc)) and (
            "does not match size of target_names" in str(exc)
        ):
            label_to_name = {i: room for i, room in enumerate(rooms)}
            all_labels = sorted(label_to_name.keys())
            result = classification_report(
                ys,
                ps,
                labels=all_labels,
                target_names=[label_to_name[l] for l in all_labels],
                output_dict=True,
                zero_division=0.0,
            )
            result = dict(result)
        else:
            raise

    result["mean_inference_ms_per_sample"] = float(
        sum(latencies_model) / max(len(latencies_model), 1)
    )
    result["mean_e2e_latency_ms_per_sample"] = float(
        sum(latencies_e2e) / max(len(latencies_e2e), 1)
    )
    save_json(result, Path(args.models_dir) / "room_test_metrics.json")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
