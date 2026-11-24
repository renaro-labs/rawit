"""Uji cleaning harga (MDE-H2-01).

Dua bagian:
1. Uji output nyata `data/interim/prices_clean.parquet` (dilewati bila file belum dibuat):
   kunci unik, tidak ada harga <= 0, max(date) < holdout, semua prov_code valid, skema persis.
2. Uji aturan dengan data sintetis (selalu jalan).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renaro.contract import HOLDOUT_START, PROV_CODES, PROVINCES, TABLE_COLUMNS
from renaro.data import cleaning as C

CLEAN = Path("data/interim/prices_clean.parquet")
EXPECTED_DTYPES = {
    "date": "datetime64[ns]", "prov_code": "string", "commodity": "string", "price_type": "int64",
    "price_raw": "float64", "price": "float64", "is_observed": "bool", "flag_outlier": "bool",
    "flag_post_lebaran": "bool", "flag_carry_forward": "bool", "source": "string",
    "available_at": "datetime64[ns]",
}


# ---------------------------------------------------------------------------
# 1. Output nyata
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def clean():
    if not CLEAN.exists():
        pytest.skip(f"{CLEAN} belum ada; jalankan python -m renaro.data.cleaning")
    return pd.read_parquet(CLEAN)


def test_schema_exact(clean):
    assert list(clean.columns) == list(TABLE_COLUMNS["prices_clean"])
    # Kolom teks: 'object' (pandas 2) atau 'str' (pandas 3) sama-sama diterima sebagai "string".
    got = {c: ("string" if pd.api.types.is_string_dtype(t) else str(t)) for c, t in clean.dtypes.items()}
    assert got == EXPECTED_DTYPES


def test_unique_key(clean):
    assert not clean.duplicated(["date", "prov_code", "commodity", "price_type"]).any()


def test_no_nonpositive_price(clean):
    assert not (clean["price"] <= 0).any()
    assert not (clean["price_raw"] <= 0).any()


def test_before_holdout(clean):
    assert clean["date"].max() < pd.Timestamp(HOLDOUT_START)


def test_prov_codes_valid(clean):
    assert set(clean["prov_code"]) == set(PROV_CODES)


def test_available_after_date(clean):
    assert (clean["available_at"] > clean["date"]).all()


def test_is_observed_matches_price(clean):
    assert (clean["is_observed"] == clean["price"].notna()).all()


def test_nan_share_below_one_percent(clean):
    raw_obs = clean["price_raw"].notna().sum()
    nan_by_cleaning = (clean["price_raw"].notna() & clean["price"].isna()).sum()
    assert nan_by_cleaning / raw_obs < 0.01


def test_post_lebaran_2022_kept(clean):
    win = clean[(clean["price_type"] == 1) & clean["date"].between("2022-05-02", "2022-05-12")]
    assert win["flag_post_lebaran"].all()
    assert (win["price"].notna() == win["price_raw"].notna()).all()   # tidak ada yang di-NaN-kan


# ---------------------------------------------------------------------------
# 2. Aturan (sintetis)
# ---------------------------------------------------------------------------
CFG = dict(C.DEFAULTS)


def _series(prices, start="2022-01-03", code="32", name="Jawa Barat", price_type=1):
    days = pd.bdate_range(start, periods=len(prices))
    return pd.DataFrame({"date": days, "prov_name_raw": name, "price_type": price_type,
                         "price_raw": np.asarray(prices, dtype=float), "price_str": "", "source_file": "x"})


def _pipeline(raw, lebaran=()):
    provinces = pd.DataFrame({"prov_code": [c for c, _ in PROVINCES], "pihps_name": [n for _, n in PROVINCES]})
    m, _ = C.map_provinces(raw, provinces)
    d, _ = C.deduplicate(m)
    w = C.flag_level(d, CFG)
    w = C.flag_series(w, CFG, [pd.Timestamp(x) for x in lebaran])
    return C.flag_carry_forward(w, CFG)


def _wiggle(n, base=38000.0, seed=0):
    rng = np.random.default_rng(seed)
    return base * np.exp(rng.normal(0, 0.01, n).cumsum() * 0.3)


def test_rp19000_spike_flagged_and_nan():
    """Kasus brief §7.1: Rp19.000 di tengah deret ~Rp38.000 pada 1 Feb 2022 -> outlier + NaN."""
    p = _wiggle(60)
    raw = _series(p, start="2022-01-03")
    idx = raw.index[raw["date"] == "2022-02-01"][0]
    raw.loc[idx, "price_raw"] = 19000.0
    w = _pipeline(raw)
    row = w[w["date"] == "2022-02-01"].iloc[0]
    assert row["flag_outlier"] and np.isnan(row["price"])
    assert w["flag_nan_spike"].sum() == 1


def test_persistent_jump_after_lebaran_kept():
    """Lonjakan bertahan setelah Idulfitri 2022 (mis. 5–6 Mei): tidak di-NaN-kan, diberi flag_post_lebaran."""
    p = _wiggle(80)
    raw = _series(p, start="2022-03-01")
    jump = raw["date"] >= "2022-05-05"
    raw.loc[jump, "price_raw"] *= 1.6
    w = _pipeline(raw, lebaran=["2022-05-02"])
    after = w[w["date"].between("2022-05-05", "2022-05-06")]
    assert after["flag_post_lebaran"].all() and after["price"].notna().all()
    assert w["flag_nan_spike"].sum() == 0


def test_spike_inside_lebaran_window_not_nan():
    p = _wiggle(60)
    raw = _series(p, start="2022-04-01")
    i = raw.index[raw["date"] == "2022-05-04"][0]
    raw.loc[i, "price_raw"] *= 2.0
    w = _pipeline(raw, lebaran=["2022-05-02"])
    row = w[w["date"] == "2022-05-04"].iloc[0]
    assert row["flag_spike"] and row["flag_post_lebaran"] and not np.isnan(row["price"])


def test_three_day_deviation_is_not_spike():
    p = _wiggle(60)
    raw = _series(p)
    raw.loc[30:32, "price_raw"] *= 1.8          # 3 hari kerja > max_spike=2
    w = _pipeline(raw)
    assert w["flag_nan_spike"].sum() == 0


def test_level_bounds_flag_only():
    p = _wiggle(40, base=4000.0)                # di bawah Rp5.000
    w = _pipeline(_series(p, code="75", name="Gorontalo", price_type=4))
    assert w["flag_outlier"].all() and w["price"].notna().all()


def test_nonpositive_to_nan():
    p = _wiggle(30)
    p[5] = 0.0
    p[6] = -10.0
    w = _pipeline(_series(p))
    assert w.loc[w["date"].isin(pd.bdate_range("2022-01-03", periods=30)[[5, 6]]), "price"].isna().all()


def test_carry_forward():
    p = np.r_[_wiggle(10), np.full(10, 40000.0), _wiggle(10, seed=1)]
    w = _pipeline(_series(p))
    assert w["flag_carry_forward"].sum() == 10
    p9 = np.r_[_wiggle(10), np.full(9, 40000.0), _wiggle(10, seed=1)]
    assert _pipeline(_series(p9))["flag_carry_forward"].sum() == 0


def test_unknown_name_raises_and_junk_dropped():
    provinces = pd.DataFrame({"prov_code": ["32"], "pihps_name": ["Jawa Barat"]})
    raw = pd.concat([_series([1.0, 2.0]), _series([1.0], name="Dum")])
    out, st = C.map_provinces(raw, provinces)
    assert st["junk_rows"] == 1 and len(out) == 2
    with pytest.raises(SystemExit):
        C.map_provinces(_series([1.0], name="Provinsi Baru"), provinces)


def test_dedup_keeps_last_and_counts_conflict():
    a = _series([40000.0, 41000.0])
    b = a.iloc[[1]].assign(price_raw=42000.0)
    a["prov_code"] = b["prov_code"] = "32"
    out, st = C.deduplicate(pd.concat([a, b]))
    assert len(out) == 2 and st["dup_rows"] == 1 and st["dup_conflicts"] == 1
    assert out.iloc[-1]["price_raw"] == 42000.0


def test_next_workday_friday_and_holiday():
    workdays = pd.DatetimeIndex(["2024-03-08", "2024-03-13", "2024-03-14"])   # Jum, (11–12 libur), Rab, Kam
    got = C.next_workday(pd.Series(pd.to_datetime(["2024-03-08", "2024-03-11", "2024-03-14"])), workdays)
    assert list(got.dt.strftime("%Y-%m-%d")) == ["2024-03-13", "2024-03-13", "2024-03-15"]
