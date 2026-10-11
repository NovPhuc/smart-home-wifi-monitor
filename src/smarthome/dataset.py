from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from .preprocessing import RSSIPreprocessor


class RoomWindowDataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        preprocessor: RSSIPreprocessor,
        rooms: Sequence[str],
        window_size: int = 5,
    ) -> None:
        self.preprocessor = preprocessor
        self.rooms = list(rooms)
        self.room_to_idx = {r: i for i, r in enumerate(self.rooms)}
        self.window_size = window_size
        self.samples: list[tuple[np.ndarray, int, float]] = []

        required = {"room", "session_id", "device_id", "timestamp"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {sorted(missing)}")

        work = df.sort_values(["session_id", "device_id", "timestamp"]).copy()
        work["_features"] = list(preprocessor.transform_frame(work))

        for _, group in work.groupby(["session_id", "device_id"], sort=False):
            feats = np.stack(group["_features"].to_list())
            labels = group["room"].tolist()
            if len(group) < window_size:
                continue
            for end in range(window_size - 1, len(group)):
                start = end - window_size + 1
                x = feats[start : end + 1].T  # [features, time]
                y = self.room_to_idx[labels[end]]
                stable = float(len(set(labels[start : end + 1])) == 1)
                self.samples.append((x.astype(np.float32), y, stable))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        x, y, stable = self.samples[idx]
        return (
            torch.from_numpy(x),
            torch.tensor(y, dtype=torch.long),
            torch.tensor(stable, dtype=torch.float32),
        )


@dataclass
class AnomalyFeatureBuilder:
    rooms: list[str]
    max_dwell_minutes: float = 180.0

    @property
    def room_dim(self) -> int:
        return len(self.rooms)

    @property
    def feature_dim(self) -> int:
        return self.room_dim + 4  # room one-hot + dwell + sin + cos + confidence

    def encode_event(self, room: str, dwell_minutes: float, hour: float, confidence: float = 1.0) -> np.ndarray:
        one_hot = np.zeros(self.room_dim, dtype=np.float32)
        if room in self.rooms:
            one_hot[self.rooms.index(room)] = 1.0
        dwell = np.clip(dwell_minutes / self.max_dwell_minutes, 0.0, 1.0)
        angle = 2.0 * np.pi * (hour % 24.0) / 24.0
        return np.concatenate(
            [one_hot, np.asarray([dwell, np.sin(angle), np.cos(angle), np.clip(confidence, 0.0, 1.0)], dtype=np.float32)]
        )

    def from_event_frame(self, df: pd.DataFrame) -> np.ndarray:
        return np.stack(
            [
                self.encode_event(
                    room=row["room"],
                    dwell_minutes=float(row["dwell_minutes"]),
                    hour=float(row["hour"]),
                    confidence=float(row.get("confidence", 1.0)),
                )
                for _, row in df.iterrows()
            ]
        )


class SequenceDataset(Dataset):
    def __init__(self, features: np.ndarray, sequence_length: int = 20):
        if features.ndim != 2:
            raise ValueError("features must have shape [N, F]")
        self.sequences = []
        for end in range(sequence_length - 1, len(features)):
            start = end - sequence_length + 1
            self.sequences.append(features[start : end + 1].astype(np.float32))

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        x = torch.from_numpy(self.sequences[idx])
        return x
