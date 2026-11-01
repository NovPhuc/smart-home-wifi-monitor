from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "server"))

import app as appmod  # server/app.py  (module-level Flask app + engine)
import app_services
from security_middleware import RateLimiter
from smarthome.storage import SmartHomeDatabase


@pytest.fixture()
def client(tmp_path):
    """Fresh database and clean runtime state for every test."""
    appmod.app.config["TESTING"] = True
    # Route đọc trạng thái qua module app_state, nên phải thay db và xoá
    # runtime state tại đó — gán appmod.db (bí danh) sẽ không có tác dụng.
    appmod.app_state.db = SmartHomeDatabase(tmp_path / "api.db")
    appmod.app_state.reset_runtime()
    # Rate limit nằm ở middleware, không thuộc app_state: bộ test gửi hàng
    # trăm request từ cùng IP 127.0.0.1 nên phải xóa bộ đếm mỗi test.
    appmod.reset_rate_limits(appmod.app)
    with appmod.app.test_client() as test_client:
        yield test_client


def register(client, email, home_name="Nhà của tôi"):
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "TEST_PASSWORD_PLACEHOLDER",
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

    good = client.post("/api/auth/login", json={"email": "first@example.com", "password": "TEST_PASSWORD_PLACEHOLDER"})
    assert good.status_code == 200


def test_register_rejects_duplicate_email(client):
    register(client, "dup@example.com")
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/register",
        json={"email": "DUP@example.com", "password": "TEST_PASSWORD_PLACEHOLDER", "display_name": "x", "home_name": "h"},
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


