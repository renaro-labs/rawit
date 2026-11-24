"""Independent lightweight Graph WaveNet baseline; outputs log-price levels.

With kernel size 2 and dilations 2**i, receptive field = 2**n_layers.
Adjacency convention: A[i,j] weights messages from node j to node i.
"""
from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class _WaveBlock(nn.Module):
    def __init__(self, hidden: int, dilation: int, dropout: float):
        super().__init__()
        self.dilation = dilation
        self.filter = nn.Conv2d(hidden, hidden, (1, 2), dilation=(1, dilation))
        self.gate = nn.Conv2d(hidden, hidden, (1, 2), dilation=(1, dilation))
        # Identity plus two diffusion orders for each of two supports.
        self.graph_mix = nn.Conv2d(5 * hidden, hidden, 1)
        self.skip = nn.Conv2d(hidden, hidden, 1)
        self.norm = nn.BatchNorm2d(hidden)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, adaptive, prior):
        padded = F.pad(x, (self.dilation, 0, 0, 0))
        z = torch.tanh(self.filter(padded)) * torch.sigmoid(self.gate(padded))
        z = self.dropout(z)
        a1 = torch.einsum('ij,bcjt->bcit', adaptive, z)
        a2 = torch.einsum('ij,bcjt->bcit', adaptive, a1)
        if prior is None:
            p1 = p2 = torch.zeros_like(z)
        else:
            p1 = torch.einsum('ij,bcjt->bcit', prior, z)
            p2 = torch.einsum('ij,bcjt->bcit', prior, p1)
        mixed = self.graph_mix(torch.cat((z, a1, a2, p1, p2), dim=1))
        out = self.norm(x + mixed)
        return out, self.skip(out[..., -1:])


class GraphWaveNetLite(nn.Module):
    """X [B,T,N,F], optional prior [N,N] -> log-price [B,H,N]."""
    def __init__(self, n_features: int, hidden: int = 32,
                 n_layers: int = 4, horizons: tuple[int, ...] = (5, 10, 20),
                 dropout: float = 0.3, use_prior: bool = True,
                 *, n_nodes: int = 34, embedding_dim: int = 10):
        super().__init__()
        if min(n_features, hidden, n_layers, n_nodes, embedding_dim) <= 0 or not horizons:
            raise ValueError('Invalid model dimensions')
        self.n_features = n_features
        self.n_nodes = n_nodes
        self.horizons = tuple(horizons)
        self.use_prior = use_prior
        self.receptive_field = 2 ** n_layers
        self.E1 = nn.Parameter(torch.randn(n_nodes, embedding_dim) * 0.1)
        self.E2 = nn.Parameter(torch.randn(embedding_dim, n_nodes) * 0.1)
        self.input_proj = nn.Conv2d(n_features, hidden, 1)
        self.blocks = nn.ModuleList(_WaveBlock(hidden, 2 ** i, dropout) for i in range(n_layers))
        self.output_head = nn.Sequential(nn.ReLU(), nn.Conv2d(hidden, hidden, 1),
                                         nn.ReLU(), nn.Conv2d(hidden, len(horizons), 1))
        # Initialize bias without using any dataset statistics.
        # Training code may replace this with the train-only median log price.
        nn.init.constant_(self.output_head[-1].bias, 0.0)

    def adaptive_adjacency(self):
        return torch.softmax(F.relu(self.E1 @ self.E2), dim=-1)

    def forward(self, x: torch.Tensor, a_prior: torch.Tensor | None = None) -> torch.Tensor:
        if x.ndim != 4 or x.shape[2:] != (self.n_nodes, self.n_features) or x.shape[1] == 0:
            raise ValueError('X must have shape [B,T,N,F] with configured N,F')
        adaptive = self.adaptive_adjacency()
        prior = None
        if self.use_prior and a_prior is not None:
            if a_prior.shape != (self.n_nodes, self.n_nodes):
                raise ValueError('a_prior must have shape [N,N]')
            prior = a_prior.to(device=x.device, dtype=torch.float32)
            if not torch.isfinite(prior).all() or (prior < 0).any():
                raise ValueError('a_prior must be finite and nonnegative')
            prior = prior / prior.sum(dim=-1, keepdim=True).clamp_min(1e-12)
        z = self.input_proj(x.permute(0, 3, 2, 1).contiguous())
        skip = None
        for block in self.blocks:
            z, s = block(z, adaptive, prior)
            skip = s if skip is None else skip + s
        return self.output_head(skip).squeeze(-1)
