"""Trạng thái dùng chung của server (singleton runtime).

Tách khỏi app.py để route/service thao tác trên MỘT nguồn sự thật. Test thay
đổi ``app_state.db`` (thay database tạm) và gọi ``reset_runtime()`` giữa các
test — mọi route đọc trạng thái qua module này nên luôn nhìn thấy thay đổi.
"""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import csv
import os
import threading

ROOT = Path(__file__).resolve().parents[1]

from smarthome.alerts import AlertThrottle
from smarthome.config import load_config
from smarthome.inference import SmartHomeInferenceEngine
from smarthome.mobile_sensor import MobileSensorMonitor
from smarthome.storage import SmartHomeDatabase

from app_security import AttemptLimiter, DUMMY_PASSWORD_HASH  # noqa: F401 (re-export)

cfg = load_config(ROOT / "config.yaml")

db = SmartHomeDatabase(os.getenv("SMART_HOME_DATABASE", ROOT / "data" / "smarthome.db"))

demo_engine = SmartHomeInferenceEngine(cfg, ROOT / "models")
engine = demo_engine  # Tương thích ngược với các script cũ import `engine`.

lock = threading.RLock()
home_engines: dict[int, SmartHomeInferenceEngine] = {}
sensor_monitors: dict[int, MobileSensorMonitor] = {}
last_results: dict[int, dict] = {}
runtime_histories: dict[int, deque] = defaultdict(lambda: deque(maxlen=300))
training_jobs: dict[int, dict] = {}

alert_throttle = AlertThrottle(
    cooldown_seconds=float(cfg.get("alerts", {}).get("repeat_cooldown_seconds", 600))
)

# 5 lần sai trong 15 phút: đủ rộng cho gõ tay nhầm, đủ chặt để dò thủ công
# mất hàng tháng thay vì vài giờ (mã chia sẻ chỉ có 10^6 khả năng).
login_limiter = AttemptLimiter(max_attempts=5, window_seconds=900)
join_code_limiter = AttemptLimiter(max_attempts=5, window_seconds=900)
# Giới hạn mã chia sẻ tính theo user_id, nên nếu đăng ký không giới hạn thì kẻ
# tấn công chỉ cần tạo tài khoản mới là lại có 5 lượt thử — 10^6 mã sẽ bị dò hết
# sau vài trăm nghìn tài khoản. Chặn luôn ở cửa đăng ký, tính theo IP.
register_limiter = AttemptLimiter(max_attempts=10, window_seconds=3600)


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


def reset_runtime() -> None:
    """Về trạng thái runtime ban đầu — dùng giữa các test và /api/reset."""
    home_engines.clear()
    sensor_monitors.clear()
    last_results.clear()
    runtime_histories.clear()
    training_jobs.clear()
    alert_throttle.reset()
    login_limiter.reset_all()
    join_code_limiter.reset_all()
    register_limiter.reset_all()
