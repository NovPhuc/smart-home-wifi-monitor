"""An Tâm Home — server Flask (bản lắp ráp sau khi tách module).

Cấu trúc:
- ``app_state``     : trạng thái dùng chung (db, engines, limiter, demo…)
- ``app_security``  : khóa session, bộ chặn dò, header bảo mật, vệ sinh CSV
- ``app_services``  : trợ giúp dùng chung giữa các route (auth, engine…)
- ``routes/``       : blueprint theo domain (auth, homes, rooms, track, training)

Đường dẫn API, tên trường JSON và mã lỗi giữ nguyên như bản cũ — app Android
và dashboard PWA không được vỡ. Module ``app`` vẫn re-export các singleton để
fixture test (thay ``app_state.db``) và script cũ tiếp tục chạy.
"""
from __future__ import annotations

from pathlib import Path
import os
import sys
import time  # noqa: F401  — giữ để test monkeypatch qua ``appmod.time``

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from flask import Flask, jsonify, render_template, send_from_directory

import app_state
from app_security import apply_security_headers, resolve_secret_key, secure_cookie_requested
from routes import register_routes
from security_middleware import (
    install_extra_headers,
    install_json_errors,
    install_rate_limiting,
    install_request_guard,
    reset_rate_limits,
)


def create_app() -> Flask:
    application = Flask(__name__, template_folder="templates", static_folder="static")
    application.config.update(
        SECRET_KEY=resolve_secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Cookie Secure khi env yêu cầu, hoặc tự bật khi server chạy HTTPS thật.
        SESSION_COOKIE_SECURE=secure_cookie_requested(),
        MAX_CONTENT_LENGTH=1_000_000,
    )
    application.after_request(apply_security_headers)

    # Thứ tự before_request: chặn flood trước, rồi mới kiểm tra kiểu body và
    # mẫu tấn công — request bị rate limit không tốn công parse.
    install_rate_limiting(application)
    install_request_guard(application)
    install_extra_headers(application)
    install_json_errors(application)

    @application.get("/api/health")
    def health():
        """Health check cho script giám sát; không lộ đường dẫn DB."""
        try:
            with app_state.db.connect() as connection:
                connection.execute("SELECT 1").fetchone()
        except Exception:  # DB hỏng/chưa tạo được là trạng thái degraded
            application.logger.warning("[Health] Khong ket noi duoc database")
            return jsonify({"status": "degraded", "database": "error"}), 503
        return jsonify({
            "status": "ok",
            "database": "ok",
            "service": "an-tam-home",
            "api": "v1",
            "time": int(time.time()),
        })

    @application.get("/")
    def index():
        return render_template("dashboard.html")

    @application.get("/service-worker.js")
    def service_worker():
        response = send_from_directory(application.static_folder, "service-worker.js")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    register_routes(application)
    return application


app = create_app()

# ---- Re-export cho test và script cũ ----------------------------------------
# Fixture test thay database bằng ``appmod.app_state.db = ...`` rồi gọi
# ``app_state.reset_runtime()``; route đọc trạng thái qua app_state nên luôn
# thấy thay đổi. Các tên dưới đây là bí danh động: mỗi lần truy cập đều đọc
# từ app_state/app_services, nhờ vậy ``appmod.db`` cũng thấy database mới thay
# vì giữ tham chiếu cũ đã bind lúc import.
import app_services  # noqa: E402  — sau khi app_state đã sẵn sàng

cfg = app_state.cfg
lock = app_state.lock
demo_engine = app_state.demo_engine
engine = app_state.engine  # Tương thích ngược với các script cũ.
demo_source = app_state.demo_source

_DYNAMIC_EXPORTS = {
    "db": (app_state, "db"),
    "home_engines": (app_state, "home_engines"),
    "sensor_monitors": (app_state, "sensor_monitors"),
    "last_results": (app_state, "last_results"),
    "runtime_histories": (app_state, "runtime_histories"),
    "training_jobs": (app_state, "training_jobs"),
    "alert_throttle": (app_state, "alert_throttle"),
    "login_limiter": (app_state, "login_limiter"),
    "join_code_limiter": (app_state, "join_code_limiter"),
    "register_limiter": (app_state, "register_limiter"),
    "calibration_settings": (app_services, "calibration_settings"),
    "persist_result": (app_services, "persist_result"),
}


def __getattr__(name: str):
    """Trả bí danh động cho tên cũ; báo AttributeError chuẩn nếu không có."""
    target = _DYNAMIC_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module, attribute = target
    return getattr(module, attribute)


if __name__ == "__main__":
    import atexit

    server_cfg = cfg["server"]
    host = server_cfg["host"]
    port = int(server_cfg["port"])
    cert = os.getenv("SMART_HOME_SSL_CERT")
    key = os.getenv("SMART_HOME_SSL_KEY")
    mdns_info = None

    if server_cfg.get("mdns_enabled", True) and not (cert and key):
        # Quảng bá "_antam._tcp." trên WiFi nhà để Android (NSD) tự tìm ra
        # địa chỉ máy chủ, không cần người dùng gõ IP.
        try:
            from zeroconf import ServiceInfo, Zeroconf

            zeroconf = Zeroconf()
            mdns_info = ServiceInfo(
                "_antam._tcp.local.",
                "An Tam Home Server._antam._tcp.local.",
                port=port,
                properties={"path": "/", "app": "antam", "api": "v1"},
                server="antam-home.local.",
            )
            zeroconf.register_service(mdns_info)
            atexit.register(lambda: (zeroconf.unregister_service(mdns_info), zeroconf.close()))
            print(f"[mDNS] Dang quang ba _antam._tcp tren cong {port} — app dien thoai se tu tim may chu.")
        except ImportError:
            print("[mDNS] Chua cai zeroconf — pip install zeroconf de app tu tim may chu.")
        except Exception as exc:  # zeroconf is a convenience, never fatal.
            mdns_info = None
            print(f"[mDNS] Khong quang ba duoc: {exc}")

    app.run(
        host=host, port=port, debug=False,
        ssl_context=(cert, key) if cert and key else None,
    )
