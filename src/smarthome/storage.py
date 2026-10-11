from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import secrets
import sqlite3
import time
import unicodedata


def _norm_room_name(name: str) -> str:
    """Chuẩn hóa tên phòng để tìm kiếm không phân biệt kiểu chữ và dấu.

    Dùng lower case Unicode kết hợp NFC Normalize để đảm bảo:
    - "Phòng Ngủ", "phòng ngủ", "PHÒNG NGỦ" → cùng giá trị
    - "Phòng Ngủ" và "Phòng ngu" vẫn khác (vẫn phân biệt chính tả)
    """
    return unicodedata.normalize("NFC", name.strip()).lower()


SCHEMA_VERSION = 2

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS homes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    model_status TEXT NOT NULL DEFAULT 'NOT_TRAINED',
    created_at REAL NOT NULL,
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    _name_key TEXT NOT NULL,
    max_dwell_minutes REAL NOT NULL DEFAULT 60,
    created_at REAL NOT NULL,
    UNIQUE(home_id, _name_key)
);

CREATE TABLE IF NOT EXISTS collector_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'android',
    token_hash TEXT NOT NULL UNIQUE,
    token_hint TEXT NOT NULL,
    last_seen_at REAL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    collector_device_id INTEGER REFERENCES collector_devices(id) ON DELETE SET NULL,
    session_code TEXT NOT NULL,
    target_samples INTEGER NOT NULL DEFAULT 100,
    status TEXT NOT NULL DEFAULT 'COLLECTING',
    started_at REAL NOT NULL,
    completed_at REAL,
    UNIQUE(home_id, room_id, session_code)
);

