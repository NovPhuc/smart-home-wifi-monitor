"""Tầng service: trợ giúp dùng chung giữa các route (auth, home context, engine)."""
from __future__ import annotations

from functools import wraps
import logging
import math
import threading

import requests
from flask import Response, jsonify, request, session as flask_session

import app_state
from smarthome.config import load_config
from smarthome.inference import SmartHomeInferenceEngine
from smarthome.mobile_sensor import MobileSensorMonitor


def finite_float(
    value,
    *,
    field: str = "Giá trị",
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Ép float và từ chối NaN/Infinity/ngoài khoảng.

    ``float("nan")`` và ``float("inf")`` không ném lỗi, nên nếu chỉ bọc
    ``float()`` thì chúng lọt vào DB/model và làm hỏng phép so sánh sau này.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} phải là số") from None
    if not math.isfinite(number):
        raise ValueError(f"{field} phải là số hữu hạn")
    if minimum is not None and number < minimum:
        raise ValueError(f"{field} phải từ {minimum:g}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{field} tối đa {maximum:g}")
    return number


def calibration_settings() -> tuple[int, int, int]:
    settings = app_state.cfg.get("calibration", {})
    return (
        int(settings.get("target_samples_per_room", 100)),
        int(settings.get("required_orientations", 3)),
        int(settings.get("required_sessions", 3)),
    )


def new_sensor_monitor() -> MobileSensorMonitor:
    settings = app_state.cfg.get("mobile_sensor", {})
    return MobileSensorMonitor(
        movement_threshold=settings.get("movement_threshold", 0.8),
        still_threshold=settings.get("still_threshold", 0.25),
        impact_threshold=settings.get("impact_threshold", 18.0),
        impact_followup_seconds=settings.get("impact_followup_seconds", 20.0),
        still_after_impact_seconds=settings.get("still_after_impact_seconds", 5.0),
    )


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not flask_session.get("user_id"):
            return jsonify({"error": "AUTH_REQUIRED"}), 401
        return function(*args, **kwargs)
    return wrapper


def active_home() -> dict | None:
    user_id = flask_session.get("user_id")
    if not user_id:
        return None
    home_id = flask_session.get("active_home_id")
    if home_id:
        home = app_state.db.get_home(int(user_id), int(home_id))
        if home:
            return home
    homes = app_state.db.list_homes(int(user_id))
    if not homes:
        return None
    flask_session["active_home_id"] = homes[0]["id"]
    return homes[0]


def require_active_home():
    home = active_home()
    if not home:
        return None, (jsonify({"error": "HOME_REQUIRED"}), 400)
    return home, None


def require_owned_home():
    """Chủ nhà mới được thay đổi dữ liệu dùng chung.

    Thành viên gia nhập qua mã chia sẻ 6 số chỉ được xem: vị trí, lịch sử,
    cảnh báo, tiến độ hiệu chuẩn và metric. Mọi thao tác ghi (phòng, thiết bị,
    thu thập, huấn luyện, xóa) phải quay về tài khoản chủ nhà.
    """
    user_id = flask_session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "AUTH_REQUIRED"}), 401)
    home_id = flask_session.get("active_home_id")
    home = app_state.db.get_owned_home(int(user_id), int(home_id)) if home_id else None
    if home:
        return home, None
    if active_home():
        return None, (jsonify({"error": "HOME_OWNER_REQUIRED", "detail": "Tài khoản chia sẻ chỉ có quyền xem"}), 403)
    return None, (jsonify({"error": "HOME_REQUIRED"}), 400)


def require_owned_home_by_id(home_id: int):
    home = app_state.db.get_owned_home(int(flask_session["user_id"]), home_id)
    if not home:
        if app_state.db.get_home(int(flask_session["user_id"]), home_id):
            return None, (jsonify({"error": "HOME_OWNER_REQUIRED", "detail": "Tài khoản chia sẻ chỉ có quyền xem"}), 403)
        return None, (jsonify({"error": "Không tìm thấy nhà"}), 404)
    return home, None


def bearer_device() -> dict | None:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    return app_state.db.authenticate_device(token) if token else None


