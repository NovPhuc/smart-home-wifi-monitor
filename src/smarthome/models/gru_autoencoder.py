from __future__ import annotations
import torch
from torch import nn
import torch.nn.functional as F


class GRUAutoencoder(nn.Module):
    def __init__(self, feature_dim: int, hidden_size: int = 48, latent_size: int = 24, num_layers: int = 1):
        super().__init__()
        self.feature_dim = feature_dim
        self.hidden_size = hidden_size
        self.latent_size = latent_size
        self.num_layers = num_layers

        self.encoder = nn.GRU(feature_dim, hidden_size, num_layers=num_layers, batch_first=True)
        self.to_latent = nn.Linear(hidden_size, latent_size)
        self.from_latent = nn.Linear(latent_size, hidden_size)
        self.decoder = nn.GRU(hidden_size, hidden_size, num_layers=num_layers, batch_first=True)
        self.out = nn.Linear(hidden_size, feature_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, h = self.encoder(x)
        last = h[-1]
        latent = torch.tanh(self.to_latent(last))
        seed = torch.tanh(self.from_latent(latent))
        dec_in = seed.unsqueeze(1).repeat(1, x.shape[1], 1)
        dec_out, _ = self.decoder(dec_in)
        return self.out(dec_out)


def reconstruction_loss(
    recon: torch.Tensor,
    target: torch.Tensor,
    room_dim: int,
    room_weight: float = 1.0,
    continuous_weight: float = 0.7,
) -> torch.Tensor:
    room_logits = recon[:, :, :room_dim]
    target_room = target[:, :, :room_dim].argmax(dim=-1)
    room_loss = F.cross_entropy(room_logits.reshape(-1, room_dim), target_room.reshape(-1))
    cont_loss = F.huber_loss(recon[:, :, room_dim:], target[:, :, room_dim:])
    return room_weight * room_loss + continuous_weight * cont_loss


def per_sequence_reconstruction_score(
    recon: torch.Tensor,
    target: torch.Tensor,
    room_dim: int,
    room_weight: float = 1.0,
    continuous_weight: float = 0.7,
) -> torch.Tensor:
    room_logits = recon[:, :, :room_dim]
    target_room = target[:, :, :room_dim].argmax(dim=-1)
    ce = F.cross_entropy(
        room_logits.reshape(-1, room_dim),
        target_room.reshape(-1),
        reduction="none",
    ).reshape(target.shape[0], target.shape[1]).mean(dim=1)
    huber = F.huber_loss(
        recon[:, :, room_dim:],
        target[:, :, room_dim:],
        reduction="none",
    ).mean(dim=(1, 2))
    return room_weight * ce + continuous_weight * huber
