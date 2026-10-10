from __future__ import annotations
import json
import sqlite3
import numpy as np
import pandas as pd
import torch

from smarthome.preprocessing import RSSIPreprocessor
from smarthome.models import RoomNetLite, GRUAutoencoder
from smarthome.topology import build_transition_matrix, TopologyFilter
from smarthome.dataset import AnomalyFeatureBuilder
from smarthome.activity import ActivityMonitor
from smarthome.alerts import AlertThrottle
from smarthome.metrics import collect_model_metrics
from smarthome.mobile_sensor import MobileSensorMonitor
from smarthome.storage import SmartHomeDatabase


def test_preprocessor_dimensions():
    df = pd.DataFrame([{ "timestamp": 1, "session_id": "S1", "device_id": "P1", "room": "A", "AP1": -45, "AP2": -100 }])
    pp = RSSIPreprocessor.fit(df)
    feat = pp.transform_row(df.iloc[0])
    assert feat.shape == (6,)
    assert pp.feature_dim == 6


def test_roomnet_shapes():
    model = RoomNetLite(in_channels=12, num_rooms=5)
    logits, emb = model(torch.randn(4, 12, 5))
    assert logits.shape == (4, 5)
    assert emb.shape[0] == 4


def test_gru_ae_shapes():
    model = GRUAutoencoder(feature_dim=9)
    x = torch.randn(3, 20, 9)
    y = model(x)
    assert y.shape == x.shape


def test_topology_rows_sum_to_one():
    rooms = ["A", "B", "C"]
    topology = {"A": ["A", "B"], "B": ["A", "B", "C"], "C": ["B", "C"]}
    mat = build_transition_matrix(rooms, topology)
    np.testing.assert_allclose(mat.sum(axis=1), 1.0)
    f = TopologyFilter(rooms, topology)
    out = f.update(np.asarray([0.8, 0.1, 0.1]))
    np.testing.assert_allclose(out.sum(), 1.0)


def test_anomaly_feature_builder():
    b = AnomalyFeatureBuilder(["A", "B", "C"])
    x = b.encode_event("B", 10, 12, .9)
    assert x.shape == (7,)
    assert x[1] == 1


def test_activity_monitor_detects_room_change_and_inactivity():
    monitor = ActivityMonitor(inactivity_minutes=1)
    first = monitor.update({"AP1": -50, "AP2": -70}, "A", 1000)
    assert first.state == "CALIBRATING"
    still = monitor.update({"AP1": -50.5, "AP2": -69.5}, "A", 1030)
    assert still.state == "STILL"
    moved = monitor.update({"AP1": -70, "AP2": -45}, "B", 1060)
    assert moved.state == "ROOM_CHANGE"
    assert moved.transitions_last_hour == 1
    inactive = monitor.update({"AP1": -70, "AP2": -45}, "B", 1130)
    assert inactive.inactive_minutes > 1


def test_activity_monitor_signal_quality():
    monitor = ActivityMonitor()
    good = monitor.update({"A": -42, "B": -55, "C": -67}, "A", 1)
    assert good.signal_quality == "GOOD"
    monitor.reset()
    weak = monitor.update({"A": -90}, "A", 2)
    assert weak.signal_quality == "WEAK"


def test_mobile_sensor_tracks_motion_and_impact_followup():
    monitor = MobileSensorMonitor(
        impact_threshold=10,
        still_after_impact_seconds=3,
        impact_followup_seconds=10,
    )
    moving = monitor.update("iphone", {"x": 1, "y": 1, "z": 0}, 100)
    assert moving["state"] == "MOVING"
    impact = monitor.update("iphone", {"x": 12, "y": 0, "z": 0}, 101)
    assert impact["possible_impact"] is True
    still = monitor.update("iphone", {"x": 0.05, "y": 0, "z": 0}, 105)
    assert still["state"] == "STILL"
    assert still["possible_impact"] is True
    assert len(monitor.alerts) == 1


