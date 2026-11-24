
"""Standard evaluation metrics for RENARO."""

from __future__ import annotations

import numpy as np
import pandas as pd


METRIC_NAMES = ("mae", "rmse", "smape")


def _valid_pairs(y, yhat):
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)

    if y.shape != yhat.shape:
        raise ValueError("Shape y dan yhat berbeda")

    mask = np.isfinite(y) & np.isfinite(yhat)

    return y[mask], yhat[mask]


def mae(y: np.ndarray, yhat: np.ndarray) -> float:
    y, yhat = _valid_pairs(y, yhat)

    if len(y) == 0:
        return float("nan")

    return float(np.mean(np.abs(y - yhat)))


def rmse(y: np.ndarray, yhat: np.ndarray) -> float:
    y, yhat = _valid_pairs(y, yhat)

    if len(y) == 0:
        return float("nan")

    return float(np.sqrt(np.mean((y - yhat) ** 2)))


def smape(y: np.ndarray, yhat: np.ndarray) -> float:
    y, yhat = _valid_pairs(y, yhat)

    if len(y) == 0:
        return float("nan")

    denominator = np.abs(y) + np.abs(yhat)

    errors = np.divide(
        2.0 * np.abs(y - yhat),
        denominator,
        out=np.zeros_like(denominator),
        where=denominator != 0,
    )

    return float(100.0 * np.mean(errors))


def evaluate(
    preds: pd.DataFrame,
    group_cols: tuple[str, ...] = ("model", "fold", "h"),
) -> pd.DataFrame:

    required = {
        *group_cols,
        "y_true",
        "y_pred",
        "y_mask",
    }

    missing = required - set(preds.columns)

    if missing:
        raise ValueError(f"Kolom tidak tersedia: {missing}")

    valid = preds.loc[
        preds["y_mask"].eq(True)
        & np.isfinite(preds["y_true"])
        & np.isfinite(preds["y_pred"])
    ].copy()

    results = []

    for keys, group in valid.groupby(
        list(group_cols), dropna=False
    ):
        if not isinstance(keys, tuple):
            keys = (keys,)

        y = group["y_true"].to_numpy()
        yhat = group["y_pred"].to_numpy()

        row = dict(zip(group_cols, keys))

        row.update({
            "mae": mae(y, yhat),
            "rmse": rmse(y, yhat),
            "smape": smape(y, yhat),
            "n": len(y),
        })

        results.append(row)

    return pd.DataFrame(
        results,
        columns=[*group_cols, *METRIC_NAMES, "n"],
    )



def per_regime(
    preds: pd.DataFrame,
    eval_splits: pd.DataFrame,
) -> pd.DataFrame:

    keys = ["date", "prov_code"]

    preds = preds.copy()
    labels = eval_splits.copy()

    for frame in (preds, labels):
        frame["date"] = pd.to_datetime(frame["date"])
        frame["prov_code"] = (
            frame["prov_code"].astype(str).str.zfill(2)
        )

    merged = preds.merge(
        labels[keys + ["label_primary"]],
        on=keys,
        how="left",
        validate="many_to_one",
    )

    if merged["label_primary"].isna().any():
        raise ValueError("Terdapat regime label yang hilang")

    merged = merged.rename(
        columns={"label_primary": "regime"}
    )

    groups = ["model", "fold", "h", "regime"]

    if "seed" in merged.columns:
        groups.append("seed")

    return evaluate(merged, tuple(groups))



def worst_regime_error(
    by_regime: pd.DataFrame,
) -> pd.DataFrame:

    groups = ["model", "fold", "h"]

    if "seed" in by_regime.columns:
        groups.append("seed")

    return (
        by_regime.groupby(groups, as_index=False)["mae"]
        .max()
        .rename(columns={"mae": "worst_regime_error"})
    )


def ood_delta(
    by_regime: pd.DataFrame,
    normal: str = "normal",
) -> pd.DataFrame:

    keys = ["model", "fold", "h"]

    if "seed" in by_regime.columns:
        keys.append("seed")

    reference = by_regime.loc[
        by_regime["regime"].eq(normal),
        keys + ["mae"],
    ].rename(columns={"mae": "normal_mae"})

    result = by_regime.loc[
        ~by_regime["regime"].eq(normal)
    ].merge(
        reference,
        on=keys,
        how="left",
        validate="many_to_one",
    )

    result["ood_delta"] = (
        result["mae"] - result["normal_mae"]
    )

    result["ood_ratio"] = (
        result["mae"]
        / result["normal_mae"].replace(0, np.nan)
    )

    return result


def seed_stability(
    by_seed: pd.DataFrame,
) -> pd.DataFrame:

    keys = ["model", "fold", "h"]

    if "regime" in by_seed.columns:
        keys.append("regime")

    if by_seed.duplicated(keys + ["seed"]).any():
        raise ValueError("Duplicate seed results")

    return (
        by_seed.groupby(keys, as_index=False)
        .agg(
            mean_mae=("mae", "mean"),
            std_mae=("mae", "std"),
            n_seeds=("seed", "nunique"),
        )
    )
