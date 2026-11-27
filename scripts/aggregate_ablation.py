#!/usr/bin/env python3
"""Aggregate MLE-H5-02 ablation run metrics."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
OUT = ROOT / "reports/ablation"


VARIANT_ORDER = {"full": 0, "no_climate": 1, "no_lag": 2, "no_gate": 3,
                 "no_calendar": 4}


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
    out["_order"] = out["variant"].map(VARIANT_ORDER)
    return out.sort_values(["_order", "horizon", "regime"]).drop(columns="_order")


def overall_summary(rows: pd.DataFrame) -> pd.DataFrame:
    """Per-run MAE weighted by the number of evaluated node-days, then mean/std."""
    records = []
    for (variant, horizon, origin, seed), g in rows.groupby(
            ["variant", "horizon", "origin", "seed"], sort=False):
        weight = g["n"].to_numpy(dtype=float)
        records.append({
            "variant": variant, "horizon": int(horizon), "origin": origin,
            "seed": int(seed),
            "mae": float(np.average(g["mae"], weights=weight)),
            "rmse": float(np.average(g["rmse"], weights=weight)),
            "smape": float(np.average(g["smape"], weights=weight)),
            "n": int(g["n"].sum()),
        })
    per_run = pd.DataFrame(records)
    out = (per_run.groupby(["variant", "horizon"], as_index=False)
           .agg(mean_mae=("mae", "mean"), std_mae=("mae", "std"),
                mean_rmse=("rmse", "mean"), mean_smape=("smape", "mean"),
                n_runs=("mae", "size"), n_node_days=("n", "sum")))
    full = (out[out["variant"] == "full"][["horizon", "mean_mae"]]
            .rename(columns={"mean_mae": "full_mae"}))
    out = out.merge(full, on="horizon", how="left")
    out["delta_vs_full"] = out["mean_mae"] - out["full_mae"]
    out["delta_pct_vs_full"] = 100.0 * out["delta_vs_full"] / out["full_mae"]
    out["_order"] = out["variant"].map(VARIANT_ORDER)
    return out.sort_values(["_order", "horizon"]).drop(columns="_order")


def main() -> None:
    frames = []
    for path in sorted(RUNS.glob("ablation_*/metrics.csv")):
        frames.append(pd.read_csv(path))
    if not frames:
        raise SystemExit("no ablation runs")
    rows = pd.concat(frames, ignore_index=True)
    if "full" not in set(rows["variant"]):
        raise SystemExit("no matched-budget full ablation runs; run all five variants")
    OUT.mkdir(parents=True, exist_ok=True)
    rows.to_csv(OUT / "ablation_val.csv", index=False)
    summary = summarize(rows)
    summary.to_csv(OUT / "ablation_summary.csv", index=False)
    overall = overall_summary(rows)
    overall.to_csv(OUT / "ablation_overall.csv", index=False)
    n_runs = int(rows.groupby(["variant", "origin", "seed"]).ngroups)
    n_variants = int(rows["variant"].nunique())
    n_origins = int(rows["origin"].nunique())
    n_seeds = int(rows["seed"].nunique())

    primary = overall[overall["horizon"] == 10]
    lines = ["# MLE-H5-02 ablation", "",
             f"Validasi: {n_variants} varian x {n_origins} origin x {n_seeds} seed "
             f"= {n_runs} run; {len(rows)} baris metrik per regime/horizon.",
             "",
             "MAE dihitung pada part `val` untuk horizon 5/10/20 dan dirata-ratakan "
             "per run (weighted by jumlah node-hari), lalu dilaporkan sebagai mean ± std "
             "antar 15 run. `delta` relatif terhadap varian `full`.",
             "",
             "## Ringkasan h10 (primary horizon)", "",
             "| variant | mean MAE ± std | delta vs full | delta % | n run |",
             "|---|---:|---:|---:|---:|"]
    for r in primary.itertuples(index=False):
        lines.append(f"| {r.variant} | {r.mean_mae:.2f} ± "
                     f"{0.0 if pd.isna(r.std_mae) else r.std_mae:.2f} | "
                     f"{r.delta_vs_full:+.2f} | {r.delta_pct_vs_full:+.2f}% | {r.n_runs} |")
    lines += ["", "## Ringkasan semua horizon", "",
              "| variant | horizon | mean MAE ± std | delta vs full | delta % | n run |",
              "|---|---:|---:|---:|---:|---:|"]
    for r in overall.itertuples(index=False):
        lines.append(f"| {r.variant} | {r.horizon} | {r.mean_mae:.2f} ± "
                     f"{0.0 if pd.isna(r.std_mae) else r.std_mae:.2f} | "
                     f"{r.delta_vs_full:+.2f} | {r.delta_pct_vs_full:+.2f}% | {r.n_runs} |")
    lines += ["", "## Rincian per regime", "",
              "| variant | horizon | regime | mean MAE | std | delta vs full | n run |",
              "|---|---:|---|---:|---:|---:|---:|"]
    for r in summary.itertuples(index=False):
        lines.append(f"| {r.variant} | {r.horizon} | {r.regime} | {r.mean_mae:.2f} | "
                     f"{0.0 if pd.isna(r.std_mae) else r.std_mae:.2f} | "
                     f"{r.delta_vs_full:+.2f} | {r.n_runs} |")
    lines += ["", "## Sanity check terhadap H5-01", ""]
    h5_path = ROOT / "reports/h5/module23_runs_summary.csv"
    if h5_path.is_file():
        h5 = pd.read_csv(h5_path)
        h5_mean = float(h5["val_h10_mae"].mean())
        # Baseline `full` saja (bukan rata-rata semua varian), dengan pembobotan
        # per-run yang sama dengan tabel ringkasan h10 di atas (audit 2026-11-27).
        full_h10 = overall[(overall["variant"] == "full") & (overall["horizon"] == 10)]
        if len(full_h10) != 1:
            raise SystemExit("baseline full h10 tidak unik")
        abl_h10 = float(full_h10["mean_mae"].iloc[0])
        lines += [f"- H5-01 `full` (2 epoch, 15 run): mean val h10 MAE {h5_mean:.2f}.",
                  f"- Ablation `full` (1 epoch, matched budget): mean val h10 MAE "
                  f"{abl_h10:.2f} (delta {abl_h10 - h5_mean:+.2f}).",
                  "- Perbedaan ini konsisten dengan pengurangan epoch; delta antar varian "
                  "di bawah tetap dihitung terhadap baseline matched-budget."]
    lines += ["", "## Protokol", "",
              "- Semua varian memakai arsitektur dan hyperparameter "
              "`configs/models/module23.yaml`; hanya komponen yang diuji yang diubah: "
              "`no_gate` = g=1 (hanya adaptif), `no_climate` = iklim dan shock gate nol, "
              "`no_lag` = L=1, `no_calendar` = kalender nol di encoder/head. Jadwal "
              "training memakai 1 epoch yang sama untuk semua varian (lihat catatan budget).",
              "- Varian dan `full` pada studi ini dilatih dengan 1 epoch agar anggaran "
              "komputasi identik antar varian. Run H5-01 `full` memakai 2 epoch; karena itu "
              "angka `full` di sini adalah baseline ablation yang matched-budget, bukan "
              "pengganti angka H5-01.",
              "- Split hash: `411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`.",
              "- Bukti run: `experiments/runs/ablation_<variant>_<origin>_s<seed>/` dan "
              "`experiments/registry.csv` (75 entri `ablation_*`)."]
    (OUT / "ablation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(overall.to_string(index=False))
    print(len(rows), "metric rows;", n_runs, "runs")


if __name__ == "__main__":
    main()
