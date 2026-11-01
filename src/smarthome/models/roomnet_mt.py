"""RoomNet-MT: multi-task model — encoder dùng chung, head phòng + head hoạt động.

Ý tưởng tham khảo từ ARIL ("Joint Activity Recognition and Indoor Localization
with WiFi Fingerprints", IEEE Access 2019): học chung một encoder cho hai bài
toán giúp embedding phòng mang thêm thông tin vận động. Khác ARIL (CSI + SDR),
ở đây hoạt động được suy trực tiếp từ biến động RSSI trong cửa sổ với đúng
ngưỡng mà ``ActivityMonitor`` đang dùng — tức là chưng cất (distillation) bộ
luật hiện có vào model, để model học được tín hiệu ổn định hơn nhiễu từng scan.
"""
from __future__ import annotations

from statistics import median

import torch
from torch import nn

ACTIVITY_LABELS: tuple[str, ...] = ("STILL", "LIGHT_ACTIVITY", "MOVING", "ROOM_CHANGE")


class RoomNetMT(nn.Module):
    """Encoder giống RoomNetLite + head hoạt động 4 lớp.

    Forward trả ``(room_logits, emb, activity_logits)`` — hai phần tử đầu
    giống hệt RoomNetLite nên mọi loss/tiện ích cũ dùng lại được.
    """

    def __init__(
        self,
        in_channels: int,
        num_rooms: int,
        hidden_channels: int = 32,
        embedding_dim: int = 64,
        dropout: float = 0.15,
        num_activities: int = len(ACTIVITY_LABELS),
    ):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, hidden_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm1d(hidden_channels),
            nn.ReLU(inplace=True),
        )
        self.depthwise = nn.Sequential(
            nn.Conv1d(hidden_channels, hidden_channels, kernel_size=3, padding=1, groups=hidden_channels, bias=False),
            nn.BatchNorm1d(hidden_channels),
            nn.ReLU(inplace=True),
        )
        self.pointwise = nn.Sequential(
            nn.Conv1d(hidden_channels, hidden_channels * 2, kernel_size=1, bias=False),
            nn.BatchNorm1d(hidden_channels * 2),
            nn.ReLU(inplace=True),
        )
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.embedding = nn.Sequential(
            nn.Flatten(),
            nn.Linear(hidden_channels * 2, embedding_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
        )
        self.classifier = nn.Linear(embedding_dim, num_rooms)
        self.activity_head = nn.Linear(embedding_dim, num_activities)

    def forward(self, x: torch.Tensor):
        z = self.stem(x)
        z = self.depthwise(z)
        z = self.pointwise(z)
        z = self.pool(z)
        emb = self.embedding(z)
        logits = self.classifier(emb)
        activity_logits = self.activity_head(emb)
        return logits, emb, activity_logits


def derive_activity_label(
    raw_deltas: "list[float] | None",
    rooms_in_window: "list[str]",
    movement_delta: float = 4.0,
    still_delta: float = 1.5,
) -> int:
    """Nhãn hoạt động của một cửa sổ, cùng ngưỡng với ``ActivityMonitor``.

    - Có sự thay đổi phòng trong cửa sổ → ``ROOM_CHANGE``.
    - Không có delta (cửa sổ thiếu dữ liệu) → ``STILL``.
    - Median delta giữa các scan liên tiếp ≤ ``still_delta`` → ``STILL``;
      ≥ ``movement_delta`` → ``MOVING``; còn lại → ``LIGHT_ACTIVITY``.

    Bộ luật gốc dùng EMA theo scan đơn; ở đây dùng median trên cửa sổ nên
    ổn định hơn với nhiễu đơn lẻ — được ghi rõ khi báo cáo.
    """
    if len(set(rooms_in_window)) > 1:
        return ACTIVITY_LABELS.index("ROOM_CHANGE")
    values = [float(d) for d in (raw_deltas or []) if d == d and d >= 0]  # lọc NaN/âm
    delta = float(median(values)) if values else 0.0
    if delta <= still_delta:
        return ACTIVITY_LABELS.index("STILL")
    if delta >= movement_delta:
        return ACTIVITY_LABELS.index("MOVING")
    return ACTIVITY_LABELS.index("LIGHT_ACTIVITY")
