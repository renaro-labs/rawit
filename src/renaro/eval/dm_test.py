
"""Diebold-Mariano test with HAC and HLN correction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scipy.stats import t as student_t


def diebold_mariano(
    loss_a: np.ndarray,
    loss_b: np.ndarray,
    *,
    horizon: int,
    hac_lag: int | None = None,
    alternative: str = "greater",
) -> dict:

    if horizon < 1:
        raise ValueError("Horizon harus positif")

    if alternative not in (
        "greater", "less", "two-sided"
    ):
        raise ValueError("Alternative tidak valid")

    a = np.asarray(loss_a, dtype=float)
    b = np.asarray(loss_b, dtype=float)

    if a.ndim != 1 or a.shape != b.shape:
        raise ValueError("Loss harus berupa seri 1D yang sejajar")

    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("Loss mengandung nilai non-finite")

    d = a - b
    n = len(d)

    if n <= horizon:
        raise ValueError("Observasi terlalu sedikit")

    lag = horizon - 1 if hac_lag is None else hac_lag

    if not 0 <= lag < n:
        raise ValueError("HAC lag tidak valid")

    mean_d = float(np.mean(d))

    # Identical predictions
    if np.all(d == 0):
        return {
            "stat": 0.0,
            "p": 1.0,
            "n": n,
            "mean_d": 0.0,
        }

    centered = d - mean_d

    # Newey-West HAC variance
    variance = np.dot(centered, centered) / n

    for k in range(1, lag + 1):
        weight = 1.0 - k / (lag + 1)
        gamma = np.dot(
            centered[k:],
            centered[:-k],
        ) / n

        variance += 2.0 * weight * gamma

    if variance <= 0:
        raise ValueError(
            "Varians HAC nol atau negatif; "
            "DM statistic tidak terdefinisi"
        )

    stat = mean_d / np.sqrt(variance / n)

    # Harvey-Leybourne-Newbold correction
    hln = np.sqrt(
        (n + 1 - 2 * horizon
         + horizon * (horizon - 1) / n) / n
    )

    stat *= hln

    # Student-t distribution
    if alternative == "greater":
        p = student_t.sf(stat, df=n - 1)

    elif alternative == "less":
        p = student_t.cdf(stat, df=n - 1)

    else:
        p = 2.0 * student_t.sf(
            abs(stat), df=n - 1
        )

    return {
        "stat": float(stat),
        "p": float(p),
        "n": n,
        "mean_d": mean_d,
    }


def build_daily_loss_series(
    preds: pd.DataFrame,
    model: str,
    fold: str,
    h: int,
) -> pd.Series:

    subset = preds.loc[
        preds["model"].eq(model)
        & preds["fold"].eq(fold)
        & preds["h"].eq(h)
        & preds["y_mask"].eq(True)
    ].copy()

    if "seed" in subset.columns:
        if subset["seed"].nunique() > 1:
            raise ValueError(
                "Pilih satu seed sebelum DM test"
            )

    subset = subset.loc[
        np.isfinite(subset["y_true"])
        & np.isfinite(subset["y_pred"])
    ]

    subset["date"] = pd.to_datetime(subset["date"])

    subset["loss"] = np.abs(
        subset["y_true"] - subset["y_pred"]
    )

    return (
        subset.groupby("date")["loss"]
        .mean()
        .sort_index()
    )
