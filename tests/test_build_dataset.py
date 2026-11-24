"""Uji unit build dataset v1 (MDE-H3-01 1/2). Uji kebocoran penuh: tests/test_no_leakage.py (2/2)."""
import numpy as np
import pandas as pd
import pytest

from renaro.contract import PROV_CODES
from renaro.data import dataset_v1 as D

T = pd.Timestamp


def _cal(days):
    d = pd.DataFrame({"date": pd.DatetimeIndex(days)})
    d["is_workday_pihps"] = d["date"].dt.day_of_week < 5
    for c in ("is_holiday", "is_cuti_bersama", "is_ramadan", "is_natal_tahunbaru", "is_post_lebaran"):
        d[c] = False
    d["days_to_lebaran"] = 10
    d["days_to_iduladha"] = 50
    d["dow"], d["month"], d["doy"] = d.date.dt.day_of_week, d.date.dt.month, d.date.dt.day_of_year
    return d


def test_skeleton_workdays_times_34_in_contract_order():
    cal = _cal(pd.date_range("2022-01-03", "2022-01-16"))
    sk = D.build_skeleton(cal, "2022-01-01", "2022-01-31")
    assert len(sk) == 10 * 34
    assert sk["prov_code"].iloc[:34].tolist() == list(PROV_CODES)
    assert (sk["date"].dt.day_of_week < 5).all()


def test_asof_uses_latest_available_not_same_day():
    panel = pd.DataFrame({"date": [T("2022-01-03"), T("2022-01-04"), T("2022-01-05")], "prov_code": "11"})
    feat = pd.DataFrame({"prov_code": "11",
                         "available_at": [T("2022-01-04"), T("2022-01-06")],
                         "x": [1.0, 2.0]})
    out = D.asof_join(panel, feat, "src", ["x"])
    assert out["x"].isna().iloc[0]                         # belum ada yang tersedia
    assert out["x"].tolist()[1:] == [1.0, 1.0]             # 2.0 baru tersedia 01-06
    assert (out["src__avail"].dropna() <= out.loc[out["src__avail"].notna(), "date"]).all()


def test_asof_is_by_province():
    panel = pd.DataFrame({"date": [T("2022-01-05")] * 2, "prov_code": ["11", "12"]})
    feat = pd.DataFrame({"prov_code": ["11", "12"], "available_at": [T("2022-01-04"), T("2022-01-06")], "x": [1.0, 2.0]})
    out = D.asof_join(panel, feat, "s", ["x"])
    assert out.loc[0, "x"] == 1.0 and np.isnan(out.loc[1, "x"])


def test_target_not_imputed_and_mask_consistent():
    sk = pd.DataFrame({"date": [T("2022-01-03"), T("2022-01-04")], "prov_code": "11"})
    prices = pd.DataFrame({"date": [T("2022-01-03")], "prov_code": "11", "price_type": 1, "price": [40000.0]})
    _, tgt = D.join_target(sk, prices)
    assert tgt["is_observed"].tolist() == [True, False]
    assert np.isnan(tgt["price"].iloc[1])


def test_price_features_use_only_past_observations():
    days = pd.bdate_range("2022-01-03", periods=30)
    prices = pd.DataFrame({"date": days, "prov_code": "11", "price_type": 1,
                           "price": np.linspace(10000, 39000, 30)})
    prices["available_at"] = list(days[1:]) + [days[-1] + pd.offsets.BDay()]
    f = D.price_features(prices, 1, "price")
    row = f[f["available_at"] == days[10]].iloc[0]        # observasi hari ke-9
    assert row["price_lag1"] == prices["price"].iloc[9]
    assert row["price_logret5"] == pytest.approx(np.log(prices.price.iloc[9] / prices.price.iloc[4]))


def test_roni_drops_phase_columns():
    r = pd.DataFrame({"year": [2022, 2022], "center_month": [1, 2], "roni": [-1.0, -0.8],
                      "available_at": ["2022-04-01", "2022-05-01"], "phase": ["lanina"] * 2,
                      "episode_id": ["x"] * 2})
    t = D.roni_table(r)
    assert not {"phase", "episode_id"} & set(t.columns)
    assert t["roni_delta"].iloc[1] == pytest.approx(0.2)


def test_nodes_include_rule():
    prov = pd.DataFrame({"prov_code": list(PROV_CODES), "prov_name": list(PROV_CODES)})
    rows = [(c, y, 1.0 if (c != "11" or y < 2022) else 0.5) for c in PROV_CODES for y in range(2018, 2026)]
    cov = pd.DataFrame(rows, columns=["prov_code", "year", "coverage"])
    n = D.node_flags(prov, cov)
    assert n["prov_code"].tolist() == list(PROV_CODES)
    assert n.set_index("prov_code").loc["11", "years_ok"] == 4
    assert not n.set_index("prov_code").loc["11", "include"]
    assert n["include"].sum() == 33


def test_quick_checks_flag_forbidden_and_future_avail():
    p = pd.DataFrame({"date": [T("2022-01-03")], "prov_code": "11",
                      "x__avail": [T("2022-01-04")], "regime_label": [1]})
    c = D.quick_checks(p)
    assert c["avail<=date:x__avail"] is False and c["no_regime_label_cols"] is False


def test_rolling_mean_std_matches_pandas_and_is_numpy_only():
    x = np.random.default_rng(1).normal(size=300)
    g = np.repeat(["11", "12", "13"], 100)
    m, s = D._rolling_mean_std(x, g, 20, 10)
    r = pd.Series(x).groupby(g)
    pm = r.transform(lambda v: v.rolling(20, min_periods=10).mean()).to_numpy()
    ps = r.transform(lambda v: v.rolling(20, min_periods=10).std()).to_numpy()
    assert (np.isnan(m) == np.isnan(pm)).all()
    assert np.nanmax(abs(m - pm)) < 1e-12 and np.nanmax(abs(s - ps)) < 1e-12
