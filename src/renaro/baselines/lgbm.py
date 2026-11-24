
"""Global direct LightGBM baseline for RAWIT."""

from __future__ import annotations

import numpy as np
import pandas as pd

import lightgbm as lgb

from renaro.contract import HORIZONS, PROV_CODES
from renaro.data.io import Panel
from renaro.eval.splits import (
    rolling_origin,
    split_indices,
)
from renaro.baselines.naive import asof_prices


LGBM_PARAMS = {
    "num_leaves": 31,
    "learning_rate": 0.05,
    "n_estimators": 2000,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "min_data_in_leaf": 50,
}

EARLY_STOPPING = 100

PRICE_LAGS = (1, 2, 3, 5, 10, 20)

CALENDAR_FEATURES = (
    "days_to_lebaran",
    "is_ramadan",
    "dow",
    "month",
    "is_holiday",
    "is_cuti_bersama",
)


def build_tabular_features(
    data: Panel,
    *,
    variant: str = "a",
) -> pd.DataFrame:

    if variant != "a":
        raise NotImplementedError(
            "Varian b/c belum diimplementasikan"
        )

    frame = data.panel.copy()

    frame = frame.sort_values(
        ["prov_code", "date"]
    ).reset_index(drop=True)

    # Gunakan harga as-of, bukan harga observasi t.
    known = (
        asof_prices(data)
        .rename_axis(
            index="date",
            columns="prov_code",
        )
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

    frame["log_price_t"] = np.log(
        frame["price_t"].where(
            frame["price_t"] > 0
        )
    )

    # Bentuk fitur dengan whitelist.
    features = [
        "date",
        "prov_code",
        "price_t",
        "log_price_t",
    ]

    grouped = frame.groupby(
        "prov_code", sort=False
    )["log_price_t"]

    for lag in PRICE_LAGS:

        name = f"log_price_lag_{lag}"

        # lag 1 = harga yang diketahui pada t.
        frame[name] = grouped.shift(lag - 1)

        features.append(name)

    for period in (5, 20):

        name = f"log_return_{period}"

        frame[name] = (
            frame["log_price_t"]
            - grouped.shift(period)
        )

        features.append(name)

    for window in (20, 60):

        mean_name = f"rolling_mean_{window}"
        std_name = f"rolling_std_{window}"

        frame[mean_name] = grouped.transform(
            lambda x: x.rolling(
                window, min_periods=window
            ).mean()
        )

        frame[std_name] = grouped.transform(
            lambda x: x.rolling(
                window, min_periods=window
            ).std()
        )

        features.extend(
            [mean_name, std_name]
        )

    for col in CALENDAR_FEATURES:

        if col in frame.columns:

            frame[col] = pd.to_numeric(
                frame[col], errors="coerce"
            )

            features.append(col)

    result = frame[features].copy()

    result["prov_code"] = pd.Categorical(
        result["prov_code"],
        categories=list(PROV_CODES),
    )

    return result.sort_values(
        ["date", "prov_code"]
    ).reset_index(drop=True)


def make_supervised(
    data: Panel,
    features: pd.DataFrame,
    indices: np.ndarray,
    horizon: int,
) -> pd.DataFrame:

    targets = []

    included = data.nodes["include"].to_numpy(
        dtype=bool
    )

    for k in indices:

        y, y_mask = data.target_at(
            int(k), horizon
        )

        mask = y_mask & included

        targets.append(pd.DataFrame({
            "date": data.dates[k],
            "prov_code": data.node_codes,
            "y_true": np.where(mask, y, np.nan),
            "y_mask": mask,
            "target_date": data.dates[
                k + horizon - 1
            ],
        }))

    target = pd.concat(
        targets, ignore_index=True
    )

    result = features.merge(
        target,
        on=["date", "prov_code"],
        how="inner",
        validate="one_to_one",
    )

    result["prov_code"] = pd.Categorical(
        result["prov_code"],
        categories=list(PROV_CODES),
    )

    result["y_return"] = (
        np.log(result["y_true"])
        - result["log_price_t"]
    )

    return result


def get_feature_columns(
    frame: pd.DataFrame,
) -> list[str]:

    excluded = {
        "date",
        "target_date",
        "price_t",
        "y_true",
        "y_mask",
        "y_return",
    }

    return [
        col for col in frame.columns
        if col not in excluded
    ]


def predict_level(
    model,
    frame: pd.DataFrame,
    feature_columns: list[str],
) -> np.ndarray:

    result = np.full(
        len(frame), np.nan, dtype=float
    )

    valid = np.isfinite(
        frame["log_price_t"]
    )

    if valid.any():

        pred_return = model.predict(
            frame.loc[valid, feature_columns]
        )

        result[valid.to_numpy()] = np.exp(
            frame.loc[
                valid, "log_price_t"
            ].to_numpy()
            + pred_return
        )

    return result


def fit_lgbm_direct(
    train: pd.DataFrame,
    val: pd.DataFrame,
    *,
    horizon: int,
    seed: int,
    feature_variant: str = "a",
) -> tuple[object, pd.DataFrame]:

    if feature_variant != "a":
        raise NotImplementedError(
            "Varian belum tersedia"
        )

    feature_columns = get_feature_columns(
        train
    )

    valid_train = (
        train["y_mask"].eq(True)
        & np.isfinite(train["y_return"])
    )

    valid_val = (
        val["y_mask"].eq(True)
        & np.isfinite(val["y_return"])
    )

    if not valid_train.any():
        raise ValueError("Training data kosong")

    if not valid_val.any():
        raise ValueError("Validation data kosong")

    model = lgb.LGBMRegressor(
        **LGBM_PARAMS,
        objective="regression_l1",
        random_state=seed,
        n_jobs=4,
        verbosity=-1,
        deterministic=True,
        force_col_wise=True,
    )

    # Early stopping memakai MAE pada level Rp/kg.
    val_log_price = val.loc[
        valid_val, "log_price_t"
    ].to_numpy()

    def level_mae(y_true, y_pred):

        actual = np.exp(
            val_log_price + y_true
        )

        prediction = np.exp(
            val_log_price + y_pred
        )

        return (
            "level_mae",
            float(
                np.mean(
                    np.abs(actual - prediction)
                )
            ),
            False,
        )

    model.set_params(metric="None")

    model.fit(
        train.loc[
            valid_train, feature_columns
        ],
        train.loc[
            valid_train, "y_return"
        ],
        eval_set=[(
            val.loc[
                valid_val, feature_columns
            ],
            val.loc[
                valid_val, "y_return"
            ],
        )],
        eval_metric=level_mae,
        categorical_feature=["prov_code"],
        callbacks=[
            lgb.early_stopping(
                EARLY_STOPPING,
                first_metric_only=True,
                verbose=False,
            ),
            lgb.log_evaluation(period=100),
        ],
    )

    predictions = val[
        [
            "date",
            "prov_code",
            "target_date",
            "y_true",
            "y_mask",
        ]
    ].copy()

    predictions["y_pred"] = predict_level(
        model, val, feature_columns
    )

    return model, predictions


def run_lgbm(
    panel: Panel,
    cfg: dict,
    origin: str,
    seed: int,
) -> pd.DataFrame:

    variant = cfg.get(
        "feature_variant", "a"
    )

    split = rolling_origin(
        origin, panel.dates
    )

    features = build_tabular_features(
        panel, variant=variant
    )

    indices = {
        part: split_indices(
            split,
            panel.dates,
            part,
            horizon=max(HORIZONS),
        )
        for part in ("train", "val", "test")
    }

    results = []

    for h in HORIZONS:

        print(f"\nTraining LightGBM h={h}")

        train = make_supervised(
            panel, features,
            indices["train"], h,
        )

        val = make_supervised(
            panel, features,
            indices["val"], h,
        )

        test = make_supervised(
            panel, features,
            indices["test"], h,
        )

        model, val_pred = fit_lgbm_direct(
            train,
            val,
            horizon=h,
            seed=seed,
            feature_variant=variant,
        )

        columns = get_feature_columns(
            train
        )

        test_pred = test[
            [
                "date",
                "prov_code",
                "target_date",
                "y_true",
                "y_mask",
            ]
        ].copy()

        test_pred["y_pred"] = predict_level(
            model, test, columns
        )

        for part, pred in (
            ("val", val_pred),
            ("test", test_pred),
        ):

            pred["model"] = "lgbm"
            pred["fold"] = origin
            pred["seed"] = seed
            pred["h"] = h
            pred["part"] = part

            results.append(pred)

        print(
            f"h={h} completed, "
            f"best_iteration="
            f"{model.best_iteration_}"
        )

    result = pd.concat(
        results, ignore_index=True
    )

    result["prov_code"] = (
        result["prov_code"].astype(str)
    )

    return result
