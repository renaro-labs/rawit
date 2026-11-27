"""MLE-H5-03: refit HOLDOUT, penjaga segel di predict, dan replika array inferensi."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renaro.contract import HOLDOUT_START, PROJECT_ROOT
from renaro.data import dummy
from renaro.data.io import load_panel
from renaro.eval.splits import rolling_origin, split_indices
from renaro.frozen import MODELS, REQUIRED, _Arrays, combine_panels, decision_indices, load_config

DATASET = PROJECT_ROOT / "data" / "processed" / "dataset_v1"


def test_gate2_configs_cover_required_models():
    for model in MODELS:
        cfg = load_config(model)
        assert cfg["model"] == model
    assert set(REQUIRED) <= set(MODELS)
    budgets = {(load_config(m)["epochs"], load_config(m)["patience"])
               for m in MODELS if MODELS[m] in ("graph", "wavenet")}
    assert budgets == {(10, 10)}, "anggaran latih model neural harus seragam"


def test_holdout_requires_refit_flag_and_test_stays_sealed():
    days = dummy.business_days()
    with pytest.raises(PermissionError):
        rolling_origin("HOLDOUT", days)
    with pytest.raises(ValueError):
        rolling_origin("O1", days, refit=True)
    split = rolling_origin("HOLDOUT", days, refit=True)
    assert split.test is None
    assert split.train[1] < pd.Timestamp("2026-01-01") <= split.val[0]
    assert split.val[1] < pd.Timestamp(HOLDOUT_START)
    with pytest.raises(PermissionError):
        split_indices(split, days, "test")
    val = split_indices(split, days, "val")
    assert days[val + 20].max() <= pd.Timestamp("2026-05-31")


def test_decision_indices_rule():
    dates = pd.bdate_range("2026-01-01", "2026-03-31")
    ks = decision_indices(dates, "2026-02-01", "2026-03-31", window=5, horizons=(5, 10, 20))
    assert dates[ks].min() >= pd.Timestamp("2026-02-01")
    assert dates[ks + 20].max() <= pd.Timestamp("2026-03-31")
    assert ks[-1] + 20 == len(dates) - 1 or dates[ks[-1] + 21] > pd.Timestamp("2026-03-31")


def _write(dirpath: Path, panel: pd.DataFrame, target: pd.DataFrame, nodes, mask) -> None:
    dirpath.mkdir(parents=True)
    panel.to_parquet(dirpath / "panel.parquet", index=False)
    target.to_parquet(dirpath / "target.parquet", index=False)
    nodes.to_csv(dirpath / "nodes.csv", index=False)
    np.save(dirpath / "bps_mask.npy", mask)


def test_combine_panels_blocks_holdout_without_key(tmp_path, monkeypatch):
    days = dummy.business_days()
    panel = dummy.make_panel(days)
    target = dummy.make_target(panel)
    nodes, mask = dummy.make_nodes(), dummy.make_mask()
    _write(tmp_path / "ctx", panel, target, nodes, mask)
    last = panel["date"].max()
    extra_days = pd.bdate_range("2026-06-02", "2026-06-30")
    def extend(frame):
        tail = frame[frame["date"] == last]
        rows = [tail.assign(date=d) for d in extra_days]
        return pd.concat([frame, *rows], ignore_index=True)
    _write(tmp_path / "new", extend(panel), extend(target), nodes, mask)
    monkeypatch.delenv("RENARO_SEALED_DIR", raising=False)
    with pytest.raises(PermissionError):
        combine_panels(tmp_path / "ctx", tmp_path / "new", pd.Timestamp(HOLDOUT_START))
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    (sealed / "HOLDOUT_UNSEALED").write_text("test", encoding="utf-8")
    monkeypatch.setenv("RENARO_SEALED_DIR", str(sealed))
    both = combine_panels(tmp_path / "ctx", tmp_path / "new", pd.Timestamp(HOLDOUT_START))
    assert both.dates.max() == extra_days.max()
    assert both.split_hash == load_panel(tmp_path / "ctx").split_hash
    # Prefix yang berbeda dari konteks harus ditolak.
    bad = extend(panel)
    bad.loc[0, "price"] = float(bad.loc[0, "price"]) + 1.0 if pd.notna(bad.loc[0, "price"]) else 1.0
    _write(tmp_path / "bad", bad, extend(target), nodes, mask)
    with pytest.raises(ValueError):
        combine_panels(tmp_path / "ctx", tmp_path / "bad", pd.Timestamp(HOLDOUT_START))


@pytest.mark.skipif(not (DATASET / "panel.parquet").is_file(), reason="dataset_v1 belum tersinkron")
def test_inference_arrays_match_window_dataset():
    from renaro.contract import ORIGINS
    from renaro.data.datasets import WindowDataset, WindowSpec

    panel = load_panel(DATASET)
    ds = WindowDataset(panel, "O3", "test", WindowSpec())
    arrays = _Arrays(panel, ORIGINS["O3"]["train"], {"mean": list(ds.normalizer.mean),
                                                     "std": list(ds.normalizer.std)})
    assert np.array_equal(arrays.x, ds.x)
    assert np.array_equal(arrays.climate, ds.climate)
    assert np.array_equal(arrays.y, ds.y)
    assert np.array_equal(arrays.observed, ds.observed)
    ks = decision_indices(panel.dates, "2025-01-01", "2026-05-31", 60, (5, 10, 20))
    assert list(ks) == list(ds.decision_indices)
    with pytest.raises(ValueError):
        _Arrays(panel, ORIGINS["O3"]["train"], {"mean": list(ds.normalizer.mean + 1.0),
                                                "std": list(ds.normalizer.std)})
