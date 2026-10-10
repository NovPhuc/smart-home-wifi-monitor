from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def read_input(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip(): rows.append(json.loads(line))
        return pd.DataFrame(rows)
    return pd.read_csv(path)


def main():
    p = argparse.ArgumentParser(description="Compress chronological room predictions into completed room visits for GRU-AE training")
    p.add_argument("--input", default=str(ROOT / "data/processed/live_predictions.jsonl"), help="CSV/JSONL with timestamp, room and optional confidence/day_id")
    p.add_argument("--output", default=str(ROOT / "data/anomaly/location_events_real.csv"))
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    args = p.parse_args()
    with Path(args.config).open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    tz_offset = float(cfg.get("time", {}).get("timezone_offset_hours", 7))
    df = read_input(Path(args.input)).sort_values("timestamp").reset_index(drop=True)
    if not {"timestamp", "room"}.issubset(df.columns):
        raise ValueError("Input must contain timestamp and room")
    if "confidence" not in df.columns: df["confidence"] = 1.0
    if "day_id" not in df.columns:
        df["day_id"] = (pd.to_datetime(df["timestamp"], unit="s", utc=True) + pd.to_timedelta(tz_offset, unit="h")).dt.strftime("%Y-%m-%d")

    events = []
    start = 0
    for i in range(1, len(df) + 1):
        boundary = i == len(df) or df.loc[i, "room"] != df.loc[start, "room"] or df.loc[i, "day_id"] != df.loc[start, "day_id"]
        if not boundary:
            continue
        first = df.loc[start]
        last = df.loc[i - 1]
        dwell = max(0.0, (float(last["timestamp"]) - float(first["timestamp"])) / 60.0)
        dt = pd.to_datetime(float(last["timestamp"]), unit="s", utc=True) + pd.to_timedelta(tz_offset, unit="h")
        events.append({
            "timestamp": float(last["timestamp"]),
            "day_id": str(first["day_id"]),
            "room": str(first["room"]),
            "dwell_minutes": dwell,
            "hour": dt.hour + dt.minute / 60.0,
            "confidence": float(df.loc[start:i-1, "confidence"].mean()),
            "is_anomaly": 0,
            "anomaly_type": "normal",
        })
        start = i
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(events).to_csv(out, index=False)
    print(f"Wrote {len(events)} completed room visits -> {out}")


if __name__ == "__main__":
    main()
