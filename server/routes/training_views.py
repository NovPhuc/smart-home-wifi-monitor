"""Huấn luyện model theo nhà (chạy nền trong tiến trình con)."""
from __future__ import annotations

import subprocess
import sys
import threading
import time

from flask import Blueprint, jsonify

import app_state
from app_services import home_progress, login_required, require_active_home, require_owned_home

bp = Blueprint("training", __name__)


def run_training(home_id: int) -> None:
    app_state.training_jobs[home_id] = {"status": "TRAINING", "started_at": time.time(), "message": "Đang huấn luyện"}
    try:
        process = subprocess.run(
            [sys.executable, str(app_state.ROOT / "scripts" / "train_home.py"), "--home-id", str(home_id), "--database", str(app_state.db.path)],
            cwd=app_state.ROOT, capture_output=True, text=True, timeout=7200,
        )
        if process.returncode != 0:
            raise RuntimeError((process.stderr or process.stdout)[-1200:])
        app_state.home_engines.pop(home_id, None)
        app_state.training_jobs[home_id] = {"status": "READY", "finished_at": time.time(), "message": "Model đã sẵn sàng"}
    except Exception as exc:
        app_state.db.set_model_status(home_id, "FAILED")
        app_state.training_jobs[home_id] = {"status": "FAILED", "finished_at": time.time(), "message": str(exc)[-1200:]}


@bp.post("/api/training/start")
@login_required
def start_training():
    home, error = require_owned_home()
    if error:
        return error
    progress = home_progress(home["id"])
    if not progress["data_ready"]:
        return jsonify({"error": "CALIBRATION_INCOMPLETE", "calibration": progress}), 409
    if app_state.training_jobs.get(home["id"], {}).get("status") == "TRAINING":
        return jsonify(app_state.training_jobs[home["id"]]), 202
    app_state.db.set_model_status(home["id"], "TRAINING")
    threading.Thread(target=run_training, args=(home["id"],), daemon=True).start()
    return jsonify({"status": "TRAINING"}), 202


@bp.get("/api/training/status")
@login_required
def training_status():
    home, error = require_active_home()
    if error:
        return error
    return jsonify(app_state.training_jobs.get(home["id"], {"status": home["model_status"]}))