def request_home_context() -> tuple[dict | None, dict | None]:
    if request.headers.get("Authorization", ""):
        # A supplied credential must authenticate: never silently downgrade an
        # invalid bearer token to the browser session.
        device = bearer_device()
        if device is None:
            return None, None
        with app_state.db.connect() as connection:
            home = connection.execute("SELECT * FROM homes WHERE id=?", (device["home_id"],)).fetchone()
        return (dict(home) if home else None), device
    return active_home(), None


def require_mutation_context() -> tuple[dict | None, dict | None, Response | None]:
    """Context ghi dữ liệu: device token hoặc tài khoản chủ nhà.

    Bearer device token là mã do chủ nhà tạo nên được coi như chủ nhà; đăng
    nhập bằng session thì tài khoản thành viên (qua mã chia sẻ) không được ghi.
    """
    home, device = request_home_context()
    if not home:
        return None, None, (jsonify({"error": "Đăng nhập hoặc cung cấp Bearer device token"}), 401)
    if device is None:
        user_id = flask_session.get("user_id")
        if not user_id or not app_state.db.is_home_owner(home["id"], int(user_id)):
            return None, None, (jsonify({"error": "HOME_OWNER_REQUIRED", "detail": "Tài khoản chia sẻ chỉ có quyền xem"}), 403)
    return home, device, None


def home_progress(home_id: int) -> dict:
    target, orientations, sessions = calibration_settings()
    return app_state.db.calibration_progress(home_id, target, orientations, sessions)


def get_home_engine(home_id: int) -> SmartHomeInferenceEngine | None:
    if home_id in app_state.home_engines:
        return app_state.home_engines[home_id]
    model_dir = app_state.ROOT / "models" / "homes" / str(home_id)
    config_path = model_dir / "config.yaml"
    if not config_path.exists() or not (model_dir / "preprocessor.json").exists() or not (model_dir / "roomnet_lite.pt").exists():
        return None
    app_state.home_engines[home_id] = SmartHomeInferenceEngine(load_config(config_path), model_dir)
    return app_state.home_engines[home_id]


def _webhook_url() -> str:
    """Đọc webhook cảnh báo từ config; chỉ chấp nhận URL http(s) hợp lệ."""
    value = app_state.cfg.get("alerts", {}).get("webhook_url", "")
    url = str(value or "").strip()
    if len(url) > 500 or not url.lower().startswith(("http://", "https://")):
        return ""
    return url


def _post_webhook(home_id: int, home_name: str, alert: dict) -> None:
    """Gửi một cảnh báo CRITICAL ra webhook ngoài (ntfy/Telegram/IFTTT…).

    Chạy trong thread nền nên mạng chậm không làm chậm vòng quét. Không đi
    theo redirect để tránh bị đổi đích ngoài ý muốn.
    """
    url = _webhook_url()
    if not url:
        return
    payload = {
        "event": "alert",
        "home_id": home_id,
        "home": home_name,
        "status": alert.get("status"),
        "room": alert.get("room"),
        "reasons": alert.get("reasons", []),
        "timestamp": alert.get("timestamp"),
    }
    try:
        requests.post(url, json=payload, timeout=5, allow_redirects=False)
    except requests.RequestException as exc:
        logging.getLogger(__name__).warning("Không gửi được webhook cảnh báo: %s", exc)


def notify_alert(home_id: int, home_name: str, alert: dict) -> None:
    """Đẩy cảnh báo CRITICAL ra webhook nếu người vận hành đã cấu hình."""
    if str(alert.get("status", "")).upper() != "CRITICAL" or not _webhook_url():
        return
    threading.Thread(
        target=_post_webhook,
        args=(home_id, home_name or f"Nhà #{home_id}", dict(alert)),
        daemon=True,
    ).start()


def persist_result(home_id: int, result: dict, home_name: str = "") -> None:
    app_state.last_results[home_id] = result
    if result.get("room"):
        app_state.db.save_prediction(home_id, result)
    status = result.get("status")
    # A sustained condition (long dwell, inactivity) produces an alert on every
    # scan. Throttle repeats so the alerts table reflects events, not poll rate.
    if status in {"WARNING", "CRITICAL"} and app_state.alert_throttle.should_emit(
        home_id, status, result.get("reasons")
    ):
        alert = {**result, "source": "wifi"}
        app_state.db.save_alert(home_id, alert)
        notify_alert(home_id, home_name, alert)
