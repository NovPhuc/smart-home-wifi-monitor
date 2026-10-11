from __future__ import annotations
import argparse
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.preprocessing import RSSIPreprocessor
from smarthome.utils import ensure_dir


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--input", default=str(ROOT / "data/raw/wifi_fingerprints.csv"))
    p.add_argument("--out-dir", default=str(ROOT / "data/processed"))
    p.add_argument("--models-dir", default=str(ROOT / "models"))
    args = p.parse_args()

    cfg = load_config(args.config)
    df = pd.read_csv(args.input)
    sessions = list(dict.fromkeys(df["session_id"].tolist()))
    n_train = int(cfg["data"]["room_train_sessions"])
    n_val = int(cfg["data"]["room_val_sessions"])
    n_test = int(cfg["data"]["room_test_sessions"])
    if len(sessions) < n_train + n_val + n_test:
        raise ValueError(f"Need at least {n_train+n_val+n_test} sessions, got {len(sessions)}")

    train_s = set(sessions[:n_train])
    val_s = set(sessions[n_train:n_train+n_val])
    test_s = set(sessions[n_train+n_val:n_train+n_val+n_test])
    splits = {
        "train": df[df.session_id.isin(train_s)].copy(),
        "val": df[df.session_id.isin(val_s)].copy(),
        "test": df[df.session_id.isin(test_s)].copy(),
    }
    out = ensure_dir(args.out_dir)
    for name, part in splits.items():
        part.to_csv(out / f"room_{name}.csv", index=False)
        print(name, sorted(part.session_id.unique()), len(part))

    dcfg = cfg["data"]
    pp = RSSIPreprocessor.fit(
        splits["train"],
        missing_rssi=float(dcfg["missing_rssi"]),
        min_rssi=float(dcfg["min_rssi"]),
        max_rssi=float(dcfg["max_rssi"]),
    )
    ensure_dir(args.models_dir)
    pp.save(Path(args.models_dir) / "preprocessor.json")
    print(f"Saved preprocessor with {len(pp.ap_columns)} APs")


if __name__ == "__main__":
    main()
