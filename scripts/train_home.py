from __future__ import annotations

import argparse
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smarthome.config import load_config
from smarthome.storage import SmartHomeDatabase


def _wrap(stream, encoding="utf-8"):
    if isinstance(stream, io.TextIOWrapper) and stream.encoding.lower() != encoding.lower():
        return io.TextIOWrapper(stream.buffer, encoding=encoding)
    return stream


def _ensure_unicode_output():
    sys.stdout = _wrap(sys.stdout)
    sys.stderr = _wrap(sys.stderr)


def _safe_text(data):
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


def _print_stdout(text):
    if not text.strip():
        return
    sys.stdout.write(text.rstrip("\n") + "\n")


def _print_stderr(text):
    if not text.strip():
        return
    sys.stderr.write(text.rstrip("\n") + "\n")


def export_home_dataset(db, home_id, output):
    scans = db.export_scans(home_id)
    if not scans:
        raise ValueError("The home has no collected Wi-Fi scans")

    records = []
    for scan in scans:
        wifi = json.loads(scan.pop("wifi_json"))
        records.append({**scan, **wifi})
    frame = pd.DataFrame(records)
    rooms = list(dict.fromkeys(frame["room"].tolist()))
    if len(rooms) < 2:
        raise ValueError("At least two rooms are required")

    session_sets = [set(frame.loc[frame.room == room, "session_id"].unique()) for room in rooms]
    common_sessions = sorted(set.intersection(*session_sets))
    if len(common_sessions) < 3:
        raise ValueError("Need at least three session codes collected in every room")
    frame = frame[frame.session_id.isin(common_sessions)].copy()
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    return rooms, common_sessions


def main():
    _ensure_unicode_output()

    parser = argparse.ArgumentParser(description="Train an isolated room model from one SQLite home")
    parser.add_argument("--home-id", type=int, required=True)
    parser.add_argument("--database", default=str(ROOT / "data" / "smarthome.db"))
    parser.add_argument("--epochs", type=int, default=None)
    args = parser.parse_args()

    db = SmartHomeDatabase(args.database)
    home_dir = ROOT / "data" / "homes" / str(args.home_id)
    model_dir = ROOT / "models" / "homes" / str(args.home_id)
    raw_csv = home_dir / "wifi_fingerprints.csv"
    processed_dir = home_dir / "processed"
    config_path = model_dir / "config.yaml"
    model_dir.mkdir(parents=True, exist_ok=True)

    db.set_model_status(args.home_id, "TRAINING")
    try:
        rooms, sessions = export_home_dataset(db, args.home_id, raw_csv)
        config = deepcopy(load_config(ROOT / "config.yaml"))
        config["rooms"] = rooms
        config["room_topology"] = {room: rooms for room in rooms}
        config["rules"]["room_max_dwell_minutes"] = {
            room["name"]: float(room["max_dwell_minutes"])
            for room in db.list_rooms(args.home_id)
            if room["name"] in rooms
        }
        config["data"]["room_train_sessions"] = len(sessions) - 2
        config["data"]["room_val_sessions"] = 1
        config["data"]["room_test_sessions"] = 1
        with config_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(config, handle, allow_unicode=True, sort_keys=False)

        commands = [
            [sys.executable, str(ROOT / "scripts" / "prepare_data.py"), "--config", str(config_path), "--input", str(raw_csv), "--out-dir", str(processed_dir), "--models-dir", str(model_dir)],
            [sys.executable, str(ROOT / "scripts" / "train_room.py"), "--config", str(config_path), "--processed-dir", str(processed_dir), "--models-dir", str(model_dir)],
            [sys.executable, str(ROOT / "scripts" / "evaluate_room.py"), "--config", str(config_path), "--processed-dir", str(processed_dir), "--models-dir", str(model_dir)],
        ]
        if args.epochs:
            commands[1].extend(["--epochs", str(args.epochs)])

        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        for command in commands:
            proc = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
            if proc.returncode != 0:
                script = Path(command[0]).name
                raise RuntimeError(
                    f"{script} failed (exit {proc.returncode}):\\n"
                    f"STDOUT:\\n{_safe_text(proc.stdout)}\\n"
                    f"STDERR:\\n{_safe_text(proc.stderr)}"
                )
            _print_stdout(_safe_text(proc.stdout))
            _print_stderr(_safe_text(proc.stderr))

        db.set_model_status(args.home_id, "READY")
        _print_stdout(f"Home {args.home_id} model ready: {model_dir}")
    except Exception:
        db.set_model_status(args.home_id, "FAILED")
        raise


if __name__ == "__main__":
    main()
