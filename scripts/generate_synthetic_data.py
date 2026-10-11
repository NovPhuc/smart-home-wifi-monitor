from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smarthome.config import load_config
from smarthome.utils import set_seed, ensure_dir


def make_room_fingerprints(config: dict, sessions: int = 8, scans_per_room: int = 120, aps: int = 12) -> pd.DataFrame:
    rng = np.random.default_rng(config["seed"])
    rooms = config["rooms"]
    ap_names = [f"AP_{i+1:02d}" for i in range(aps)]

    # Base RSSI centers per room - more realistic overlapping distributions
    base = {}
    for r_idx, room in enumerate(rooms):
        center = rng.uniform(-80, -50, size=aps)
        # Inject a mild room-specific signature (reduced from +14/+9 to +6/+4)
        # This makes rooms separable but with realistic overlap
        center[(r_idx * 2) % aps] += 6
        center[(r_idx * 2 + 1) % aps] += 4
        base[room] = np.clip(center, -90, -35)

    # Environmental interference that affects all rooms (neighbor WiFi, microwave, etc.)
    env_interference = rng.normal(0, 2.0, size=aps)

    rows = []
    ts = 1_780_000_000
    for s in range(sessions):
        # Session-level variations (device position, orientation, people movement)
        session_shift = rng.normal(0, 3.0, size=aps)
        device_shift = rng.normal(0, 2.0)
        # Per-session AP-specific drift (some APs more stable than others)
        ap_drift = rng.normal(0, 1.5, size=aps)

        for room in rooms:
            for i in range(scans_per_room):
                # Increased noise from 3.0 to 6.0 for more realistic variance
                # Added environmental interference
                vals = (base[room]
                        + session_shift
                        + device_shift
                        + ap_drift
                        + env_interference
                        + rng.normal(0, 6.0, size=aps))

                # More realistic missing AP pattern: correlated missingness (e.g., far APs)
                # Base missing rate 15%, higher for distant APs
                base_miss_prob = 0.15
                dist_factor = np.linspace(0.5, 1.5, aps)  # Farther APs more likely missing
                miss_prob = base_miss_prob * dist_factor
                miss = rng.random(aps) < miss_prob
                vals[miss] = -100

                # Occasional burst interference (microwave, bluetooth) affecting 2-3 APs
                if rng.random() < 0.05:
                    burst_aps = rng.choice(aps, size=rng.integers(2, 4), replace=False)
                    vals[burst_aps] += rng.normal(-10, 5, size=len(burst_aps))
                    vals = np.clip(vals, -100, -30)

                row = {
                    "timestamp": ts,
                    "session_id": f"S{s+1:02d}",
                    "device_id": "phone01",
                    "room": room,
                }
                row.update({ap: round(float(v), 2) for ap, v in zip(ap_names, vals)})
                rows.append(row)
                ts += 2
    return pd.DataFrame(rows)


def make_events(config: dict, days: int = 14) -> pd.DataFrame:
    rng = np.random.default_rng(config["seed"] + 11)
    rooms = config["rooms"]
    normal_routes = [
        ["Bedroom", "Corridor", "Bathroom", "Corridor", "LivingRoom", "Kitchen", "LivingRoom", "Corridor", "Bedroom"],
        ["LivingRoom", "Kitchen", "LivingRoom", "Corridor", "Bedroom", "Corridor", "Bathroom", "Corridor", "LivingRoom"],
        ["Bedroom", "Corridor", "LivingRoom", "Kitchen", "LivingRoom", "Corridor", "Bathroom", "Corridor", "Bedroom"],
    ]
    rows = []
    ts = 1_780_000_000
    for day in range(days):
        route = normal_routes[day % len(normal_routes)]
        hour = 7.0
        for rep in range(40):
            room = route[rep % len(route)]
            if room == "Corridor": dwell = rng.uniform(0.5, 4)
            elif room == "Bathroom": dwell = rng.uniform(5, 18)
            elif room == "Kitchen": dwell = rng.uniform(8, 35)
            elif room == "Bedroom": dwell = rng.uniform(20, 120)
            else: dwell = rng.uniform(15, 100)
            hour = 7.0 + rep * 0.32 + rng.uniform(-0.05, 0.05)
            rows.append({
                "timestamp": ts,
                "day_id": f"D{day+1:02d}",
                "room": room,
                "dwell_minutes": round(float(dwell), 3),
                "hour": round(float(hour), 3),
                "confidence": round(float(rng.uniform(0.82, 0.99)), 3),
                "is_anomaly": 0,
                "anomaly_type": "normal",
            })
            ts += int(max(2, dwell * 60))

        # Controlled anomalies on the last 4 days.
        if day >= days - 4:
            anomaly_specs = [
                ("Bathroom", 90.0, "long_bathroom_stay"),
                ("Corridor", 25.0, "long_corridor_stay"),
                ("Kitchen", 65.0, "night_activity"),
                ("Bedroom", 8.0, "unusual_transition_pattern"),
            ]
            room, dwell, kind = anomaly_specs[(day - (days - 4)) % len(anomaly_specs)]
            hour = 2.5 if kind == "night_activity" else hour
            # Increased from 7 to 50 samples per anomaly type for better training balance
            for k in range(50):
                rr = room
                if kind == "unusual_transition_pattern":
                    rr = ["Bedroom", "Kitchen", "Bedroom", "Kitchen", "Bedroom", "Kitchen", "Bedroom"][k % 7]
                # Add some variation to dwell minutes
                dwell_var = dwell if k == 0 else max(1.0, dwell / 4) * rng.uniform(0.8, 1.2)
                rows.append({
                    "timestamp": ts,
                    "day_id": f"D{day+1:02d}",
                    "room": rr,
                    "dwell_minutes": round(float(dwell_var), 3),
                    "hour": round(float(hour), 3),
                    "confidence": round(float(rng.uniform(0.82, 0.99)), 3),
                    "is_anomaly": 1,
                    "anomaly_type": kind,
                })
                ts += int(max(2, dwell_var * 60 / 4))
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--output-dir", default=str(ROOT / "data"))
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(int(config["seed"]))
    out = Path(args.output_dir)
    ensure_dir(out / "raw")
    ensure_dir(out / "anomaly")

    room_df = make_room_fingerprints(config)
    events_df = make_events(config)
    room_path = out / "raw" / "wifi_fingerprints.csv"
    event_path = out / "anomaly" / "location_events.csv"
    room_df.to_csv(room_path, index=False)
    events_df.to_csv(event_path, index=False)
    print(f"Wrote {len(room_df):,} fingerprint rows -> {room_path}")
    print(f"Wrote {len(events_df):,} trajectory rows -> {event_path}")


if __name__ == "__main__":
    main()
