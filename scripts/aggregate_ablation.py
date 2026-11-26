#!/usr/bin/env python3
"""Aggregate MLE-H5-02 ablation run metrics."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from renaro.eval.metrics import mae, rmse, smape

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
OUT = ROOT / "reports/ablation"


def summarize(rows: pd.DataFrame) -> pd.DataFrame:
    full = (rows[rows["variant"] == "full"]
            .groupby(["horizon", "regime"], as_index=False)
            .agg(full_mae=("mae", "mean")))
    out = (rows.groupby(["variant", "horizon", "regime"], as_index=False)
           .agg(mean_mae=("mae", "mean"), std_mae=("mae", "std"),
                mean_rmse=("rmse", "mean"), mean_smape=("smape", "mean"),
                n_runs=("mae", "size")))
    out = out.merge(full, on=["horizon", "regime"], how="left")
    out["delta_vs_full"] = out["mean_mae"] - out["full_mae"]
    return out


def main() -> None:
    frames = []
    for path in sorted(RUNS.glob("ablation_*/metrics.csv")):
        frames.append(pd.read_csv(path))
    if not frames:
        raise SystemExit("no ablation runs")
    # The H5-01 full runs are the same module23 configuration; reuse their
    # validation predictions instead of paying for another 15 full training runs.
    if not any(pd.read_csv(x).get("variant", pd.Series(dtype=str)).eq("full").any() for x in sorted(RUNS.glob("ablation_*/metrics.csv"))):
        for run in sorted(RUNS.glob("h5_module23_*")):
            pred_path = run / "preds.csv"
            if not pred_path.is_file():
                continue
            origin = run.name.split("_")[-2]
            seed = int(run.name.split("_s")[-1])
            preds = pd.read_csv(pred_path)
            preds = preds[preds["part"] == "val"].copy()
            split = pd.read_parquet(ROOT / f"data/processed/eval_splits/{origin}_val.parquet")
            split["date"] = pd.to_datetime(split["date"]).astype("datetime64[ns]")
            split["prov_code"] = split["prov_code"].astype(str).str.zfill(2)
            merged = preds.merge(split[["date", "prov_code", "label_primary"]],
                                 on=["date", "prov_code"], how="left", validate="many_to_one")
            merged = merged.rename(columns={"label_primary": "regime"})
            merged = merged[merged["y_mask"].astype(bool) & np.isfinite(merged["y_true"]) &
                            np.isfinite(merged["y_pred"])]
            for (h, regime), g in merged.groupby(["h", "regime"]):
                frames.append(pd.DataFrame([{"variant": "full", "origin": origin,
                    "horizon": int(h), "seed": seed, "regime": regime,
                    "mae": mae(g["y_true"], g["y_pred"]), "rmse": rmse(g["y_true"], g["y_pred"]),
                    "smape": smape(g["y_true"], g["y_pred"]), "n": len(g)}]))
    rows = pd.concat(frames, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    rows.to_csv(OUT / "ablation_val.csv", index=False)
    summary = summarize(rows)
    summary.to_csv(OUT / "ablation_summary.csv", index=False)
    lines = ["# MLE-H5-02 ablation", "",
             "Rata-rata validasi 3 origin x 5 seed. Delta MAE relatif terhadap `full`.",
             "", "| variant | horizon | regime | mean MAE | std | delta vs full | n |",
             "|---|---:|---|---:|---:|---:|---:|"]
    for r in summary.sort_values(["horizon", "regime", "variant"]).itertuples(index=False):
        lines.append(f"| {r.variant} | {r.horizon} | {r.regime} | {r.mean_mae:.2f} | "
                     f"{0.0 if pd.isna(r.std_mae) else r.std_mae:.2f} | "
                     f"{r.delta_vs_full:+.2f} | {r.n_runs} |")
    lines += ["", "Semua varian memakai konfigurasi `full`; hanya komponen yang diuji yang diubah.",
              "`no_gate` = g=1 (hanya adaptif), `no_climate` = iklim dan shock gate nol, "
              "`no_lag` = L=1, `no_calendar` = kalender nol di encoder/head."]
    (OUT / "ablation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print(len(rows), "metric rows")


if __name__ == "__main__":
    main()
