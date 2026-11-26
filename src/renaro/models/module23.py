"""MLE-H5-01: stable/adaptive graph model with a reliability gate.

The model keeps Module 1's climate-conditioned adaptive graph and adds a
static (climate-free) graph path.  A per-node gate mixes the two messages using
only information available at the decision time:

    z_t = g_t * H_adapt + (1 - g_t) * H_stable

This is the validation implementation of the H5 module 2-3 specification.
"""
from __future__ import annotations

import math

import torch
from torch import nn

from renaro.data.datasets import CLIMATE_FEATURES, FEATURES
from renaro.models.module1 import ClimateConditionedLagGraph
from renaro.models.module1_training import run_registered


class StableAdaptiveGate(nn.Module):
    """Per-node reliability gate from shock, attention reliability and shift."""

    def __init__(self, hidden: int, n_shock: int = 3, n_reliability: int = 2,
                 n_shift: int = 1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_shock + n_reliability + n_shift, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, shock, reliability, shift):
        return torch.sigmoid(self.net(torch.cat([shock, reliability, shift], dim=-1)))


class Module23(ClimateConditionedLagGraph):
    def __init__(self, n_features: int, n_climate: int, *, hidden: int = 64,
                 n_lags: int = 6, horizons=(5, 10, 20), n_nodes: int = 34,
                 static_prior: torch.Tensor | None = None,
                 no_gate: bool = False, no_climate_gate: bool = False,
                 no_calendar: bool = False, no_climate: bool = False):
        super().__init__(
            n_features=n_features, n_climate=n_climate, n_edge_features=4,
            n_calendar_future=4, hidden=hidden, n_lags=n_lags,
            horizons=horizons, null_option=True, forecast_aligned=True,
            n_nodes=n_nodes,
        )
        self.no_gate = bool(no_gate)
        self.no_climate_gate = bool(no_climate_gate)
        self.no_calendar = bool(no_calendar)
        self.no_climate = bool(no_climate)
        self.gate_override = None
        self.calendar_idx = [FEATURES.index(f) for f in
                             ("is_ramadan", "days_to_lebaran", "dow", "month")]
        self.climate_idx = [CLIMATE_FEATURES.index(f) for f in
                            ("dry_spell_days", "extreme_5d", "roni")]
        if static_prior is None:
            static_prior = torch.eye(n_nodes)
        prior = static_prior.float().clamp_min(0)
        prior = prior / prior.sum(dim=-1, keepdim=True).clamp_min(1e-6)
        self.register_buffer("static_prior", prior)
        self.register_buffer("a_train_mean", prior.clone())
        self.static_logits = nn.Parameter(torch.log(prior + 1e-6))
        self.gate = StableAdaptiveGate(hidden)

    def _static_graph(self, candidate_mask):
        n = self.static_logits.shape[0]
        mask = candidate_mask.to(device=self.static_logits.device, dtype=torch.bool)
        offdiag = ~torch.eye(n, dtype=torch.bool, device=self.static_logits.device)
        fallback = ~mask.any(dim=-1)
        valid = mask | (fallback[:, None] & offdiag)
        logits = self.static_logits.masked_fill(~valid, float("-inf"))
        return torch.softmax(logits, dim=-1)

    def forward(self, x, c, s, candidate_mask, cal_future):
        b, t, n, f = x.shape
        if self.no_calendar:
            x = x.clone()
            x[..., self.calendar_idx] = 0
        z, hn = self.encoder(x.transpose(1, 2).reshape(b * n, t, f))
        h = hn[-1].reshape(b, n, -1)
        z = z.reshape(b, n, t, -1).transpose(1, 2)
        z_lag = self.lagged_states(z)
        climate = []
        for lag in range(8):
            end = t - 5 * lag
            climate.append(c[:, end - 5:end].mean(1) if end >= 5
                           else c.new_zeros(b, n, c.shape[-1]))
        e = self.climate_mlp(torch.cat(climate, dim=-1))
        if self.no_climate:
            e = torch.zeros_like(e)
        lag_mask = (torch.arange(self.n_lags, device=x.device) + 1) * 5 <= t
        a = self.graph(h, z_lag, e, s, candidate_mask, lag_mask)
        k = len(self.horizons)

        if self.forecast_aligned:
            offsets = torch.tensor(self.horizons, device=x.device)[:, None] - 1
            delays = 5 * (torch.arange(self.n_lags, device=x.device) + 1)
            indices = (t - 1 + offsets - delays).clamp(0, t - 1)
            values = self.value(z[:, indices]) + self.input_value(x[:, indices])
            messages = torch.einsum("bijl,bkljd->bkid", a, values)
        else:
            messages = torch.einsum("bijl,bljd->bid", a, self.value(z_lag))
            messages = messages[:, None].expand(-1, k, -1, -1)
        m_adapt = messages.mean(dim=1)  # [B,N,H]

        static = self._static_graph(candidate_mask)
        stable_state = self.value(z_lag[:, 0])
        m_stable = torch.einsum("ij,bjd->bid", static, stable_state)

        c_recent = c[:, -10:].mean(1)
        shock_src = c_recent[..., self.climate_idx]
        if self.no_climate or self.no_climate_gate:
            shock = x.new_zeros(b, n, 3)
        else:
            shock = torch.einsum("ij,bjf->bif", static, shock_src)
            shock = torch.stack([shock[..., 0], shock[..., 1],
                                 shock[..., 2].abs()], dim=-1)

        p = a.float().clamp_min(1e-12)
        ent = -(p * p.log()).sum(dim=(-1, -2)) / max(math.log(float(n * self.n_lags)), 1.0)
        a_mean = a.float().mean(dim=-1)
        if self.training:
            with torch.no_grad():
                self.a_train_mean.mul_(0.99).add_(a_mean.detach().mean(0) * 0.01)
        rel_dist = (a_mean - self.a_train_mean.to(a_mean.device)[None]).abs().sum(-1)
        rel = torch.stack([ent, rel_dist], dim=-1)
        shift = x[:, -20:].mean(1).abs().mean(-1, keepdim=True)
        if self.gate_override is not None:
            g = x.new_full((b, n, 1), float(self.gate_override))
        elif self.no_gate:
            g = x.new_ones(b, n, 1)
        else:
            g = self.gate(shock, rel, shift)
        self.last_gate = g
        self.last_adapt = m_adapt
        self.last_stable = m_stable
        z_t = g * m_adapt + (1.0 - g) * m_stable

        cal = cal_future
        if self.no_calendar:
            cal = torch.zeros_like(cal)
        hm = torch.cat([h, z_t], dim=-1)[:, None].expand(-1, k, -1, -1)
        cal = cal[:, :, None, :].expand(-1, -1, n, -1)
        outputs = self.head(torch.cat([hm, cal], dim=-1))
        yhat = outputs.diagonal(dim1=1, dim2=3).transpose(1, 2).contiguous()
        return yhat, a


def build(panel, cfg, spec):
    prior = torch.as_tensor(panel.mask, dtype=torch.float32)
    return Module23(
        n_features=len(FEATURES), n_climate=len(CLIMATE_FEATURES),
        hidden=int(cfg.get("hidden", 64)), n_lags=int(cfg.get("n_lags", 6)),
        horizons=spec.horizons, n_nodes=panel.mask.shape[0], static_prior=prior,
        no_gate=bool(cfg.get("no_gate", False)),
        no_climate_gate=bool(cfg.get("no_climate_gate", False)),
        no_calendar=bool(cfg.get("no_calendar", False)),
        no_climate=bool(cfg.get("no_climate_gate", False)),
    )


def run(panel, cfg, origin, seed):
    return run_registered(panel, cfg, origin, seed, model_factory=build)
