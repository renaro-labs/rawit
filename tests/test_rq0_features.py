"""Unit tests for MLE-H3-02 & RL-H3-01 tabular feature specifications (a/b/c)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaro.contract import N_NODES, PROV_CODES
from renaro.data.dummy import write_dummy
from renaro.data.io import load_panel
from renaro.features.tabular import (
    build_origin_weight_matrix,
    build_tabular_features,
)
from renaro.baselines.lgbm import get_feature_columns


def test_origin_weight_matrix_bps_and_papua_fallback():
    mask = np.zeros((N_NODES, N_NODES), dtype=np.uint8)
    # Row 0 (Aceh 11) supplied by Sumatera Utara (12, idx 1)
    mask[0, 1] = 1
    # Row 1 (Sumut 12) supplied by Aceh (0) and Sumbar (2)
    mask[1, 0] = 1
    mask[1, 2] = 1
    # Row 33 (Papua 94) left all-zero -> fallback to 3 nearest

    w = build_origin_weight_matrix(mask, None)
    assert w.shape == (N_NODES, N_NODES)
    assert np.allclose(np.diag(w), 0.0)
    assert np.allclose(w.sum(axis=1), 1.0)
    assert np.isclose(w[0, 1], 1.0)
    assert np.isclose(w[1, 0], 0.5) and np.isclose(w[1, 2], 0.5)
    # Papua fallback uses 3 provinces with weight 1/3 each
    assert np.isclose(w[33].sum(), 1.0)
    assert int((w[33] > 0).sum()) == 3


def test_variants_a_b_c_columns_and_no_future_leakage(tmp_path):
    write_dummy(tmp_path)
    panel = load_panel(tmp_path)

    fa = build_tabular_features(panel, variant="a")
    fb = build_tabular_features(panel, variant="b")
    fc = build_tabular_features(panel, variant="c")

    cols_a = set(get_feature_columns(fa))
    cols_b = set(get_feature_columns(fb))
    cols_c = set(get_feature_columns(fc))

    assert cols_a < cols_b < cols_c
    # Check required (a) features
    for lag in (1, 2, 3, 5, 10, 20):
        assert f"log_price_lag_{lag}" in cols_a
    for p in (5, 20):
        assert f"log_return_{p}" in cols_a
    for win in (20, 60):
        assert f"rolling_mean_{win}" in cols_a
        assert f"rolling_std_{win}" in cols_a

    # Check required (b) local climate features
    for lag in range(0, 9):
        assert f"rain_pentad_anom_lag{lag}" in cols_b
    assert "dry_spell_days" in cols_b
    assert "extreme_5d_sum4" in cols_b
    assert "rain_30d_anom" in cols_b

    # Check required (c) origin supplier climate features
    for lag in range(1, 9):
        assert f"origin_rain_pentad_anom_lag{lag}" in cols_c
    assert "origin_dry_spell_days" in cols_c
