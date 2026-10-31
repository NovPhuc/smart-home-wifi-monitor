from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from functools import wraps
from pathlib import Path
import csv
import io
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import threading
import time

from flask import Flask, Response, jsonify, render_template, request, send_from_directory, session as flask_session
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smarthome.alerts import AlertThrottle
from smarthome.config import load_config
from smarthome.inference import SmartHomeInferenceEngine
from smarthome.metrics import collect_model_metrics
from smarthome.mobile_sensor import MobileSensorMonitor
from smarthome.storage import SmartHomeDatabase


cfg = load_config(ROOT / "config.yaml")
def resolve_secret_key() -> str:
    """Khóa ký session cookie.

    Ưu tiên biến môi trường SMART_HOME_SECRET_KEY (README đã hướng dẫn).
    Nếu không có, sinh khóa ngẫu nhiên và lưu vào file data/secret_key để
    phiên đăng nhập (kể cả app Android khôi phục phiên) không mất sau mỗi
    lần khởi động lại. Bản cũ dùng chuỗi cố định
    "change-this-development-secret" — ai đọc được source có thể tự ký
    cookie để giả mạo đăng nhập, nên không bao giờ dùng khóa mặc định.
    """
    from_env = os.getenv("SMART_HOME_SECRET_KEY", "").strip()
    if from_env:
        return from_env
    database_path = Path(os.getenv("SMART_HOME_DATABASE", ROOT / "data" / "smarthome.db"))
    key_file = database_path.parent / "secret_key"
    try:
        if key_file.exists():
            stored = key_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        key = secrets.token_hex(32)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key, encoding="utf-8")
        print(f"[Bao mat] SMART_HOME_SECRET_KEY chua dat — da sinh khoa moi, luu tai {key_file} (khong dua len Git).")
        return key
    except OSError:
        print("[Bao mat] SMART_HOME_SECRET_KEY chua dat — dung khoa ngau nhien cho phien nay, doi sau khi restart.")
        return secrets.token_hex(32)


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY=resolve_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SMART_HOME_SECURE_COOKIE", "0") == "1",
    MAX_CONTENT_LENGTH=1_000_000,
)

db = SmartHomeDatabase(os.getenv("SMART_HOME_DATABASE", ROOT / "data" / "smarthome.db"))


@app.after_request
def security_headers(response: Response) -> Response:
    """Header bảo mật cơ bản cho trình duyệt.

    - nosniff: chặn trình duyệt đoán kiểu nội dung.
    - X-Frame-Options / frame-ancestors: chặn nhúng dashboard trong iframe
      (clickjacking).
    - CSP: chỉ cho phép tài nguyên cùng nguồn. style-src cần 'unsafe-inline'
      vì app.js vẽ thanh xác suất bằng thuộc tính style nội tuyến
      (style="transform:scaleX(...)").
    """
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    return response
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


