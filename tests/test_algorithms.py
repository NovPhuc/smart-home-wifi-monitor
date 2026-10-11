from __future__ import annotations

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
import pytest

from smarthome.activity import ActivityMonitor
from smarthome.anomaly import RuleEngine
from smarthome.config import load_config
from smarthome.inference import SmartHomeInferenceEngine
from smarthome.metrics import binary_anomaly_metrics, room_metrics
from smarthome.preprocessing import RSSIPreprocessor
from smarthome.storage import SmartHomeDatabase
from smarthome.topology import TopologyFilter, build_transition_matrix

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Algorithm
# --------------------------------------------------------------------------- #
def test_preprocessor_masks_missing_ap_and_tolerates_nan():
    df = pd.DataFrame([
        {"timestamp": 1, "session_id": "S1", "device_id": "D", "room": "A", "AP1": -50.0, "AP2": np.nan}
    ])
    pp = RSSIPreprocessor.fit(df)

    # NaN in training data must be treated as "not visible", not as a real value.
    train = pp.transform_row(df.iloc[0])
    assert train.shape == (6,)
    np.testing.assert_allclose(train[4:], [1.0, 0.0])
    np.testing.assert_allclose(train[3], -1.0, atol=1e-6)

    # An AP absent from the live scan must be masked the same way as at training.
    live = pp.transform_wifi_dict({"AP1": -50.0})
    np.testing.assert_allclose(live[4:], [1.0, 0.0])
    np.testing.assert_allclose(live[3], -1.0, atol=1e-6)

    # A live scan carrying extra, unknown access points must be ignored.
    extra = pp.transform_wifi_dict({"AP1": -50.0, "AP_UNKNOWN": -70.0})
    assert extra.shape == train.shape


def test_topology_filter_stays_normalised_over_long_run():
    rooms = ["A", "B", "C"]
    topology = {"A": ["A", "B"], "B": ["A", "B", "C"], "C": ["B", "C"]}
    filt = TopologyFilter(rooms, topology)
    for step in range(200):
        posterior = filt.update(np.asarray([0.1, 0.8, 0.1]) if step % 2 else np.asarray([0.8, 0.1, 0.1]))
        assert np.isfinite(posterior).all(), f"non-finite posterior at step {step}"
        np.testing.assert_allclose(posterior.sum(), 1.0, rtol=1e-5)
        assert (posterior >= 0).all()


def test_topology_filter_renormalises_all_zero_emission():
    rooms = ["A", "B"]
    filt = TopologyFilter(rooms, {"A": ["A"], "B": ["B"]})
    posterior = filt.update(np.zeros(2))
    np.testing.assert_allclose(posterior.sum(), 1.0, rtol=1e-5)


def test_transition_matrix_rows_sum_to_one_with_unknown_neighbours():
    rooms = ["A", "B"]
    # Topology pointing at rooms that do not exist must not create dead rows.
    mat = build_transition_matrix(rooms, {"A": ["A", "GHOST"], "B": ["GHOST"]})
    np.testing.assert_allclose(mat.sum(axis=1), 1.0)


def test_activity_monitor_handles_out_of_order_timestamps():
    monitor = ActivityMonitor(inactivity_minutes=1)
    monitor.update({"AP1": -50.0}, "A", 1000.0)
    snapshot = monitor.update({"AP1": -50.0}, "A", 500.0)  # clock jumped backwards
    assert snapshot.inactive_minutes >= 0
    assert snapshot.transitions_last_hour >= 0


def test_activity_monitor_purges_old_transitions():
    monitor = ActivityMonitor(inactivity_minutes=1)
    monitor.update({"AP1": -50.0}, "A", 0.0)
    monitor.update({"AP1": -50.0}, "B", 10.0)   # one transition at t=10
    snapshot = monitor.update({"AP1": -50.0}, "B", 20.0)
    assert snapshot.transitions_last_hour == 1
    snapshot = monitor.update({"AP1": -50.0}, "B", 1000.0)  # still inside the one-hour window
    assert snapshot.transitions_last_hour == 1
    snapshot = monitor.update({"AP1": -50.0}, "B", 4000.0)  # t=10 is now older than an hour
    assert snapshot.transitions_last_hour == 0


