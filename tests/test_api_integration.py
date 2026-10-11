from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "server"))

# Lỗi #5: import server/app.py khởi tạo SmartHomeDatabase trỏ DB THẬT (data/smarthome.db)
# → các lần chạy test cũ từng ghi home "Nhà Smoke Test" vào DB thật. Chuyển DB của
# quá trình import sang file tạm TRƯỚC khi import (fixture bên dưới vẫn thay
# appmod.db bằng DB tmp riêng cho từng test).
import os
import tempfile
os.environ["SMART_HOME_DATABASE"] = str(Path(tempfile.gettempdir()) / "smarthome_api_tests.db")

import app as appmod  # server/app.py  (module-level Flask app + engine)
from smarthome.storage import SmartHomeDatabase


@pytest.fixture()
def client(tmp_path):
    """Fresh database and clean runtime state for every test."""
    appmod.app.config["TESTING"] = True
    appmod.db = SmartHomeDatabase(tmp_path / "api.db")
    appmod.home_engines.clear()
    appmod.sensor_monitors.clear()
    appmod.last_results.clear()
    appmod.runtime_histories.clear()
    appmod.training_jobs.clear()
    appmod.alert_throttle.reset()
    with appmod.app.test_client() as test_client:
        yield test_client


def register(client, email, home_name="Nhà của tôi"):
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "password123",
            "display_name": email.split("@")[0],
            "home_name": home_name,
        },
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()


def create_rooms(client, names):
    created = []
    for name in names:
        response = client.post("/api/rooms", json={"name": name, "max_dwell_minutes": 60})
        assert response.status_code == 201, response.get_data(as_text=True)
        created.append(response.get_json())
    return created


def test_register_and_login_round_trip(client):
    payload = register(client, "first@example.com")
    assert payload["user"]["email"] == "first@example.com"
    assert payload["active_home"]["id"]

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["display_name"] == "first"

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    bad = client.post("/api/auth/login", json={"email": "first@example.com", "password": "wrong-pass"})
    assert bad.status_code == 401

    good = client.post("/api/auth/login", json={"email": "first@example.com", "password": "password123"})
    assert good.status_code == 200


def test_register_rejects_duplicate_email(client):
    register(client, "dup@example.com")
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/register",
        json={"email": "DUP@example.com", "password": "password123", "display_name": "x", "home_name": "h"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == "EMAIL_EXISTS"


def test_second_account_cannot_see_first_accounts_home(client):
    alice = register(client, "alice@example.com", "Nhà Alice")
    alice_home = alice["active_home"]["id"]
    create_rooms(client, ["Phòng ngủ"])

    client.post("/api/auth/logout")
    register(client, "bob@example.com", "Nhà Bob")
    create_rooms(client, ["Phòng bếp"])

    rooms = client.get("/api/rooms").get_json()
    assert [room["name"] for room in rooms] == ["Phòng bếp"], "Bob must not see Alice's rooms"

    # Bob cannot switch into Alice's home.
    hijack = client.post(f"/api/homes/{alice_home}/select")
    assert hijack.status_code == 404

    # Bob's own home is untouched.
    assert [room["name"] for room in client.get("/api/rooms").get_json()] == ["Phòng bếp"]


def test_room_names_are_matched_case_and_diacritic_insensitively(client):
    register(client, "rooms@example.com")
    create_rooms(client, ["PHÒNG NGỦ"])

    lookup = client.get("/api/rooms").get_json()
    assert [room["name"] for room in lookup] == ["PHÒNG NGỦ"]

    duplicate = client.post("/api/rooms", json={"name": "phòng ngủ", "max_dwell_minutes": 30})
    assert duplicate.status_code == 409


def test_device_token_authenticates_collect_and_scopes_home(client):
    register(client, "device@example.com")
    create_rooms(client, ["Phòng ngủ", "Phòng khách"])
    device = client.post("/api/devices", json={"name": "Pixel", "platform": "android"})
    assert device.status_code == 201
    token = device.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    target, orientations, sessions = appmod.calibration_settings()
    per_session = -(-target // sessions)
    orientation_cycle = ("PORTRAIT_UP", "LANDSCAPE_LEFT", "FLAT_UP")
    for session in ("S01", "S02", "S03"):
        for room in ("Phòng ngủ", "Phòng khách"):
            for index in range(per_session):
                response = client.post(
                    "/api/collect",
                    headers=headers,
                    json={
                        "wifi": {"AP1": -50.0 - index},
                        "room": room,
                        "session_id": session,
                        "orientation": orientation_cycle[index % len(orientation_cycle)],
                        "timestamp": 1000.0 + index,
                        "device_id": "Pixel 8",
                    },
                )
                assert response.status_code == 200, response.get_data(as_text=True)

    progress = client.get("/api/calibration").get_json()
    assert progress["data_ready"] is True
    assert progress["localization_ready"] is False
    assert {room["name"]: room["samples"] for room in progress["rooms"]} == {
        "Phòng ngủ": per_session * 3,
        "Phòng khách": per_session * 3,
    }

    exported = client.get("/api/export/scans.csv")
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.get_data(as_text=True))))
    assert len(rows) == per_session * 3 * 2

    # An anonymous request must not reach the collection endpoint.
    client.post("/api/auth/logout")
    assert client.post("/api/collect", json={"wifi": {"AP1": -50.0}, "room": "x", "session_id": "S01"}).status_code == 401


