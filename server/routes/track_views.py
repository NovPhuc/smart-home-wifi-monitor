"""Theo dõi: trang dashboard, hiệu chuẩn, quét, cảm biến, trạng thái, xuất CSV."""
from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
import time

from flask import Blueprint, Response, jsonify, request, session as flask_session

import app_state
from app_security import csv_formula_safe
from app_services import (
    calibration_settings,
    finite_float,
    get_home_engine,
    home_progress,
    login_required,
    new_sensor_monitor,
    notify_alert,
    persist_result,
    require_active_home,
    require_mutation_context,
    require_owned_home,
)
from smarthome.metrics import collect_model_metrics

bp = Blueprint("track", __name__)


@bp.get("/api/calibration")
@login_required
def calibration():
    home, error = require_active_home()
    if error:
        return error
    return jsonify(home_progress(home["id"]))


@bp.post("/api/collect")
def collect():
    home, device, error = require_mutation_context()
    if error:
        return error
    payload = request.get_json(force=True, silent=False) or {}
    wifi = payload.get("wifi")
    room_name = str(payload.get("room", "")).strip()[:80]
    session_code = str(payload.get("session_id", "")).strip()
    orientation = str(payload.get("orientation", "UNKNOWN")).strip()[:32] or "UNKNOWN"
    if not isinstance(wifi, dict) or not wifi or not room_name or not session_code:
        return jsonify({"error": "wifi, room và session_id là bắt buộc"}), 400
    if len(session_code) > 40:
        return jsonify({"error": "session_id tối đa 40 ký tự"}), 400
    if len(wifi) > 64:
        return jsonify({"error": "Tối đa 64 access point mỗi lần quét"}), 400
    try:
        clean_wifi = {
            str(key)[:64]: finite_float(value, field=f"RSSI của {str(key)[:64]}")
            for key, value in wifi.items()
        }
        scan_timestamp = finite_float(payload.get("timestamp", time.time()), field="timestamp")
        target, orientations, required_sessions = calibration_settings()
        session_target = (target + required_sessions - 1) // required_sessions
        result = app_state.db.record_wifi_scan(
            home_id=home["id"], room_name=room_name, session_code=session_code,
            device_name=str(payload.get("device_id", device["name"] if device else "web-collector"))[:80],
            wifi=clean_wifi, orientation=orientation,
            timestamp=scan_timestamp,
            collector_device_id=device["id"] if device else None,
            target_samples=session_target, required_orientations=orientations,
        )
    except (TypeError, ValueError, LookupError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, **result})


