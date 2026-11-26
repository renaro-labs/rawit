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
        self.context_gru = nn.GRU(1, hidden, batch_first=True)
        self.context_head = nn.Linear(hidden, self.k_states)
        self.state_adj = nn.Parameter(torch.zeros(self.k_states, n_nodes, n_nodes))
        self._pi = None

    def forward(self, x, c, s, candidate_mask, cal_future):
        # Market-context encoder: 20 daily returns for every province, encoded
        # by a separate GRU and pooled across nodes into pi_t [B, K].
        price = x[:, :, :, 0]
        returns = price.diff(dim=1)[:, -20:]
        b, t_ret, n = returns.shape
        if t_ret == 0:
            self._pi = x.new_full((b, self.k_states), 1.0 / self.k_states)
        else:
            inp = returns.permute(0, 2, 1).reshape(b * n, t_ret, 1)
            out, _ = self.context_gru(inp)
            pooled = out[:, -1].reshape(b, n, -1).mean(dim=1)
            self._pi = torch.softmax(self.context_head(pooled), dim=-1)
        if self._pi is None:
            self._pi = x.new_full((b, self.k_states), 1.0 / self.k_states)
        return super().forward(x, c, s, candidate_mask, cal_future)

    def graph(self, h, z_lag, e, s, candidate_mask, lag_mask=None):
        b, n, _ = h.shape
        mask = candidate_mask.to(device=h.device, dtype=torch.bool)
        offdiag = ~torch.eye(n, dtype=torch.bool, device=h.device)
        # Preserve the BPS candidate graph, with an off-diagonal fallback for a
        # destination that has no candidate supplier (Papua in the BPS mask).
        fallback = ~mask.any(dim=-1)
        valid = mask[None, None, :, :] | (
            fallback[None, None, :, None] & offdiag[None, None, :, :]
        )
        logits = self.state_adj[None].expand(b, -1, -1, -1)
        logits = logits.masked_fill(~valid, float("-inf"))
        adjacency = torch.softmax(logits, dim=-1)  # [B,K,N,N]
        pi = self._pi if self._pi is not None else h.new_full(
            (b, self.k_states), 1.0 / self.k_states
        )
        a = (pi[:, :, None, None] * adjacency).sum(dim=1)  # [B,N,N]
        self.last_null_mass = torch.zeros(b, n, device=h.device)
        return a.unsqueeze(-1)

    def entropy_regularizer(self, a):
        # fit() adds entropy_lambda * this value. Returning negative H(pi)
        # therefore implements the intended -lambda * H(pi) penalty.
        if self._pi is None:
            return a.new_zeros(())
        p = self._pi.float().clamp_min(1e-12)
        return -(p * p.log()).sum(dim=-1).mean()


def build(panel, cfg, spec):
    return LatentRegimeLite(
        n_features=10, n_climate=5,
        hidden=int(cfg.get("hidden", 64)), n_nodes=panel.mask.shape[0],
        k_states=int(cfg.get("k_states", 3)), horizons=spec.horizons,
    )


def run(panel, cfg, origin, seed):
    return run_registered(panel, cfg, origin, seed, model_factory=build)
