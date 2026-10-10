from __future__ import annotations
import numpy as np
import pandas as pd
import torch

from smarthome.preprocessing import RSSIPreprocessor
from smarthome.models import RoomNetLite, GRUAutoencoder
from smarthome.topology import build_transition_matrix, TopologyFilter
from smarthome.dataset import AnomalyFeatureBuilder
from smarthome.activity import ActivityMonitor
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
