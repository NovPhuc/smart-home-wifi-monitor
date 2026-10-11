from __future__ import annotations
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import time
import numpy as np
import torch
import torch.nn.functional as F

from .preprocessing import RSSIPreprocessor
from .models import RoomNetLite, GRUAutoencoder
from .topology import TopologyFilter
from .dataset import AnomalyFeatureBuilder
from .anomaly import RuleEngine, OnlineAnomalyDetector, fuse_alert, MobileSensorFusion, MobileSensorEvent
from .activity import ActivityMonitor


class SmartHomeInferenceEngine:
    def __init__(self, config: dict, artifact_dir: str | Path = "models", device: str | None = None):
        self.config = config
        self.rooms = config["rooms"]
        self.artifact_dir = Path(artifact_dir)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.preprocessor = RSSIPreprocessor.load(self.artifact_dir / "preprocessor.json")
        room_cfg = config["room_model"]
        self.room_model = RoomNetLite(
            in_channels=self.preprocessor.feature_dim,
            num_rooms=len(self.rooms),
            hidden_channels=int(room_cfg["hidden_channels"]),
            embedding_dim=int(room_cfg["embedding_dim"]),
            dropout=float(room_cfg["dropout"]),
        ).to(self.device)
        self.room_model.load_state_dict(torch.load(self.artifact_dir / "roomnet_lite.pt", map_location=self.device))
        self.room_model.eval()

        self.window_size = int(config["data"]["window_size"])
        self.rssi_buffer = deque(maxlen=self.window_size)
        topology_self_weight = float(config.get("topology", {}).get("self_weight", 0.75))
        self.topology_filter = TopologyFilter(self.rooms, config["room_topology"], topology_self_weight)

        self.anomaly_detector = None
        threshold_path = self.artifact_dir / "anomaly_threshold.json"
        anomaly_path = self.artifact_dir / "gru_autoencoder.pt"
        if threshold_path.exists() and anomaly_path.exists():
            with threshold_path.open("r", encoding="utf-8") as f:
                threshold = float(json.load(f)["threshold"])
            builder = AnomalyFeatureBuilder(self.rooms, float(config["data"].get("anomaly_feature_max_dwell_minutes", 180)))
            anomaly_cfg = config["anomaly_model"]
            model = GRUAutoencoder(
                feature_dim=builder.feature_dim,
                hidden_size=int(anomaly_cfg["hidden_size"]),
                latent_size=int(anomaly_cfg["latent_size"]),
                num_layers=int(anomaly_cfg["num_layers"]),
            )
            model.load_state_dict(torch.load(anomaly_path, map_location=self.device))
            self.anomaly_detector = OnlineAnomalyDetector(
                model=model,
                feature_builder=builder,
                sequence_length=int(config["data"]["anomaly_sequence_length"]),
                threshold=threshold,
                room_loss_weight=float(anomaly_cfg["room_loss_weight"]),
                continuous_loss_weight=float(anomaly_cfg["continuous_loss_weight"]),
                device=self.device,
            )

        # Mobile sensor fusion for fall detection
        mobile_cfg = config.get("mobile_sensor", {})
        self.mobile_fusion = MobileSensorFusion(
            impact_followup_seconds=mobile_cfg.get("impact_followup_seconds", 20.0),
            still_threshold=mobile_cfg.get("still_threshold", 0.25),
        )

        self.rule_engine = RuleEngine(self.rooms, config["room_topology"], config["rules"])
        activity_cfg = config.get("activity", {})
        self.activity_monitor = ActivityMonitor(
            movement_rssi_delta=activity_cfg.get("movement_rssi_delta", 4.0),
            still_rssi_delta=activity_cfg.get("still_rssi_delta", 1.5),
            inactivity_minutes=activity_cfg.get("inactivity_warning_minutes", 45.0),
            ema_alpha=activity_cfg.get("ema_alpha", 0.45),
        )
        self.current_room: str | None = None
        self.room_since: float | None = None
        self.history = deque(maxlen=300)
        self.alerts = deque(maxlen=100)
        self.last_anomaly_score: float | None = None
        self.last_room_confidence: float = 1.0
        self.started_at: float | None = None

    def reset(self):
        self.rssi_buffer.clear()
        self.topology_filter.reset()
        if self.anomaly_detector:
            self.anomaly_detector.reset()
        self.mobile_fusion = MobileSensorFusion(
            impact_followup_seconds=self.config.get("mobile_sensor", {}).get("impact_followup_seconds", 20.0),
            still_threshold=self.config.get("mobile_sensor", {}).get("still_threshold", 0.25),
        )
        self.rule_engine = RuleEngine(self.rooms, self.config["room_topology"], self.config["rules"])
        self.activity_monitor.reset()
        self.current_room = None
        self.room_since = None
        self.history.clear()
        self.alerts.clear()
        self.last_anomaly_score = None
        self.last_room_confidence = 1.0
        self.started_at = None

    def process_mobile_sensor(self, acceleration: dict[str, float], device_id: str = "phone", timestamp: float | None = None) -> list[str]:
        """Process mobile sensor (accelerometer) data for fall detection."""
        timestamp = float(timestamp if timestamp is not None else time.time())
        # Simple magnitude calculation
        mag = float(np.sqrt(sum(float(acceleration.get(k, 0.0))**2 for k in ("x", "y", "z"))))
        
        # Determine state based on magnitude (simplified version of MobileSensorMonitor)
        mobile_cfg = self.config.get("mobile_sensor", {})
        impact_threshold = mobile_cfg.get("impact_threshold", 18.0)
        movement_threshold = mobile_cfg.get("movement_threshold", 0.8)
        still_threshold = mobile_cfg.get("still_threshold", 0.25)

        if mag >= impact_threshold:
            state = "IMPACT_RECORDED"
        elif mag >= movement_threshold:
            state = "MOVING"
        else:
            state = "STILL"

        event = MobileSensorEvent(
            device_id=device_id,
            timestamp=timestamp,
            state=state,
            motion_magnitude=mag,
            possible_impact=(state == "IMPACT_RECORDED"),
        )
        return self.mobile_fusion.update(event)

    @torch.no_grad()
    def process_scan(self, wifi: dict[str, float], timestamp: float | None = None, mobile_acceleration: dict[str, float] | None = None, mobile_device_id: str = "phone") -> dict:
        timestamp = float(timestamp if timestamp is not None else time.time())
        if self.started_at is None:
            self.started_at = timestamp
        feat = self.preprocessor.transform_wifi_dict(wifi)
        self.rssi_buffer.append(feat)

        if len(self.rssi_buffer) < self.window_size:
            return {
                "status": "COLLECTING",
                "samples_collected": len(self.rssi_buffer),
                "samples_required": self.window_size,
                "timestamp": timestamp,
            }

        x = np.stack(self.rssi_buffer).T
        xt = torch.tensor(x, dtype=torch.float32, device=self.device).unsqueeze(0)
        logits, _ = self.room_model(xt)
        raw_probs = F.softmax(logits, dim=-1).squeeze(0).cpu().numpy()
        smooth_probs = self.topology_filter.update(raw_probs)
        room_idx = int(np.argmax(smooth_probs))
        room = self.rooms[room_idx]
        confidence = float(smooth_probs[room_idx])

        previous_room = self.current_room
        previous_since = self.room_since
        transitioned = previous_room is not None and room != previous_room
        tz = timezone(timedelta(hours=float(self.config.get("time", {}).get("timezone_offset_hours", 7))))
        local_dt = datetime.fromtimestamp(timestamp, tz=tz)
        hour = local_dt.hour + local_dt.minute / 60.0

        # The GRU-AE consumes completed room visits. Long ongoing dwell is handled by rules.
        decision_anomaly_score = None
        threshold = self.anomaly_detector.threshold if self.anomaly_detector is not None else None
        if transitioned and self.anomaly_detector is not None and previous_since is not None:
            completed_dwell = max(0.0, (timestamp - previous_since) / 60.0)
            decision_anomaly_score = self.anomaly_detector.update(
                previous_room, completed_dwell, hour, self.last_room_confidence
            )
            if decision_anomaly_score is not None:
                self.last_anomaly_score = decision_anomaly_score

        if room != self.current_room:
            self.current_room = room
            self.room_since = timestamp
        if self.room_since is None:
            self.room_since = timestamp
        self.last_room_confidence = confidence
        dwell_minutes = max(0.0, (timestamp - self.room_since) / 60.0)

        reasons = self.rule_engine.evaluate(room, previous_room, dwell_minutes, hour)
        activity = self.activity_monitor.update(wifi, room, timestamp)
        if activity.inactive_minutes > self.activity_monitor.inactivity_minutes:
            reasons.append(f"No detected movement for {activity.inactive_minutes:.1f} min")

        # Process mobile sensor if provided
        mobile_reasons = []
        if mobile_acceleration is not None:
            mobile_reasons = self.process_mobile_sensor(mobile_acceleration, mobile_device_id, timestamp)

        alert = fuse_alert(decision_anomaly_score, threshold, reasons, mobile_reasons)
        anomaly_score = self.last_anomaly_score

        event = {
            "timestamp": timestamp,
            "room": room,
            "confidence": confidence,
            "raw_probabilities": {r: float(p) for r, p in zip(self.rooms, raw_probs)},
            "smoothed_probabilities": {r: float(p) for r, p in zip(self.rooms, smooth_probs)},
            "dwell_minutes": dwell_minutes,
            "anomaly_score": anomaly_score,
            "anomaly_threshold": threshold,
            "status": alert.status,
            "reasons": alert.reasons,
            "activity": {
                "state": activity.state,
                "movement_score": activity.movement_score,
                "is_moving": activity.is_moving,
                "last_movement_at": activity.last_movement_at,
                "inactive_minutes": activity.inactive_minutes,
                "transitions_last_hour": activity.transitions_last_hour,
            },
            "signal": {
                "quality": activity.signal_quality,
                "visible_access_points": activity.visible_access_points,
            },
            "monitoring_minutes": max(0.0, (timestamp - (self.started_at or timestamp)) / 60.0),
        }
        self.history.append(event)
        if alert.status in {"WARNING", "CRITICAL"}:
            self.alerts.append(event)
        return event

    def status(self) -> dict:
        if not self.history:
            return {"status": "NO_DATA", "room": self.current_room}
        return dict(self.history[-1])
