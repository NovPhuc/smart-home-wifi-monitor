from __future__ import annotations

import re
import time

_SEVERITY = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
_NUMERIC = re.compile(r"\d+(?:\.\d+)?")


def _severity(status: str) -> int:
    return _SEVERITY.get(str(status).upper(), 0)


def _reason_signature(reasons) -> tuple[str, ...]:
    """Collapse volatile numbers so repeating a condition keeps the same signature.

    Rule reasons embed live measurements (\"Long dwell in Bedroom: 45.3 min\"),
    which change on every scan. Stripping digits lets an unchanged condition be
    recognised as a duplicate while still treating a genuinely new reason as new.
    """
    return tuple(sorted(_NUMERIC.sub("#", str(reason)) for reason in (reasons or [])))


class AlertThrottle:
    """Keep continuous conditions from writing one full alert per scan.

    An alert is emitted when it is new, when its severity escalates
    (``WARNING`` -> ``CRITICAL``), when the set of reasons changes, or once the
    cooldown has elapsed so a still-active condition resurfaces periodically.
    """

    def __init__(self, cooldown_seconds: float = 600.0):
        self.cooldown_seconds = float(cooldown_seconds)
        self._last: dict[object, tuple[tuple[str, tuple[str, ...]], float]] = {}

    def should_emit(self, key: object, status: str, reasons, now: float | None = None) -> bool:
        moment = float(time.time() if now is None else now)
        signature = (str(status).upper(), _reason_signature(reasons))
        previous = self._last.get(key)
        if previous is None:
            self._last[key] = (signature, moment)
            return True
        previous_signature, previous_at = previous
        escalated = _severity(signature[0]) > _severity(previous_signature[0])
        if escalated or signature != previous_signature or moment - previous_at >= self.cooldown_seconds:
            self._last[key] = (signature, moment)
            return True
        return False

    def reset(self, key: object | None = None) -> None:
        if key is None:
            self._last.clear()
        else:
            self._last.pop(key, None)
