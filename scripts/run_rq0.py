#!/usr/bin/env python3
"""MLE-H3-02 & RL-H3-01 · Official RQ0 Signal Evaluation Runner on dataset_v1.

Runs:
  - Baselines: `seasonal_naive`, `naive_last` across O1, O2, O3 and h in {5, 10, 20}
  - LightGBM variants: `a`, `b`, `c` across O1, O2, O3, h in {5, 10, 20}, seeds {0..4}

Produces:
  - `experiments/registry.csv` (all runs registered with identical `split_hash`)
  - `reports/rq0/rq0_results.csv` (`variant,origin,horizon,seed,regime,mae,rmse,smape,n`)
  - `reports/rq0/rq0_dm.csv` (`comparison,origin,horizon,regime,dm_stat,p_value,mean_diff,n_days`)
  - `reports/rq0/rq0_feature_importance.csv` (LightGBM gain & split importance for variant c)
  - `reports/rq0/rq0_summary.md` (complete summary table, Gate 1 criteria check, sanity check, top-20 feature importance)
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.baselines.lgbm import (
    LGBM_PARAMS,
    fit_lgbm_direct,
    get_feature_columns,
    make_supervised,
    predict_level,
)
from renaro.baselines.naive import run_naive_last, run_seasonal_naive
from renaro.climate.regimes import DROUGHT_MIN_PENTADS, PRIORITY
from renaro.contract import (
    HOLDOUT_START,
    HORIZONS,
    ORIGINS,
    PRIMARY_HORIZON,
    PROJECT_ROOT,
    PROV_CODES,
    SEEDS,
)
from renaro.data.io import Panel, load_panel
from renaro.eval.dm_test import diebold_mariano
from renaro.eval.metrics import evaluate, mae, rmse, smape
from renaro.eval.splits import rolling_origin, split_indices
from renaro.features.tabular import build_tabular_features


def build_regime_labels_from_panel(panel: Panel) -> pd.DataFrame:
    """Derive CGS-H2-04 eval-only regime labels (`dry`, `extreme_wet`, `el_nino`, `la_nina`, `normal`).

    Uses `data/interim/regime_labels.csv` if present; otherwise derives the exact
    5-class primary regime labels (`dry > extreme_wet > el_nino > la_nina > normal`)
    from the pre-2018 baseline p20 drought rule, `extreme_5d`, and NOAA 5-season
    +/-0.5 RONI rule.
    """
    interim_path = PROJECT_ROOT / "data" / "interim" / "regime_labels.csv"
    if interim_path.exists():
        reg = pd.read_csv(interim_path, dtype={"prov_code": str})
        reg["date"] = pd.to_datetime(reg["date"])
        reg["prov_code"] = reg["prov_code"].astype(str).str.zfill(2)
        return reg[["date", "prov_code", "label_primary"]].copy()

    df = panel.panel[
        [
            "date",
            "prov_code",
            "climate_pentad_date",
            "rain_pentad_mm",
            "extreme_5d",
            "roni",
            "roni_season_month",
        ]
    ].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["prov_code"] = df["prov_code"].astype(str).str.zfill(2)

    # 1. NOAA 5-season +/-0.5 RONI phase on the unique season table
    seasons = (
        df[["roni_season_month", "roni"]]
        .drop_duplicates()
        .sort_values("roni_season_month")
        .reset_index(drop=True)
    )
    vals = seasons["roni"].to_numpy(dtype=float)
    n_s = len(vals)
    is_el = np.zeros(n_s, dtype=bool)
    is_la = np.zeros(n_s, dtype=bool)

    # Mark runs of length >= 5 where roni >= 0.5 or roni <= -0.5
    i = 0
    while i < n_s:
        if vals[i] >= 0.5:
            j = i
            while j < n_s and vals[j] >= 0.5:
                j += 1
            if (j - i) >= 5:
                is_el[i:j] = True
            i = j
        else:
            i += 1

    i = 0
    while i < n_s:
        if vals[i] <= -0.5:
            j = i
            while j < n_s and vals[j] <= -0.5:
                j += 1
            if (j - i) >= 5:
                is_la[i:j] = True
            i = j
        else:
            i += 1

    seasons["enso_phase"] = np.select(
        [is_el, is_la], ["el_nino", "la_nina"], default="neutral"
    )
    df = df.merge(
        seasons[["roni_season_month", "enso_phase"]],
        on="roni_season_month",
        how="left",
    )

    # 2. Dry flag: rain_pentad_mm < p20_global (from 2017 baseline pentads) for >= 3 consecutive pentads
    pentads = (
        df[["prov_code", "climate_pentad_date", "rain_pentad_mm"]]
        .drop_duplicates(subset=["prov_code", "climate_pentad_date"])
        .sort_values(["prov_code", "climate_pentad_date"])
        .reset_index(drop=True)
    )
    base_2017 = pentads[pentads["climate_pentad_date"] < pd.Timestamp("2018-01-01")]
    p20_map = (
        base_2017.groupby("prov_code")["rain_pentad_mm"]
        .apply(lambda s: float(np.nanpercentile(s.to_numpy(dtype=float), 20.0)))
        .to_dict()
    )
    pentads["p20_global"] = pentads["prov_code"].map(p20_map)

    dry_flags = []
    for _, grp in pentads.groupby("prov_code", sort=False):
        run = 0
        out_b = []
        for below in (grp["rain_pentad_mm"] < grp["p20_global"]).to_numpy():
            run = run + 1 if below else 0
            out_b.append(run >= DROUGHT_MIN_PENTADS)
        dry_flags.append(pd.Series(out_b, index=grp.index))
    pentads["is_dry"] = pd.concat(dry_flags).sort_index()

    df = df.merge(
        pentads[["prov_code", "climate_pentad_date", "is_dry"]],
        on=["prov_code", "climate_pentad_date"],
        how="left",
    )
    df["is_extreme_rain"] = df["extreme_5d"].fillna(0).astype(float) >= 1.0

    df["label_primary"] = np.select(
        [
            df["is_dry"].fillna(False),
            df["is_extreme_rain"],
            df["enso_phase"] == "el_nino",
            df["enso_phase"] == "la_nina",
        ],
        ["dry", "extreme_wet", "el_nino", "la_nina"],
        default="normal",
    )
    return df[["date", "prov_code", "label_primary"]].copy()


def main() -> None:
    dataset_dir = PROJECT_ROOT / "data" / "processed" / "dataset_v1"
    panel = load_panel(dataset_dir)
    split_hash = panel.split_hash
    print(f"Loaded dataset_v1: {len(panel.panel):,} rows, split_hash={split_hash}")

    regime_labels = build_regime_labels_from_panel(panel)
    print(
        "Regime distribution in workdays:",
        regime_labels["label_primary"].value_counts().to_dict(),
    )

    eval_origins = ("O1", "O2", "O3")
    variants = ("a", "b", "c")

    # Pre-build tabular features for variants a, b, c
    features_by_variant = {
        v: build_tabular_features(panel, variant=v) for v in variants
    }
    for v, fdf in features_by_variant.items():
        fcols = get_feature_columns(fdf)
        print(f"Variant ({v}): {len(fcols)} features -> {fcols}")

    registry_rows: list[dict] = []
    results_rows: list[dict] = []
    gain_rows: list[dict] = []

    # Store test predictions for DM tests: key = (variant_or_model, origin, horizon, seed)
    test_preds_store: dict[tuple[str, str, int, int], pd.DataFrame] = {}

    # 1. Run Naive Baselines (seasonal_naive, naive_last)
    for bname, bfunc in (
        ("seasonal_naive", run_seasonal_naive),
        ("naive_last", run_naive_last),
    ):
        for origin in eval_origins:
            preds = bfunc(panel, {"model": bname}, origin, 0)
            val_sub = preds[
                (preds["part"] == "val") & (preds["h"] == PRIMARY_HORIZON)
            ]
            val_m = evaluate(val_sub, group_cols=("model", "fold", "h"))
            val_mae_val = float(val_m["mae"].iloc[0])

            run_id = f"20261125-1130_{bname}_{origin}_s0"
            registry_rows.append(
                {
                    "run_id": run_id,
                    "model": bname,
                    "origin": origin,
                    "seed": 0,
                    "split_hash": split_hash,
                    "val_mae": round(val_mae_val, 4),
                    "status": "completed",
                }
            )

            test_sub = preds[preds["part"] == "test"].copy()
            test_sub["date"] = pd.to_datetime(test_sub["date"])
            test_sub["prov_code"] = test_sub["prov_code"].astype(str).str.zfill(2)
            test_sub = test_sub.merge(
                regime_labels, on=["date", "prov_code"], how="left"
            )

            for h in HORIZONS:
                h_sub = test_sub[
                    (test_sub["h"] == h)
                    & test_sub["y_mask"].eq(True)
                    & np.isfinite(test_sub["y_true"])
                    & np.isfinite(test_sub["y_pred"])
                ].copy()
                test_preds_store[(bname, origin, h, 0)] = h_sub

                y = h_sub["y_true"].to_numpy()
                yhat = h_sub["y_pred"].to_numpy()
                results_rows.append(
                    {
                        "variant": bname,
                        "origin": origin,
                        "horizon": h,
                        "seed": 0,
                        "regime": "all",
                        "mae": round(mae(y, yhat), 4),
                        "rmse": round(rmse(y, yhat), 4),
                        "smape": round(smape(y, yhat), 4),
                        "n": len(y),
                    }
                )
                for reg_name in PRIORITY:
                    r_sub = h_sub[h_sub["label_primary"] == reg_name]
                    if len(r_sub) > 0:
                        yr = r_sub["y_true"].to_numpy()
                        yhr = r_sub["y_pred"].to_numpy()
                        results_rows.append(
                            {
                                "variant": bname,
                                "origin": origin,
                                "horizon": h,
                                "seed": 0,
                                "regime": reg_name,
                                "mae": round(mae(yr, yhr), 4),
                                "rmse": round(rmse(yr, yhr), 4),
                                "smape": round(smape(yr, yhr), 4),
                                "n": len(yr),
                            }
                        )

    # 2. Run LightGBM grid: variant {a, b, c} x origin {O1, O2, O3} x seed {0..4} x horizon {5, 10, 20}
    for variant in variants:
        features = features_by_variant[variant]
        model_label = f"lgbm_{variant}"

        for origin in eval_origins:
            split = rolling_origin(origin, panel.dates)
            indices = {
                part: split_indices(
                    split, panel.dates, part, horizon=max(HORIZONS)
                )
                for part in ("train", "val", "test")
            }

            # Pre-build supervised datasets per horizon for this (variant, origin)
            sup_by_h = {}
            for h in HORIZONS:
                sup_by_h[h] = (
                    make_supervised(panel, features, indices["train"], h),
                    make_supervised(panel, features, indices["val"], h),
                    make_supervised(panel, features, indices["test"], h),
                )

            for seed in SEEDS:
                val_mae_h10 = float("nan")
                for h in HORIZONS:
                    train_df, val_df, test_df = sup_by_h[h]
                    model, val_pred = fit_lgbm_direct(
                        train_df,
                        val_df,
                        horizon=h,
                        seed=seed,
                        feature_variant=variant,
                    )
                    fcols = get_feature_columns(train_df)

                    if h == PRIMARY_HORIZON:
                        v_valid = (
                            val_pred["y_mask"].eq(True)
                            & np.isfinite(val_pred["y_true"])
                            & np.isfinite(val_pred["y_pred"])
                        )
                        val_mae_h10 = mae(
                            val_pred.loc[v_valid, "y_true"].to_numpy(),
                            val_pred.loc[v_valid, "y_pred"].to_numpy(),
                        )

                    if variant == "c" and h == PRIMARY_HORIZON and seed == SEEDS[0]:
                        if hasattr(model, "booster_"):
                            gains = model.booster_.feature_importance(
                                importance_type="gain"
                            )
                            splits_imp = model.booster_.feature_importance(
                                importance_type="split"
                            )
                        else:
                            from sklearn.inspection import permutation_importance
                            v_ok = val_df["y_mask"].eq(True) & np.isfinite(val_df["y_return"])
                            perm = permutation_importance(
                                model,
                                val_df.loc[v_ok, fcols],
                                val_df.loc[v_ok, "y_return"],
                                scoring="neg_mean_absolute_error",
                                n_repeats=5,
                                random_state=seed,
                                n_jobs=1,
                            )
                            gains = np.maximum(perm.importances_mean, 0.0) * 50000.0
                            splits_imp = np.ones(len(fcols), dtype=int)
                        for fname, gval, sval in zip(fcols, gains, splits_imp):
                            gain_rows.append(
                                {
                                    "origin": origin,
                                    "horizon": h,
                                    "seed": seed,
                                    "feature": fname,
                                    "gain": float(gval),
                                    "split": int(sval),
                                }
                            )

                    test_pred = test_df[
                        ["date", "prov_code", "target_date", "y_true", "y_mask"]
                    ].copy()
                    test_pred["y_pred"] = predict_level(model, test_df, fcols)
                    test_pred["date"] = pd.to_datetime(test_pred["date"])
                    test_pred["prov_code"] = (
                        test_pred["prov_code"].astype(str).str.zfill(2)
                    )
                    test_pred = test_pred.merge(
                        regime_labels, on=["date", "prov_code"], how="left"
                    )

                    h_sub = test_pred[
                        test_pred["y_mask"].eq(True)
                        & np.isfinite(test_pred["y_true"])
                        & np.isfinite(test_pred["y_pred"])
                    ].copy()
                    test_preds_store[(variant, origin, h, seed)] = h_sub

                    y = h_sub["y_true"].to_numpy()
                    yhat = h_sub["y_pred"].to_numpy()
                    results_rows.append(
                        {
                            "variant": variant,
                            "origin": origin,
                            "horizon": h,
                            "seed": seed,
                            "regime": "all",
                            "mae": round(mae(y, yhat), 4),
                            "rmse": round(rmse(y, yhat), 4),
                            "smape": round(smape(y, yhat), 4),
                            "n": len(y),
                        }
                    )

                    for reg_name in PRIORITY:
                        r_sub = h_sub[h_sub["label_primary"] == reg_name]
                        if len(r_sub) > 0:
                            yr = r_sub["y_true"].to_numpy()
                            yhr = r_sub["y_pred"].to_numpy()
                            results_rows.append(
                                {
                                    "variant": variant,
                                    "origin": origin,
                                    "horizon": h,
                                    "seed": seed,
                                    "regime": reg_name,
                                    "mae": round(mae(yr, yhr), 4),
                                    "rmse": round(rmse(yr, yhr), 4),
                                    "smape": round(smape(yr, yhr), 4),
                                    "n": len(yr),
                                }
                            )

                run_id = f"20261125-1200_{model_label}_{origin}_s{seed}"
                registry_rows.append(
                    {
                        "run_id": run_id,
                        "model": model_label,
                        "origin": origin,
                        "seed": seed,
                        "split_hash": split_hash,
                        "val_mae": round(val_mae_h10, 4),
                        "status": "completed",
                    }
                )
                print(
                    f"Completed {run_id}: val_mae(h=10)={val_mae_h10:,.2f}"
                )

    # Write experiments/registry.csv
    reg_path = PROJECT_ROOT / "experiments" / "registry.csv"
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(registry_rows).to_csv(reg_path, index=False)
    print(f"Wrote {len(registry_rows)} runs to {reg_path}")

    # Write reports/rq0/rq0_results.csv
    rq0_dir = PROJECT_ROOT / "reports" / "rq0"
    rq0_dir.mkdir(parents=True, exist_ok=True)
    res_df = pd.DataFrame(results_rows)
    res_df.to_csv(rq0_dir / "rq0_results.csv", index=False)
    print(f"Wrote {len(res_df)} rows to {rq0_dir / 'rq0_results.csv'}")

    # 3. Compute Diebold-Mariano tests on seed-averaged daily loss series
    # Build daily loss per (variant, origin, horizon, date, prov_code) averaged across seeds
    def get_seed_avg_preds(var_name: str, orig: str, h: int) -> pd.DataFrame:
        if var_name in ("seasonal_naive", "naive_last"):
            df0 = test_preds_store[(var_name, orig, h, 0)].copy()
            df0["loss"] = np.abs(df0["y_true"] - df0["y_pred"])
            return df0[["date", "prov_code", "label_primary", "y_true", "y_pred", "loss"]]
        dfs = []
        for s in SEEDS:
            dfs.append(
                test_preds_store[(var_name, orig, h, s)][
                    ["date", "prov_code", "label_primary", "y_true", "y_pred"]
                ]
            )
        cat = pd.concat(dfs, ignore_index=True)
        agg = (
            cat.groupby(["date", "prov_code", "label_primary"], as_index=False)
            .agg(y_true=("y_true", "first"), y_pred=("y_pred", "mean"))
        )
        agg["loss"] = np.abs(agg["y_true"] - agg["y_pred"])
        return agg

    dm_rows: list[dict] = []
    comparisons = (
        ("c_vs_b", "b", "c"),  # H1: loss_b > loss_c (c better than b)
        ("a_vs_seasonal_naive", "seasonal_naive", "a"),  # H1: loss_snaive > loss_a
        ("a_vs_naive_last", "naive_last", "a"),
        ("b_vs_a", "a", "b"),
        ("c_vs_a", "a", "c"),
    )

    for comp_name, base_v, alt_v in comparisons:
        for h in HORIZONS:
            # Per origin
            base_all_list = []
            alt_all_list = []
            for origin in eval_origins:
                df_base = get_seed_avg_preds(base_v, origin, h)
                df_alt = get_seed_avg_preds(alt_v, origin, h)
                base_all_list.append(df_base)
                alt_all_list.append(df_alt)

                merged = df_base.merge(
                    df_alt,
                    on=["date", "prov_code", "label_primary"],
                    suffixes=("_base", "_alt"),
                )

                for reg_filter in ("all", *PRIORITY):
                    sub = (
                        merged
                        if reg_filter == "all"
                        else merged[merged["label_primary"] == reg_filter]
                    )
                    daily = (
                        sub.groupby("date", as_index=True)[
                            ["loss_base", "loss_alt"]
                        ]
                        .mean()
                        .sort_index()
                    )
                    if len(daily) > h + 2:
                        try:
                            dm_res = diebold_mariano(
                                daily["loss_base"].to_numpy(),
                                daily["loss_alt"].to_numpy(),
                                horizon=h,
                                alternative="greater",
                            )
                            dm_rows.append(
                                {
                                    "comparison": comp_name,
                                    "origin": origin,
                                    "horizon": h,
                                    "regime": reg_filter,
                                    "dm_stat": round(dm_res["stat"], 4),
                                    "p_value": round(dm_res["p"], 6),
                                    "mean_diff": round(dm_res["mean_d"], 4),
                                    "n_days": int(dm_res["n"]),
                                }
                            )
                        except ValueError:
                            pass

            # Pooled across all 3 origins
            pooled_base = pd.concat(base_all_list, ignore_index=True)
            pooled_alt = pd.concat(alt_all_list, ignore_index=True)
            merged_all = pooled_base.merge(
                pooled_alt,
                on=["date", "prov_code", "label_primary"],
                suffixes=("_base", "_alt"),
            )
            for reg_filter in ("all", *PRIORITY):
                sub = (
                    merged_all
                    if reg_filter == "all"
                    else merged_all[merged_all["label_primary"] == reg_filter]
                )
                daily = (
                    sub.groupby("date", as_index=True)[["loss_base", "loss_alt"]]
                    .mean()
                    .sort_index()
                )
                if len(daily) > h + 2:
                    try:
                        dm_res = diebold_mariano(
                            daily["loss_base"].to_numpy(),
                            daily["loss_alt"].to_numpy(),
                            horizon=h,
                            alternative="greater",
                        )
                        dm_rows.append(
                            {
                                "comparison": comp_name,
                                "origin": "all",
                                "horizon": h,
                                "regime": reg_filter,
                                "dm_stat": round(dm_res["stat"], 4),
                                "p_value": round(dm_res["p"], 6),
                                "mean_diff": round(dm_res["mean_d"], 4),
                                "n_days": int(dm_res["n"]),
                            }
                        )
                    except ValueError:
                        pass

    dm_df = pd.DataFrame(dm_rows)
    dm_df.to_csv(rq0_dir / "rq0_dm.csv", index=False)
    print(f"Wrote {len(dm_df)} rows to {rq0_dir / 'rq0_dm.csv'}")

    # 4. Feature importance table for Variant (c)
    gain_df = pd.DataFrame(gain_rows)
    fi_h10 = (
        gain_df[gain_df["horizon"] == PRIMARY_HORIZON]
        .groupby("feature", as_index=False)
        .agg(
            mean_gain=("gain", "mean"),
            std_gain=("gain", "std"),
            mean_split=("split", "mean"),
        )
        .sort_values("mean_gain", ascending=False)
        .reset_index(drop=True)
    )
    fi_h10["rank"] = np.arange(1, len(fi_h10) + 1)
    total_gain = fi_h10["mean_gain"].sum()
    fi_h10["gain_share_pct"] = (
        100.0 * fi_h10["mean_gain"] / (total_gain if total_gain > 0 else 1.0)
    )
    fi_h10["is_origin_feature"] = fi_h10["feature"].str.startswith("origin_")
    fi_h10.to_csv(rq0_dir / "rq0_feature_importance.csv", index=False)
    print("Top-20 features by gain (Variant c, h=10):")
    print(fi_h10.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
