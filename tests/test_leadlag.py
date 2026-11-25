import numpy as np
import pandas as pd

from renaro.eval.leadlag import bh_fdr, edges_from_mask, pentadize


def test_bh_fdr_known():
    q = bh_fdr(np.array([0.01, 0.02, 0.03, 0.04, np.nan]))
    assert np.isnan(q[-1])
    assert np.all(np.diff(q[:4]) >= 0)
    assert q[0] == 0.04


def test_edges_from_mask_direction():
    mask = np.zeros((34, 34), dtype=np.uint8)
    mask[1, 0] = 1  # dest 1, origin 0
    edges = edges_from_mask(mask)
    assert edges == [("11", "12")]


def test_pentadize_price_and_rain():
    panel = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-08", "2024-01-09"]),
        "prov_code": ["11"] * 4,
        "price": [100.0, 110.0, 121.0, 133.1],
        "is_observed": [True] * 4,
        "rain_pentad_anom": [0.1, 0.2, 0.3, 0.4],
    })
    regimes = pd.DataFrame({
        "date": panel["date"],
        "prov_code": ["11"] * 4,
        "enso_phase": ["neutral"] * 4,
        "is_dry": [False, False, True, True],
    })
    out = pentadize(panel, regimes)
    assert len(out) == 2
    assert out["n_price"].tolist() == [2, 2]
    assert out["delta_log"].isna().sum() == 1
    assert out["is_dry"].tolist() == [False, True]
    assert np.allclose(out["rain_anom"].to_numpy(), [0.15, 0.35])
