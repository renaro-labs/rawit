import pandas as pd
import pytest

from renaro.eval.regimes import build_split, filter


def _panel():
    return pd.DataFrame({
        "date": pd.to_datetime(["2022-07-01", "2022-07-04", "2022-07-05"] * 2),
        "prov_code": ["11", "11", "11", "12", "12", "12"],
        "is_observed": [True, False, True, True, True, False],
    })


def _regimes():
    dates = pd.to_datetime(["2022-07-01", "2022-07-04", "2022-07-05"] * 2)
    return pd.DataFrame({
        "date": dates,
        "prov_code": ["11", "11", "11", "12", "12", "12"],
        "enso_phase": ["neutral"] * 3 + ["la_nina"] * 3,
        "is_dry": [False, True, True, False, False, False],
        "is_extreme_rain": [False, False, True, False, False, False],
        "is_normal": [True, False, False, False, True, True],
        "label_primary": ["normal", "dry", "extreme_wet", "normal", "la_nina", "la_nina"],
        "episode_id": [None, "dry_1", "extreme_1", None, "lanina_1", "lanina_1"],
    })


def test_build_split_columns_and_observed_mask():
    split = build_split(_panel(), _regimes(), "O1", "val",
                        start="2022-07-01", end="2022-07-05")
    assert list(split.columns) == [
        "date", "prov_code", "is_target_observed", "enso_phase", "is_dry",
        "is_extreme_rain", "is_normal", "label_primary", "episode_id",
    ]
    assert split["is_target_observed"].tolist() == [True, True, False, True, True, False]
    assert split["label_primary"].tolist() == ["normal", "normal", "dry", "la_nina", "extreme_wet", "la_nina"]


def test_filter_regime_and_observed(tmp_path):
    split = build_split(_panel(), _regimes(), "O1", "val",
                        start="2022-07-01", end="2022-07-05")
    split.to_parquet(tmp_path / "O1_val.parquet", index=False)
    preds = pd.DataFrame({
        "date": pd.to_datetime(["2022-07-01", "2022-07-04", "2022-07-05"]),
        "prov_code": ["11", "11", "11"],
        "yhat": [1.0, 2.0, 3.0],
    })
    out = filter(preds, "O1", "val", "dry", splits_dir=tmp_path, observed_only=False)
    assert len(out) == 1
    assert out.iloc[0]["yhat"] == 2.0
    assert out.iloc[0]["is_target_observed"] == False
    # observed_only drops the only dry row (it is unobserved)
    out2 = filter(preds, "O1", "val", "dry", splits_dir=tmp_path, observed_only=True)
    assert out2.empty


def test_filter_unknown_regime(tmp_path):
    with pytest.raises(ValueError):
        filter(pd.DataFrame({"date": [], "prov_code": []}), "O1", "val", "nope", splits_dir=tmp_path)
