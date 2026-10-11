from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from functools import wraps
from pathlib import Path
import csv
import io
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time

from flask import Flask, Response, jsonify, render_template, request, send_from_directory, session as flask_session
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Nạp biến môi trường từ .env (SMART_HOME_SECRET_KEY, SMART_HOME_SECURE_COOKIE,
# và sau này DATABASE_URL nếu chuyển DB lên cloud). Lỗi ImportError chỉ xảy ra
# khi python-dotenv chưa cài — khi đó có thể export biến môi trường thủ công.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from smarthome.alerts import AlertThrottle
from smarthome.config import load_config
from smarthome.inference import SmartHomeInferenceEngine
from smarthome.metrics import collect_model_metrics
from smarthome.mobile_sensor import MobileSensorMonitor
from smarthome.storage import SmartHomeDatabase


cfg = load_config(ROOT / "config.yaml")
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY=os.getenv("SMART_HOME_SECRET_KEY", "change-this-development-secret"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SMART_HOME_SECURE_COOKIE", "0") == "1",
    MAX_CONTENT_LENGTH=1_000_000,
)

db = SmartHomeDatabase(os.getenv("SMART_HOME_DATABASE", ROOT / "data" / "smarthome.db"))
demo_engine = SmartHomeInferenceEngine(cfg, ROOT / "models")
engine = demo_engine  # Backward-compatible import for existing scripts.
lock = threading.RLock()
home_engines: dict[int, SmartHomeInferenceEngine] = {}
sensor_monitors: dict[int, MobileSensorMonitor] = {}
last_results: dict[int, dict] = {}
runtime_histories: dict[int, deque] = defaultdict(lambda: deque(maxlen=300))
training_jobs: dict[int, dict] = {}
alert_throttle = AlertThrottle(
    cooldown_seconds=float(cfg.get("alerts", {}).get("repeat_cooldown_seconds", 600))
)


def calibration_settings() -> tuple[int, int, int]:
    settings = cfg.get("calibration", {})
    return (
        int(settings.get("target_samples_per_room", 100)),
        int(settings.get("required_orientations", 3)),
        int(settings.get("required_sessions", 3)),
    )


def new_sensor_monitor() -> MobileSensorMonitor:
    settings = cfg.get("mobile_sensor", {})
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
        home = db.get_home(int(user_id), int(home_id))
        if home:
            return home
    homes = db.list_homes(int(user_id))
    if not homes:
        return None
    flask_session["active_home_id"] = homes[0]["id"]
    return homes[0]


def require_active_home():
    home = active_home()
    if not home:
        return None, (jsonify({"error": "HOME_REQUIRED"}), 400)
    return home, None


def bearer_device() -> dict | None:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    return db.authenticate_device(token) if token else None


def request_home_context() -> tuple[dict | None, dict | None]:
    if request.headers.get("Authorization", ""):
        # A supplied credential must authenticate: never silently downgrade an
        # invalid bearer token to the browser session.
        device = bearer_device()
        if device is None:
            return None, None
        with db.connect() as connection:
            home = connection.execute("SELECT * FROM homes WHERE id=?", (device["home_id"],)).fetchone()
        return (dict(home) if home else None), device
    return active_home(), None


def home_progress(home_id: int) -> dict:
    target, orientations, sessions = calibration_settings()
    return db.calibration_progress(home_id, target, orientations, sessions)


def get_home_engine(home_id: int) -> SmartHomeInferenceEngine | None:
    if home_id in home_engines:
        return home_engines[home_id]
    model_dir = ROOT / "models" / "homes" / str(home_id)
    config_path = model_dir / "config.yaml"
    if not config_path.exists() or not (model_dir / "preprocessor.json").exists() or not (model_dir / "roomnet_lite.pt").exists():
        return None
    home_engines[home_id] = SmartHomeInferenceEngine(load_config(config_path), model_dir)
    return home_engines[home_id]


def persist_result(home_id: int, result: dict) -> None:
    last_results[home_id] = result
    if result.get("room"):
        db.save_prediction(home_id, result)
    status = result.get("status")
    # A sustained condition (long dwell, inactivity) produces an alert on every
    # scan. Throttle repeats so the alerts table reflects events, not poll rate.
    if status in {"WARNING", "CRITICAL"} and alert_throttle.should_emit(
        home_id, status, result.get("reasons")
    ):
        db.save_alert(home_id, {**result, "source": "wifi"})


class DemoSource:
    def __init__(self, path: Path, rooms: list[str], ap_columns: list[str]):
        self.rooms = rooms
        self.ap_columns = ap_columns
        self.by_room = {room: [] for room in rooms}
        if path.exists():
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    room = row.get("room")
                    if room in self.by_room:
                        self.by_room[room].append({ap: float(row[ap]) for ap in ap_columns if row.get(ap)})
        self.room_index = 0
        self.sample_index = 0

    def reset(self) -> None:
        self.room_index = 0
        self.sample_index = 0

    def next(self, requested_room: str | None = None) -> tuple[str, dict[str, float]]:
        room = requested_room if requested_room in self.by_room else self.rooms[self.room_index]
        samples = self.by_room.get(room, [])
        if not samples:
            raise RuntimeError("Demo fingerprints are not available")
        wifi = samples[self.sample_index % len(samples)]
        self.sample_index += 1
        if requested_room is None and self.sample_index % 12 == 0:
            current = self.rooms[self.room_index]
            neighbours = [name for name in cfg["room_topology"].get(current, []) if name != current]
            self.room_index = self.rooms.index(neighbours[0]) if neighbours else (self.room_index + 1) % len(self.rooms)
        return room, wifi


demo_source = DemoSource(ROOT / "data" / "raw" / "wifi_fingerprints.csv", cfg["rooms"], demo_engine.preprocessor.ap_columns)


@app.get("/")
def index():
    return render_template("dashboard.html")


@app.get("/service-worker.js")
def service_worker():
    response = send_from_directory(app.static_folder, "service-worker.js")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.post("/api/auth/register")
def register():
    payload = request.get_json(force=True, silent=False) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    display_name = str(payload.get("display_name", "")).strip()
    home_name = str(payload.get("home_name", "")).strip() or "Nhà của tôi"
    errors = {}
    if "@" not in email or len(email) > 254:
        errors["email"] = "Email không hợp lệ"
    if len(password) < 8:
        errors["password"] = "Mật khẩu cần ít nhất 8 ký tự"
    if not display_name or len(display_name) > 80:
        errors["display_name"] = "Tên hiển thị không hợp lệ"
    if not home_name or len(home_name) > 100:
        errors["home_name"] = "Tên nhà không hợp lệ"
    if errors:
        return jsonify({"error": "VALIDATION_ERROR", "fields": errors}), 400
    try:
        user = db.create_user(email, generate_password_hash(password), display_name)
        home = db.create_home(user["id"], home_name)
    except sqlite3.IntegrityError:
        return jsonify({"error": "EMAIL_EXISTS", "fields": {"email": "Email đã được đăng ký"}}), 409
    flask_session.clear()
    flask_session["user_id"] = user["id"]
    flask_session["active_home_id"] = home["id"]
    return jsonify({"user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]}, "active_home": home}), 201


@app.post("/api/auth/login")
def login():
    payload = request.get_json(force=True, silent=False) or {}
    user = db.get_user_by_email(str(payload.get("email", "")))
    if not user or not check_password_hash(user["password_hash"], str(payload.get("password", ""))):
        return jsonify({"error": "INVALID_CREDENTIALS"}), 401
    flask_session.clear()
    flask_session["user_id"] = user["id"]
    homes = db.list_homes(user["id"])
    if homes:
        flask_session["active_home_id"] = homes[0]["id"]
    return jsonify({"ok": True})


@app.post("/api/auth/logout")
def logout():
    flask_session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
@login_required
def me():
    user = db.get_user(int(flask_session["user_id"]))
    home = active_home()
    return jsonify({
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
        "homes": db.list_homes(user["id"]),
        "active_home": home,
    })


@app.route("/api/homes", methods=["GET", "POST"])
@login_required
def homes():
    user_id = int(flask_session["user_id"])
    if request.method == "GET":
        return jsonify(db.list_homes(user_id))
    name = str((request.get_json(force=True) or {}).get("name", "")).strip()
    if not name or len(name) > 100:
        return jsonify({"error": "Tên nhà phải từ 1 đến 100 ký tự"}), 400
    try:
        home = db.create_home(user_id, name)
    except sqlite3.IntegrityError:
        return jsonify({"error": "Tên nhà đã tồn tại"}), 409
    flask_session["active_home_id"] = home["id"]
    return jsonify(home), 201


@app.post("/api/homes/<int:home_id>/select")
@login_required
def select_home(home_id: int):
    home = db.get_home(int(flask_session["user_id"]), home_id)
    if not home:
        return jsonify({"error": "Không tìm thấy nhà"}), 404
    flask_session["active_home_id"] = home_id
    return jsonify({"active_home": home})


@app.route("/api/homes/<int:home_id>", methods=["PATCH", "DELETE"])
@login_required
def modify_home(home_id: int):
    user_id = int(flask_session["user_id"])
    if request.method == "DELETE":
        if not db.delete_home(user_id, home_id):
            return jsonify({"error": "Không tìm thấy nhà"}), 404
        if flask_session.get("active_home_id") == home_id:
            flask_session.pop("active_home_id", None)
        home_engines.pop(home_id, None)
        return jsonify({"ok": True})
    name = str((request.get_json(force=True) or {}).get("name", "")).strip()
    if not name or len(name) > 100:
        return jsonify({"error": "Tên nhà không hợp lệ"}), 400
    try:
        changed = db.rename_home(user_id, home_id, name)
    except sqlite3.IntegrityError:
        return jsonify({"error": "Tên nhà đã tồn tại"}), 409
    return jsonify({"ok": changed}) if changed else (jsonify({"error": "Không tìm thấy nhà"}), 404)


@app.route("/api/rooms", methods=["GET", "POST"])
@login_required
def rooms():
    home, error = require_active_home()
    if error:
        return error
    if request.method == "GET":
        return jsonify(db.list_rooms(home["id"]))
    payload = request.get_json(force=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 80:
        return jsonify({"error": "Tên phòng phải từ 1 đến 80 ký tự"}), 400
    try:
        room = db.create_room(home["id"], name, float(payload.get("max_dwell_minutes", 60)))
    except (ValueError, sqlite3.IntegrityError):
        return jsonify({"error": "Tên phòng đã tồn tại hoặc thời gian không hợp lệ"}), 409
    db.set_model_status(home["id"], "NOT_TRAINED")
    home_engines.pop(home["id"], None)
    return jsonify(room), 201


@app.route("/api/rooms/<int:room_id>", methods=["PATCH", "DELETE"])
@login_required
def modify_room(room_id: int):
    home, error = require_active_home()
    if error:
        return error
    if request.method == "DELETE":
        changed = db.delete_room(home["id"], room_id)
    else:
        payload = request.get_json(force=True) or {}
        name = str(payload.get("name", "")).strip()
        if not name or len(name) > 80:
            return jsonify({"error": "Tên phòng không hợp lệ"}), 400
        try:
            changed = db.update_room(home["id"], room_id, name, float(payload.get("max_dwell_minutes", 60)))
        except (ValueError, sqlite3.IntegrityError):
            return jsonify({"error": "Tên phòng đã tồn tại hoặc thời gian không hợp lệ"}), 409
    if not changed:
        return jsonify({"error": "Không tìm thấy phòng"}), 404
    db.set_model_status(home["id"], "NOT_TRAINED")
    home_engines.pop(home["id"], None)
    return jsonify({"ok": True})


@app.route("/api/devices", methods=["GET", "POST"])
@login_required
def devices():
    home, error = require_active_home()
    if error:
        return error
    if request.method == "GET":
        return jsonify(db.list_devices(home["id"]))
    payload = request.get_json(force=True) or {}
    name = str(payload.get("name", "Điện thoại Android")).strip()[:80]
    device, token = db.create_device(home["id"], name, str(payload.get("platform", "android")))
    return jsonify({"device": device, "token": token, "message": "Token chỉ hiển thị một lần"}), 201


@app.delete("/api/devices/<int:device_id>")
@login_required
def revoke_device(device_id: int):
    home, error = require_active_home()
    if error:
        return error
    return jsonify({"ok": db.revoke_device(home["id"], device_id)})


@app.get("/api/calibration")
@login_required
def calibration():
    home, error = require_active_home()
    if error:
        return error
    return jsonify(home_progress(home["id"]))


@app.post("/api/collect")
def collect():
    home, device = request_home_context()
    if not home:
        return jsonify({"error": "Đăng nhập hoặc cung cấp Bearer device token"}), 401
    payload = request.get_json(force=True, silent=False) or {}
    wifi = payload.get("wifi")
    room_name = str(payload.get("room", "")).strip()
    session_code = str(payload.get("session_id", "")).strip()
    if not isinstance(wifi, dict) or not wifi or not room_name or not session_code:
        return jsonify({"error": "wifi, room và session_id là bắt buộc"}), 400
    try:
        clean_wifi = {str(key): float(value) for key, value in wifi.items()}
        target, orientations, required_sessions = calibration_settings()
        session_target = (target + required_sessions - 1) // required_sessions
        result = db.record_wifi_scan(
            home_id=home["id"], room_name=room_name, session_code=session_code,
            device_name=str(payload.get("device_id", device["name"] if device else "web-collector")),
            wifi=clean_wifi, orientation=str(payload.get("orientation", "UNKNOWN")),
            timestamp=float(payload.get("timestamp", time.time())),
            collector_device_id=device["id"] if device else None,
            target_samples=session_target, required_orientations=orientations,
        )
    except (TypeError, ValueError, LookupError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, **result})


@app.post("/api/scan")
def scan():
    home, _device = request_home_context()
    if not home:
        return jsonify({"error": "Đăng nhập hoặc cung cấp Bearer device token"}), 401
    progress = home_progress(home["id"])
    if not progress["localization_ready"]:
        return jsonify({"error": "CALIBRATION_REQUIRED", "calibration": progress}), 409
    payload = request.get_json(force=True, silent=False) or {}
    wifi = payload.get("wifi")
    if not isinstance(wifi, dict) or not wifi:
        return jsonify({"error": "wifi phải là object RSSI không rỗng"}), 400
    home_engine = get_home_engine(home["id"])
    if home_engine is None:
        return jsonify({"error": "MODEL_NOT_AVAILABLE"}), 409
    with lock:
        result = home_engine.process_scan(wifi, payload.get("timestamp"))
        if result.get("room"):
            persist_result(home["id"], result)
    return jsonify(result)


@app.post("/api/demo/scan")
@login_required
def demo_scan():
    home, error = require_active_home()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    requested_room = payload.get("room")
    if requested_room is not None and requested_room not in cfg["rooms"]:
        return jsonify({"error": "unknown room", "rooms": cfg["rooms"]}), 400
    with lock:
        source_room, wifi = demo_source.next(requested_room)
        result = demo_engine.process_scan(wifi)
        result["demo_source_room"] = source_room
        result["demo"] = True
        last_results[home["id"]] = result
        if result.get("room"):
            runtime_histories[home["id"]].append(result)
    return jsonify(result)


@app.post("/api/sensor")
def sensor_update():
    home, _device = request_home_context()
    if not home:
        return jsonify({"error": "Đăng nhập hoặc cung cấp Bearer device token"}), 401
    payload = request.get_json(force=True, silent=False) or {}
    acceleration = payload.get("acceleration")
    if not isinstance(acceleration, dict):
        return jsonify({"error": "acceleration phải có x, y và z"}), 400
    with lock:
        monitor = sensor_monitors.setdefault(home["id"], new_sensor_monitor())
        alert_count = len(monitor.alerts)
        try:
            result = monitor.update(payload.get("device_id", "phone-pwa"), acceleration, payload.get("timestamp"))
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        db.save_sensor_sample(home["id"], acceleration, result)
        if len(monitor.alerts) > alert_count:
            db.save_alert(home["id"], monitor.alerts[-1])
    return jsonify(result)


@app.get("/api/sensor/status")
@login_required
def sensor_status():
    home, error = require_active_home()
    if error:
        return error
    monitor = sensor_monitors.get(home["id"])
    snapshot = monitor.status(request.args.get("device_id")) if monitor else None
    return jsonify(snapshot or {"state": "NO_DATA"})


@app.get("/api/status")
@login_required
def status():
    home, error = require_active_home()
    if error:
        return error
    result = deepcopy(last_results.get(home["id"], {"status": "NO_DATA", "room": None}))
    result["home"] = {"id": home["id"], "name": home["name"]}
    result["calibration"] = home_progress(home["id"])
    monitor = sensor_monitors.get(home["id"])
    result["mobile_sensor"] = monitor.status() if monitor else None
    return jsonify(result)


@app.get("/api/history")
@login_required
def history():
    home, error = require_active_home()
    if error:
        return error
    persisted = db.prediction_history(home["id"], 300)
    runtime = list(runtime_histories.get(home["id"], []))
    return jsonify((persisted + runtime)[-300:])


@app.get("/api/alerts")
@login_required
def alerts():
    home, error = require_active_home()
    if error:
        return error
    return jsonify(db.list_alerts(home["id"], 100))


@app.get("/api/config")
@login_required
def public_config():
    home, error = require_active_home()
    if error:
        return error
    return jsonify({
        "rooms": db.list_rooms(home["id"]),
        "calibration": home_progress(home["id"]),
        "window_size": cfg["data"]["window_size"],
        "disclaimer": "Không phải thiết bị y tế hoặc hệ thống xác nhận té ngã.",
    })


@app.get("/api/metrics")
@login_required
def metrics():
    home, error = require_active_home()
    if error:
        return error
    model_dir = ROOT / "models" / "homes" / str(home["id"])
    return jsonify({
        **collect_model_metrics(model_dir, ROOT / "models"),
        "data_notice": "Kết quả riêng của căn nhà đang chọn; chỉ xuất hiện sau khi huấn luyện.",
    })


@app.get("/api/export/scans.csv")
@login_required
def export_scans():
    home, error = require_active_home()
    if error:
        return error
    scans = db.export_scans(home["id"])
    aps = sorted({ap for scan in scans for ap in json.loads(scan["wifi_json"]).keys()})
    fields = ["timestamp", "session_id", "device_id", "room", "orientation", *aps]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for scan in scans:
        wifi = json.loads(scan.pop("wifi_json"))
        writer.writerow({**scan, **wifi})
    return Response(
        output.getvalue(), mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="home-{home["id"]}-wifi-scans.csv"'},
    )


def run_training(home_id: int) -> None:
    training_jobs[home_id] = {"status": "TRAINING", "started_at": time.time(), "message": "Đang huấn luyện"}
    try:
        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "train_home.py"), "--home-id", str(home_id), "--database", str(db.path)],
            cwd=ROOT, capture_output=True, text=True, timeout=7200,
        )
        if process.returncode != 0:
            raise RuntimeError((process.stderr or process.stdout)[-1200:])
        home_engines.pop(home_id, None)
        training_jobs[home_id] = {"status": "READY", "finished_at": time.time(), "message": "Model đã sẵn sàng"}
    except Exception as exc:
        db.set_model_status(home_id, "FAILED")
        training_jobs[home_id] = {"status": "FAILED", "finished_at": time.time(), "message": str(exc)[-1200:]}