def test_rule_engine_night_window_wraps_past_midnight():
    rooms = ["Kitchen"]
    rules = {
        "default_max_dwell_minutes": 45,
        "room_max_dwell_minutes": {"Kitchen": 90},
        "nighttime_start_hour": 22,
        "nighttime_end_hour": 5,
        "nighttime_sensitive_rooms": ["Kitchen"],
        "nighttime_max_dwell_minutes": 20,
        "suspicious_night_transitions": 4,
    }
    engine = RuleEngine(rooms, {"Kitchen": ["Kitchen"]}, rules)
    # 23:00 falls inside a 22 -> 05 window even though start > end.
    reasons = engine.evaluate("Kitchen", None, 30.0, 23.0)
    assert any("nighttime" in reason for reason in reasons)


def test_anomaly_feature_builder_encodes_unknown_room_safely():
    from smarthome.dataset import AnomalyFeatureBuilder

    builder = AnomalyFeatureBuilder(["A", "B", "C"])
    encoded = builder.encode_event("NOT_A_ROOM", 10.0, 12.0, 0.5)
    assert encoded.shape == (7,)
    np.testing.assert_allclose(encoded[:3], [0.0, 0.0, 0.0])
    assert np.isfinite(encoded).all()


def test_room_metrics_confusion_matrix_covers_every_room():
    metrics = room_metrics([0, 0], [0, 0], ["A", "B", "C"])
    # The classification report already accounts for absent rooms; the matrix must too.
    assert len(metrics["confusion_matrix"]) == 3
    assert all(len(row) == 3 for row in metrics["confusion_matrix"])


def test_binary_anomaly_metrics_without_positive_predictions():
    metrics = binary_anomaly_metrics([1, 1, 0], [0, 0, 0])
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0


def test_inference_engine_predicts_normalised_posterior_after_window():
    cfg = load_config(ROOT / "config.yaml")
    engine = SmartHomeInferenceEngine(cfg, ROOT / "models")
    aps = engine.preprocessor.ap_columns
    assert aps, "preprocessor must expose access point columns"
    wifi = {ap: -55.0 for ap in aps[:3]}
    wifi.update({ap: -88.0 for ap in aps[3:]})

    for step in range(int(cfg["data"]["window_size"])):
        result = engine.process_scan(wifi, timestamp=1_700_000_000 + step * 3)

    assert "room" in result, "engine must localise once the window is filled"
    posterior = result["smoothed_probabilities"]
    assert set(posterior) == set(cfg["rooms"])
    np.testing.assert_allclose(sum(posterior.values()), 1.0, rtol=1e-5)
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["status"] in {"NORMAL", "WARNING", "CRITICAL"}


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
def test_db_cascade_delete_removes_dependent_rows(tmp_path):
    db = SmartHomeDatabase(tmp_path / "cascade.db")
    user = db.create_user("cascade@example.com", "hash", "Cascade")
    home = db.create_home(user["id"], "Home")
    db.create_room(home["id"], "Phòng ngủ")
    db.record_wifi_scan(
        home_id=home["id"], room_name="Phòng ngủ", session_code="S01", device_name="Pixel",
        wifi={"AP1": -50.0}, orientation="FLAT_UP", timestamp=1000.0, target_samples=6,
    )
    db.save_prediction(home["id"], {"timestamp": 1000.0, "room": "Phòng ngủ", "status": "NORMAL"})
    db.save_alert(home["id"], {"timestamp": 1000.0, "room": "Phòng ngủ", "status": "WARNING"})

    assert db.delete_home(user["id"], home["id"]) is True

    with db.connect() as connection:
        for table in ("homes", "rooms", "collection_sessions", "wifi_scans", "predictions", "alerts"):
            # `homes` keys on `id`; every dependent table keys on `home_id`.
            key = "id" if table == "homes" else "home_id"
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {key}=?", (home["id"],)
            ).fetchone()[0]
            assert count == 0, f"{table} still holds {count} orphan rows"


def test_db_home_isolation_between_users(tmp_path):
    db = SmartHomeDatabase(tmp_path / "isolated.db")
    alice = db.create_user("alice@example.com", "h", "Alice")
    bob = db.create_user("bob@example.com", "h", "Bob")
    alice_home = db.create_home(alice["id"], "Alice Home")
    bob_home = db.create_home(bob["id"], "Bob Home")
    db.create_room(alice_home["id"], "Alice Room")

    assert db.get_home(bob["id"], alice_home["id"]) is None
    assert db.get_home(alice["id"], alice_home["id"]) is not None
    assert [h["id"] for h in db.list_homes(bob["id"])] == [bob_home["id"]]
    # Bob must not be able to resolve Alice's room by name.
    assert db.find_room_by_name(bob_home["id"], "Alice Room") is None


