#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tạo database sạch cho phát hành — chỉ giữ demo/test data."""
from __future__ import annotations
import sqlite3
import os
from pathlib import Path
from werkzeug.security import generate_password_hash

SRC_DB = Path("/app/data/smarthome.db")
DST_DB = Path("/app/data/smarthome_clean.db")

# Schema từ storage.py
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS homes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    max_dwell_minutes REAL NOT NULL DEFAULT 60,
    created_at REAL NOT NULL,
    _name_key TEXT NOT NULL DEFAULT ''
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
    target_samples INTEGER NOT NULL,
    started_at REAL NOT NULL,
    completed_at REAL,
    status TEXT NOT NULL DEFAULT 'IN_PROGRESS'
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
    wifi_json TEXT NOT NULL,
    scan_ts REAL,
    wifi_hash TEXT
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
CREATE TABLE IF NOT EXISTS home_shares (
    code TEXT PRIMARY KEY,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    revoked_at REAL
);
CREATE TABLE IF NOT EXISTS home_members (
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at REAL NOT NULL,
    PRIMARY KEY (home_id, user_id)
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    room_name TEXT,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    device_id TEXT,
    resolved_at REAL
);
CREATE INDEX IF NOT EXISTS idx_wifi_scans_home_room ON wifi_scans(home_id, room_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_predictions_home_time ON predictions(home_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_home_time ON alerts(home_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_home_time ON sensor_samples(home_id, timestamp DESC);
"""

import time

def main():
    # Kết nối DB nguồn và đích
    src = sqlite3.connect(SRC_DB)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(DST_DB)
    dst.row_factory = sqlite3.Row
    
    # Tạo schema sạch
    dst.executescript(SCHEMA)
    
    # Chỉ copy user demo
    demo_users = [
        ("demo@home.vn", generate_password_hash("demo123"), "Gia dinh demo"),
    ]
    
    now = time.time()
    with dst:
        for email, pwd_hash, name in demo_users:
            dst.execute(
                "INSERT INTO users (email, password_hash, display_name, created_at) VALUES (?,?,?,?)",
                (email, pwd_hash, name, now)
            )
        demo_user_id = dst.execute("SELECT id FROM users WHERE email=?", ("demo@home.vn",)).fetchone()[0]
        
        # Tạo 1 home demo
        dst.execute(
            "INSERT INTO homes (name, owner_id, created_at) VALUES (?,?,?)",
            ("Nhà demo", demo_user_id, now)
        )
        home_id = dst.execute("SELECT id FROM homes WHERE owner_id=?", (demo_user_id,)).fetchone()[0]
        
        # Tạo rooms mặc định
        rooms = ["Phòng ngủ", "Phòng khách", "Phòng bếp", "Nhà tắm"]
        for room in rooms:
            dst.execute(
                "INSERT INTO rooms (home_id, name, max_dwell_minutes, created_at, _name_key) VALUES (?,?,?,?,?)",
                (home_id, room, 60, now, room.lower().replace(" ", "_"))
            )
        
        # Tạo device demo
        import secrets
        token = secrets.token_urlsafe(28)
        token_hash = generate_password_hash(token)  # dùng generate_password_hash để nhất quán
        token_hint = token[:6]
        dst.execute(
            "INSERT INTO collector_devices (home_id, name, platform, token_hash, token_hint, created_at) VALUES (?,?,?,?,?,?)",
            (home_id, "Điện thoại demo", "android", token_hash, token_hint, now)
        )
        
        # Tạo share code demo
        share_code = "123456"
        dst.execute(
            "INSERT INTO home_shares (code, home_id, created_by, created_at, expires_at) VALUES (?,?,?,?,?)",
            (share_code, home_id, demo_user_id, now, now + 86400)
        )
        
        # Thêm secret_key nếu chưa có
        dst.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        dst.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", ("secret_key", secrets.token_hex(32)))
    
    print("✓ Đã tạo smarthome_clean.db chỉ chứa demo data")
    print(f"  User: demo@home.vn / demo123")
    print(f"  Home: Nhà demo (id={home_id})")
    print(f"  Device token: {token}")
    print(f"  Share code: {share_code}")

if __name__ == "__main__":
    main()