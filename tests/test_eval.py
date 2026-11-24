
import numpy as np
import pandas as pd
import pytest

from renaro.eval.metrics import (
    mae,
    rmse,
    smape,
    evaluate,
)

from renaro.eval.dm_test import diebold_mariano


def test_mae():
    assert mae([10, 20], [12, 18]) == 2.0


def test_rmse():
    assert rmse([10, 20], [12, 18]) == 2.0


def test_smape():
    assert smape([100], [100]) == 0.0


def test_smape_zero():
    assert smape([0], [0]) == 0.0


def test_metrics_ignore_nan():
    assert mae(
        [10, np.nan],
        [12, 100],
    ) == 2.0


def test_evaluate_mask():
    preds = pd.DataFrame({
        "model": ["lgbm", "lgbm"],
        "fold": ["O1", "O1"],
        "h": [10, 10],
        "y_true": [100, 100],
        "y_pred": [110, 1000],
        "y_mask": [True, False],
    })

    result = evaluate(preds)

    assert result.iloc[0]["mae"] == 10.0
    assert result.iloc[0]["n"] == 1


def test_dm_identical():
    loss = np.arange(100, dtype=float)

    result = diebold_mariano(
        loss,
        loss,
        horizon=10,
    )

    assert result["stat"] == 0.0
    assert result["p"] == 1.0


def test_dm_better_model():
    rng = np.random.default_rng(42)

    baseline = rng.uniform(80, 120, 500)
    model = rng.uniform(10, 30, 500)

    result = diebold_mariano(
        baseline,
        model,
        horizon=10,
        alternative="greater",
    )

    assert result["stat"] > 0
    assert result["p"] < 0.05


def test_dm_two_sided():
    rng = np.random.default_rng(42)

    a = rng.uniform(80, 120, 500)
    b = rng.uniform(10, 30, 500)

    result = diebold_mariano(
        a,
        b,
        horizon=10,
        alternative="two-sided",
    )

    assert result["p"] < 0.05


from renaro.eval.splits import (
    Split,
    rolling_origin,
    assert_no_overlap,
    split_indices,
)


def test_rolling_origins():

    dates = pd.bdate_range(
        "2017-07-01",
        "2026-05-31",
    )

    for origin in ("O1", "O2", "O3"):

        split = rolling_origin(origin, dates)

        assert_no_overlap(split)

        assert split.train[1] < split.val[0]
        assert split.val[1] < split.test[0]


def test_split_overlap():

    split = Split(
        origin="O1",
        train=(
            pd.Timestamp("2020-01-01"),
            pd.Timestamp("2022-08-01"),
        ),
        val=(
            pd.Timestamp("2022-07-01"),
            pd.Timestamp("2022-12-01"),
        ),
        test=(
            pd.Timestamp("2023-01-02"),
            pd.Timestamp("2023-12-29"),
        ),
    )

    with pytest.raises(ValueError):
        assert_no_overlap(split)


def test_holdout_sealed():

    dates = pd.bdate_range(
        "2017-07-01",
        "2026-05-31",
    )

    with pytest.raises(PermissionError):
        rolling_origin("HOLDOUT", dates)


def test_split_indices():

    dates = pd.bdate_range(
        "2017-07-01",
        "2026-05-31",
    )

    split = rolling_origin("O1", dates)

    train = split_indices(split, dates, "train")
    val = split_indices(split, dates, "val")
    test = split_indices(split, dates, "test")

    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0

    assert len(np.intersect1d(train, val)) == 0
    assert len(np.intersect1d(val, test)) == 0

    assert dates[train[-1] + 20] <= pd.Timestamp(
        "2022-06-30"
    )

    assert dates[val[-1] + 20] <= pd.Timestamp(
        "2022-12-31"
    )

    assert dates[test[-1] + 20] <= pd.Timestamp(
        "2023-12-31"
    )


def test_embargo_o1():

    dates = pd.bdate_range(
        "2017-07-01",
        "2026-05-31",
    )

    split = rolling_origin("O1", dates)

    assert split.train[1] == pd.Timestamp(
        "2022-06-02"
    )

    assert split.val[1] == pd.Timestamp(
        "2022-12-02"
    )

    assert split.embargo_workdays == 20
