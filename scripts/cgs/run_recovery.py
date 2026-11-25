#!/usr/bin/env python3
"""CGS/MLE-H3-01: synthetic lag-recovery diagnostics for Module 1.

Evaluates:
- module1 trained on synth/default (5 seeds)
- module1 trained on synth/unconditioned (5 seeds)
- e_j=0/no-climate inference control on the default checkpoints

Outputs reports/synth/recovery_metrics.csv, recovery_summary.md and
lag_true_vs_hat.parquet. Only synthetic data; no real holdout.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from renaro.data.datasets import CLIMATE_FEATURES, FEATURES
from renaro.data.io import load_panel
from renaro.contract import PROV_CODES
from renaro.eval.splits import load_global_config
from renaro.models.module1_training import fit, prepare

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "experiments/runs"
OUT = ROOT / "reports/synth"


def load_checkpoint(path: Path):
    data = torch.load(path, map_location="cpu")
    return data["model_state_dict"] if "model_state_dict" in data else data


def edge_metrics(A: np.ndarray, t_index: np.ndarray, truth: dict, regime: str):
    G = truth["G"].astype(bool)
    lag_n = truth["lag_normal"]
    lag_d = truth["lag_dry"]
    dry = truth["dry"]
    rows = []
    expected = {}
    true_lag = {}
    for i, j in zip(*np.nonzero(G)):
        source_dry = dry[t_index, j]
        selected = source_dry if regime == "dry" else ~source_dry
        if not selected.any():
            continue
        mean_a = A[selected, i, j, :].mean(axis=0)
        mass = float(mean_a.sum())
        norm = mean_a / mass if mass > 1e-12 else np.full_like(mean_a, np.nan)
        expected[(int(i), int(j))] = float(np.sum((np.arange(1, 9) * norm))) if np.isfinite(norm).all() else np.nan
        true_lag[(int(i), int(j))] = int(lag_d[i, j] if regime == "dry" else lag_n[i, j])
        lag_hat = int(np.argmax(mean_a) + 1) if mass > 1e-12 else np.nan
        rows.append({
            "origin": PROV_CODES[int(j)], "dest": PROV_CODES[int(i)],
            "lag_true": true_lag[(int(i), int(j))], "lag_hat": lag_hat,
            "expected_lag": expected[(int(i), int(j))],
            "mass": mass,
        })
    keys = sorted(expected)
    exp = np.array([expected[k] for k in keys], dtype=float)
    tru = np.array([true_lag[k] for k in keys], dtype=float)
    ok = np.isfinite(exp) & np.isfinite(tru)
    rho = float(spearmanr(exp[ok], tru[ok]).statistic) if ok.sum() > 2 else float("nan")
    lag_acc = float(np.mean([r["lag_hat"] == r["lag_true"] for r in rows])) if rows else float("nan")
    lag_mae = float(np.nanmean([abs(r["lag_hat"] - r["lag_true"]) for r in rows])) if rows else float("nan")
    # Edge AUROC: pooled over samples and ordered edges, using total attention mass.
    scores, labels = [], []
    for s, t in enumerate(t_index):
        for i, j in zip(*np.nonzero(G)):
            if bool(dry[t, j]) != (regime == "dry"):
                continue
            scores.append(float(A[s, i, j, :].sum()))
            labels.append(1)
        for i in range(G.shape[0]):
            for j in range(G.shape[1]):
                if i != j and not G[i, j] and bool(dry[t, j]) == (regime == "dry"):
                    scores.append(float(A[s, i, j, :].sum()))
                    labels.append(0)
    try:
        auroc = float(roc_auc_score(labels, scores)) if len(set(labels)) > 1 else float("nan")
    except Exception:
        auroc = float("nan")
    return rows, {"lag_acc": lag_acc, "lag_mae": lag_mae, "spearman": rho,
                  "auroc": auroc, "n_edges": len(rows)}


def eval_model(model, loader, truth, device, cfg, *, no_climate=False):
    model.eval()
    a_parts, t_parts = [], []
    edge = torch.as_tensor(np.zeros((34, 34, 4), dtype=np.float32), device=device)
    # Use the BPS prior from the synthetic panel via the loader caller's model prior.
    # model forward needs edge/candidate; caller passes a closure through `prior`.
    raise RuntimeError("eval_model requires prior; use evaluate_with_prior")


def collect_attention(model, loader, device, prior, *, no_climate=False):
    edge, cand = prior
    edge = edge.to(device); cand = cand.to(device)
    clim_idx = [FEATURES.index(f) for f in CLIMATE_FEATURES]
    out_a, out_t = [], []
    model.eval()
    with torch.no_grad():
        for batch in loader:
            x = batch["X"].to(device).clone()
            c = batch["C"].to(device).clone()
            cal = batch["cal"].to(device)
            if no_climate:
                x[:, :, :, clim_idx] = 0
                c.zero_()
                model.no_climate = True
            else:
                model.no_climate = False
            _, a = model(x, c, edge, cand, cal)
            out_a.append(a.detach().cpu().numpy())
            out_t.extend(batch["t_index"].tolist())
    return np.concatenate(out_a, axis=0), np.asarray(out_t, dtype=int)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "configs/models/module1.yaml").read_text())
    glob = load_global_config()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    all_rows, metrics = [], []
    for data_variant in ("default", "unconditioned"):
        data = ROOT / "data/synth" / data_variant
        panel = load_panel(data)
        truth = {k: np.load(data / "truth.npz")[k] for k in ("G", "lag_normal", "lag_dry", "dry")}
        for seed in args.seeds:
            if data_variant == "default":
                ckpt = RUNS / f"module1_synth_O1_s{seed}/best.pt"
                if not ckpt.is_file():
                    raise FileNotFoundError(ckpt)
                model, spec, loaders, device, prior = prepare(panel, cfg, glob, "O1", seed, ("test",))
                model.load_state_dict(load_checkpoint(ckpt))
                model.to(device)
                variants = [("module1_default", False)]
            else:
                ckpt = RUNS / f"module1_uncond_O1_s{seed}/best.pt"
                model, spec, loaders, device, prior = prepare(panel, cfg, glob, "O1", seed, ("val", "test"))
                if not ckpt.is_file():
                    ckpt.parent.mkdir(parents=True, exist_ok=True)
                    fit(model, loaders["train"], loaders["val"], device=device, a_prior=prior,
                        lr=float(cfg["lr"]), epochs=args.epochs, patience=10,
                        grad_clip=float(cfg["grad_clip"]), amp=bool(cfg["amp"]),
                        checkpoint=ckpt, entropy_lambda=float(cfg.get("entropy_lambda", 0)))
                model.load_state_dict(load_checkpoint(ckpt))
                model.to(device)
                variants = [("module1_unconditioned", False)]
            for variant, no_climate in variants:
                A, t = collect_attention(model, loaders["test"], device, prior, no_climate=no_climate)
                for regime in ("normal", "dry"):
                    rows, m = edge_metrics(A, t, truth, regime)
                    for r in rows:
                        r.update(seed=seed, data_variant=data_variant, model_variant=variant, regime=regime)
                    all_rows.extend(rows)
                    m.update(seed=seed, data_variant=data_variant, model_variant=variant, regime=regime,
                             delta_lag=np.nan)
                    metrics.append(m)
                # no-climate control: use the default checkpoint, but zero climate at inference.
                if data_variant == "default":
                    A0, t0 = collect_attention(model, loaders["test"], device, prior, no_climate=True)
                    for regime in ("normal", "dry"):
                        rows, m = edge_metrics(A0, t0, truth, regime)
                        for r in rows:
                            r.update(seed=seed, data_variant=data_variant, model_variant="module1_no_climate", regime=regime)
                        all_rows.extend(rows)
                        m.update(seed=seed, data_variant=data_variant, model_variant="module1_no_climate",
                                 regime=regime, delta_lag=np.nan)
                        metrics.append(m)
    # Delta lag per seed/variant from normal/dry expected lags.
    frame = pd.DataFrame(all_rows)
    met = pd.DataFrame(metrics)
    deltas = []
    for (seed, dv, mv), group in frame.groupby(["seed", "data_variant", "model_variant"]):
        n = group[group.regime == "normal"].set_index(["origin", "dest"])["expected_lag"]
        d = group[group.regime == "dry"].set_index(["origin", "dest"])["expected_lag"]
        common = n.index.intersection(d.index)
        delta = float((d.loc[common] - n.loc[common]).mean()) if len(common) else float("nan")
        for regime in ("normal", "dry"):
            met.loc[(met.seed == seed) & (met.data_variant == dv) &
                    (met.model_variant == mv) & (met.regime == regime), "delta_lag"] = delta
    args.out.mkdir(parents=True, exist_ok=True)
    met.to_csv(args.out / "recovery_metrics.csv", index=False)
    frame.to_parquet(args.out / "lag_true_vs_hat.parquet", index=False)
    # Summary with explicit protocol thresholds.
    lines = [
        "# CGS/MLE-H3-01 — synthetic lag recovery",
        "",
        "Evaluasi pada test set sintetis; 5 seed; Module 1 default, unconditioned, dan kontrol e_j=0.",
        "Ambang protokol v1 §5.5: Spearman > 0.70 (multi-edge), MAE lag ≤ 1.0 pentad, AUROC > 0.85.",
        "Tabel di bawah adalah rata-rata 5 seed; detail per seed ada di `recovery_metrics.csv`.",
        "",
        "| data | model | regime | n_seed | lag_acc | MAE lag | Spearman | AUROC | Δlag |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    grouped = met.groupby(["data_variant", "model_variant", "regime"], as_index=False).agg(
        n_seed=("seed", "nunique"),
        lag_acc=("lag_acc", "mean"),
        lag_mae=("lag_mae", "mean"),
        spearman=("spearman", "mean"),
        auroc=("auroc", "mean"),
        delta_lag=("delta_lag", "mean"),
    )
    for _, r in grouped.sort_values(["data_variant", "model_variant", "regime"]).iterrows():
        lines.append(f"| {r.data_variant} | {r.model_variant} | {r.regime} | {int(r.n_seed)} | "
                     f"{r.lag_acc:.3f} | {r.lag_mae:.3f} | {r.spearman:.3f} | "
                     f"{r.auroc:.3f} | {r.delta_lag:.3f} |")
    default = met[(met.data_variant == "default") & (met.model_variant == "module1_default")]
    controls = met[met.model_variant.isin(["module1_unconditioned", "module1_no_climate"])]
    n_seeds = int(default["seed"].nunique())
    # Protocol threshold is the multi-edge overall level; dry-only is reported
    # separately in the table rather than silently replacing the overall result.
    ok_spearman = bool(default["spearman"].mean() > 0.70)
    ok_mae = bool(default["lag_mae"].mean() <= 1.0)
    ok_auroc = bool(default["auroc"].mean() > 0.85)
    ctrl_delta = float(controls["delta_lag"].abs().mean()) if len(controls) else float("nan")
    lines += [
        "",
        "## Kesimpulan",
        "",
        f"- Module 1 default (rata-rata normal+dry, {n_seeds} seed): Spearman "
        f"{'LULUS' if ok_spearman else 'TIDAK LULUS'} (ambang >0.70), "
        f"MAE lag {'LULUS' if ok_mae else 'TIDAK LULUS'} (ambang ≤1.0), "
        f"AUROC {'LULUS' if ok_auroc else 'TIDAK LULUS'} (ambang >0.85).",
        f"- Δlag default rata-rata = {default['delta_lag'].mean():.3f} (nilai benar sintetis = 2.0); "
        "dry-only tetap dilaporkan pada tabel.",
        f"- Kontrol tanpa iklim/unconditioned: |Δlag| rata-rata = {ctrl_delta:.3f} (harus mendekati 0).",
        f"- Kesimpulan: **{'LULUS' if (n_seeds == 5 and ok_spearman and ok_mae and ok_auroc and ctrl_delta < 0.25) else 'TIDAK LULUS'}** terhadap ambang protokol v1.",
        "",
    ]
    (args.out / "recovery_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(met.to_string(index=False))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