@bp.post("/api/scan")
def scan():
    home, _device, error = require_mutation_context()
    if error:
        return error
    progress = home_progress(home["id"])
    if not progress["localization_ready"]:
        return jsonify({"error": "CALIBRATION_REQUIRED", "calibration": progress}), 409
    payload = request.get_json(force=True, silent=False) or {}
    wifi = payload.get("wifi")
    if not isinstance(wifi, dict) or not wifi:
        return jsonify({"error": "wifi phải là object RSSI không rỗng"}), 400
    if len(wifi) > 64:
        return jsonify({"error": "Tối đa 64 access point mỗi lần quét"}), 400
    try:
        # Chuẩn hóa trước khi đưa vào model: giá trị sai/NaN phải trả 400 thay
        # vì để float() trong preprocessor ném lỗi 500 hoặc làm hỏng model.
        clean_wifi = {
            str(key)[:64]: finite_float(value, field=f"RSSI của {str(key)[:64]}")
            for key, value in wifi.items()
        }
        scan_timestamp = (
            finite_float(payload["timestamp"], field="timestamp")
            if payload.get("timestamp") is not None else None
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    home_engine = get_home_engine(home["id"])
    if home_engine is None:
        return jsonify({"error": "MODEL_NOT_AVAILABLE"}), 409
    with app_state.lock:
        result = home_engine.process_scan(clean_wifi, scan_timestamp)
        if result.get("room"):
            persist_result(home["id"], result, home["name"])
    return jsonify(result)


@bp.post("/api/demo/scan")
@login_required
def demo_scan():
    home, error = require_owned_home()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    requested_room = payload.get("room")
    if requested_room is not None and requested_room not in app_state.cfg["rooms"]:
        return jsonify({"error": "unknown room", "rooms": app_state.cfg["rooms"]}), 400
    with app_state.lock:
        source_room, wifi = app_state.demo_source.next(requested_room)
        result = app_state.demo_engine.process_scan(wifi)
        result["demo_source_room"] = source_room
        result["demo"] = True
        app_state.last_results[home["id"]] = result
        if result.get("room"):
            app_state.runtime_histories[home["id"]].append(result)
    return jsonify(result)


@bp.post("/api/sensor")
def sensor_update():
    home, _device, error = require_mutation_context()
    if error:
        return error
    payload = request.get_json(force=True, silent=False) or {}
    acceleration = payload.get("acceleration")
    if not isinstance(acceleration, dict):
        return jsonify({"error": "acceleration phải có x, y và z"}), 400
    with app_state.lock:
        monitor = app_state.sensor_monitors.setdefault(home["id"], new_sensor_monitor())
        alert_count = len(monitor.alerts)
        device_id = str(payload.get("device_id", "phone-pwa")).strip()[:80] or "phone-pwa"
        try:
            result = monitor.update(device_id, acceleration, payload.get("timestamp"))
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        app_state.db.save_sensor_sample(home["id"], acceleration, result)
        if len(monitor.alerts) > alert_count:
            alert = monitor.alerts[-1]
            app_state.db.save_alert(home["id"], alert)
            notify_alert(home["id"], home["name"], alert)
    return jsonify(result)


@bp.get("/api/sensor/status")
@login_required
def sensor_status():
    home, error = require_active_home()
    if error:
        return error
    monitor = app_state.sensor_monitors.get(home["id"])
    snapshot = monitor.status(request.args.get("device_id")) if monitor else None
    return jsonify(snapshot or {"state": "NO_DATA"})


@bp.get("/api/status")
@login_required
def status():
    home, error = require_active_home()
    if error:
        return error
    result = deepcopy(app_state.last_results.get(home["id"], {"status": "NO_DATA", "room": None}))
    result["home"] = {"id": home["id"], "name": home["name"]}
    result["calibration"] = home_progress(home["id"])
    monitor = app_state.sensor_monitors.get(home["id"])
    result["mobile_sensor"] = monitor.status() if monitor else None
    return jsonify(result)


@bp.get("/api/history")
@login_required
def history():
    home, error = require_active_home()
    if error:
        return error
    persisted = app_state.db.prediction_history(home["id"], 300)
    runtime = list(app_state.runtime_histories.get(home["id"], []))
    return jsonify((persisted + runtime)[-300:])


@bp.get("/api/alerts")
@login_required
def alerts():
    home, error = require_active_home()
    if error:
        return error
    return jsonify(app_state.db.list_alerts(home["id"], 100))


@bp.get("/api/config")
@login_required
def public_config():
    home, error = require_active_home()
    if error:
        return error
    return jsonify({
        "rooms": app_state.db.list_rooms(home["id"]),
        "calibration": home_progress(home["id"]),
        "window_size": app_state.cfg["data"]["window_size"],
        "disclaimer": "Không phải thiết bị y tế hoặc hệ thống xác nhận té ngã.",
    })


@bp.get("/api/metrics")
@login_required
def metrics():
    home, error = require_active_home()
    if error:
        return error
    model_dir = app_state.ROOT / "models" / "homes" / str(home["id"])
    return jsonify({
        **collect_model_metrics(model_dir, app_state.ROOT / "models"),
        "data_notice": "Kết quả riêng của căn nhà đang chọn; chỉ xuất hiện sau khi huấn luyện.",
    })


@bp.get("/api/export/scans.csv")
@login_required
def export_scans():
    home, error = require_owned_home()
    if error:
        return error
    scans = app_state.db.export_scans(home["id"])
    aps = sorted({ap for scan in scans for ap in json.loads(scan["wifi_json"]).keys()})
    fields = ["timestamp", "session_id", "device_id", "room", "orientation", *aps]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for scan in scans:
        wifi = json.loads(scan.pop("wifi_json"))
        row = {**scan, **wifi}
        for field in ("session_id", "device_id", "room", "orientation"):
            row[field] = csv_formula_safe(row.get(field, ""))
        writer.writerow(row)
    return Response(
        output.getvalue(), mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="home-{home["id"]}-wifi-scans.csv"'},
    )


@bp.post("/api/reset")
@login_required
def reset():
    home, error = require_owned_home()
    if error:
        return error
    with app_state.lock:
        app_state.last_results.pop(home["id"], None)
        app_state.runtime_histories.pop(home["id"], None)
        app_state.sensor_monitors.pop(home["id"], None)
        app_state.alert_throttle.reset(home["id"])
        if home["id"] in app_state.home_engines:
            app_state.home_engines[home["id"]].reset()
        app_state.demo_engine.reset()
        app_state.demo_source.reset()
    return jsonify({"ok": True, "persistent_data_kept": True})
