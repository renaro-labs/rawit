"""Uji kebocoran dataset v1 (MDE-H3-01 2/2). Berjalan pada dataset beku + input nyata.

Jalankan dulu: python scripts/build_dataset.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renaro.contract import HOLDOUT_START, content_hash, sha256_file
from renaro.data import dataset_v1 as D

DS = Path("data/processed/dataset_v1")
START, END = "2017-07-01", "2026-05-31"

pytestmark = pytest.mark.skipif(
    not (DS / "panel.parquet").exists() or not (DS / "VERSION").exists(),
    reason="dataset v1 belum dibangun: python scripts/build_dataset.py",
)


@pytest.fixture(scope="module")
def panel():
    return pd.read_parquet(DS / "panel.parquet")


@pytest.fixture(scope="module")
def target():
    return pd.read_parquet(DS / "target.parquet")


@pytest.fixture(scope="module")
def version():
    return json.loads((DS / "VERSION").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def inputs(version):
    paths = D.input_paths(Path("data"))
    need = ["prices", "calendar", "provinces", "mask", "coverage", "roni"]
    if version["version"] != "v1-price":
        need.append("climate")
    if not all(Path(paths[k]).exists() for k in need):
        pytest.skip("input data/interim tidak lengkap; uji truncation butuh input asli")
    inp = D.read_inputs(paths, allow_missing_climate=version["version"] == "v1-price")
    return D.truncate_inputs(inp, pd.Timestamp(HOLDOUT_START) - pd.Timedelta(days=1))


# 1. setiap kolom *__avail <= date -------------------------------------------
def test_has_avail_columns(panel):
    av = D.avail_columns(panel)
    assert {"price_lag__avail", "prod_price__avail", "climate__avail", "roni__avail"} <= set(av)


@pytest.mark.parametrize("col", ["price_lag__avail", "prod_price__avail", "climate__avail", "roni__avail"])
def test_avail_not_after_date(panel, col):
    a = pd.to_datetime(panel[col])
    ok = a.isna() | (a <= panel["date"])
    assert ok.all(), f"{col}: {int((~ok).sum())} baris available_at > date"


def test_used_observation_dates_strictly_before_date(panel):
    # harga yang dipakai fitur berasal dari observasi sebelum hari ini (aturan next_workday)
    for c in ("price_obs_date", "prod_price_obs_date"):
        d = pd.to_datetime(panel[c])
        assert (d.isna() | (d < panel["date"])).all()
    # pentad iklim berakhir minimal 2 hari sebelum date (Opsi B)
    p = pd.to_datetime(panel["climate_pentad_date"])
    if p.notna().any():
        assert ((p.isna()) | (panel["date"] - p >= pd.Timedelta(days=2))).all()


# 2. tidak ada tanggal >= holdout --------------------------------------------
def test_no_holdout_dates(panel, target):
    h = pd.Timestamp(HOLDOUT_START)
    assert panel["date"].max() < h and target["date"].max() < h
    for c in D.avail_columns(panel) + ["price_obs_date", "climate_pentad_date", "roni_season_month"]:
        assert (pd.to_datetime(panel[c]).dropna() < h).all(), c


# 3. tidak ada kolom regime/label --------------------------------------------
def test_no_regime_or_label_columns(panel, target):
    for frame in (panel, target):
        bad = [c for c in frame.columns if any(t in c.lower() for t in D.FORBIDDEN_TOKENS)]
        assert not bad, bad


# 4. truncation ----------------------------------------------------------------
def test_truncation_random_cutoffs(panel, inputs):
    cuts = D.truncation_cutoffs(panel, n=3)
    res = D.truncation_check(inputs, START, END, cuts)
    assert all(res.values()), res


def test_truncation_climate_edge(inputs):
    """Potong tepat di akhir pentad: pentad itu baru boleh terpakai 2 hari kemudian."""
    t = pd.Timestamp("2023-08-15")
    res = D.truncation_check(inputs, START, END, [t])
    assert all(res.values()), res


# beku & reproducible -----------------------------------------------------------
def test_sha256sums_match_files():
    lines = (DS / "SHA256SUMS").read_text(encoding="utf-8").split("\n")
    entries = [ln.split("  ", 1) for ln in lines if ln.strip()]
    names = {n for _, n in entries}
    assert {"panel.parquet", "target.parquet", "nodes.csv", "bps_mask.npy", "feature_dict.csv", "VERSION"} <= names
    for sha, name in entries:
        assert sha256_file(DS / name) == sha, name


def test_content_hash_matches_version(panel, target, version):
    assert content_hash(panel, ("date", "prov_code")) == version["content_hash"]["panel"]
    assert content_hash(target, ("date", "prov_code")) == version["content_hash"]["target"]
    mask = np.load(DS / "bps_mask.npy")
    import hashlib
    assert hashlib.sha256(np.ascontiguousarray(mask).tobytes()).hexdigest() == version["content_hash"]["bps_mask"]


def test_rebuild_from_inputs_is_identical(inputs, version):
    p, t, _ = D.build(inputs, START, END)
    assert content_hash(p, ("date", "prov_code")) == version["content_hash"]["panel"]
    assert content_hash(t, ("date", "prov_code")) == version["content_hash"]["target"]


def test_panel_price_is_same_day_target(panel, target):
    """Desain kontrak §2.7: panel.price = observasi hari itu (loader MLE menggeser H+1)."""
    m = panel[["date", "prov_code", "price", "is_observed"]].merge(
        target, on=["date", "prov_code"], suffixes=("", "_t"))
    assert len(m) == len(panel)
    assert (m["is_observed"] == m["is_observed_t"]).all()
    assert m["price"].equals(m["price_t"])
