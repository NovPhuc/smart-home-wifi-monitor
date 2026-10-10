from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from datetime import datetime
import numpy as np
import torch
from .dataset import AnomalyFeatureBuilder
from .models.gru_autoencoder import per_sequence_reconstruction_score


@dataclass
class AlertResult:
    status: str
    anomaly_score: float | None
    reasons: list[str]


class RuleEngine:
    def __init__(self, rooms: list[str], topology: dict[str, list[str]], config: dict):
        self.rooms = rooms
        self.topology = topology
        self.config = config
        self.recent_rooms = deque(maxlen=20)

    def evaluate(self, room: str, previous_room: str | None, dwell_minutes: float, hour: float) -> list[str]:
        reasons: list[str] = []
        limits = self.config.get("room_max_dwell_minutes", {})
        max_dwell = float(limits.get(room, self.config.get("default_max_dwell_minutes", 45)))
        if dwell_minutes > max_dwell:
            reasons.append(f"Long dwell in {room}: {dwell_minutes:.1f} min > {max_dwell:.1f} min")

        if previous_room and previous_room != room:
            allowed = self.topology.get(previous_room, [])
            if room not in allowed:
                reasons.append(f"Impossible/unlikely transition: {previous_room} -> {room}")

        self.recent_rooms.append(room)
        start = float(self.config.get("nighttime_start_hour", 0))
        end = float(self.config.get("nighttime_end_hour", 5))
        is_night = start <= hour < end if start <= end else (hour >= start or hour < end)
        if is_night:
            sensitive = set(self.config.get("nighttime_sensitive_rooms", []))
            night_limit = float(self.config.get("nighttime_max_dwell_minutes", 20))
            if room in sensitive and dwell_minutes > night_limit:
                reasons.append(f"Unusual nighttime dwell in {room}: {dwell_minutes:.1f} min")
            if len(self.recent_rooms) >= 6:
                transitions = sum(a != b for a, b in zip(self.recent_rooms, list(self.recent_rooms)[1:]))
                if transitions >= int(self.config.get("suspicious_night_transitions", 4)):
                    reasons.append(f"Unusual nighttime movement: {transitions} recent transitions")
        return reasons


class OnlineAnomalyDetector:
    def __init__(
        self,
        model,
        feature_builder: AnomalyFeatureBuilder,
        sequence_length: int,
        threshold: float,
        room_loss_weight: float = 1.0,
        continuous_loss_weight: float = 0.7,
        device: str = "cpu",
    ):
        self.model = model.to(device).eval()
        self.feature_builder = feature_builder
        self.sequence_length = sequence_length
        self.threshold = float(threshold)
        self.room_loss_weight = room_loss_weight
        self.continuous_loss_weight = continuous_loss_weight
        self.device = device
        self.buffer = deque(maxlen=sequence_length)
        self.last_score: float | None = None

    def reset(self):
        self.buffer.clear()
        self.last_score = None

    @torch.no_grad()
    def update(self, room: str, dwell_minutes: float, hour: float, confidence: float) -> float | None:
        feat = self.feature_builder.encode_event(room, dwell_minutes, hour, confidence)
        self.buffer.append(feat)
        if len(self.buffer) < self.sequence_length:
            return None
        x = torch.tensor(np.stack(self.buffer), dtype=torch.float32, device=self.device).unsqueeze(0)
        recon = self.model(x)
        score = per_sequence_reconstruction_score(
            recon,
            x,
            room_dim=self.feature_builder.room_dim,
            room_weight=self.room_loss_weight,
            continuous_weight=self.continuous_loss_weight,
        )
        self.last_score = float(score.item())
        return self.last_score


def fuse_alert(anomaly_score: float | None, threshold: float | None, rule_reasons: list[str]) -> AlertResult:
    deep_anomaly = anomaly_score is not None and threshold is not None and anomaly_score > threshold
    if deep_anomaly and rule_reasons:
        return AlertResult("CRITICAL", anomaly_score, ["High trajectory reconstruction error", *rule_reasons])
    if deep_anomaly:
        return AlertResult("WARNING", anomaly_score, ["High trajectory reconstruction error"])
    if rule_reasons:
        severity = "CRITICAL" if len(rule_reasons) >= 2 else "WARNING"
        return AlertResult(severity, anomaly_score, rule_reasons)
    return AlertResult("NORMAL", anomaly_score, [])
