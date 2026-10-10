from __future__ import annotations
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path
import requests
import json
import csv

ROOT = Path(__file__).resolve().parents[1]


def scan_windows_wifi() -> dict[str, float]:
    try:
        output = subprocess.check_output(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except FileNotFoundError:
        print("Error: netsh not found. This scanner requires Windows with WiFi adapter.", file=sys.stderr)
        return {}
    except subprocess.CalledProcessError as e:
        print(f"Error: netsh failed with code {e.returncode}", file=sys.stderr)
        return {}

    aps: dict[str, float] = {}
    lines = output.splitlines()
    i = 0
    while i < len(lines):
        bssid_match = re.search(r"BSSID\s+\d+\s*:\s*([0-9a-fA-F:]{17})", lines[i])
        if bssid_match:
            bssid = bssid_match.group(1).lower()
            rssi = None
            for j in range(i + 1, min(i + 8, len(lines))):
                signal_match = re.search(r"(\d+)\s*%", lines[j])
                if signal_match:
                    pct = int(signal_match.group(1))
                    rssi = float((pct * 0.5) - 100.0)
                    break
            if rssi is not None:
                aps[bssid] = rssi
        i += 1
    return aps


def map_to_ap_slots(aps: dict[str, float]) -> dict[str, float]:
    sorted_aps = sorted(aps.items(), key=lambda x: x[1], reverse=True)
    wifi: dict[str, float] = {}
    for idx, (bssid, rssi) in enumerate(sorted_aps[:12]):
        wifi[f"AP_{idx + 1:02d}"] = rssi
    return wifi


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:5000")
    p.add_argument("--room", required=True, help="Room label for collection (e.g., LivingRoom)")
    p.add_argument("--session", default="real-session-01")
    p.add_argument("--sleep", type=float, default=1.0)
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--output", default=str(ROOT / "data/raw/real_scans.csv"))
    args = p.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sent = 0
    rows = []
    while True:
        aps = scan_windows_wifi()
        if not aps:
            print("No WiFi networks found, waiting...")
            time.sleep(args.sleep)
            continue

        wifi = map_to_ap_slots(aps)
        payload = {
            "wifi": wifi,
            "room": args.room,
            "timestamp": time.time(),
            "session_id": args.session,
            "device_id": "windows-pc",
        }
        try:
            r = requests.post(f"{args.url}/api/collect", json=payload, timeout=5)
            data = r.json()
            print(f"{r.status_code} room={args.room} aps={len(aps)} saved={data.get('ok')}")
            row = {
                "timestamp": payload["timestamp"],
                "session_id": args.session,
                "device_id": "windows-pc",
                "room": args.room,
                **wifi,
            }
            rows.append(row)
        except Exception as e:
            print(f"Error: {e}")

        sent += 1
        if args.limit and sent >= args.limit:
            break

        time.sleep(args.sleep)

    if rows:
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nSaved {len(rows)} labeled scans to {out_path}")
        print("Next step: retrain model with --input data/raw/real_scans.csv")


if __name__ == "__main__":
    main()
