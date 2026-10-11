from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import math
import time


@dataclass
class MobileSensorSnapshot:
    device_id: str
    state: str
    motion_magnitude: float
    last_seen_at: float
    last_motion_at: float
    possible_impact: bool
    samples_received: int


class MobileSensorMonitor:
    """Track opt-in phone motion data without claiming medical fall detection."""

    def __init__(
        self,
        movement_threshold: float = 0.8,
        still_threshold: float = 0.25,
        impact_threshold: float = 18.0,
        impact_followup_seconds: float = 20.0,
        still_after_impact_seconds: float = 5.0,
    ):
        self.movement_threshold = float(movement_threshold)
        self.still_threshold = float(still_threshold)
        self.impact_threshold = float(impact_threshold)
        self.impact_followup_seconds = float(impact_followup_seconds)
        self.still_after_impact_seconds = float(still_after_impact_seconds)
        self.devices: dict[str, MobileSensorSnapshot] = {}
        self.pending_impacts: dict[str, float] = {}
        self.alerts: deque[dict] = deque(maxlen=100)

    def reset(self) -> None:
        self.devices.clear()
        self.pending_impacts.clear()
        self.alerts.clear()

    @staticmethod
    def _magnitude(acceleration: dict[str, float]) -> float:
        values = [float(acceleration.get(axis, 0.0)) for axis in ("x", "y", "z")]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("acceleration values must be finite numbers")
        return math.sqrt(sum(value * value for value in values))

    def update(
        self,
        device_id: str,
        acceleration: dict[str, float],
        timestamp: float | None = None,
    ) -> dict:
        timestamp = float(timestamp if timestamp is not None else time.time())
        if not math.isfinite(timestamp):
            raise ValueError("timestamp must be a finite number")
        device_id = str(device_id).strip()[:80] or "iphone-pwa"
        magnitude = self._magnitude(acceleration)
        previous = self.devices.get(device_id)
        possible_impact = magnitude >= self.impact_threshold

        if possible_impact:
            state = "IMPACT_RECORDED"
            last_motion_at = timestamp
            self.pending_impacts[device_id] = timestamp
        elif magnitude >= self.movement_threshold:
            state = "MOVING"
            last_motion_at = timestamp
        else:
            state = "STILL"
            last_motion_at = previous.last_motion_at if previous else timestamp

        impact_at = self.pending_impacts.get(device_id)
        confirmed_followup = False
        if impact_at is not None:
            elapsed = timestamp - impact_at
            if elapsed > self.impact_followup_seconds:
                self.pending_impacts.pop(device_id, None)
            elif elapsed >= self.still_after_impact_seconds and magnitude <= self.still_threshold:
                confirmed_followup = True
                self.pending_impacts.pop(device_id, None)
                self.alerts.append({
                    "timestamp": timestamp,
                    "room": None,
                    "status": "WARNING",
                    "source": "iphone_motion",
                    "reasons": ["Possible impact followed by low motion; caregiver review required"],
                })

        snapshot = MobileSensorSnapshot(
            device_id=device_id,
            state=state,
            motion_magnitude=round(magnitude, 3),
            last_seen_at=timestamp,
            last_motion_at=last_motion_at,
            possible_impact=possible_impact or confirmed_followup,
            samples_received=(previous.samples_received + 1) if previous else 1,
        )
        self.devices[device_id] = snapshot
        return asdict(snapshot)

    def status(self, device_id: str | None = None) -> dict | None:
        if device_id:
            snapshot = self.devices.get(device_id)
        else:
            snapshot = max(self.devices.values(), key=lambda item: item.last_seen_at, default=None)
        return asdict(snapshot) if snapshot else None
