from __future__ import annotations
import argparse
from pathlib import Path
import sys
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--input", default=str(ROOT / "data/processed/room_test.csv"))
    p.add_argument("--url", default="http://127.0.0.1:5000")
    p.add_argument("--sleep", type=float, default=0.5)
    p.add_argument("--limit", type=int, default=120)
    args = p.parse_args()

    cfg = load_config(args.config)
    import pandas as pd
    df = pd.read_csv(args.input).sort_values("timestamp")
    metadata_cols = {"timestamp", "session_id", "device_id", "room", "is_anomaly", "anomaly_type", "confidence"}
    ap_cols = [c for c in df.columns if c not in metadata_cols]

    for _, row in df.head(args.limit).iterrows():
        wifi = {ap: float(row[ap]) for ap in ap_cols}
        payload = {
            "wifi": wifi,
            "timestamp": float(row["timestamp"]),
        }
        try:
            r = requests.post(f"{args.url}/api/scan", json=payload, timeout=5)
            print(r.status_code, r.json().get("room"), r.json().get("status"))
        except Exception as e:
            print("Error:", e)
            break
        if args.sleep:
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