CREATE TABLE IF NOT EXISTS wifi_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_session_id INTEGER NOT NULL REFERENCES collection_sessions(id) ON DELETE CASCADE,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    orientation TEXT NOT NULL DEFAULT 'UNKNOWN',
    ap_count INTEGER NOT NULL,
    wifi_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    room_name TEXT,
    confidence REAL,
    status TEXT NOT NULL,
    activity TEXT,
    anomaly_score REAL,
    reasons_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS sensor_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    magnitude REAL NOT NULL,
    state TEXT NOT NULL,
    possible_impact INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    room_name TEXT,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    reasons_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wifi_scans_home_room ON wifi_scans(home_id, room_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_predictions_home_time ON predictions(home_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_home_time ON alerts(home_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_home_time ON sensor_samples(home_id, timestamp DESC);
"""


class SmartHomeDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version < SCHEMA_VERSION:
                self._migrate_rooms_name_key(connection)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _migrate_rooms_name_key(connection: sqlite3.Connection) -> None:
        """Backfill ``rooms._name_key`` with the same normaliser used at runtime.

        Databases written before ``_name_key`` existed, and databases migrated by
        the earlier version of this method, filled the key with SQLite's
        ``LOWER(name)``. ``LOWER()`` only folds ASCII ``A-Z``, so Vietnamese room
        names with uppercase diacritics ("NHÀ VỆ SINH", "PHÒNG NGỦ") produced
        keys that never matched :func:`_norm_room_name`, leaving already-collected
        rooms unreachable. Recompute every key in Python and rebuild the unique
        index so persistence and lookups agree.
        """
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(rooms)").fetchall()}
        if "_name_key" not in columns:
            connection.execute("ALTER TABLE rooms ADD COLUMN _name_key TEXT NOT NULL DEFAULT ''")
        # Drop the index while keys are rewritten so conflicting legacy rows are
        # resolved before uniqueness is enforced again.
        connection.execute("DROP INDEX IF EXISTS idx_rooms_home_name_key")
        seen: dict[tuple[int, str], int] = {}
        updates: list[tuple[str, int]] = []
        for row in connection.execute(
            "SELECT id, home_id, name, _name_key FROM rooms ORDER BY id"
        ).fetchall():
            key = _norm_room_name(row["name"])
            scope = (int(row["home_id"]), key)
            if scope in seen:
                # Legacy rows can collapse to the same key ("Kitchen"/"kitchen").
                # Keep the first and give the rest a stable suffix instead of
                # failing to build the unique index at startup.
                key = f"{key}#{row['id']}"
            seen[scope] = int(row["id"])
            if row["_name_key"] != key:
                updates.append((key, int(row["id"])))
        if updates:
            connection.executemany("UPDATE rooms SET _name_key=? WHERE id=?", updates)
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_rooms_home_name_key ON rooms(home_id, _name_key)"
        )

    @staticmethod
    def _dict(row: sqlite3.Row | None) -> dict | None:
        return dict(row) if row else None

    def create_user(self, email: str, password_hash: str, display_name: str) -> dict:
        now = time.time()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users(email, password_hash, display_name, created_at) VALUES(?,?,?,?)",
                (email.strip().lower(), password_hash, display_name.strip(), now),
            )
            return self.get_user(cursor.lastrowid, connection)

    def get_user(self, user_id: int, connection=None) -> dict | None:
        if connection is not None:
            return self._dict(connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        with self.connect() as owned:
            return self.get_user(user_id, owned)

    def get_user_by_email(self, email: str) -> dict | None:
        with self.connect() as connection:
            return self._dict(connection.execute(
                "SELECT * FROM users WHERE email=? COLLATE NOCASE", (email.strip(),)
            ).fetchone())

    def create_home(self, user_id: int, name: str) -> dict:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO homes(user_id, name, created_at) VALUES(?,?,?)",
                (user_id, name.strip(), time.time()),
            )
            return self._dict(connection.execute("SELECT * FROM homes WHERE id=?", (cursor.lastrowid,)).fetchone())

    def list_homes(self, user_id: int) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM homes WHERE user_id=? ORDER BY created_at", (user_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_home(self, user_id: int, home_id: int) -> dict | None:
        with self.connect() as connection:
            return self._dict(connection.execute(
                "SELECT * FROM homes WHERE id=? AND user_id=?", (home_id, user_id)
            ).fetchone())

    def rename_home(self, user_id: int, home_id: int, name: str) -> bool:
        with self.connect() as connection:
            return connection.execute(
                "UPDATE homes SET name=? WHERE id=? AND user_id=?", (name.strip(), home_id, user_id)
            ).rowcount == 1

    def delete_home(self, user_id: int, home_id: int) -> bool:
        with self.connect() as connection:
            return connection.execute(
                "DELETE FROM homes WHERE id=? AND user_id=?", (home_id, user_id)
            ).rowcount == 1

    def set_model_status(self, home_id: int, status: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE homes SET model_status=? WHERE id=?", (status, home_id))

    def find_room_by_name(self, home_id: int, name: str) -> dict | None:
        """Tìm phòng theo tên đã chuẩn hóa, hỗ trợ nhập khớp bất kể hoa/thường và dấu."""
        key = _norm_room_name(name)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM rooms WHERE home_id=? AND _name_key=?",
                (home_id, key),
            ).fetchone()
            return self._dict(row) if row else None

    def create_room(self, home_id: int, name: str, max_dwell_minutes: float = 60) -> dict:
        normalized = _norm_room_name(name)
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO rooms(home_id, name, _name_key, max_dwell_minutes, created_at) VALUES(?,?,?,?,?)",
                (home_id, name.strip(), normalized, float(max_dwell_minutes), time.time()),
            )
            return self._dict(connection.execute("SELECT * FROM rooms WHERE id=?", (cursor.lastrowid,)).fetchone())

    def list_rooms(self, home_id: int) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, home_id, name, max_dwell_minutes, created_at FROM rooms WHERE home_id=? ORDER BY created_at",
                (home_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def update_room(self, home_id: int, room_id: int, name: str, max_dwell_minutes: float) -> bool:
        normalized = _norm_room_name(name)
        with self.connect() as connection:
            return connection.execute(
                "UPDATE rooms SET name=?, _name_key=?, max_dwell_minutes=? WHERE id=? AND home_id=?",
                (name.strip(), normalized, float(max_dwell_minutes), room_id, home_id),
            ).rowcount == 1

    def delete_room(self, home_id: int, room_id: int) -> bool:
        with self.connect() as connection:
            return connection.execute(
                "DELETE FROM rooms WHERE id=? AND home_id=?", (room_id, home_id)
            ).rowcount == 1

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_device(self, home_id: int, name: str, platform: str = "android") -> tuple[dict, str]:
        token = "ath_" + secrets.token_urlsafe(28)
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO collector_devices(home_id,name,platform,token_hash,token_hint,created_at) VALUES(?,?,?,?,?,?)",
                (home_id, name.strip(), platform.strip().lower(), self._token_hash(token), token[-6:], time.time()),
            )
            device = self._dict(connection.execute(
                "SELECT id,home_id,name,platform,token_hint,last_seen_at,created_at FROM collector_devices WHERE id=?",
                (cursor.lastrowid,),
            ).fetchone())
        return device, token

    def list_devices(self, home_id: int) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id,home_id,name,platform,token_hint,last_seen_at,created_at FROM collector_devices WHERE home_id=? ORDER BY created_at",
                (home_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def revoke_device(self, home_id: int, device_id: int) -> bool:
        with self.connect() as connection:
            return connection.execute(
                "DELETE FROM collector_devices WHERE id=? AND home_id=?", (device_id, home_id)
            ).rowcount == 1

    def authenticate_device(self, token: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM collector_devices WHERE token_hash=?", (self._token_hash(token),)
            ).fetchone()
            if not row:
                return None
            connection.execute("UPDATE collector_devices SET last_seen_at=? WHERE id=?", (time.time(), row["id"]))
            return dict(row)

    def record_wifi_scan(
        self,
        home_id: int,
        room_name: str,
        session_code: str,
        device_name: str,
        wifi: dict[str, float],
        orientation: str,
        timestamp: float,
        collector_device_id: int | None = None,
        target_samples: int = 100,
        required_orientations: int = 3,
    ) -> dict:
        orientation = (orientation or "UNKNOWN").strip().upper()[:32]
        normalized = _norm_room_name(room_name)
        with self.connect() as connection:
            room = connection.execute(
                "SELECT * FROM rooms WHERE home_id=? AND _name_key=?",
                (home_id, normalized),
            ).fetchone()
            if not room:
                raise LookupError("Room does not exist in the selected home")
            session_row = connection.execute(
                "SELECT * FROM collection_sessions WHERE home_id=? AND room_id=? AND session_code=?",
                (home_id, room["id"], session_code.strip()),
            ).fetchone()
            if not session_row:
                cursor = connection.execute(
                    "INSERT INTO collection_sessions(home_id,room_id,collector_device_id,session_code,target_samples,started_at) VALUES(?,?,?,?,?,?)",
                    (home_id, room["id"], collector_device_id, session_code.strip(), int(target_samples), time.time()),
                )
                session_id = cursor.lastrowid
            else:
                session_id = session_row["id"]
            connection.execute(
                "INSERT INTO wifi_scans(collection_session_id,home_id,room_id,device_id,timestamp,orientation,ap_count,wifi_json) VALUES(?,?,?,?,?,?,?,?)",
                (session_id, home_id, room["id"], device_name, float(timestamp), orientation, len(wifi), json.dumps(wifi)),
            )
            counts = connection.execute(
                "SELECT COUNT(*) AS samples, COUNT(DISTINCT CASE WHEN orientation!='UNKNOWN' THEN orientation END) AS orientations FROM wifi_scans WHERE collection_session_id=?",
                (session_id,),
            ).fetchone()
            ready = counts["samples"] >= int(target_samples) and counts["orientations"] >= int(required_orientations)
            if ready:
                connection.execute(
                    "UPDATE collection_sessions SET status='COMPLETE', completed_at=COALESCE(completed_at,?) WHERE id=?",
                    (time.time(), session_id),
                )
            return {
                "session_id": session_id,
                "session_code": session_code,
                "room_id": room["id"],
                "room": room["name"],
                "samples": counts["samples"],
                "orientations": counts["orientations"],
                "target_samples": int(target_samples),
                "ready": ready,
                "aps": len(wifi),
            }

    def calibration_progress(
        self,
        home_id: int,
        target_samples: int = 100,
        required_orientations: int = 3,
        required_sessions: int = 3,
    ) -> dict:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT r.id, r.name,
                       COUNT(ws.id) AS samples,
                       COUNT(DISTINCT CASE WHEN ws.orientation!='UNKNOWN' THEN ws.orientation END) AS orientations,
                       COUNT(DISTINCT cs.session_code) AS sessions
                FROM rooms r
                LEFT JOIN collection_sessions cs ON cs.room_id=r.id
                LEFT JOIN wifi_scans ws ON ws.collection_session_id=cs.id
                WHERE r.home_id=?
                GROUP BY r.id, r.name
                ORDER BY r.created_at
                """,
                (home_id,),
            ).fetchall()
            home = connection.execute("SELECT model_status FROM homes WHERE id=?", (home_id,)).fetchone()
        rooms = []
        for row in rows:
            item = dict(row)
            item["target_samples"] = int(target_samples)
            item["required_orientations"] = int(required_orientations)
            item["required_sessions"] = int(required_sessions)
            item["ready"] = (
                item["samples"] >= target_samples
                and item["orientations"] >= required_orientations
                and item["sessions"] >= required_sessions
            )
            rooms.append(item)
        data_ready = len(rooms) >= 2 and all(room["ready"] for room in rooms)
        return {
            "rooms": rooms,
            "data_ready": data_ready,
            "model_status": home["model_status"] if home else "NOT_TRAINED",
            "localization_ready": data_ready and home is not None and home["model_status"] == "READY",
        }

    def save_prediction(self, home_id: int, result: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO predictions(home_id,timestamp,room_name,confidence,status,activity,anomaly_score,reasons_json) VALUES(?,?,?,?,?,?,?,?)",
                (
                    home_id, result.get("timestamp", time.time()), result.get("room"), result.get("confidence"),
                    result.get("status", "UNKNOWN"), result.get("activity", {}).get("state"),
                    result.get("anomaly_score"), json.dumps(result.get("reasons", []), ensure_ascii=False),
                ),
            )

    def prediction_history(self, home_id: int, limit: int = 300) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM predictions WHERE home_id=? ORDER BY timestamp DESC LIMIT ?", (home_id, int(limit))
            ).fetchall()
        result = []
        for row in reversed(rows):
            item = dict(row)
            item["room"] = item.pop("room_name")
            item["reasons"] = json.loads(item.pop("reasons_json"))
            item["activity"] = {"state": item.pop("activity")} if item.get("activity") else {}
            result.append(item)
        return result

    def save_sensor_sample(self, home_id: int, acceleration: dict, snapshot: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sensor_samples(home_id,device_id,timestamp,x,y,z,magnitude,state,possible_impact) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    home_id, snapshot["device_id"], snapshot["last_seen_at"], float(acceleration.get("x", 0)),
                    float(acceleration.get("y", 0)), float(acceleration.get("z", 0)), snapshot["motion_magnitude"],
                    snapshot["state"], int(snapshot["possible_impact"]),
                ),
            )

    def save_alert(self, home_id: int, alert: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO alerts(home_id,timestamp,room_name,status,source,reasons_json) VALUES(?,?,?,?,?,?)",
                (
                    home_id, alert.get("timestamp", time.time()), alert.get("room"), alert.get("status", "WARNING"),
                    alert.get("source", "wifi"), json.dumps(alert.get("reasons", []), ensure_ascii=False),
                ),
            )

    def list_alerts(self, home_id: int, limit: int = 100) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM alerts WHERE home_id=? ORDER BY timestamp DESC LIMIT ?", (home_id, int(limit))
            ).fetchall()
        alerts = []
        for row in reversed(rows):
            item = dict(row)
            item["room"] = item.pop("room_name")
            item["reasons"] = json.loads(item.pop("reasons_json"))
            alerts.append(item)
        return alerts

    def export_scans(self, home_id: int) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT ws.timestamp, cs.session_code AS session_id, ws.device_id, r.name AS room,
                       ws.orientation, ws.wifi_json
                FROM wifi_scans ws
                JOIN rooms r ON r.id=ws.room_id
                JOIN collection_sessions cs ON cs.id=ws.collection_session_id
                WHERE ws.home_id=? ORDER BY ws.timestamp
                """,
                (home_id,),
            ).fetchall()
        return [dict(row) for row in rows]