def test_db_rejects_room_names_that_normalise_identically(tmp_path):
    db = SmartHomeDatabase(tmp_path / "dup.db")
    user = db.create_user("dup@example.com", "h", "Dup")
    home = db.create_home(user["id"], "Home")
    db.create_room(home["id"], "Kitchen")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_room(home["id"], "kitchen")


def test_db_rename_updates_name_key_so_lookups_follow(tmp_path):
    db = SmartHomeDatabase(tmp_path / "rename.db")
    user = db.create_user("rename@example.com", "h", "Rename")
    home = db.create_home(user["id"], "Home")
    room = db.create_room(home["id"], "Phòng khách")

    assert db.update_room(home["id"], room["id"], "Phòng ăn", 30.0) is True
    assert db.find_room_by_name(home["id"], "Phòng ăn")["id"] == room["id"]
    assert db.find_room_by_name(home["id"], "Phòng khách") is None


def test_db_calibration_progress_counts_sessions_samples_and_orientations(tmp_path):
    db = SmartHomeDatabase(tmp_path / "calib.db")
    user = db.create_user("calib@example.com", "h", "Calib")
    home = db.create_home(user["id"], "Home")
    db.create_room(home["id"], "A")
    db.create_room(home["id"], "B")

    for session in ("S01", "S02", "S03"):
        for room in ("A", "B"):
            for index, orientation in enumerate(("PORTRAIT_UP", "LANDSCAPE_LEFT", "FLAT_UP")):
                db.record_wifi_scan(
                    home_id=home["id"], room_name=room, session_code=session,
                    device_name="Pixel", wifi={"AP1": -50.0 - index},
                    orientation=orientation, timestamp=1000.0 + index,
                    target_samples=6,
                )

    progress = db.calibration_progress(home["id"], target_samples=6, required_orientations=3, required_sessions=3)
    assert progress["data_ready"] is True
    by_name = {room["name"]: room for room in progress["rooms"]}
    assert by_name["A"]["samples"] == 9
    assert by_name["A"]["sessions"] == 3
    assert by_name["A"]["orientations"] == 3
    assert len(db.export_scans(home["id"])) == 18


def test_db_prediction_history_returns_most_recent_in_chronological_order(tmp_path):
    db = SmartHomeDatabase(tmp_path / "hist.db")
    user = db.create_user("hist@example.com", "h", "Hist")
    home = db.create_home(user["id"], "Home")
    for index in range(350):
        db.save_prediction(home["id"], {"timestamp": float(index), "room": f"R{index}", "status": "NORMAL"})

    history = db.prediction_history(home["id"], 300)
    assert len(history) == 300
    stamps = [item["timestamp"] for item in history]
    assert stamps == sorted(stamps), "history must be chronological"
    assert stamps[-1] == 349.0, "the newest event must be last"


def test_db_alert_list_returns_most_recent_last(tmp_path):
    db = SmartHomeDatabase(tmp_path / "alerts.db")
    user = db.create_user("alerts@example.com", "h", "Alerts")
    home = db.create_home(user["id"], "Home")
    for index in range(120):
        db.save_alert(home["id"], {"timestamp": float(index), "room": "R", "status": "WARNING"})

    alerts = db.list_alerts(home["id"], 100)
    assert len(alerts) == 100
    stamps = [item["timestamp"] for item in alerts]
    assert stamps == sorted(stamps)
    assert stamps[-1] == 119.0


def test_db_initialize_is_idempotent_and_keeps_schema_version(tmp_path):
    path = tmp_path / "idem.db"
    first = SmartHomeDatabase(path)
    with first.connect() as connection:
        version_before = connection.execute("PRAGMA user_version").fetchone()[0]

    second = SmartHomeDatabase(path)  # re-opens and re-runs initialize
    with second.connect() as connection:
        version_after = connection.execute("PRAGMA user_version").fetchone()[0]
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(rooms)").fetchall()}

    assert version_before == version_after
    assert "_name_key" in columns
