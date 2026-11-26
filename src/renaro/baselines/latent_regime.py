"""H4-02: simplified latent-regime graph baseline (RCSGNet-inspired).

A GRU encoder produces a market context; a softmax over K latent states mixes
K learned directed adjacency matrices. No climate input is used. This is a
simplified head-to-head competitor, not a reproduction of RCSGNet.
"""
from __future__ import annotations

import torch
from torch import nn

from renaro.models.module1 import ClimateConditionedLagGraph
from renaro.models.module1_training import run_registered


class LatentRegimeLite(ClimateConditionedLagGraph):
    def __init__(self, n_features: int, n_climate: int, *, hidden: int = 64,
                 n_nodes: int = 34, k_states: int = 3,
                 horizons=(5, 10, 20)):
        super().__init__(
            n_features=n_features, n_climate=n_climate, n_edge_features=4,
            n_calendar_future=4, hidden=hidden, n_lags=1,
            horizons=horizons, null_option=False, forecast_aligned=True,
            n_nodes=None,
        )
        self.no_climate = True
        self.k_states = int(k_states)
        self.pi_head = nn.Linear(hidden, self.k_states)
        self.state_adj = nn.Parameter(torch.zeros(self.k_states, n_nodes, n_nodes))

    def graph(self, h, z_lag, e, s, candidate_mask, lag_mask=None):
        b, n, _ = h.shape
        # Latent regime graph: learn the directed adjacency from the market
        # context. Deliberately do not use the BPS geographic mask here.
        offdiag = ~torch.eye(n, dtype=torch.bool, device=h.device)
        valid = offdiag[None, None, :, :].expand(b, self.k_states, n, n)
        logits = self.state_adj[None].expand(b, -1, -1, -1)
        logits = logits.masked_fill(~valid, float("-inf"))
        adjacency = torch.softmax(logits, dim=-1)  # [B,K,N,N]
        pi = torch.softmax(self.pi_head(h), dim=-1)  # [B,N,K]
        a = (pi.transpose(1, 2).unsqueeze(-1) * adjacency).sum(dim=1)  # [B,N,N]
        self.last_null_mass = torch.zeros(b, n, device=h.device)
        return a.unsqueeze(-1)


def build(panel, cfg, spec):
    return LatentRegimeLite(
        n_features=10, n_climate=5,
        hidden=int(cfg.get("hidden", 64)), n_nodes=panel.mask.shape[0],
        k_states=int(cfg.get("k_states", 3)), horizons=spec.horizons,
    )


def run(panel, cfg, origin, seed):
    return run_registered(panel, cfg, origin, seed, model_factory=build)