@app.post("/api/training/start")
@login_required
def start_training():
    home, error = require_active_home()
    if error:
        return error
    progress = home_progress(home["id"])
    if not progress["data_ready"]:
        return jsonify({"error": "CALIBRATION_INCOMPLETE", "calibration": progress}), 409
    if training_jobs.get(home["id"], {}).get("status") == "TRAINING":
        return jsonify(training_jobs[home["id"]]), 202
    db.set_model_status(home["id"], "TRAINING")
    threading.Thread(target=run_training, args=(home["id"],), daemon=True).start()
    return jsonify({"status": "TRAINING"}), 202


@app.get("/api/training/status")
@login_required
def training_status():
    home, error = require_active_home()
    if error:
        return error
    return jsonify(training_jobs.get(home["id"], {"status": home["model_status"]}))


@app.post("/api/reset")
@login_required
def reset():
    home, error = require_active_home()
    if error:
        return error
    with lock:
        last_results.pop(home["id"], None)
        runtime_histories.pop(home["id"], None)
        sensor_monitors.pop(home["id"], None)
        alert_throttle.reset(home["id"])
        if home["id"] in home_engines:
            home_engines[home["id"]].reset()
        demo_engine.reset()
        demo_source.reset()
    return jsonify({"ok": True, "persistent_data_kept": True})


if __name__ == "__main__":
    server_cfg = cfg["server"]
    cert = os.getenv("SMART_HOME_SSL_CERT")
    key = os.getenv("SMART_HOME_SSL_KEY")
    app.run(
        host=server_cfg["host"], port=int(server_cfg["port"]), debug=False,
        ssl_context=(cert, key) if cert and key else None,
    )
