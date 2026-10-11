from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import median


@dataclass
class ActivitySnapshot:
    state: str
    movement_score: float
    is_moving: bool
    last_movement_at: float | None
    inactive_minutes: float
    transitions_last_hour: int
    signal_quality: str
    visible_access_points: int


class ActivityMonitor:
    """Estimate coarse movement from RSSI changes and room transitions."""

    def __init__(
        self,
        movement_rssi_delta: float = 4.0,
        still_rssi_delta: float = 1.5,
        inactivity_minutes: float = 45.0,
        ema_alpha: float = 0.45,
    ):
        self.movement_rssi_delta = float(movement_rssi_delta)
        self.still_rssi_delta = float(still_rssi_delta)
        self.inactivity_minutes = float(inactivity_minutes)
        self.ema_alpha = float(ema_alpha)
        self.previous_wifi: dict[str, float] | None = None
        self.previous_room: str | None = None
        self.last_movement_at: float | None = None
        self.first_seen_at: float | None = None
        self.score = 0.0
        self.transitions: deque[float] = deque(maxlen=500)

    def reset(self) -> None:
        self.previous_wifi = None
        self.previous_room = None
        self.last_movement_at = None
        self.first_seen_at = None
        self.score = 0.0
        self.transitions.clear()

    @staticmethod
    def _rssi_delta(previous: dict[str, float], current: dict[str, float]) -> float:
        common = previous.keys() & current.keys()
        if not common:
            return 0.0
        return float(median(abs(float(current[ap]) - float(previous[ap])) for ap in common))

    @staticmethod
    def _signal_quality(wifi: dict[str, float]) -> str:
        if not wifi:
            return "NO_SIGNAL"
        strongest = max(float(value) for value in wifi.values())
        if strongest >= -60 and len(wifi) >= 3:
            return "GOOD"
        if strongest >= -75 and len(wifi) >= 2:
            return "FAIR"
        return "WEAK"

    def update(self, wifi: dict[str, float], room: str, timestamp: float) -> ActivitySnapshot:
        timestamp = float(timestamp)
        if self.first_seen_at is None:
            self.first_seen_at = timestamp
            self.last_movement_at = timestamp

        delta = self._rssi_delta(self.previous_wifi or {}, wifi)
        self.score = self.ema_alpha * delta + (1.0 - self.ema_alpha) * self.score
        room_changed = self.previous_room is not None and room != self.previous_room

        if room_changed:
            self.transitions.append(timestamp)
            self.last_movement_at = timestamp
            state = "ROOM_CHANGE"
        elif self.previous_wifi is None:
            state = "CALIBRATING"
        elif self.score >= self.movement_rssi_delta and delta > self.still_rssi_delta:
            self.last_movement_at = timestamp
            state = "MOVING"
        elif delta <= self.still_rssi_delta:
            state = "STILL"
        else:
            state = "LIGHT_ACTIVITY"
            self.last_movement_at = timestamp

        cutoff = timestamp - 3600.0
        while self.transitions and self.transitions[0] < cutoff:
            self.transitions.popleft()
        inactive = max(0.0, (timestamp - (self.last_movement_at or timestamp)) / 60.0)

        self.previous_wifi = {str(key): float(value) for key, value in wifi.items()}
        self.previous_room = room
        return ActivitySnapshot(
            state=state,
            movement_score=round(self.score, 3),
            is_moving=state in {"MOVING", "LIGHT_ACTIVITY", "ROOM_CHANGE"},
            last_movement_at=self.last_movement_at,
            inactive_minutes=inactive,
            transitions_last_hour=len(self.transitions),
            signal_quality=self._signal_quality(wifi),
            visible_access_points=len(wifi),
        )
