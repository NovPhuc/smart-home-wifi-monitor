"""Theo dõi: trang dashboard, hiệu chuẩn, quét, cảm biến, trạng thái, xuất CSV."""
from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
import threading
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

# SSE: đẩy dữ liệu mỗi 2 giây (cùng nhịp polling cũ), nhưng chỉ gửi event khi
# payload đổi. Status vẫn được gửi lại mỗi 15 giây để dashboard cập nhật được
# trạng thái "dữ liệu đã cũ" dù không có scan mới.
STREAM_INTERVAL_SECONDS = 2.0
STREAM_HEARTBEAT_SECONDS = 15.0
# Mỗi kết nối SSE chiếm một thread của Flask. Giới hạn để một tài khoản mở
# hàng trăm tab không làm cạn thread của máy chủ gia đình.
MAX_STREAMS = 32


class _StreamSlots:
    """Đếm số kết nối SSE đang mở, có khóa để dùng được từ nhiều thread."""

    def __init__(self, limit: int) -> None:
        self._slots = threading.BoundedSemaphore(limit)

    def acquire(self) -> bool:
        return self._slots.acquire(blocking=False)

    def release(self) -> None:
        self._slots.release()


_stream_slots = _StreamSlots(MAX_STREAMS)


def _status_payload(home: dict) -> dict:
    """Dữ liệu của /api/status, dùng chung cho REST và SSE."""
    with app_state.lock:
        result = deepcopy(app_state.last_results.get(home["id"], {"status": "NO_DATA", "room": None}))
        monitor = app_state.sensor_monitors.get(home["id"])
        sensor = monitor.status() if monitor else None
    result["home"] = {"id": home["id"], "name": home["name"]}
    result["calibration"] = home_progress(home["id"])
    result["mobile_sensor"] = sensor
    return result


def _history_payload(home: dict) -> list:
    """Dữ liệu của /api/history, dùng chung cho REST và SSE."""
    persisted = app_state.db.prediction_history(home["id"], 300)
    with app_state.lock:
        runtime = list(app_state.runtime_histories.get(home["id"], []))
    return (persisted + runtime)[-300:]


def _alerts_payload(home: dict) -> list:
    """Dữ liệu của /api/alerts, dùng chung cho REST và SSE."""
    return app_state.db.list_alerts(home["id"], 100)


def _sse_event(name: str, body: str) -> str:
    return f"event: {name}\ndata: {body}\n\n"


def _dashboard_stream(home: dict, user_id: int):
    """Sinh event SSE cho một căn nhà cho tới khi client đóng kết nối.

    Không dùng ``stream_with_context`` vì generator chỉ đọc ``app_state`` và
    dữ liệu đã được chụp lại trong ``home``; giữ request context suốt 2 giây
    mỗi vòng là không cần thiết.
    """
    previous: dict[str, str] = {}
    last_status_at = 0.0
    last_heartbeat = time.monotonic()
    while True:
        # Quyền xem có thể bị thu hồi sau khi stream đã mở (chủ nhà gỡ thành
        # viên). Polling cũ phát hiện trong 2 giây; SSE phải kiểm tra lại,
        # nếu không thành viên đã bị gỡ vẫn nhận dữ liệu mãi.
        if app_state.db.get_home(user_id, home["id"]) is None:
            yield _sse_event("auth", '{"error":"HOME_ACCESS_REVOKED"}')
            return
        now = time.monotonic()
        payloads = {
            "status": _status_payload(home),
            "history": _history_payload(home),
            "alerts": _alerts_payload(home),
        }
        for name in ("status", "history", "alerts"):
            body = json.dumps(payloads[name], ensure_ascii=False, separators=(",", ":"))
            force_status = name == "status" and now - last_status_at >= STREAM_HEARTBEAT_SECONDS
            if force_status or previous.get(name) != body:
                yield _sse_event(name, body)
                previous[name] = body
                if name == "status":
                    last_status_at = now
        if now - last_heartbeat >= STREAM_HEARTBEAT_SECONDS:
            yield ": heartbeat\n\n"
            last_heartbeat = now
        time.sleep(STREAM_INTERVAL_SECONDS)


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
        # Client Android mới gửi thêm "scan_timestamp" (epoch giây của lần quét
        # theo đồng hồ thiết bị) để server nhận diện bản trùng theo (a). Client
        # cũ không có trường này → server tự rơi về so sánh hash nội dung (b).
        scan_ts_payload = payload.get("scan_timestamp")
        scan_ts = (
            finite_float(scan_ts_payload, field="scan_timestamp")
            if scan_ts_payload is not None
            else None
        )
        target, orientations, required_sessions = calibration_settings()
        session_target = (target + required_sessions - 1) // required_sessions
        result = app_state.db.record_wifi_scan(
            home_id=home["id"], room_name=room_name, session_code=session_code,
            device_name=str(payload.get("device_id", device["name"] if device else "web-collector"))[:80],
            wifi=clean_wifi, orientation=orientation,
            timestamp=scan_timestamp,
            collector_device_id=device["id"] if device else None,
            target_samples=session_target, required_orientations=orientations,
            scan_timestamp=scan_ts,
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
    return jsonify(_status_payload(home))


@bp.get("/api/stream")
@login_required
def stream():
    """Server-Sent Events: đẩy status/history/alerts thay cho polling 3 request."""
    home, error = require_active_home()
    if error:
        return error
    if not _stream_slots.acquire():
        response = jsonify({
            "error": "TOO_MANY_STREAMS",
            "message": "Quá nhiều kết nối realtime, vui lòng thử lại sau",
        })
        response.status_code = 503
        response.headers["Retry-After"] = "30"
        return response
    response = Response(_dashboard_stream(home, int(flask_session["user_id"])), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache, no-store"
    # Reverse proxy (nginx) mặc định gom response; tắt để event tới ngay.
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    # call_on_close chạy cả khi client ngắt giữa chừng, nên không rò slot.
    response.call_on_close(_stream_slots.release)
    return response


@bp.get("/api/history")
@login_required
def history():
    home, error = require_active_home()
    if error:
        return error
    return jsonify(_history_payload(home))


@bp.get("/api/alerts")
@login_required
def alerts():
    home, error = require_active_home()
    if error:
        return error
    return jsonify(_alerts_payload(home))


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