def test_rejected_device_token_cannot_collect(client):
    register(client, "badtoken@example.com")
    create_rooms(client, ["Phòng ngủ"])
    response = client.post(
        "/api/collect",
        headers={"Authorization": "Bearer ath_notarealtoken"},
        json={"wifi": {"AP1": -50.0}, "room": "Phòng ngủ", "session_id": "S01"},
    )
    assert response.status_code == 401


def test_metrics_exposes_anomaly_and_baselines(client):
    register(client, "metrics@example.com")
    metrics = client.get("/api/metrics")
    assert metrics.status_code == 200
    payload = metrics.get_json()
    assert payload["anomaly_model"]["recall"] is not None
    assert payload["baselines"], "baseline comparison must not be empty"
    assert "accuracy" in payload["room_model"]


def test_scan_requires_calibration(client):
    register(client, "locked@example.com")
    create_rooms(client, ["Phòng ngủ", "Phòng khách"])
    response = client.post("/api/scan", json={"wifi": {"AP1": -50.0}})
    assert response.status_code == 409
    assert response.get_json()["error"] == "CALIBRATION_REQUIRED"


def test_persistent_warning_writes_one_alert_not_one_per_scan(client):
    register(client, "flood@example.com")
    home_id = client.get("/api/auth/me").get_json()["active_home"]["id"]
    before = appmod.db.list_alerts(home_id, 1000)

    reasons = ["Long dwell in Bedroom: 45.3 min"]
    for index in range(50):
        appmod.persist_result(home_id, {
            "timestamp": float(index),
            "room": "Bedroom",
            "status": "WARNING",
            "reasons": [f"Long dwell in Bedroom: {45.0 + index / 10:.1f} min"],
        })

    after = appmod.db.list_alerts(home_id, 1000)
    assert len(after) == len(before) + 1, "a sustained warning must not flood the alerts table"

    # Escalation is still surfaced immediately.
    appmod.persist_result(home_id, {
        "timestamp": 999.0,
        "room": "Bedroom",
        "status": "CRITICAL",
        "reasons": reasons,
    })
    assert len(appmod.db.list_alerts(home_id, 1000)) == len(before) + 2

    # A new home is tracked independently of the first.
    assert appmod.alert_throttle.should_emit(home_id + 999, "WARNING", reasons, now=10.0) is True


def test_reset_clears_runtime_state_but_keeps_rows(client):
    register(client, "reset@example.com")
    home_id = client.get("/api/auth/me").get_json()["active_home"]["id"]
    appmod.persist_result(home_id, {"room": "R", "status": "NORMAL", "timestamp": 1.0})

    assert client.get("/api/status").get_json()["room"] == "R"
    response = client.post("/api/reset")
    assert response.status_code == 200
    assert response.get_json()["persistent_data_kept"] is True
    assert client.get("/api/status").get_json()["room"] is None
    assert appmod.db.prediction_history(home_id, 100), "reset must not delete stored predictions"


def test_sensor_endpoint_rejects_non_finite_samples(client):
    register(client, "sensor@example.com")
    response = client.post(
        "/api/sensor",
        json={"device_id": "phone", "acceleration": {"x": float("nan"), "y": 0, "z": 0}},
    )
    assert response.status_code == 400
    status = client.get("/api/sensor/status")
    assert status.status_code == 200
    assert status.get_json() == {"state": "NO_DATA"}