def _read_stream_events(response, expected, max_chunks=10):
    """Đọc các block SSE cho tới khi thấy đủ tên event cần thiết."""
    buffer = ""
    events = {}
    iterator = iter(response.response)
    for _ in range(max_chunks):
        chunk = next(iterator)
        buffer += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            name = None
            data = []
            for line in block.splitlines():
                if line.startswith("event:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data.append(line.split(":", 1)[1].lstrip())
            if name:
                events[name] = "\n".join(data)
        if all(name in events for name in expected):
            break
    return events


def test_stream_requires_login(client):
    response = client.get("/api/stream")
    assert response.status_code == 401
    assert response.get_json()["error"] == "AUTH_REQUIRED"


def test_stream_emits_initial_dashboard_events(client):
    register(client, "stream@example.com")
    home = client.get("/api/auth/me").get_json()["active_home"]
    response = client.get("/api/stream", buffered=False)
    try:
        assert response.status_code == 200
        assert response.mimetype == "text/event-stream"
        assert response.headers["Cache-Control"] == "no-cache, no-store"
        assert response.headers["X-Accel-Buffering"] == "no"
        events = _read_stream_events(response, {"status", "history", "alerts"})
    finally:
        response.close()

    assert set(events) == {"status", "history", "alerts"}
    status = json.loads(events["status"])
    assert status["status"] == "NO_DATA"
    assert status["home"]["id"] == home["id"]
    assert json.loads(events["history"]) == []
    assert json.loads(events["alerts"]) == []


def test_dashboard_stream_pushes_only_changed_status(client, monkeypatch):
    register(client, "stream2@example.com")
    home = client.get("/api/auth/me").get_json()["active_home"]

    import routes.track_views as track_views
    monkeypatch.setattr(track_views, "STREAM_INTERVAL_SECONDS", 0)
    user_id = client.get("/api/auth/me").get_json()["user"]["id"]
    generator = track_views._dashboard_stream(home, user_id)
    try:
        assert "event: status" in next(generator)
        assert "event: history" in next(generator)
        assert "event: alerts" in next(generator)

        appmod.persist_result(home["id"], {"room": "Bedroom", "status": "NORMAL", "timestamp": 10.0})
        changed = next(generator)
    finally:
        generator.close()

    assert "event: status" in changed
    assert '"room":"Bedroom"' in changed


def test_stream_stops_after_member_access_is_revoked(client, monkeypatch):
    register(client, "stream-owner@example.com", "Nhà Chủ")
    home_id = client.get("/api/auth/me").get_json()["active_home"]["id"]
    code = create_share(client, home_id)

    client.post("/api/auth/logout")
    register(client, "stream-member@example.com", "Nhà Thành Viên")
    assert client.post("/api/homes/join", json={"code": code}).status_code == 200
    assert client.post(f"/api/homes/{home_id}/select").status_code == 200
    me = client.get("/api/auth/me").get_json()
    home = me["active_home"]
    user_id = me["user"]["id"]

    import routes.track_views as track_views
    monkeypatch.setattr(track_views, "STREAM_INTERVAL_SECONDS", 0)
    generator = track_views._dashboard_stream(home, user_id)
    try:
        next(generator)
        next(generator)
        next(generator)
        appmod.db.remove_home_member(home_id, user_id)
        revoked = next(generator)
    finally:
        generator.close()

    assert "event: auth" in revoked
    assert "HOME_ACCESS_REVOKED" in revoked


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


def create_share(client, home_id):
    response = client.post(f"/api/homes/{home_id}/share")
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["share"]["code"]


def login_as(client, email, password=None):
    if password is None:
        password = os.environ.get("TEST_PASSWORD", "TEST_PASSWORD_PLACEHOLDER")
    assert client.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200


def test_share_code_lets_member_view_but_not_write(client):
    register(client, "owner@example.com", "Nhà Ông Bà")
    owner_home = client.get("/api/auth/me").get_json()["active_home"]["id"]
    create_rooms(client, ["Phòng ngủ", "Phòng khách"])
    code = create_share(client, owner_home)

    # Mã gồm 6 chữ số và chủ nhà đọc lại được mã đang còn hiệu lực.
    assert code.isdigit() and len(code) == 6
    assert client.get(f"/api/homes/{owner_home}/share").get_json()["share"]["code"] == code

    client.post("/api/auth/logout")
    register(client, "friend@example.com", "Nhà Của Friend")
    joined = client.post("/api/homes/join", json={"code": code})
    assert joined.status_code == 200, joined.get_data(as_text=True)
    joined_home = joined.get_json()["joined_home"]
    assert joined_home["id"] == owner_home
    assert joined_home["role"] == "member"

    me = client.get("/api/auth/me").get_json()
    assert [h["role"] for h in me["homes"] if h["id"] == owner_home] == ["member"]
    client.post(f"/api/homes/{owner_home}/select")

    # Thành viên được xem dữ liệu chung.
    assert client.get("/api/status").status_code == 200
    assert client.get("/api/history").status_code == 200
    assert client.get("/api/alerts").status_code == 200
    assert client.get("/api/rooms").get_json()[0]["name"] == "Phòng ngủ"

    # Thành viên không được ghi: phòng, thu thập, demo, train, xuất CSV.
    assert client.post("/api/rooms", json={"name": "Phòng mới"}).status_code == 403
    assert client.post("/api/collect", json={"wifi": {"AP1": -50}, "room": "Phòng ngủ", "session_id": "S01"}).status_code == 403
    assert client.post("/api/demo/scan", json={}).status_code == 403
    assert client.post("/api/training/start").status_code == 403
    assert client.get("/api/export/scans.csv").status_code == 403

    # Tạo mã chia sẻ chỉ dành cho chủ nhà.
    assert client.post(f"/api/homes/{owner_home}/share").status_code == 403

    client.post("/api/auth/logout")
    login_as(client, "owner@example.com")
    members = client.get(f"/api/homes/{owner_home}/members").get_json()
    assert [m["email"] for m in members] == ["friend@example.com"]


def test_invalid_expired_and_rotated_share_codes(client):
    register(client, "root@example.com", "Nhà Gốc")
    home_id = client.get("/api/auth/me").get_json()["active_home"]["id"]
    first_code = create_share(client, home_id)

    client.post("/api/auth/logout")
    register(client, "guest@example.com", "Nhà Khách")

    assert client.post("/api/homes/join", json={"code": "abc123"}).status_code == 400
    assert client.post("/api/homes/join", json={"code": "000000"}).status_code == 404

    # Chủ nhà tạo mã mới → mã cũ bị vô hiệu.
    client.post("/api/auth/logout")
    login_as(client, "root@example.com")
    create_share(client, home_id)
    client.post("/api/auth/logout")
    login_as(client, "guest@example.com")
    assert client.post("/api/homes/join", json={"code": first_code}).status_code == 404

    # Thu hồi mã → mã mới nhất cũng không dùng được nữa.
    client.post("/api/auth/logout")
    login_as(client, "root@example.com")
    assert client.delete(f"/api/homes/{home_id}/share").get_json()["ok"] is True
    assert client.get(f"/api/homes/{home_id}/share").get_json()["share"] is None
    last_code = create_share(client, home_id)
    assert client.delete(f"/api/homes/{home_id}/share").get_json()["ok"] is True
    client.post("/api/auth/logout"); login_as(client, "guest@example.com")
    assert client.post("/api/homes/join", json={"code": last_code}).status_code == 404


def test_serial_share_code_expiry(client, monkeypatch):
    register(client, "exp@example.com", "Nhá Hạn")
    home_id = client.get("/api/auth/me").get_json()["active_home"]["id"]
    create_share(client, home_id)

    import time as time_module
    real_time = time_module.time
    monkeypatch.setattr(appmod.time, "time", lambda: real_time() + 25 * 3600)

    client.post("/api/auth/logout")
    register(client, "late@example.com", "Nhà Muộn")
    assert client.post("/api/homes/join", json={"code": "111111"}).status_code == 404

    # Mã hết hạn 24 giờ khiến share hiển thị là trống.
    client.post("/api/auth/logout"); login_as(client, "exp@example.com")
    assert client.get(f"/api/homes/{home_id}/share").get_json()["share"] is None


def test_owner_can_remove_member(client):
    register(client, "keeper@example.com", "Nhà Gỡ")
    home_id = client.get("/api/auth/me").get_json()["active_home"]["id"]
    code = create_share(client, home_id)

    client.post("/api/auth/logout")
    register(client, "gone@example.com", "Nhà Biến Mất")
    client.post("/api/homes/join", json={"code": code})
    assert client.post(f"/api/homes/{home_id}/select").status_code == 200
    assert client.get("/api/status").status_code == 200

    client.post("/api/auth/logout")
    login_as(client, "keeper@example.com")
    victim_id = client.get(f"/api/homes/{home_id}/members").get_json()[0]["user_id"]
    assert client.delete(f"/api/homes/{home_id}/members/{victim_id}").get_json()["ok"] is True

    client.post("/api/auth/logout")
    login_as(client, "gone@example.com")
    assert client.post(f"/api/homes/{home_id}/select").status_code == 404
    assert all(h["id"] != home_id for h in client.get("/api/auth/me").get_json()["homes"])


def test_password_rejected_over_max_length(client):
    too_long = client.post("/api/auth/register", json={
        "email": "long@example.com", "password": "x" * 129,
        "display_name": "Long", "home_name": "Nhà",
    })
    assert too_long.status_code == 400
    assert too_long.get_json()["fields"]["password"]
    assert client.post("/api/auth/register", json={
        "email": "long@example.com", "password": "x" * 128,
        "display_name": "Long", "home_name": "Nhà",
    }).status_code == 201


def test_login_brute_force_lockout(client):
    register(client, "victim@example.com")
    for _ in range(5):
        bad = client.post("/api/auth/login", json={"email": "victim@example.com", "password": "wrong-pass"})
        assert bad.status_code == 401
    blocked = client.post("/api/auth/login", json={"email": "victim@example.com", "password": "TEST_PASSWORD_PLACEHOLDER"})
    assert blocked.status_code == 429
    assert blocked.get_json()["error"] == "TOO_MANY_ATTEMPTS"
    # Tài khoản khác không bị ảnh hưởng bởi khóa theo email.
    register(client, "other@example.com")
    assert client.post("/api/auth/login", json={"email": "other@example.com", "password": "TEST_PASSWORD_PLACEHOLDER"}).status_code == 200


def test_share_code_join_brute_force_lockout(client):
    register(client, "owner@example.com", "Nhá Chia Sẻ")
    client.post("/api/auth/logout")
    register(client, "joiner@example.com", "Nhà Dò Mã")
    for _ in range(5):
        assert client.post("/api/homes/join", json={"code": "000000"}).status_code == 404
    blocked = client.post("/api/homes/join", json={"code": "123456"})
    assert blocked.status_code == 429
    assert blocked.get_json()["error"] == "TOO_MANY_ATTEMPTS"


def test_register_rate_limited_per_ip(client):
    """Giới hạn dò mã chia sẻ tính theo user_id, nên nếu đăng ký không giới hạn
    thì chỉ cần tạo tài khoản mới là lại có 5 lượt thử — mã 6 số sẽ bị dò hết.
    Cửa đăng ký phải chặn theo IP."""
    for index in range(10):
        register(client, f"mass{index}@example.com")
    blocked = client.post("/api/auth/register", json={
        "email": "mass-final@example.com", "password": "TEST_PASSWORD_PLACEHOLDER",
        "display_name": "Mass", "home_name": "Nhà",
    })
    assert blocked.status_code == 429
    assert blocked.get_json()["error"] == "TOO_MANY_ATTEMPTS"


def test_health_endpoint_is_public_and_json(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["database"] == "ok"


def test_unknown_api_route_returns_json_not_html(client):
    response = client.get("/api/khong-ton-tai")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "NOT_FOUND"


def test_write_endpoint_rejects_non_json_body(client):
    # HTML form chỉ gửi được text/plain hoặc urlencoded, không gửi được JSON.
    response = client.post(
        "/api/auth/logout", data="email=a@b.c", content_type="text/plain"
    )
    assert response.status_code == 415
    assert response.get_json()["error"] == "UNSUPPORTED_MEDIA_TYPE"


def test_security_headers_allow_motion_sensors(client):
    response = client.get("/")
    policy = response.headers["Permissions-Policy"]
    assert "accelerometer=(self)" in policy
    assert "gyroscope=(self)" in policy
    # Dashboard chạy HTTP trong LAN: không được gửi HSTS cho kết nối chưa TLS.
    assert "Strict-Transport-Security" not in response.headers

    secure = client.get("/api/health", base_url="https://localhost")
    assert secure.headers["Strict-Transport-Security"].startswith("max-age=")


def test_room_rejects_non_finite_dwell_minutes(client):
    register(client, "dwell@example.com")
    for index, value in enumerate((float("nan"), float("inf"), -5, 5000)):
        response = client.post(
            "/api/rooms",
            json={"name": f"Phòng {index}", "max_dwell_minutes": value},
        )
        assert response.status_code == 400, response.get_data(as_text=True)


def test_collect_rejects_non_finite_rssi(client):
    register(client, "rssi@example.com")
    create_rooms(client, ["Phòng ngủ"])
    for value in (float("nan"), float("inf")):
        response = client.post("/api/collect", json={
            "wifi": {"AP1": value}, "room": "Phòng ngủ", "session_id": "S01",
        })
        assert response.status_code == 400, response.get_data(as_text=True)


def test_device_platform_is_capped(client):
    register(client, "platform@example.com")
    response = client.post(
        "/api/devices", json={"name": "Phone", "platform": "x" * 500}
    )
    assert response.status_code == 201
    assert len(response.get_json()["device"]["platform"]) == 40


def test_rate_limiter_ignores_forwarded_for_unless_proxy_trusted(client, monkeypatch):
    monkeypatch.setenv("SMART_HOME_TRUST_PROXY", "0")
    with appmod.app.test_request_context(
        headers={"X-Forwarded-For": "203.0.113.9"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        assert RateLimiter._client_id() == "127.0.0.1"

    monkeypatch.setenv("SMART_HOME_TRUST_PROXY", "1")
    with appmod.app.test_request_context(
        headers={"X-Forwarded-For": "203.0.113.9"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        assert RateLimiter._client_id() == "203.0.113.9"


def test_rate_limiter_blocks_then_resets(client):
    limiter = RateLimiter()
    with appmod.app.test_request_context():
        assert limiter.check("test", 2, 60)[0] is True
        assert limiter.check("test", 2, 60)[0] is True
        allowed, info = limiter.check("test", 2, 60)
        assert allowed is False
        assert info["retry_after"] == 60
        limiter.reset()
        assert limiter.check("test", 2, 60)[0] is True


def test_critical_alert_webhook_payload(client, monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))

    monkeypatch.setattr(app_services.requests, "post", fake_post)
    monkeypatch.setitem(appmod.cfg["alerts"], "webhook_url", "https://example.test/hook")

    app_services._post_webhook(
        7, "Nhà Ông Bà",
        {"status": "CRITICAL", "room": "Bedroom", "reasons": ["x"], "timestamp": 1.0},
    )
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://example.test/hook"
    assert kwargs["json"]["home"] == "Nhà Ông Bà"
    assert kwargs["json"]["home_id"] == 7
    assert kwargs["allow_redirects"] is False


def test_notify_alert_only_for_critical_and_configured(monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, **kwargs):
            started.append(kwargs)

        def start(self):
            pass

    monkeypatch.setattr(app_services.threading, "Thread", FakeThread)
    monkeypatch.setitem(appmod.cfg["alerts"], "webhook_url", "")
    app_services.notify_alert(1, "Nhà", {"status": "CRITICAL"})
    assert not started

    monkeypatch.setitem(appmod.cfg["alerts"], "webhook_url", "https://example.test/hook")
    app_services.notify_alert(1, "Nhà", {"status": "WARNING"})
    assert not started

    app_services.notify_alert(1, "Nhà", {"status": "CRITICAL"})
    assert len(started) == 1
    assert started[0]["args"][1] == "Nhà"


def test_health_reports_degraded_when_database_is_unavailable(client):
    class BrokenDatabase:
        def connect(self):
            raise RuntimeError("database is gone")

    original = appmod.app_state.db
    appmod.app_state.db = BrokenDatabase()
    try:
        response = client.get("/api/health")
    finally:
        appmod.app_state.db = original
    assert response.status_code == 503
    assert response.get_json()["database"] == "error"


def test_expired_session_is_rejected(client):
    """Cookie chỉ được ký chứ không có hạn server-side: nếu không kiểm tra
    tuổi phiên, cookie bị chụp lại dùng được mãi. Quá hạn phải bị xoá."""
    register(client, "expire@example.com")
    assert client.get("/api/auth/me").status_code == 200

    # Giả lập cookie được cấp phát 8 ngày trước — quá hạn 7 ngày mặc định.
    with client.session_transaction() as session:
        session["_iat"] = time.time() - 8 * 24 * 3600
    assert client.get("/api/auth/me").status_code == 401

    # Phiên thiếu dấu _iat (cookie cũ trước khi có cơ chế này) cũng bị từ chối.
    with client.session_transaction() as session:
        session.clear()
        session["user_id"] = 999
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.get_json()["error"] == "AUTH_REQUIRED"

    # Đăng nhập lại cấp phiên mới, dùng được ngay.
    login_as(client, "expire@example.com")
    assert client.get("/api/auth/me").status_code == 200


def test_csv_export_header_neutralizes_formula_in_ap_name(client):
    """Tên AP do client tự gửi lọt qua /api/collect (chỉ cắt 64 ký tự); nếu
    dòng header không vệ sinh như giá trị ô thì '=HYPERLINK(...)' sẽ chạy
    công thức khi chủ nhà mở file export bằng Excel."""
    register(client, "csvhead@example.com")
    create_rooms(client, ["Phòng ngủ", "Phòng khách"])
    device = client.post("/api/devices", json={"name": "Pixel", "platform": "android"})
    token = device.get_json()["token"]
    assert client.post(
        "/api/collect",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "wifi": {'=HYPERLINK("http://evil","x")': -50.0},
            "room": "Phòng ngủ",
            "session_id": "S01",
            "orientation": "FLAT_UP",
            "timestamp": 1000.0,
        },
    ).status_code == 200

    exported = client.get("/api/export/scans.csv")
    assert exported.status_code == 200
    header = exported.get_data(as_text=True).splitlines()[0]
    assert "'=HYPERLINK" in header, "header phải được vệ sinh như giá trị ô"
    # Giá trị dòng dữ liệu vẫn map đúng vào cột đã đổi tên.
    rows = list(csv.DictReader(io.StringIO(exported.get_data(as_text=True))))
    assert len(rows) == 1
    assert rows[0]["'=HYPERLINK(\"http://evil\",\"x\")"] == "-50.0"