class AttemptLimiter:
    """Chặn dò mật khẩu / dò mã chia sẻ bằng cách thử lặp.

    Mỗi khóa (email khi đăng nhập, user khi tham gia nhà) chỉ được thất bại
    tối đa ``max_attempts`` lần trong ``window_seconds``; thành công thì xóa
    đếm. Bộ đếm nằm trong RAM — khởi động lại server là xóa — đủ cho máy chủ
    gia đình mà không cần thêm thư viện. Mốc 10.000 khóa chặn phình bộ nhớ
    khi bị dò hàng loạt email khác nhau.
    """

    def __init__(self, max_attempts: int, window_seconds: float):
        self.max_attempts = int(max_attempts)
        self.window_seconds = float(window_seconds)
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_blocked(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            attempts = self._failures[key]
            while attempts and now - attempts[0] > self.window_seconds:
                attempts.popleft()
            return len(attempts) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            if len(self._failures) > 10_000:
                self._failures.clear()
            self._failures[key].append(time.time())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset_all(self) -> None:
        with self._lock:
            self._failures.clear()


# 5 lần sai trong 15 phút: đủ rộng cho gõ tay nhầm, đủ chặt để dò thủ công
# mất hàng tháng thay vì vài giờ (mã chia sẻ chỉ có 10^6 khả năng).
login_limiter = AttemptLimiter(max_attempts=5, window_seconds=900)
join_code_limiter = AttemptLimiter(max_attempts=5, window_seconds=900)
# Giới hạn mã chia sẻ tính theo user_id, nên nếu đăng ký không giới hạn thì kẻ
# tấn công chỉ cần tạo tài khoản mới là lại có 5 lượt thử — 10^6 mã sẽ bị dò hết
# sau vài trăm nghìn tài khoản. Chặn luôn ở cửa đăng ký, tính theo IP.
register_limiter = AttemptLimiter(max_attempts=10, window_seconds=3600)

# Hash giả chỉ để tốn thời gian như một lần kiểm tra thật, chống đoán email
# nào đã đăng ký qua độ trễ phản hồi (timing attack).
DUMMY_PASSWORD_HASH = generate_password_hash("tai-khoan-khong-ton-tai")


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
    home = db.get_owned_home(int(user_id), int(home_id)) if home_id else None
    if home:
        return home, None
    if active_home():
        return None, (jsonify({"error": "HOME_OWNER_REQUIRED", "detail": "Tài khoản chia sẻ chỉ có quyền xem"}), 403)
    return None, (jsonify({"error": "HOME_REQUIRED"}), 400)


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
        if not user_id or not db.is_home_owner(home["id"], int(user_id)):
            return None, None, (jsonify({"error": "HOME_OWNER_REQUIRED", "detail": "Tài khoản chia sẻ chỉ có quyền xem"}), 403)
    return home, device, None


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
    client_ip = request.remote_addr or "unknown"
    if register_limiter.is_blocked(client_ip):
        return jsonify({
            "error": "TOO_MANY_ATTEMPTS",
            "detail": "Tạo tài khoản quá nhiều lần. Thử lại sau.",
        }), 429
    register_limiter.record_failure(client_ip)
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
    elif len(password) > 128:
        errors["password"] = "Mật khẩu tối đa 128 ký tự"
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
    email = str(payload.get("email", "")).strip().lower()
    # Khóa theo email: kẻ dò một tài khoản bị chặn, các tài khoản khác không
    # ảnh hưởng. Đánh đổi: người xấu có thể cố tình khóa email của nạn nhân.
    if login_limiter.is_blocked(email):
        return jsonify({"error": "TOO_MANY_ATTEMPTS", "detail": "Thử lại sau 15 phút"}), 429
    user = db.get_user_by_email(email)
    if user is None:
        # Email không tồn tại vẫn chạy một lần băm để thời gian phản hồi
        # giống hệt trường hợp sai mật khẩu.
        check_password_hash(DUMMY_PASSWORD_HASH, str(payload.get("password", "")))
    if not user or not check_password_hash(user["password_hash"], str(payload.get("password", ""))):
        login_limiter.record_failure(email)
        return jsonify({"error": "INVALID_CREDENTIALS"}), 401
    login_limiter.reset(email)
    flask_session.clear()
    flask_session["user_id"] = user["id"]
    homes = db.list_homes(user["id"])
    if homes:
        flask_session["active_home_id"] = homes[0]["id"]
    return jsonify({
        "ok": True,
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
        "homes": homes,
        "active_home": homes[0] if homes else None,
    })


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


@app.get("/api/homes/<int:home_id>/share")
@login_required
def get_share(home_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    share = db.active_share(home_id)
    ttl = float(cfg.get("sharing", {}).get("code_ttl_hours", 24))
    return jsonify({"share": share, "ttl_hours": ttl})


@app.post("/api/homes/<int:home_id>/share")
@login_required
def rotate_share(home_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    ttl = float(cfg.get("sharing", {}).get("code_ttl_hours", 24))
    share = db.create_share_code(home_id, int(flask_session["user_id"]), ttl)
    return jsonify({"share": share, "ttl_hours": ttl}), 201


@app.delete("/api/homes/<int:home_id>/share")
@login_required
def drop_share(home_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    return jsonify({"ok": db.revoke_share_code(home_id)})


@app.get("/api/homes/<int:home_id>/members")
@login_required
def members(home_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    return jsonify(db.list_home_members(home_id))


@app.delete("/api/homes/<int:home_id>/members/<int:user_id>")
@login_required
def kick_member(home_id: int, user_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    return jsonify({"ok": db.remove_home_member(home_id, user_id)})


@app.post("/api/homes/join")
@login_required
def join_home():
    payload = request.get_json(force=True, silent=False) or {}
    code = str(payload.get("code", "")).strip()
    if not code.isdigit() or len(code) != 6:
        return jsonify({"error": "Mã chia sẻ gồm 6 chữ số"}), 400
    user_id = int(flask_session["user_id"])
    if join_code_limiter.is_blocked(str(user_id)):
        return jsonify({"error": "TOO_MANY_ATTEMPTS", "detail": "Thử lại sau 15 phút"}), 429
    try:
        home = db.join_home_by_code(user_id, code)
    except LookupError as exc:
        # Mã sai/hết hạn là một lần đoán — đếm vào hạn mức dò mã.
        join_code_limiter.record_failure(str(user_id))
        return jsonify({"error": str(exc)}), 404
    join_code_limiter.reset(str(user_id))
    flask_session["active_home_id"] = home["id"]
    return jsonify({"joined_home": home})


def require_owned_home_by_id(home_id: int):
    home = db.get_owned_home(int(flask_session["user_id"]), home_id)
    if not home:
        if db.get_home(int(flask_session["user_id"]), home_id):
            return None, (jsonify({"error": "HOME_OWNER_REQUIRED", "detail": "Tài khoản chia sẻ chỉ có quyền xem"}), 403)
        return None, (jsonify({"error": "Không tìm thấy nhà"}), 404)
    return home, None


@app.route("/api/rooms", methods=["GET", "POST"])
@login_required
def rooms():
    home, error = require_owned_home() if request.method == "POST" else require_active_home()
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
    home, error = require_owned_home()
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
    home, error = require_owned_home() if request.method == "POST" else require_active_home()
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
    home, error = require_owned_home()
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
    home, device, error = require_mutation_context()
    if error:
        return error
    payload = request.get_json(force=True, silent=False) or {}
    wifi = payload.get("wifi")
    room_name = str(payload.get("room", "")).strip()
    session_code = str(payload.get("session_id", "")).strip()
    if not isinstance(wifi, dict) or not wifi or not room_name or not session_code:
        return jsonify({"error": "wifi, room và session_id là bắt buộc"}), 400
    if len(session_code) > 40:
        return jsonify({"error": "session_id tối đa 40 ký tự"}), 400
    if len(wifi) > 64:
        return jsonify({"error": "Tối đa 64 access point mỗi lần quét"}), 400
    try:
        clean_wifi = {str(key)[:64]: float(value) for key, value in wifi.items()}
        target, orientations, required_sessions = calibration_settings()
        session_target = (target + required_sessions - 1) // required_sessions
        result = db.record_wifi_scan(
            home_id=home["id"], room_name=room_name, session_code=session_code,
            device_name=str(payload.get("device_id", device["name"] if device else "web-collector"))[:80],
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
        # Chuẩn hóa trước khi đưa vào model: giá trị sai phải trả 400 thay vì
        # để float() trong preprocessor ném lỗi 500.
        clean_wifi = {str(key)[:64]: float(value) for key, value in wifi.items()}
    except (TypeError, ValueError):
        return jsonify({"error": "Giá trị RSSI phải là số"}), 400
    try:
        scan_timestamp = float(payload["timestamp"]) if payload.get("timestamp") is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "timestamp phải là số"}), 400
    home_engine = get_home_engine(home["id"])
    if home_engine is None:
        return jsonify({"error": "MODEL_NOT_AVAILABLE"}), 409
    with lock:
        result = home_engine.process_scan(clean_wifi, scan_timestamp)
        if result.get("room"):
            persist_result(home["id"], result)
    return jsonify(result)


@app.post("/api/demo/scan")
@login_required
def demo_scan():
    home, error = require_owned_home()
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
    home, _device, error = require_mutation_context()
    if error:
        return error
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


def csv_formula_safe(value) -> str:
    """Chống "CSV injection" khi mở file export bằng Excel/LibreOffice.

    Ô văn bản bắt đầu bằng ``=`` ``+`` ``-`` ``@`` có thể bị hiểu là công
    thức (ví dụ tên phòng do người dùng tự đặt). Thêm dấu nháy đơn phía
    trước để Excel đọc nguyên chuỗi. Chỉ áp dụng cho các cột văn bản —
    cột RSSI là số âm thật và phải giữ nguyên.
    """
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


@app.get("/api/export/scans.csv")
@login_required
def export_scans():
    home, error = require_owned_home()
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
        row = {**scan, **wifi}
        for field in ("session_id", "device_id", "room", "orientation"):
            row[field] = csv_formula_safe(row.get(field, ""))
        writer.writerow(row)
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
    home, error = require_owned_home()
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
    home, error = require_owned_home()
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
    import atexit

    server_cfg = cfg["server"]
    host = server_cfg["host"]
    port = int(server_cfg["port"])
    cert = os.getenv("SMART_HOME_SSL_CERT")
    key = os.getenv("SMART_HOME_SSL_KEY")
    if cert and key and os.getenv("SMART_HOME_SECURE_COOKIE") is None:
        # Chạy HTTPS thật thì cookie phiên phải chỉ gửi qua kết nối mã hóa.
        app.config["SESSION_COOKIE_SECURE"] = True
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
