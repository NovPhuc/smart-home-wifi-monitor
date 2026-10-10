from __future__ import annotations
import argparse
from pathlib import Path
import sys
import time
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.inference import SmartHomeInferenceEngine


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--input", default=str(ROOT / "data/processed/room_test.csv"))
    p.add_argument("--sleep", type=float, default=0.0)
    args = p.parse_args()
    cfg = load_config(args.config)
    engine = SmartHomeInferenceEngine(cfg, ROOT / "models")
    df = pd.read_csv(args.input).sort_values("timestamp")
    ap_cols = engine.preprocessor.ap_columns
    for _, row in df.head(120).iterrows():
        wifi = {ap: float(row[ap]) for ap in ap_cols}
        result = engine.process_scan(wifi, float(row["timestamp"]))
        print(result)
        if args.sleep: time.sleep(args.sleep)


if __name__ == "__main__":
    main()
