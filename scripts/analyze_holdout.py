#!/usr/bin/env python3
"""MLE-H6-01: holdout analysis for the frozen Gate 2 models.

Inputs (all committed, no sealed raw data):
  reports/holdout/predictions/preds_<model>_s<seed>.parquet
  reports/holdout/regime_labels_holdout_panel.csv
  reports/h5/gate2_validation_summary.csv
  frozen/manifest.yaml

Outputs in reports/holdout/:
  metrics_overall.csv / .md          model x horizon, mean +/- sd over 5 seeds
  metrics_by_regime.csv / .md        model x horizon x regime
  metrics_by_seed.csv                raw per-seed metrics
  dm_tests.csv / dm_summary.csv      DM vs best_baseline_on_validation (lgbm_c)
  table_main.csv / table_main.md     main h=10 table
  table_by_horizon.csv / .md         all horizons
  fig_error_timeline.png
  fig_per_regime.png
  fig_robustness_combined.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "reports/holdout"
PRED = OUT / "predictions"
LABELS = OUT / "regime_labels_holdout_panel.csv"
VAL = ROOT / "reports/h5/gate2_validation_summary.csv"
MANIFEST = ROOT / "frozen/manifest.yaml"
REGIMES = ("dry", "extreme_wet", "normal")
HORIZONS = (5, 10, 20)
PRIMARY = 10


def smape(y: np.ndarray, yhat: np.ndarray) -> float:
    den = np.abs(y) + np.abs(yhat)
    err = np.divide(2.0 * np.abs(y - yhat), den, out=np.zeros_like(den), where=den != 0)
    return float(100.0 * np.mean(err))


def valid(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[
        frame["y_mask"].astype(bool)
        & np.isfinite(frame["y_true"])
        & np.isfinite(frame["y_pred"])
    ].copy()


def metric_row(frame: pd.DataFrame) -> dict:
    y = frame["y_true"].to_numpy(float)
    yhat = frame["y_pred"].to_numpy(float)
    return {
        "mae": float(np.mean(np.abs(y - yhat))) if len(y) else float("nan"),
        "rmse": float(np.sqrt(np.mean((y - yhat) ** 2))) if len(y) else float("nan"),
        "smape": smape(y, yhat) if len(y) else float("nan"),
        "n": int(len(y)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(PRED.glob("preds_*.parquet"))
    if len(files) != 50:
        raise SystemExit(f"expected 50 prediction files, got {len(files)}")
    preds = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    preds["date"] = pd.to_datetime(preds["date"]).astype("datetime64[ns]")
    preds["target_date"] = pd.to_datetime(preds["target_date"]).astype("datetime64[ns]")
    preds["prov_code"] = preds["prov_code"].astype(str).str.zfill(2)

    labels = pd.read_csv(LABELS, dtype={"prov_code": str}, parse_dates=["date", "pentad_end"])
    labels["prov_code"] = labels["prov_code"].astype(str).str.zfill(2)
    labels = labels[["date", "prov_code", "label_primary"]].rename(columns={"label_primary": "regime"})
    preds = preds.merge(labels, on=["date", "prov_code"], how="left", validate="many_to_one")
    if preds["regime"].isna().any():
        raise SystemExit("missing regime labels on predictions")

    # Per-seed metrics
    rows = []
    for (model, seed, h), group in preds.groupby(["model", "seed", "h"], sort=True):
        v = valid(group)
        row = {"model": model, "seed": int(seed), "h": int(h)}
        row.update(metric_row(v))
        row["n_mask"] = int(group["y_mask"].astype(bool).sum())
        row["coverage"] = row["n"] / row["n_mask"] if row["n_mask"] else np.nan
        rows.append(row)
    by_seed = pd.DataFrame(rows)

    rows = []
    for (model, seed, h, regime), group in preds.groupby(["model", "seed", "h", "regime"], sort=True):
        v = valid(group)
        row = {"model": model, "seed": int(seed), "h": int(h), "regime": regime}
        row.update(metric_row(v))
        rows.append(row)
    by_seed_regime = pd.DataFrame(rows)

    # Aggregate across seeds (mean, sample sd, n seeds)
    def aggregate(frame: pd.DataFrame, keys: list[str], value_cols: list[str], out_name: str) -> pd.DataFrame:
        agg = (frame.groupby(keys, as_index=False)[value_cols]
               .agg(["mean", "std", "count"]))
        agg.columns = [f"{a}_{b}" if b else a for a, b in agg.columns.to_flat_index()]
        count_cols = [c for c in agg.columns if c.endswith("_count")]
        if count_cols:
            agg["n_seeds"] = agg[count_cols[0]]
            agg = agg.drop(columns=count_cols)
        agg.to_csv(OUT / f"{out_name}.csv", index=False)
        return agg

    overall = aggregate(by_seed, ["model", "h"], ["mae", "rmse", "smape", "n", "coverage"],
                        "metrics_overall")
    by_regime = aggregate(by_seed_regime, ["model", "h", "regime"],
                          ["mae", "rmse", "smape", "n"], "metrics_by_regime")
    by_seed.to_csv(OUT / "metrics_by_seed.csv", index=False)
    by_seed_regime.to_csv(OUT / "metrics_by_regime_seed.csv", index=False)

    # Main h=10 table
    val = pd.read_csv(VAL)
    val = val.set_index("model")
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    baseline = manifest["best_baseline_on_validation"]
    h10 = overall[overall.h == PRIMARY].set_index("model")
    reg10 = by_regime[by_regime.h == PRIMARY]
    worst_all = reg10.groupby("model")["mae_mean"].max().rename("worst_regime_mae")
    reg_n = reg10.pivot(index="model", columns="regime", values="n_mean")
    worst_n200 = reg10[reg10["n_mean"] >= 200].groupby("model")["mae_mean"].max().rename("worst_regime_mae_n200")

    def delta(reg_a: str, reg_b: str = "normal") -> pd.Series:
        a = reg10[reg10.regime == reg_a].set_index("model")["mae_mean"]
        b = reg10[reg10.regime == reg_b].set_index("model")["mae_mean"]
        return (a - b).rename(f"delta_{reg_a}_minus_{reg_b}")

    delta_dry = delta("dry")
    delta_ext = delta("extreme_wet")

    table = pd.DataFrame(index=h10.index)
    table["role"] = ["module" if not bool(val.loc[m, "is_baseline"]) else "baseline" for m in table.index]
    table["val_3origin_avg_h10"] = val["val_3origin_avg"]
    table["val_refit_avg_h10"] = val["holdout_val_avg"]
    table["holdout_mae_mean"] = h10["mae_mean"]
    table["holdout_mae_sd"] = h10["mae_std"]
    table["holdout_rmse_mean"] = h10["rmse_mean"]
    table["holdout_smape_mean"] = h10["smape_mean"]
    table["holdout_coverage_mean"] = h10["coverage_mean"]
    table["worst_regime_mae"] = worst_all
    table["worst_regime_mae_n200"] = worst_n200
    table["delta_dry_minus_normal"] = delta_dry
    table["delta_extreme_minus_normal"] = delta_ext
    table["delta_holdout_minus_val"] = table["holdout_mae_mean"] - table["val_3origin_avg_h10"]
    for regime in ("dry", "normal", "extreme_wet"):
        table[f"n_{regime}"] = reg_n[regime] if regime in reg_n else np.nan
    table = table.sort_values("holdout_mae_mean")

    # DM tests vs frozen baseline, per seed, h=10
    dm_rows = []
    base = preds[(preds.model == baseline) & (preds.h == PRIMARY)][
        ["seed", "date", "prov_code", "y_true", "y_pred", "y_mask"]
    ].copy()
    base["loss_base"] = (base["y_true"] - base["y_pred"]).abs()
    for model in sorted(preds.model.unique()):
        if model == baseline:
            continue
        for seed in sorted(preds.seed.unique()):
            sub = preds[(preds.model == model) & (preds.seed == seed) & (preds.h == PRIMARY)][
                ["date", "prov_code", "y_true", "y_pred", "y_mask"]
            ].copy()
            m = sub.merge(base[base.seed == seed][["date", "prov_code", "loss_base", "y_mask"]],
                          on=["date", "prov_code"], suffixes=("", "_base"))
            m = m[(m.y_mask.astype(bool)) & (m.y_mask_base.astype(bool))
                  & np.isfinite(m.y_true) & np.isfinite(m.y_pred)
                  & np.isfinite(m.loss_base)]
            m["loss_model"] = (m["y_true"] - m["y_pred"]).abs()
            daily = m.groupby("date")[["loss_model", "loss_base"]].mean().sort_index()
            # DM: d = loss_model - loss_baseline; alternative 'less' => model better.
            try:
                from renaro.eval.dm_test import diebold_mariano
                res = diebold_mariano(daily.loss_model.to_numpy(), daily.loss_base.to_numpy(),
                                      horizon=PRIMARY, alternative="less")
            except Exception as exc:  # noqa: BLE001
                res = {"stat": np.nan, "p": np.nan, "n": len(daily), "mean_d": np.nan,
                       "error": str(exc)}
            dm_rows.append({"model": model, "seed": int(seed), "h": PRIMARY,
                            "n_days": res.get("n"), "mean_d": res.get("mean_d"),
                            "stat": res.get("stat"), "p": res.get("p"),
                            "error": res.get("error", "")})
    dm = pd.DataFrame(dm_rows)
    dm.to_csv(OUT / "dm_tests.csv", index=False)
    dm_summary = (dm.groupby(["model", "h"], as_index=False)
                  .agg(median_p=("p", "median"), min_p=("p", "min"),
                       mean_stat=("stat", "mean"), mean_d=("mean_d", "mean"),
                       n_seeds=("seed", "size"),
                       sig_05=("p", lambda s: int((s < 0.05).sum())),
                       sig_01=("p", lambda s: int((s < 0.01).sum()))))
    dm_summary.to_csv(OUT / "dm_summary.csv", index=False)
    dm_idx = dm_summary.set_index("model")
    table["dm_median_p_vs_baseline"] = dm_idx["median_p"]
    table["dm_sig_05_of_5"] = dm_idx["sig_05"]
    table["dm_mean_loss_diff"] = dm_idx["mean_d"]
    table.to_csv(OUT / "table_main.csv")

    # Markdown tables
    def fmt(v: float, digits: int = 2) -> str:
        if pd.isna(v):
            return "–"
        return f"{v:,.{digits}f}"

    lines = [
        "# Tabel utama holdout — h = 10",
        "",
        "MAE/RMSE dalam Rp/kg. `val 3-origin` = rata-rata validasi O1–O3 pada konfigurasi beku; "
        "`val refit` = validasi refit HOLDOUT (Jan–Mei 2026), bukan holdout test. "
        "`Δ dry−normal` dan `Δ extreme−normal` dihitung di dalam holdout; tidak ada label `el_nino` "
        "karena RONI resmi masih netral. `worst-regime` = max MAE antar regime holdout yang tersedia.",
        "",
        "| Model | Peran | Val 3-origin | Val refit | Holdout MAE (mean ± sd) | RMSE | sMAPE | Coverage | Worst-regime | Worst n≥200 | Δ dry−normal | Δ extreme−normal | Δ vs val | DM median p | Sig. p<0.05 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m, r in table.iterrows():
        lines.append(
            f"| `{m}` | {r['role']} | {fmt(r['val_3origin_avg_h10'],1)} | {fmt(r['val_refit_avg_h10'],1)} | "
            f"{fmt(r['holdout_mae_mean'],1)} ± {fmt(r['holdout_mae_sd'],1)} | {fmt(r['holdout_rmse_mean'],1)} | "
            f"{fmt(r['holdout_smape_mean'],2)} | {fmt(r['holdout_coverage_mean']*100,2)}% | "
            f"{fmt(r['worst_regime_mae'],1)} | {fmt(r['worst_regime_mae_n200'],1)} | "
            f"{fmt(r['delta_dry_minus_normal'],1)} | {fmt(r['delta_extreme_minus_normal'],1)} | "
            f"{fmt(r['delta_holdout_minus_val'],1)} | {fmt(r['dm_median_p_vs_baseline'],4)} | "
            f"{fmt(r['dm_sig_05_of_5'],0)}/5 |"
        )
    lines += [
        "",
        "Catatan: DM memakai `d = loss_model − loss_lgbm_c`; p satu sisi (`alternative='less'`), "
        "semakin kecil semakin kuat bukti model lebih baik dari baseline. Nilai p adalah median 5 seed. "
        "`seasonal_naive` memiliki 75 baris NaN/file; baris tersebut tidak masuk metrik (coverage < 100%).",
    ]
    (OUT / "table_main.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # All horizons table
    lines = [
        "# Metrik holdout per horizon",
        "",
        "Mean ± sd antar 5 seed. MAE dalam Rp/kg.",
        "",
        "| Model | h | MAE | RMSE | sMAPE | n | Coverage |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in overall.sort_values(["model", "h"]).iterrows():
        lines.append(
            f"| `{r['model']}` | {int(r['h'])} | {fmt(r['mae_mean'],1)} ± {fmt(r['mae_std'],1)} | "
            f"{fmt(r['rmse_mean'],1)} | {fmt(r['smape_mean'],2)} | {fmt(r['n_mean'],0)} | "
            f"{fmt(r['coverage_mean']*100,2)}% |"
        )
    (OUT / "table_by_horizon.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    overall.to_csv(OUT / "table_by_horizon.csv", index=False)

    print(table.to_string())
    print(f"[out] {OUT/'table_main.md'}")

    # ---------------- figures ----------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import Normalize

    # 1) error timeline h=10, mean across seeds
    h10p = preds[preds.h == PRIMARY].copy()
    h10p = h10p[h10p.y_mask.astype(bool) & np.isfinite(h10p.y_true) & np.isfinite(h10p.y_pred)]
    h10p["err"] = (h10p.y_true - h10p.y_pred).abs()
    daily = (h10p.groupby(["model", "seed", "date"])["err"].mean()
             .groupby(["model", "date"]).agg(["mean", "std"]).reset_index())
    models = table.index.tolist()
    fig, ax = plt.subplots(figsize=(14, 6.5), dpi=160)
    colors = plt.get_cmap("tab10").colors
    for i, m in enumerate(models):
        d = daily[daily.model == m].sort_values("date")
        ax.plot(d.date, d["mean"], label=m, color=colors[i % 10], linewidth=1.6)
    # dominant regime background
    lab = labels.copy()
    lab = lab[(lab.date >= daily.date.min()) & (lab.date <= daily.date.max())]
    dominant = (lab.groupby(["date", "regime"]).size().reset_index(name="n")
                .sort_values(["date", "n"], ascending=[True, False])
                .drop_duplicates("date").set_index("date")["regime"])
    all_dates = pd.date_range(daily.date.min(), daily.date.max(), freq="D")
    dom = dominant.reindex(all_dates).ffill()
    colors_bg = {"dry": "#f2e6d0", "normal": "#e6f0e6", "extreme_wet": "#dce8f5"}
    start = None
    prev = None
    for d in all_dates:
        r = dom.get(d)
        if r != prev:
            if prev is not None and start is not None:
                ax.axvspan(start, d - pd.Timedelta(days=1), color=colors_bg.get(prev, "#f5f5f5"), alpha=0.55, zorder=0)
            start = d
            prev = r
    if prev is not None and start is not None:
        ax.axvspan(start, all_dates[-1], color=colors_bg.get(prev, "#f5f5f5"), alpha=0.55, zorder=0)
    ax.set_ylabel("MAE harian rata-rata lintas provinsi (Rp/kg)")
    ax.set_title("Holdout h=10 — error harian rata-rata 5 seed; arsir = regime dominan")
    ax.grid(axis="y", alpha=0.25)
    handles, labels_ = ax.get_legend_handles_labels()
    handles += [mpatches.Patch(color=colors_bg[k], label=f"dominant {k}") for k in colors_bg]
    labels_ += [f"dominant {k}" for k in colors_bg]
    ax.legend(handles, labels_, fontsize=8, ncol=3, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1))
    fig.tight_layout()
    fig.savefig(OUT / "fig_error_timeline.png", bbox_inches="tight")

    # 2) per-regime heatmap h=10
    pivot = reg10.pivot(index="model", columns="regime", values="mae_mean").reindex(
        index=table.index, columns=["dry", "normal", "extreme_wet"])
    counts = reg10.pivot(index="model", columns="regime", values="n_mean").reindex(
        index=table.index, columns=["dry", "normal", "extreme_wet"])
    fig, ax = plt.subplots(figsize=(7.5, 6.2), dpi=170)
    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="magma_r")
    ax.set_xticks(range(pivot.shape[1]))
    ax.set_xticklabels([f"{c}\n(n≈{counts[c].mean():,.0f})" for c in pivot.columns], fontsize=9)
    ax.set_yticks(range(pivot.shape[0]))
    ax.set_yticklabels(pivot.index, fontsize=9)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.iloc[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v:,.0f}", ha="center", va="center", fontsize=8,
                        color="white" if v > np.nanmedian(pivot.to_numpy()) else "black")
    ax.set_title("MAE holdout per regime per model (h=10, mean 5 seed)")
    fig.colorbar(im, ax=ax, shrink=0.8, label="MAE (Rp/kg)")
    fig.tight_layout()
    fig.savefig(OUT / "fig_per_regime.png", bbox_inches="tight")

    # 3) combine robustness figures from CGS-H5-01
    try:
        from PIL import Image
        paths = [ROOT / "reports/robustness/fig_mae_vs_p.png",
                 ROOT / "reports/robustness/fig_joint_shift.png"]
        imgs = [Image.open(p).convert("RGB") for p in paths if p.is_file()]
        if imgs:
            width = max(im.width for im in imgs)
            imgs = [im.resize((width, int(im.height * width / im.width))) for im in imgs]
            total = sum(im.height for im in imgs)
            canvas = Image.new("RGB", (width, total), "white")
            y = 0
            for im in imgs:
                canvas.paste(im, (0, y)); y += im.height
            canvas.save(OUT / "fig_robustness_combined.png")
            print("[out] fig_robustness_combined.png")
    except Exception as exc:  # noqa: BLE001
        print("[warn] robustness composite skipped:", exc)

    print(f"[out] {OUT/'fig_error_timeline.png'}")
    print(f"[out] {OUT/'fig_per_regime.png'}")


if __name__ == "__main__":
    main()
