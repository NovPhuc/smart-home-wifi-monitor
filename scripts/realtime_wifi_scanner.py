from __future__ import annotations
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path
import requests

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
    p.add_argument("--sleep", type=float, default=1.0)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    sent = 0
    while True:
        aps = scan_windows_wifi()
        if not aps:
            print("No WiFi networks found")
            time.sleep(args.sleep)
            continue

        wifi = map_to_ap_slots(aps)
        payload = {
            "wifi": wifi,
            "timestamp": time.time(),
        }
        try:
            r = requests.post(f"{args.url}/api/scan", json=payload, timeout=5)
            data = r.json()
            print(
                f"{r.status_code} room={data.get('room')} status={data.get('status')} "
                f"aps={len(aps)} conf={data.get('confidence', 0):.2f}"
            )
        except Exception as e:
            print(f"Error: {e}")

        sent += 1
        if args.limit and sent >= args.limit:
            break

        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
