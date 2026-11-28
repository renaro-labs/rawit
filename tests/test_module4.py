"""Unit tests for MLE-H5-04 Module 4 (perturbation robustness, causal cross-regime risk,
and soft BPS prior regularization).
"""
from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml

from renaro.contract import PROJECT_ROOT
from renaro.data.datasets import CLIMATE_FEATURES, FEATURES
from renaro.models import module4
from renaro.models.module4 import (
    Module4,
    causal_origin_climate_groups,
    cross_regime_risk_loss,
    perturb_candidate_mask,
    perturbation_sensitivity_loss,
    soft_prior_l1_loss,
)


def test_module4_never_references_regime_labels_csv():
    src = inspect.getsource(module4)
    # Only docstrings may warn against regime_labels.csv; no actual file load or import.
    assert "eval_splits" not in src
    assert "label_primary" not in src
    assert "read_parquet" not in src
    assert "read_csv" not in src


def test_module4_config_has_no_regime_or_holdout_features():
    cfg_path = PROJECT_ROOT / "configs" / "models" / "module4.yaml"
    txt = cfg_path.read_text(encoding="utf-8")
    cfg = yaml.safe_load(txt)
    assert cfg["model"] == "module4"
    assert cfg["prior"] == "soft_bps"
    assert cfg["group_feature"] in CLIMATE_FEATURES
    for forbidden in ("regime", "label_primary", "is_dry", "is_extreme", "enso_phase", "holdout"):
        assert forbidden not in txt.lower(), f"Forbidden token {forbidden} in module4.yaml"


def test_perturb_candidate_mask_valid_and_nonzero_diff():
    n = 12
    rng = np.random.default_rng(42)
    bps = torch.zeros((n, n), dtype=torch.float32)
    for i in range(n):
        bps[i, (i + 1) % n] = 1.0
        bps[i, (i + 2) % n] = 1.0
    cand_dense = ~torch.eye(n, dtype=torch.bool)
    tilde = perturb_candidate_mask(cand_dense, bps, p_min=0.2, p_max=0.4, mode="mixed", rng=rng)
    assert tilde.shape == (n, n)
    assert tilde.dtype == torch.bool
    assert not torch.diag(tilde).any()
    assert not torch.equal(tilde, cand_dense)


def test_soft_prior_l1_loss_zero_on_bps_and_positive_off_bps():
    b, n, l = 2, 6, 4
    bps = torch.zeros((n, n), dtype=torch.float32)
    for i in range(n):
        bps[i, (i + 1) % n] = 1.0
    a_on = torch.zeros((b, n, n, l), dtype=torch.float32)
    for i in range(n):
        a_on[:, i, (i + 1) % n, 0] = 1.0
    assert float(soft_prior_l1_loss(a_on, bps)) == pytest.approx(0.0, abs=1e-7)

    a_off = torch.zeros((b, n, n, l), dtype=torch.float32)
    for i in range(n):
        a_off[:, i, (i + 2) % n, 0] = 0.5
    assert float(soft_prior_l1_loss(a_off, bps)) == pytest.approx(0.5, abs=1e-6)


def test_causal_cross_regime_risk_variance_and_causality():
    torch.manual_seed(0)
    b, t, n, f_c = 8, 20, 6, len(CLIMATE_FEATURES)
    c = torch.randn(b, t, n, f_c)
    w = torch.eye(n)
    g1 = causal_origin_climate_groups(c, w, feature_idx=1, n_groups=3, lookback=5)
    assert g1.shape == (b, n)
    assert set(g1.unique().tolist()).issubset({0, 1, 2})
    assert len(g1.unique()) >= 2

    # Perturbing earlier steps outside lookback does not change recent-pentad groups.
    c_mod = c.clone()
    c_mod[:, :-5, :, :] = 999.0
    g2 = causal_origin_climate_groups(c_mod, w, feature_idx=1, n_groups=3, lookback=5)
    assert torch.equal(g1, g2)

    # Identical errors across groups -> variance 0; different errors -> variance > 0.
    y = torch.full((b, 3, n), 10000.0)
    mask = torch.ones((b, 3, n), dtype=torch.bool)
    pred_equal = torch.full((b, 3, n), float(np.log(10000.0)) + 0.1, requires_grad=True)
    var_eq, n_act = cross_regime_risk_loss(pred_equal, y, mask, g1, n_groups=3)
    assert n_act >= 2
    assert float(var_eq) == pytest.approx(0.0, abs=1e-7)

    offset = (g1.float() * 0.2)[:, None, :].expand(b, 3, n)
    pred_diff = (torch.full((b, 3, n), float(np.log(10000.0))) + offset).requires_grad_(True)
    var_diff, _ = cross_regime_risk_loss(pred_diff, y, mask, g1, n_groups=3)
    assert float(var_diff) > 0.01
    var_diff.backward()
    assert pred_diff.grad is not None and torch.isfinite(pred_diff.grad).all()


def test_module4_forward_and_all_three_losses_backward():
    torch.manual_seed(7)
    b, t, n, h = 4, 30, 8, 3
    bps = torch.zeros((n, n), dtype=torch.float32)
    for i in range(n):
        bps[i, (i + 1) % n] = 1.0
    net = Module4(
        n_features=len(FEATURES),
        n_climate=len(CLIMATE_FEATURES),
        hidden=16,
        n_lags=4,
        horizons=(5, 10, 20),
        n_nodes=n,
        static_prior=bps,
    )
    x = torch.randn(b, t, n, len(FEATURES))
    c = torch.randn(b, t, n, len(CLIMATE_FEATURES))
    s = torch.zeros(n, n, 4)
    s[:, :, 1] = bps
    cand = ~torch.eye(n, dtype=torch.bool)
    tilde = perturb_candidate_mask(cand, bps, p_min=0.3, p_max=0.4, rng=np.random.default_rng(1))
    cal = torch.zeros(b, h, 4)
    y = torch.full((b, h, n), 50000.0)
    mask = torch.ones((b, h, n), dtype=torch.bool)

    # Verify factorized forward matches single-pass forward in eval mode.
    net.eval()
    with torch.no_grad():
        p_direct, a_direct = net(x, c, s, cand, cal)
        p_clean, a_clean, _, p_tilde, _ = net.forward_clean_and_perturbed(x, c, s, cand, tilde, cal)
        p_tilde_direct, _ = net(x, c, s, tilde, cal)
    assert torch.allclose(p_direct, p_clean, atol=1e-6)
    assert torch.allclose(a_direct, a_clean, atol=1e-6)
    assert torch.allclose(p_tilde, p_tilde_direct, atol=1e-6)

    # Full training objective backward pass with finite gradients.
    net.train()
    p_clean, a_clean, static, p_tilde, _ = net.forward_clean_and_perturbed(x, c, s, cand, tilde, cal)
    l_pred = (p_clean[mask] - y[mask].log()).abs().mean()
    l_pert = perturbation_sensitivity_loss(p_clean, p_tilde, mask, norm="l1")
    groups = causal_origin_climate_groups(c, net.origin_weights, feature_idx=1, n_groups=3)
    l_vrex, n_act = cross_regime_risk_loss(p_clean, y, mask, groups, n_groups=3)
    l_prior = soft_prior_l1_loss(a_clean, bps, a_static=static)
    assert n_act >= 2
    assert float(l_pert) >= 0.0 and float(l_prior) > 0.0
    total = l_pred + 0.15 * l_pert + 5.0 * l_vrex + 0.05 * l_prior
    total.backward()
    grads = [p.grad for p in net.parameters() if p.grad is not None]
    assert len(grads) > 0 and all(torch.isfinite(g).all() for g in grads)
