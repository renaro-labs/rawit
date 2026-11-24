
"""Naive baseline models for RAWIT."""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaro.contract import HORIZONS
from renaro.data.io import Panel
from renaro.eval.splits import (
    rolling_origin,
    split_indices,
)


def price_matrix(data: Panel) -> pd.DataFrame:
    """Harga observasi dalam format date x province."""

    frame = data.panel.copy()

    price = pd.to_numeric(
        frame["price"], errors="coerce"
    )

    valid = (
        frame["is_observed"].eq(True)
        & np.isfinite(price)
        & price.gt(0)
    )

    frame["price"] = price.where(valid)

    return (
        frame.pivot(
            index="date",
            columns="prov_code",
            values="price",
        )
        .reindex(
            index=data.dates,
            columns=data.node_codes,
        )
    )


def asof_prices(data: Panel) -> pd.DataFrame:
    """Harga terakhir yang diketahui pada decision date."""

    return price_matrix(data).shift(1).ffill()


def prediction_frame(
    data: Panel,
    k: int,
    h: int,
    prediction: np.ndarray,
    *,
    model: str,
    origin: str,
    seed: int,
    part: str,
) -> pd.DataFrame:

    y, y_mask = data.target_at(k, h)

    included = data.nodes["include"].to_numpy(
        dtype=bool
    )

    y_mask = y_mask & included

    prediction = np.asarray(
        prediction, dtype=float
    )

    if prediction.shape != y.shape:
        raise ValueError("Shape prediksi tidak valid")

    return pd.DataFrame({
        "model": model,
        "fold": origin,
        "seed": seed,
        "date": data.dates[k],
        "prov_code": data.node_codes,
        "h": h,
        "y_true": np.where(y_mask, y, np.nan),
        "y_pred": prediction,
        "y_mask": y_mask,
        "part": part,
        "target_date": data.dates[k + h - 1],
    })


def predict_naive_last(
    data: Panel,
    k: int,
    h: int,
    prices: pd.DataFrame | None = None,
) -> np.ndarray:

    if prices is None:
        prices = asof_prices(data)

    return prices.iloc[k].to_numpy(dtype=float)


def predict_seasonal_naive(
    data: Panel,
    k: int,
    h: int,
    lag_days: int = 364,
    prices: pd.DataFrame | None = None,
) -> np.ndarray:

    if prices is None:
        prices = price_matrix(data)

    target_date = data.dates[k + h - 1]

    seasonal_date = (
        target_date
        - pd.Timedelta(days=lag_days)
    )

    # Starter code: hari kerja pada/sesudah
    # tanggal target dikurangi 364 hari.
    idx = data.dates.searchsorted(
        seasonal_date, side="left"
    )

    # Jangan menggunakan observasi masa depan.
    if (
        seasonal_date < data.dates[0]
        or idx >= k
        or idx >= len(data.dates)
    ):
        return np.full(
            len(data.node_codes), np.nan
        )

    return prices.iloc[idx].to_numpy(dtype=float)


def run_naive(
    data: Panel,
    cfg: dict,
    origin: str,
    seed: int,
    *,
    name: str,
) -> pd.DataFrame:

    split = rolling_origin(origin, data.dates)

    raw_prices = price_matrix(data)
    last_prices = raw_prices.shift(1).ffill()

    results = []

    for part in ("val", "test"):

        indices = split_indices(
            split,
            data.dates,
            part,
            horizon=max(HORIZONS),
        )

        for h in HORIZONS:

            for k in indices:

                if name == "naive_last":

                    pred = predict_naive_last(
                        data, k, h, last_prices
                    )

                elif name == "seasonal_naive":

                    pred = predict_seasonal_naive(
                        data,
                        k,
                        h,
                        prices=raw_prices,
                    )

                else:
                    raise ValueError(
                        f"Unknown baseline: {name}"
                    )

                results.append(
                    prediction_frame(
                        data,
                        k,
                        h,
                        pred,
                        model=name,
                        origin=origin,
                        seed=seed,
                        part=part,
                    )
                )

    if not results:
        raise ValueError("Tidak ada hasil prediksi")

    return pd.concat(
        results, ignore_index=True
    )


def run_naive_last(
    panel: Panel,
    cfg: dict,
    origin: str,
    seed: int,
) -> pd.DataFrame:

    return run_naive(
        panel,
        cfg,
        origin,
        seed,
        name="naive_last",
    )


def run_seasonal_naive(
    panel: Panel,
    cfg: dict,
    origin: str,
    seed: int,
) -> pd.DataFrame:

    return run_naive(
        panel,
        cfg,
        origin,
        seed,
        name="seasonal_naive",
    )
