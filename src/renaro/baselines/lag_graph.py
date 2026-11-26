"""H4-03: simplified MillGNN-style lag graph baseline.

Module 1 without exogenous climate input, with a learned global decay bias over
lag bins. It is a baseline, not a reproduction of MillGNN.
"""
from __future__ import annotations

import torch
from torch import nn

from renaro.contract import N_LAG_BINS
from renaro.models.module1 import ClimateConditionedLagGraph
from renaro.models.module1_training import run_registered


class LagGraphLite(ClimateConditionedLagGraph):
    def __init__(self, n_features: int, n_climate: int, *, hidden: int = 64,
                 n_lags: int = N_LAG_BINS, n_nodes: int = 34,
                 horizons=(5, 10, 20)):
        super().__init__(
            n_features=n_features, n_climate=n_climate, n_edge_features=4,
            n_calendar_future=4, hidden=hidden, n_lags=n_lags,
            horizons=horizons, null_option=True, forecast_aligned=True,
            n_nodes=n_nodes,
        )
        self.no_climate = True
        # A learned decay prior: older lag bins start with a lower score.
        if self.edge_lag_bias is not None:
            with torch.no_grad():
                lag = torch.arange(n_lags, dtype=self.edge_lag_bias.dtype)
                self.edge_lag_bias.copy_(-0.08 * lag.view(1, 1, -1).expand_as(self.edge_lag_bias))


def build(panel, cfg, spec):
    return LagGraphLite(
        n_features=10, n_climate=5,
        hidden=int(cfg.get("hidden", 64)), n_lags=int(cfg.get("n_lags", N_LAG_BINS)),
        n_nodes=panel.mask.shape[0], horizons=spec.horizons,
    )


def run(panel, cfg, origin, seed):
    return run_registered(panel, cfg, origin, seed, model_factory=build)
