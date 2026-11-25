"""Tabular feature builder for RAWIT RQ0 (MLE-H3-02 & Protocol v1 §8).

Implements feature variants:
  (a) Own price lags (1, 2, 3, 5, 10, 20 workdays), 5/20-day log returns,
      20/60-day rolling mean & std of log price, producer price lag 1,
      and calendar features (days_to_lebaran, is_ramadan, dow, month,
      is_holiday, is_cuti_bersama).
  (b) Variant (a) + local province climate features: rain_pentad_anom at
      pentad lags 0..8, dry_spell_days, extreme_5d (current and 4-pentad
      rolling sum), rain_30d_anom, roni, and roni_delta.
  (c) Variant (b) + supplier-origin climate features weighted by the directed
      BPS Poldis 2022 trade mask (`bps_mask.npy`, where A[i, j] = 1 if j -> i,
      row = destination i, col = origin j). For provinces with zero in-degree
      in BPS 2022 (Papua `94`), falls back to the 3 nearest provinces by
      centroid (Papua Barat `91`, Maluku `81`, Maluku Utara `82`) per Protocol
      v1 §8 & `reports/qa/bps_mask.md`. Aggregates origin `rain_pentad_anom`
      at pentad lags 1..8 plus origin `dry_spell_days`, `extreme_5d_sum4`,
      and `rain_30d_anom`.

All features strictly satisfy `available_at <= date` (0 leakage).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaro.baselines.naive import asof_prices
from renaro.contract import N_NODES, PENTAD_LAGS, PROV_CODES
from renaro.data.io import Panel

PRICE_LAGS: tuple[int, ...] = (1, 2, 3, 5, 10, 20)
RETURN_PERIODS: tuple[int, ...] = (5, 20)
ROLLING_WINDOWS: tuple[int, ...] = (20, 60)

CALENDAR_FEATURES: tuple[str, ...] = (
    "days_to_lebaran",
    "is_ramadan",
    "dow",
    "month",
    "is_holiday",
    "is_cuti_bersama",
)

VALID_VARIANTS: tuple[str, ...] = ("a", "b", "c")


def build_origin_weight_matrix(
    mask: np.ndarray,
    nodes: pd.DataFrame | None = None,
    *,
    k_fallback: int = 3,
) -> np.ndarray:
    """Return row-normalized origin weight matrix W [N, N] where W[i, j] > 0 means j -> i.

    Convention in `bps_mask.npy` (`MDE-H2-03`):
      mask[i, j] == 1 iff province j supplies destination province i.
    If row i has zero incoming BPS edges (Papua `94`), falls back to the
    `k_fallback` nearest provinces by Haversine/Euclidean centroid distance
    from `nodes.csv` (`lat`, `lon`), or `91, 81, 82` for Papua (`94`).
    """
    arr = np.asarray(mask, dtype=np.float64)
    if arr.shape != (N_NODES, N_NODES):
        raise ValueError(f"bps_mask shape {arr.shape} != {(N_NODES, N_NODES)}")

    weights = arr.copy()
    np.fill_diagonal(weights, 0.0)

    row_sums = weights.sum(axis=1)
    zero_rows = np.where(row_sums <= 0.0)[0]

    if len(zero_rows) > 0:
        if (
            nodes is not None
            and {"lat", "lon"}.issubset(nodes.columns)
            and len(nodes) == N_NODES
        ):
            lat = pd.to_numeric(nodes["lat"], errors="coerce").to_numpy(dtype=float)
            lon = pd.to_numeric(nodes["lon"], errors="coerce").to_numpy(dtype=float)
            for i in zero_rows:
                d2 = (lat - lat[i]) ** 2 + (lon - lon[i]) ** 2
                d2[i] = np.inf
                nearest = np.argsort(d2)[:k_fallback]
                weights[i, nearest] = 1.0
        else:
            # Explicit fallback for Papua (94, idx 33): Papua Barat (91), Maluku (81), Maluku Utara (82)
            code_to_idx = {code: idx for idx, code in enumerate(PROV_CODES)}
            fallback_indices = [
                code_to_idx[c] for c in ("91", "81", "82") if c in code_to_idx
            ]
            for i in zero_rows:
                for j in fallback_indices:
                    if j != i:
                        weights[i, j] = 1.0

    row_sums = weights.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums > 0.0, row_sums, 1.0)
    return weights / row_sums


def _build_pentad_climate_table(panel_df: pd.DataFrame) -> pd.DataFrame:
    """Build per-(prov_code, climate_pentad_date) lagged pentad features.

    Because `climate_pentad_date` in `dataset_v1/panel.parquet` was joined via
    `merge_asof(date <- climate__avail, backward)`, every pentad up to
    `climate_pentad_date` at row `date` has `available_at <= date`. Shifting
    along the province's unique pentad sequence by `0..8` pentads is 100% causal.
    """
    pentad_col = (
        "climate_pentad_date"
        if "climate_pentad_date" in panel_df.columns
        else "date"
    )

    base_cols = ["prov_code", pentad_col]
    val_cols = [
        c
        for c in (
            "rain_pentad_anom",
            "rain_30d_anom",
            "dry_spell_days",
            "extreme_5d",
            "rain_pentad_mm",
        )
        if c in panel_df.columns
    ]

    pentads = (
        panel_df[base_cols + val_cols]
        .drop_duplicates(subset=["prov_code", pentad_col], keep="first")
        .sort_values(["prov_code", pentad_col])
        .reset_index(drop=True)
    )

    grp_anom = pentads.groupby("prov_code", sort=False)["rain_pentad_anom"]
    for lag in PENTAD_LAGS:
        pentads[f"rain_pentad_anom_lag{lag}"] = grp_anom.shift(lag)

    if "extreme_5d" in pentads.columns:
        grp_ext = pentads.groupby("prov_code", sort=False)["extreme_5d"]
        pentads["extreme_5d_sum4"] = grp_ext.transform(
            lambda x: x.rolling(4, min_periods=1).sum()
        )

    keep_cols = (
        ["prov_code", pentad_col]
        + [f"rain_pentad_anom_lag{lag}" for lag in PENTAD_LAGS]
        + (["extreme_5d_sum4"] if "extreme_5d_sum4" in pentads.columns else [])
    )
    return pentads[keep_cols]


def build_tabular_features(
    data: Panel,
    *,
    variant: str = "a",
) -> pd.DataFrame:
    """Construct causal tabular features for variant (a), (b), or (c)."""
    variant = str(variant).strip().lower()
    if variant not in VALID_VARIANTS:
        raise ValueError(
            f"Varian fitur tidak dikenal: {variant!r} (pilih dari {VALID_VARIANTS})"
        )

    frame = data.panel.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["prov_code"] = frame["prov_code"].astype(str)

    # Verify causality of all *__avail columns if present in dataset_v1
    for avail_col in (
        "price_lag__avail",
        "prod_price__avail",
        "climate__avail",
        "roni__avail",
    ):
        if avail_col in frame.columns:
            avail_ts = pd.to_datetime(frame[avail_col])
            valid_avail = avail_ts.notna()
            if (avail_ts[valid_avail] > frame.loc[valid_avail, "date"]).any():
                raise ValueError(
                    f"Pelanggaran kausalitas available_at > date pada {avail_col}"
                )

    frame = frame.sort_values(["prov_code", "date"]).reset_index(drop=True)

    # Gunakan harga as-of (diketahui pada decision date t), bukan harga observasi t.
    known = (
        asof_prices(data)
        .rename_axis(index="date", columns="prov_code")
        .stack()
        .rename("price_t")
        .reset_index()
    )

    frame = frame.merge(
        known,
        on=["date", "prov_code"],
        how="left",
        validate="one_to_one",
    )

    frame["log_price_t"] = np.log(frame["price_t"].where(frame["price_t"] > 0))

    features: list[str] = [
        "date",
        "prov_code",
        "price_t",
        "log_price_t",
    ]

    grouped = frame.groupby("prov_code", sort=False)["log_price_t"]

    # (a) Lag log-harga sendiri (1, 2, 3, 5, 10, 20 hari kerja)
    for lag in PRICE_LAGS:
        name = f"log_price_lag_{lag}"
        frame[name] = grouped.shift(lag - 1)
        features.append(name)

    # Return 5 dan 20 hari kerja
    for period in RETURN_PERIODS:
        name = f"log_return_{period}"
        frame[name] = frame["log_price_t"] - grouped.shift(period)
        features.append(name)

    # Rata-rata dan std bergulir 20 dan 60 hari kerja
    for window in ROLLING_WINDOWS:
        mean_name = f"rolling_mean_{window}"
        std_name = f"rolling_std_{window}"
        frame[mean_name] = grouped.transform(
            lambda x: x.rolling(window, min_periods=window).mean()
        )
        frame[std_name] = grouped.transform(
            lambda x: x.rolling(window, min_periods=window).std()
        )
        features.extend([mean_name, std_name])

    # Kalender
    for col in CALENDAR_FEATURES:
        if col not in frame.columns:
            frame[col] = 0.0
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
        features.append(col)

    if variant in ("b", "c"):
        if "roni" in frame.columns and "roni_delta" not in frame.columns:
            frame["roni_delta"] = (
                frame.groupby("prov_code", sort=False)["roni"]
                .diff()
                .fillna(0.0)
            )
        pentad_col = (
            "climate_pentad_date"
            if "climate_pentad_date" in frame.columns
            else "date"
        )
        pentad_table = _build_pentad_climate_table(frame)
        frame = frame.merge(
            pentad_table,
            on=["prov_code", pentad_col],
            how="left",
            validate="many_to_one",
        )

        # (b) Iklim provinsi sendiri: rain_pentad_anom jeda pentad 0..8,
        # dry_spell_days, extreme_5d (4 pentad terakhir), rain_30d_anom, roni
        local_climate_cols: list[str] = []
        for lag in PENTAD_LAGS:
            col = f"rain_pentad_anom_lag{lag}"
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
            local_climate_cols.append(col)

        for col in (
            "dry_spell_days",
            "extreme_5d",
            "extreme_5d_sum4",
            "rain_30d_anom",
            "roni",
            "roni_delta",
        ):
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
                local_climate_cols.append(col)

        features.extend(local_climate_cols)

    if variant == "c":
        # (c) Iklim wilayah asal pemasok memakai mask BPS (A[i, j] = 1 bila j -> i)
        weights = build_origin_weight_matrix(data.mask, data.nodes)
        prov_order = list(PROV_CODES)

        origin_source_cols = [
            f"rain_pentad_anom_lag{lag}" for lag in range(1, 9)
        ] + [
            c
            for c in ("dry_spell_days", "extreme_5d_sum4", "rain_30d_anom")
            if c in frame.columns
        ]

        pivoted_frames: list[pd.DataFrame] = []
        origin_feature_names: list[str] = []

        for col in origin_source_cols:
            mat = (
                frame.pivot(index="date", columns="prov_code", values=col)
                .reindex(index=data.dates, columns=prov_order)
            )
            arr = mat.to_numpy(dtype=np.float64)
            valid = np.isfinite(arr)
            filled = np.where(valid, arr, 0.0)
            # num[t, i] = sum_j W[i, j] * X[t, j]
            num = filled @ weights.T
            den = valid.astype(np.float64) @ weights.T
            with np.errstate(invalid="ignore", divide="ignore"):
                agg = np.where(den > 0.0, num / den, np.nan)

            out_col = f"origin_{col}"
            origin_feature_names.append(out_col)
            s = (
                pd.DataFrame(agg, index=data.dates, columns=prov_order)
                .rename_axis(index="date", columns="prov_code")
                .stack(future_stack=True)
                .rename(out_col)
            )
            pivoted_frames.append(s)

        if pivoted_frames:
            orig_df = pd.concat(pivoted_frames, axis=1).reset_index()
            frame = frame.merge(
                orig_df,
                on=["date", "prov_code"],
                how="left",
                validate="one_to_one",
            )
            features.extend(origin_feature_names)

    result = frame[features].copy()
    result["prov_code"] = pd.Categorical(
        result["prov_code"],
        categories=list(PROV_CODES),
    )

    return result.sort_values(["date", "prov_code"]).reset_index(drop=True)