def test_mobile_sensor_rejects_non_finite_values():
    monitor = MobileSensorMonitor()
    try:
        monitor.update("iphone", {"x": float("nan"), "y": 0, "z": 0}, 100)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_sqlite_multi_home_calibration_and_device_token(tmp_path):
    database = SmartHomeDatabase(tmp_path / "test.db")
    user = database.create_user("family@example.com", "hash", "Gia đình")
    home = database.create_home(user["id"], "Nhà Ba Mẹ")
    database.create_room(home["id"], "Phòng ngủ")
    database.create_room(home["id"], "Phòng khách")
    device, token = database.create_device(home["id"], "Pixel 8")
    assert database.authenticate_device(token)["id"] == device["id"]

    for session_code in ("S01", "S02", "S03"):
        for room in ("Phòng ngủ", "Phòng khách"):
            for index, orientation in enumerate(("PORTRAIT_UP", "LANDSCAPE_LEFT", "FLAT_UP")):
                result = database.record_wifi_scan(
                    home_id=home["id"], room_name=room, session_code=session_code,
                    device_name="Pixel 8", wifi={"AP1": -50 - index},
                    orientation=orientation, timestamp=1000 + index,
                    collector_device_id=device["id"], target_samples=6,
                )
                assert result["aps"] == 1

    progress = database.calibration_progress(
        home["id"], target_samples=6, required_orientations=3, required_sessions=3
    )
    assert progress["data_ready"] is True
    assert progress["localization_ready"] is False
    assert len(database.export_scans(home["id"])) == 18


def test_room_key_migration_backfills_vietnamese_names(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            max_dwell_minutes REAL NOT NULL DEFAULT 60,
            created_at REAL NOT NULL
        );
        INSERT INTO rooms(home_id, name, max_dwell_minutes, created_at) VALUES
            (1, 'NHÀ VỆ SINH', 30, 1),
            (1, 'Phòng Ngủ', 720, 1),
            (2, 'Kitchen', 45, 1),
            (2, 'kitchen', 45, 1);
        """
    )
    connection.commit()
    connection.close()

    # Constructing the database runs the migration on the legacy rooms table.
    database = SmartHomeDatabase(path)

    # Runtime lookups use NFC+lowercase; SQL LOWER() would leave 'À'/'Ệ' uppercase
    # and make these migrated rooms unreachable.
    found = database.find_room_by_name(1, "nhà vệ sinh")
    assert found is not None and found["name"] == "NHÀ VỆ SINH"
    assert database.find_room_by_name(1, "PHÒNG NGỦ")["name"] == "Phòng Ngủ"

    # Duplicate normalised names must still allow the unique index to build.
    with database.connect() as connection:
        keys = [row["_name_key"] for row in connection.execute(
            "SELECT _name_key FROM rooms WHERE home_id=2 ORDER BY id"
        ).fetchall()]
    assert len(keys) == len(set(keys)) == 2
    assert database.find_room_by_name(2, "kitchen")["name"] == "Kitchen"


def test_alert_throttle_suppresses_repeats_and_escalates():
    throttle = AlertThrottle(cooldown_seconds=600)
    reasons = ["Long dwell in Bedroom: 45.3 min"]
    assert throttle.should_emit(1, "WARNING", reasons, now=1000) is True
    # Same condition, only the embedded measurement changed -> suppressed.
    assert throttle.should_emit(1, "WARNING", ["Long dwell in Bedroom: 46.1 min"], now=1010) is False
    # Escalation is surfaced immediately.
    assert throttle.should_emit(1, "CRITICAL", ["Long dwell in Bedroom: 47.0 min"], now=1020) is True
    # A genuinely new reason is surfaced even without escalation.
    assert throttle.should_emit(1, "CRITICAL", ["Unusual nighttime movement"], now=1030) is True
    assert throttle.should_emit(1, "CRITICAL", ["Unusual nighttime movement"], now=1040) is False
    # After the cooldown the still-active condition resurfaces.
    assert throttle.should_emit(1, "CRITICAL", ["Unusual nighttime movement"], now=1631) is True
    # Different homes are tracked independently.
    assert throttle.should_emit(2, "WARNING", reasons, now=1110) is True


def test_collect_model_metrics_reads_home_and_shared_artifacts(tmp_path):
    home = tmp_path / "home"
    shared = tmp_path / "shared"
    home.mkdir()
    shared.mkdir()
    (home / "room_test_metrics.json").write_text(
        json.dumps({"accuracy": 0.9, "macro_f1": 0.88, "mean_inference_ms_per_sample": 0.5}),
        encoding="utf-8",
    )
    (shared / "anomaly_test_metrics.json").write_text(
        json.dumps({"hybrid_ae_plus_rules": {"precision": 0.7, "recall": 0.96, "f1": 0.8}, "threshold": 1.5}),
        encoding="utf-8",
    )
    (shared / "baseline_metrics.json").write_text(
        json.dumps({"kNN": {"accuracy": 0.98, "macro_f1": 0.97}}),
        encoding="utf-8",
    )
    metrics = collect_model_metrics(home, shared)
    assert metrics["room_model"] == {"accuracy": 0.9, "macro_f1": 0.88, "mean_inference_ms": 0.5}
    assert metrics["anomaly_model"]["recall"] == 0.96
    assert metrics["anomaly_model"]["threshold"] == 1.5
    assert metrics["baselines"]["kNN"]["accuracy"] == 0.98
