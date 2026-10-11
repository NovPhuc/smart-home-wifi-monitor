from __future__ import annotations
import torch
from torch import nn
import torch.nn.functional as F


class RoomNetLite(nn.Module):
    def __init__(self, in_channels: int, num_rooms: int, hidden_channels: int = 32, embedding_dim: int = 64, dropout: float = 0.15):
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

    def forward(self, x: torch.Tensor):
        z = self.stem(x)
        z = self.depthwise(z)
        z = self.pointwise(z)
        z = self.pool(z)
        emb = self.embedding(z)
        logits = self.classifier(emb)
        return logits, emb


class SimpleCNN(nn.Module):
    """Baseline CNN without depthwise separable conv, for comparison with RoomNetLite."""
    def __init__(self, in_channels: int, num_rooms: int, hidden_channels: int = 32, embedding_dim: int = 64, dropout: float = 0.15):
        super().__init__()
        self.conv1 = nn.Sequential(
            nn.Conv1d(in_channels, hidden_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm1d(hidden_channels),
            nn.ReLU(inplace=True),
        )
        self.conv2 = nn.Sequential(
            nn.Conv1d(hidden_channels, hidden_channels * 2, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm1d(hidden_channels * 2),
            nn.ReLU(inplace=True),
        )
        self.conv3 = nn.Sequential(
            nn.Conv1d(hidden_channels * 2, hidden_channels * 2, kernel_size=3, padding=1, bias=False),
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

    def forward(self, x: torch.Tensor):
        z = self.conv1(x)
        z = self.conv2(z)
        z = self.conv3(z)
        z = self.pool(z)
        emb = self.embedding(z)
        logits = self.classifier(emb)
        return logits, emb


class CenterLoss(nn.Module):
    def __init__(self, num_classes: int, feat_dim: int):
        super().__init__()
        self.centers = nn.Parameter(torch.randn(num_classes, feat_dim))

    def forward(self, features: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        centers_batch = self.centers.index_select(0, labels)
        return 0.5 * ((features - centers_batch) ** 2).sum(dim=1).mean()


def js_divergence_from_logits(p_logits: torch.Tensor, q_logits: torch.Tensor) -> torch.Tensor:
    p = F.softmax(p_logits, dim=-1)
    q = F.softmax(q_logits, dim=-1)
    m = 0.5 * (p + q)
    kl_pm = F.kl_div(torch.log(m + 1e-8), p, reduction="none").sum(dim=-1)
    kl_qm = F.kl_div(torch.log(m + 1e-8), q, reduction="none").sum(dim=-1)
    return 0.5 * (kl_pm + kl_qm)
