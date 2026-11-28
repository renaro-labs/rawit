#!/usr/bin/env python3
"""MLE-H5-04: Train and evaluate Module 4 (O1-O3 x 5 seeds) + O3 perturbation robustness
comparison against Gate 2 Module 2-3 and Module 1.

Strictly stays on dataset_v1 (< 2026-06-01). Never touches HOLDOUT and never reads
regime_labels.csv during training (only for post-hoc evaluation reporting).
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import subprocess
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yaml

from renaro.contract import HOLDOUT_START
from renaro.data.io import load_panel
from renaro.eval.metrics import mae, per_regime, rmse, smape
from renaro.frozen import sha256_file
from renaro.graph_perturb import perturbation_grid
from renaro.models.module1_training import predict
from renaro.models.module23 import build as build_module23
from renaro.models.module4 import (
    build as build_module4,
    module4_edge_tensors,
    prepare_module4,
    run_registered_module4,
)

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments" / "runs"
REGISTRY = ROOT / "experiments" / "registry.csv"
SPLITS_DIR = ROOT / "data" / "processed" / "eval_splits"
OUT_DIR = ROOT / "reports" / "module4"


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _metrics_dict(preds: pd.DataFrame) -> dict[str, float | int]:
    out: dict[str, float | int] = {}
    for (part, h), g in preds.groupby(["part", "h"]):
        v = g[g["y_mask"].astype(bool) & np.isfinite(g["y_true"]) & np.isfinite(g["y_pred"])]
        out[f"{part}_h{int(h)}_mae"] = float((v["y_true"] - v["y_pred"]).abs().mean())
        out[f"{part}_h{int(h)}_rmse"] = rmse(v["y_true"], v["y_pred"])
        out[f"{part}_h{int(h)}_smape"] = smape(v["y_true"], v["y_pred"])
        out[f"{part}_h{int(h)}_n"] = int(len(v))
    return out


def _upsert_registry(run_id: str, origin: str, seed: int, split_hash: str, val_mae: float) -> None:
    fields = ["run_id", "model", "origin", "seed", "split_hash", "val_mae", "status"]
    if REGISTRY.exists() and REGISTRY.stat().st_size > 0:
        reg = pd.read_csv(REGISTRY, dtype=str)
    else:
        reg = pd.DataFrame(columns=fields)
    reg = reg[reg["run_id"] != run_id]
    entry = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "model": "module4",
                "origin": origin,
                "seed": str(seed),
                "split_hash": split_hash,
                "val_mae": f"{val_mae:.6f}",
                "status": "completed",
            }
        ],
        columns=fields,
    )
    reg = pd.concat([reg, entry], ignore_index=True)
    reg.to_csv(REGISTRY, index=False)


def train_grid(
    panel,
    cfg: dict,
    origins: tuple[str, ...],
    seeds: tuple[int, ...],
    *,
    force: bool = False,
    smoke: bool = False,
) -> pd.DataFrame:
    sha = _git_sha()
    holdout_cutoff = pd.Timestamp(HOLDOUT_START)
    rows = []
    for origin in origins:
        if origin == "HOLDOUT":
            raise PermissionError("MLE-H5-04 hanya untuk O1-O3; HOLDOUT tersegel.")
        for seed in seeds:
            run_id = f"h5_module4_{origin}_s{seed}"
            out = RUNS / run_id
            ckpt_path = out / "ckpt.pt"
            preds_path = out / "preds.parquet"
            summ_path = out / "summary.json"

            if not force and all(p.is_file() for p in (ckpt_path, preds_path, summ_path)):
                summ = json.loads(summ_path.read_text(encoding="utf-8"))
                m = summ["metrics"]
                print(f"[skip] {run_id} (val_h10_mae={m['val_h10_mae']:.2f})", flush=True)
            else:
                out.mkdir(parents=True, exist_ok=True)
                t0 = time.perf_counter()
                preds = run_registered_module4(
                    panel, cfg, origin, seed, checkpoint=ckpt_path, smoke=smoke
                )
                elapsed = time.perf_counter() - t0
                preds["date"] = pd.to_datetime(preds["date"]).astype("datetime64[ns]")
                preds["target_date"] = pd.to_datetime(preds["target_date"]).astype("datetime64[ns]")
                assert (preds["date"] < holdout_cutoff).all() and (
                    preds["target_date"] < holdout_cutoff
                ).all(), "PA-04 violation"
                preds.to_parquet(preds_path, index=False)
                ckpt_sha = sha256_file(ckpt_path)
                (out / "ckpt.sha256").write_text(f"{ckpt_sha}  ckpt.pt\n", encoding="utf-8")
                (out / "git_sha.txt").write_text(f"{sha}\n", encoding="utf-8")
                m = _metrics_dict(preds)
                tr = preds.attrs.get("training", {})
                summ = {
                    "run_id": run_id,
                    "model": "module4",
                    "origin": origin,
                    "seed": seed,
                    "git_sha": sha,
                    "split_hash": panel.split_hash,
                    "ckpt_sha256": ckpt_sha,
                    "seconds": round(elapsed, 2),
                    "config": {k: v for k, v in cfg.items() if k != "global"},
                    "training": tr,
                    "metrics": m,
                }
                summ_path.write_text(json.dumps(summ, indent=2), encoding="utf-8")
                if not smoke:
                    _upsert_registry(run_id, origin, seed, panel.split_hash, float(m["val_h10_mae"]))
                print(
                    f"[done] {run_id} | val_h10={m['val_h10_mae']:.2f} | "
                    f"test_h10={m['test_h10_mae']:.2f} | {elapsed:.1f}s | "
                    f"vram={tr.get('peak_allocated_gb')}",
                    flush=True,
                )

            tr = summ.get("training", {})
            last_hist = (tr.get("history") or [{}])[-1]
            rows.append(
                {
                    "run_id": run_id,
                    "model": "module4",
                    "origin": origin,
                    "seed": seed,
                    "val_h5_mae": summ["metrics"]["val_h5_mae"],
                    "val_h10_mae": summ["metrics"]["val_h10_mae"],
                    "val_h20_mae": summ["metrics"]["val_h20_mae"],
                    "test_h5_mae": summ["metrics"]["test_h5_mae"],
                    "test_h10_mae": summ["metrics"]["test_h10_mae"],
                    "test_h20_mae": summ["metrics"]["test_h20_mae"],
                    "best_epoch": tr.get("best_epoch"),
                    "peak_allocated_gb": tr.get("peak_allocated_gb"),
                    "final_loss_perturb": last_hist.get("loss_perturb"),
                    "final_loss_vrex": last_hist.get("loss_vrex"),
                    "final_loss_prior": last_hist.get("loss_prior"),
                    "final_off_bps_mass": last_hist.get("off_bps_mass"),
                    "seconds": summ.get("seconds"),
                    "ckpt_sha256": summ.get("ckpt_sha256"),
                }
            )
    return pd.DataFrame(rows)


def _proxy_regime_table(panel) -> pd.DataFrame:
    """Fallback eval-only climate-regime table derived from dataset_v1 panel columns
    when gitignored data/processed/eval_splits/ is absent on a clean clone.
    Priority matches CGS-H2-04: dry > extreme_wet > el_nino > la_nina > normal.
    """
    df = panel.panel[["date", "prov_code", "dry_spell_days", "extreme_5d", "roni"]].copy()
    df["date"] = pd.to_datetime(df["date"]).astype("datetime64[ns]")
    df["prov_code"] = df["prov_code"].astype(str).str.zfill(2)
    is_dry = df["dry_spell_days"].fillna(0.0) >= 15.0
    is_ext = df["extreme_5d"].fillna(0.0) >= 1.0
    roni = df["roni"].fillna(0.0)
    df["label_primary"] = np.select(
        [is_dry, is_ext, roni >= 0.5, roni <= -0.5],
        ["dry", "extreme_wet", "el_nino", "la_nina"],
        default="normal",
    )
    return df[["date", "prov_code", "label_primary"]]


def _load_eval_split_or_proxy(panel, origin: str, part: str) -> tuple[pd.DataFrame, str]:
    split_path = SPLITS_DIR / f"{origin}_{part}.parquet"
    if split_path.is_file():
        return pd.read_parquet(split_path), "eval_splits"
    return _proxy_regime_table(panel), "panel_climate_proxy"


def evaluate_per_regime_comparison(
    panel, origins: tuple[str, ...], seeds: tuple[int, ...]
) -> tuple[pd.DataFrame, str]:
    """Compare module4 vs Gate 2 module23 and module1 per regime on O1-O3 test/val."""
    records = []
    source_used = "eval_splits"
    model_specs = [
        ("module4", "h5_module4_{origin}_s{seed}"),
        ("module23_g2", "g2_module23_{origin}_s{seed}"),
        ("module1_g2", "g2_module1_{origin}_s{seed}"),
    ]
    for label, pattern in model_specs:
        for origin in origins:
            for part in ("val", "test"):
                split_df, source_used = _load_eval_split_or_proxy(panel, origin, part)
                for seed in seeds:
                    pfile = RUNS / pattern.format(origin=origin, seed=seed) / "preds.parquet"
                    if not pfile.is_file():
                        continue
                    pdf = pd.read_parquet(pfile)
                    pdf = pdf[pdf["part"] == part].copy()
                    pdf["model"] = label
                    pr = per_regime(pdf, split_df)
                    pr["part"] = part
                    records.append(pr)
    return (pd.concat(records, ignore_index=True) if records else pd.DataFrame()), source_used


def _predict_o3_with_mask(model, loader, device, edge, cand_mask, spec, panel) -> pd.DataFrame:
    dates_all, provs_all, h_all, yt_all, ym_all, yp_all = [], [], [], [], [], []
    prior = (edge, cand_mask)
    node_codes = np.asarray(panel.node_codes, dtype=object)
    n_nodes = len(node_codes)
    h_idx = spec.horizons.index(10)
    for batch in loader:
        log_pred, _ = predict(model, batch, device, prior)
        pred = log_pred[:, h_idx, :].float().exp().cpu().numpy()  # [B, N]
        y_true = batch["y"][:, h_idx, :].numpy()
        y_mask = batch["y_mask"][:, h_idx, :].numpy().astype(bool)
        ks = batch["t_index"].numpy()
        b = len(ks)
        dates_all.append(np.repeat(panel.dates[ks].to_numpy(), n_nodes))
        provs_all.append(np.tile(node_codes, b))
        h_all.append(np.full(b * n_nodes, 10, dtype=np.int32))
        yt_all.append(y_true.reshape(-1))
        ym_all.append(y_mask.reshape(-1))
        yp_all.append(pred.reshape(-1))
    out = pd.DataFrame(
        {
            "date": np.concatenate(dates_all),
            "prov_code": np.concatenate(provs_all),
            "h": np.concatenate(h_all),
            "y_true": np.concatenate(yt_all),
            "y_mask": np.concatenate(ym_all),
            "y_pred": np.concatenate(yp_all),
        }
    )
    out.loc[~out["y_mask"], "y_true"] = np.nan
    return out


def evaluate_o3_perturbation_robustness(
    panel, cfg_m4: dict, seeds: tuple[int, ...]
) -> pd.DataFrame:
    """Head-to-head test-mode perturbation robustness on O3: module4 vs Gate 2 module23."""
    cfg_m23 = copy.deepcopy(
        yaml.safe_load((ROOT / "configs/models/gate2/module23.yaml").read_text(encoding="utf-8"))
    )
    cfg_m23["global"] = cfg_m4["global"]
    masks = list(perturbation_grid(panel.mask))
    split_test, _ = _load_eval_split_or_proxy(panel, "O3", "test")
    split_test = split_test.copy()
    split_test["date"] = pd.to_datetime(split_test["date"]).astype("datetime64[ns]")
    split_test["prov_code"] = split_test["prov_code"].astype(str).str.zfill(2)

    edge_all, _, _ = module4_edge_tensors(panel, "soft_bps")
    rows = []

    for seed in seeds:
        # Prepare O3 loaders once per seed
        m4, spec, loaders, device, _, _ = prepare_module4(panel, cfg_m4, cfg_m4["global"], "O3", seed, ("test",))
        edge_dev = edge_all.to(device)
        m4_ckpt = torch.load(RUNS / f"h5_module4_O3_s{seed}" / "ckpt.pt", map_location="cpu", weights_only=True)
        m4.load_state_dict(m4_ckpt["model_state_dict"])
        m4.to(device).eval()

        m23 = build_module23(panel, cfg_m23, spec)
        m23_ckpt = torch.load(RUNS / f"g2_module23_O3_s{seed}" / "ckpt.pt", map_location="cpu", weights_only=True)
        m23.load_state_dict(m23_ckpt["state_dict"])
        m23.to(device).eval()

        # Also include soft_full (unperturbed soft_bps ~eye(N)) as reference for module4
        full_offdiag = ~np.eye(panel.mask.shape[0], dtype=bool)
        eval_masks = [("soft_full", full_offdiag, "soft_full", 0.0, -1), *masks]

        for model_label, net in (("module4", m4), ("module23_g2", m23)):
            for mask_name, mask_arr, op, frac, pert_seed in eval_masks:
                if model_label == "module23_g2" and op == "soft_full":
                    continue
                cand = torch.as_tensor(mask_arr > 0, dtype=torch.bool, device=device)
                preds = _predict_o3_with_mask(net, loaders["test"], device, edge_dev, cand, spec, panel)
                merged = preds.merge(
                    split_test[["date", "prov_code", "label_primary"]],
                    on=["date", "prov_code"],
                    how="left",
                    validate="many_to_one",
                )
                v10 = merged[
                    (merged["h"] == 10)
                    & merged["y_mask"].astype(bool)
                    & np.isfinite(merged["y_true"])
                    & np.isfinite(merged["y_pred"])
                ]
                overall_mae = mae(v10["y_true"], v10["y_pred"])
                rows.append(
                    {
                        "model": model_label,
                        "seed": seed,
                        "mask_name": mask_name,
                        "op": op,
                        "p": float(frac),
                        "pert_seed": int(pert_seed),
                        "regime": "ALL",
                        "mae_h10": overall_mae,
                        "n": int(len(v10)),
                    }
                )
                for reg_name, g in v10.groupby("label_primary"):
                    rows.append(
                        {
                            "model": model_label,
                            "seed": seed,
                            "mask_name": mask_name,
                            "op": op,
                            "p": float(frac),
                            "pert_seed": int(pert_seed),
                            "regime": str(reg_name),
                            "mae_h10": mae(g["y_true"], g["y_pred"]),
                            "n": int(len(g)),
                        }
                    )
        print(f"[robustness O3] seed {seed} done (module4 vs module23_g2, 47 masks)", flush=True)
    return pd.DataFrame(rows)


def plot_robustness(rob_df: pd.DataFrame, out_dir: Path) -> None:
    if rob_df.empty:
        return
    sub = rob_df[rob_df["regime"] == "ALL"]
    ops = ("drop", "add", "rewire")
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0), sharey=True)
    colors = {"module4": "#1b7837", "module23_g2": "#762a83"}
    labels = {"module4": "Module 4 (robustness objective)", "module23_g2": "Module 2-3 (Gate 2, 10 ep)"}
    for ax, op in zip(axes, ops):
        for m in ("module23_g2", "module4"):
            g = sub[(sub["model"] == m) & (sub["op"] == op)]
            agg = g.groupby("p")["mae_h10"].agg(["mean", "std"]).reset_index()
            clean = sub[(sub["model"] == m) & (sub["op"] == "clean")]["mae_h10"].mean()
            ax.plot(agg["p"] * 100, agg["mean"], marker="o", linewidth=2, color=colors[m], label=labels[m])
            ax.axhline(clean, linestyle="--", linewidth=1, color=colors[m], alpha=0.65)
        ax.set_title(f"Perturbasi: {op}")
        ax.set_xlabel("Fraksi perturbasi p (%)")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("O3 Test h=10 MAE (Rp/kg)")
    axes[0].legend(fontsize=8, loc="best")
    fig.suptitle("MLE-H5-04: Ketahanan Perturbasi Graf pada Uji O3 (5 Seed x 3 Perturbation Seed)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_module4_robustness.png", dpi=200)
    plt.close(fig)


def write_summary_report(
    runs_df: pd.DataFrame,
    reg_df: pd.DataFrame,
    rob_df: pd.DataFrame,
    out_dir: Path,
    regime_source: str = "eval_splits",
) -> None:
    g2_summ = pd.read_csv(ROOT / "reports/h5/gate2_validation_summary.csv")
    m23_row = g2_summ[g2_summ["model"] == "module23"].iloc[0]
    m1_row = g2_summ[g2_summ["model"] == "module1"].iloc[0]

    o_val = [runs_df[runs_df["origin"] == o]["val_h10_mae"].mean() for o in ("O1", "O2", "O3")]
    o_test = [runs_df[runs_df["origin"] == o]["test_h10_mae"].mean() for o in ("O1", "O2", "O3")]
    o_val_cv = [
        runs_df[runs_df["origin"] == o]["val_h10_mae"].std()
        / runs_df[runs_df["origin"] == o]["val_h10_mae"].mean()
        * 100
        for o in ("O1", "O2", "O3")
    ]
    o_test_cv = [
        runs_df[runs_df["origin"] == o]["test_h10_mae"].std()
        / runs_df[runs_df["origin"] == o]["test_h10_mae"].mean()
        * 100
        for o in ("O1", "O2", "O3")
    ]

    lines = [
        "# Laporan MLE-H5-04: Modul 4 (Tujuan Pelatihan Tahan-Perturbasi & Lintas-Regime)",
        "",
        "- **Status Gate 2**: Modul 4 (`MLE-H5-04`) adalah *stretch goal* yang **TIDAK mengubah** paket beku `gate2-freeze` (`b0d0ff9`) maupun `frozen/manifest.yaml` (tetap tercatat di `excluded` untuk holdout Sprint 1). Seluruh evaluasi dilakukan **strictly pada `dataset_v1` (`O1–O3`, `< 2026-06-01`)**.",
        "- **Tiga komponen tujuan pelatihan Modul 4 (`src/renaro/models/module4.py`)**:",
        "  1. **Penalti sensitivitas perturbasi graf**: `lambda_perturb * ||f(X, A) - f(X, A_tilde)||_1` (`lambda_perturb = 0.15`), dengan `A_tilde` dibentuk dari perturbasi acak `candidate_mask` per batch (`p in [0.10, 0.50]`, campuran edge-dropout & perturbasi `drop/add/rewire` pada prior BPS).",
        "  2. **Risiko lintas-regime (V-REx kausal)**: `lambda_group_var * Var_g(R_g)` (`lambda_group_var = 5.0`), dengan `3` kelompok kuantil dibentuk **murni dari fitur iklim as-of `<= t`** (agregat asal `rain_30d_anom` 5 hari kerja terakhir; **0 akses `regime_labels.csv`** saat pelatihan).",
        "  3. **Regularisasi prior lunak**: `lambda_prior * ||A * (1 - M_bps)||_1` (`lambda_prior = 0.05`) di atas `candidate_mask` off-diagonal penuh (`prior: soft_bps`), sehingga model dapat memanfaatkan edge non-BPS saat prior meleset namun tetap tertarik lunak ke `M_bps`.",
        f"- **VRAM Puncak GPU**: `{runs_df['peak_allocated_gb'].max():.3f} GB` (< batas protokol `3,00 GB`).",
        f"- **Fraksi Massa Perhatian Non-BPS (`off_bps_mass`) akhir rata-rata**: `{runs_df['final_off_bps_mass'].mean():.3f}`.",
        "",
        "## 1. Perbandingan Head-to-Head O1-O3 (Seragam 10 Epoch, 5 Seed `0..4`, `h=10 MAE` Rp/kg)",
        "",
        "| Model | `Val O1` | `Val O2` | `Val O3` | `Val 3-Origin Avg` | `Val Max CV` | `Test O1` | `Test O2` | `Test O3` | `Test 3-Origin Avg` | `Test Max CV` |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `module1` (Gate 2, 10 ep) | {m1_row['val_O1']:,.2f} | {m1_row['val_O2']:,.2f} | {m1_row['val_O3']:,.2f} | {m1_row['val_3origin_avg']:,.2f} | {m1_row['val_max_cv_pct']:.2f}% | {m1_row['test_O1']:,.2f} | {m1_row['test_O2']:,.2f} | {m1_row['test_O3']:,.2f} | {m1_row['test_3origin_avg']:,.2f} | {m1_row['test_max_cv_pct']:.2f}% |",
        f"| `module23` (Gate 2, 10 ep) | {m23_row['val_O1']:,.2f} | {m23_row['val_O2']:,.2f} | {m23_row['val_O3']:,.2f} | {m23_row['val_3origin_avg']:,.2f} | {m23_row['val_max_cv_pct']:.2f}% | {m23_row['test_O1']:,.2f} | {m23_row['test_O2']:,.2f} | {m23_row['test_O3']:,.2f} | {m23_row['test_3origin_avg']:,.2f} | {m23_row['test_max_cv_pct']:.2f}% |",
        f"| **`module4` (`MLE-H5-04`, 10 ep)** | **{o_val[0]:,.2f}** | **{o_val[1]:,.2f}** | **{o_val[2]:,.2f}** | **{np.mean(o_val):,.2f}** | **{np.nanmax(o_val_cv):.2f}%** | **{o_test[0]:,.2f}** | **{o_test[1]:,.2f}** | **{o_test[2]:,.2f}** | **{np.mean(o_test):,.2f}** | **{np.nanmax(o_test_cv):.2f}%** |",
        "",
    ]

    if not reg_df.empty:
        t10 = reg_df[(reg_df["part"] == "test") & (reg_df["h"] == 10)]
        piv = (
            t10.groupby(["model", "regime"])["mae"]
            .mean()
            .unstack("regime")
        )
        worst = piv.max(axis=1)
        reg_note = (
            "sumber: `data/processed/eval_splits/` (khusus evaluasi)"
            if regime_source == "eval_splits"
            else "sumber: proxy evaluasi iklim `dataset_v1/panel.parquet` (`dry_spell_days>=15`, `extreme_5d>=1`, `|roni|>=0.5`) karena `eval_splits/` ter-gitignore; 0 akses saat pelatihan"
        )
        lines += [
            f"## 2. Evaluasi Lintas-Regime Uji `O1-O3` (`h=10 MAE` Rp/kg; {reg_note})",
            "",
            "| Model | " + " | ".join(f"`{c}`" for c in piv.columns) + " | **Worst-Regime MAE** | **Std Lintas-Regime** |",
            "| :--- | " + " | ".join("---:" for _ in piv.columns) + " | ---: | ---: |",
        ]
        for mname in piv.index:
            vals = " | ".join(f"{piv.loc[mname, c]:,.2f}" for c in piv.columns)
            lines.append(
                f"| `{mname}` | {vals} | **{worst.loc[mname]:,.2f}** | {piv.loc[mname].std():,.2f} |"
            )
        lines.append("")

    if not rob_df.empty:
        sub = rob_df[rob_df["regime"] == "ALL"]
        lines += [
            "## 3. Uji Ketahanan Perturbasi Graf pada Uji `O3` (`h=10 MAE` Rp/kg, 5 Seed x 3 Perturbation Seed)",
            "",
            "| Model | `clean` (`M_bps`) | `none` (0 edge) | `drop` `p=50%` (delta vs clean) | `add` `p=50%` (delta vs clean) | `rewire` `p=50%` (delta vs clean) | Rata-rata `|delta|` `p=10..50%` |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for mname in ("module23_g2", "module4"):
            msub = sub[sub["model"] == mname]
            c_mae = msub[msub["op"] == "clean"]["mae_h10"].mean()
            n_mae = msub[msub["op"] == "none"]["mae_h10"].mean()
            d50 = msub[(msub["op"] == "drop") & (msub["p"].round(2) == 0.5)]["mae_h10"].mean()
            a50 = msub[(msub["op"] == "add") & (msub["p"].round(2) == 0.5)]["mae_h10"].mean()
            r50 = msub[(msub["op"] == "rewire") & (msub["p"].round(2) == 0.5)]["mae_h10"].mean()
            all_p = msub[msub["op"].isin(("drop", "add", "rewire"))]["mae_h10"]
            mean_abs_delta = float((all_p - c_mae).abs().mean())
            lines.append(
                f"| `{mname}` | {c_mae:,.2f} | {n_mae:,.2f} ({n_mae - c_mae:+.2f}) | "
                f"{d50:,.2f} ({d50 - c_mae:+.2f}) | {a50:,.2f} ({a50 - c_mae:+.2f}) | "
                f"{r50:,.2f} ({r50 - c_mae:+.2f}) | **{mean_abs_delta:,.2f}** |"
            )
        sf = sub[(sub["model"] == "module4") & (sub["op"] == "soft_full")]["mae_h10"].mean()
        lines += [
            "",
            f"- Referensi `module4` dengan mask pelatihan `soft_full` (`~eye(34)`): `O3 Test h=10 MAE = {sf:,.2f} Rp/kg`.",
            "- Figur kurva ketahanan perturbasi: `reports/module4/fig_module4_robustness.png`.",
            "",
        ]

    (out_dir / "module4_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--origins", default="O1,O2,O3")
    ap.add_argument("--seeds", default="0,1,2,3,4")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--skip-robustness", action="store_true")
    args = ap.parse_args()

    origins = tuple(x.strip() for x in args.origins.split(",") if x.strip())
    seeds = tuple(int(x.strip()) for x in args.seeds.split(",") if x.strip())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = copy.deepcopy(yaml.safe_load((ROOT / "configs/models/module4.yaml").read_text(encoding="utf-8")))
    cfg["global"] = yaml.safe_load((ROOT / "configs/global.yaml").read_text(encoding="utf-8"))
    if args.smoke:
        cfg["epochs"] = 2
        cfg["patience"] = 2

    panel = load_panel(ROOT / "data/processed/dataset_v1")
    runs_df = train_grid(panel, cfg, origins, seeds, force=args.force, smoke=args.smoke)
    if args.smoke:
        print("[smoke ok]", runs_df[["run_id", "val_h10_mae", "test_h10_mae", "peak_allocated_gb"]].to_string(index=False))
        return

    runs_df.to_csv(OUT_DIR / "module4_runs.csv", index=False)
    reg_df, regime_source = evaluate_per_regime_comparison(panel, origins, seeds)
    if not reg_df.empty:
        reg_df.to_csv(OUT_DIR / "module4_per_regime.csv", index=False)

    rob_df = pd.DataFrame()
    if not args.skip_robustness and "O3" in origins:
        rob_df = evaluate_o3_perturbation_robustness(panel, cfg, seeds)
        rob_df.to_csv(OUT_DIR / "module4_robustness.csv", index=False)
        plot_robustness(rob_df, OUT_DIR)

    write_summary_report(runs_df, reg_df, rob_df, OUT_DIR, regime_source=regime_source)
    print(f"[DONE] Module 4 artifacts written to {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
