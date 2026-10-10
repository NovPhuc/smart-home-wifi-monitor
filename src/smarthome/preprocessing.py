from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
import json
import numpy as np
import pandas as pd


@dataclass
class RSSIPreprocessor:
    ap_columns: list[str]
    missing_rssi: float = -100.0
    min_rssi: float = -100.0
    max_rssi: float = -30.0

    @classmethod
    def fit(
        cls,
        df: pd.DataFrame,
        missing_rssi: float = -100.0,
        min_rssi: float = -100.0,
        max_rssi: float = -30.0,
    ) -> "RSSIPreprocessor":
        metadata = {
            "timestamp", "session_id", "device_id", "room", "orientation",
            "is_anomaly", "anomaly_type", "confidence",
        }
        ap_columns = [c for c in df.columns if c not in metadata]
        if not ap_columns:
            raise ValueError("No AP/RSSI columns were found in dataframe.")
        return cls(ap_columns=ap_columns, missing_rssi=missing_rssi, min_rssi=min_rssi, max_rssi=max_rssi)

    def _raw_vector(self, row: pd.Series | dict) -> np.ndarray:
        vals = []
        for ap in self.ap_columns:
            value = row.get(ap, self.missing_rssi) if isinstance(row, dict) else row.get(ap, self.missing_rssi)
            if value is None or (isinstance(value, float) and np.isnan(value)):
                value = self.missing_rssi
            vals.append(float(value))
        return np.asarray(vals, dtype=np.float32)

    def transform_row(self, row: pd.Series | dict) -> np.ndarray:
        rssi = self._raw_vector(row)
        mask = (rssi > self.missing_rssi + 1e-6).astype(np.float32)
        clipped = np.clip(rssi, self.min_rssi, self.max_rssi)
        denom = max(self.max_rssi - self.min_rssi, 1e-6)
        absolute = (clipped - self.min_rssi) / denom

        visible = rssi[mask > 0]
        median = float(np.median(visible)) if len(visible) else self.missing_rssi
        relative = np.clip((rssi - median) / (denom / 2.0), -1.0, 1.0)
        relative[mask == 0] = -1.0

        return np.concatenate([absolute, relative.astype(np.float32), mask], axis=0).astype(np.float32)

    def transform_frame(self, df: pd.DataFrame) -> np.ndarray:
        return np.stack([self.transform_row(row) for _, row in df.iterrows()])

    def transform_wifi_dict(self, wifi: dict[str, float]) -> np.ndarray:
        row = {ap: float(wifi.get(ap, self.missing_rssi)) for ap in self.ap_columns}
        return self.transform_row(row)

    @property
    def feature_dim(self) -> int:
        return len(self.ap_columns) * 3

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with Path(path).open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "RSSIPreprocessor":
        with Path(path).open("r", encoding="utf-8") as f:
            return cls(**json.load(f))
