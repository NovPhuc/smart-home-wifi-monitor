from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description="Convert Android collection JSONL into wide RSSI fingerprint CSV")
    p.add_argument("--input", default=str(ROOT / "data/raw/android_scans.jsonl"))
    p.add_argument("--output", default=str(ROOT / "data/raw/wifi_fingerprints.csv"))
    p.add_argument("--missing-rssi", type=float, default=-100.0)
    args = p.parse_args()

    records = []
    aps = set()
    with Path(args.input).open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            aps.update(obj.get("wifi", {}).keys())
            records.append(obj)
    if not records:
        raise ValueError("No records found")
    ap_cols = sorted(aps)
    rows = []
    for obj in records:
        row = {
            "timestamp": obj["timestamp"],
            "session_id": obj.get("session_id", "android-session"),
            "device_id": obj.get("device_id", "android-phone"),
            "room": obj["room"],
        }
        wifi = obj.get("wifi", {})
        for ap in ap_cols:
            row[ap] = float(wifi.get(ap, args.missing_rssi))
        rows.append(row)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Converted {len(rows)} scans, {len(ap_cols)} APs -> {out}")


if __name__ == "__main__":
    main()
