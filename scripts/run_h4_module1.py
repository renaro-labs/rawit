#!/usr/bin/env python3
"""H4-01: run/tune Module 1 on the real dataset and save attention artefacts."""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

from renaro.baselines.naive import asof_prices
from renaro.data.io import load_panel
from renaro.models.module1_training import evaluate, fit, predict, prepare

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
REGISTRY = ROOT / "experiments/registry.csv"
REPORT = ROOT / "reports/mle"
TUNE_EPOCHS = 5


def load_cfg(path: Path, glob: dict, *, epochs: int, hidden: int | None = None,
             lr: float | None = None, n_lags: int | None = None,
             prior: str = "bps", batch_size: int = 32) -> dict:
    cfg = copy.deepcopy(yaml.safe_load(path.read_text()))
    cfg["global"] = glob
    cfg["epochs"] = int(epochs)
    cfg["patience"] = min(int(cfg.get("patience", 10)), 10)
    cfg["batch_size"] = int(batch_size)
    cfg["prior"] = prior
    cfg["model"] = "module1"
    cfg["zero_climate"] = False
    if hidden is not None:
        cfg["hidden"] = int(hidden)
    if lr is not None:
        cfg["lr"] = float(lr)
    if n_lags is not None:
        cfg["n_lags"] = int(n_lags)
    return cfg


def metrics_from_preds(preds: pd.DataFrame) -> dict:
    out = {}
    for (part, h), group in preds.groupby(["part", "h"]):
        common = group[group["y_mask"].astype(bool) & np.isfinite(group["y_true"]) &
                       np.isfinite(group["y_pred"])]
        out[f"{part}_h{int(h)}_mae"] = float((common["y_true"] - common["y_pred"]).abs().mean())
        out[f"{part}_h{int(h)}_n"] = int(len(common))
    return out


def append_registry(run_id: str, model: str, origin: str, seed: int,
                    split_hash: str, val_mae: float) -> None:
    fields = ["run_id", "model", "origin", "seed", "split_hash", "val_mae", "status"]
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    exists = REGISTRY.exists() and REGISTRY.stat().st_size > 0
    with REGISTRY.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({"run_id": run_id, "model": model, "origin": origin, "seed": seed,
                    "split_hash": split_hash, "val_mae": val_mae, "status": "completed"})


def attention_by_regime(panel, labels: pd.DataFrame, loader, model, device, prior, spec):
    """Average A[:, i, :, :] by the destination province's regime label."""
    key = labels.set_index(["date", "prov_code"])["label_primary"]
    regimes = ("dry", "extreme_wet", "el_nino", "la_nina", "normal")
    n = len(panel.node_codes)
    l = int(spec.horizons and model.n_lags)
    sums = {r: np.zeros((n, n, model.n_lags), dtype=np.float64) for r in regimes}
    counts = {r: np.zeros(n, dtype=np.int64) for r in regimes}
    with torch.no_grad():
        for batch in loader:
            _, a = predict(model, batch, device, prior)
            a = a.detach().cpu().numpy()
            for s, k in enumerate(batch["t_index"].tolist()):
                date = panel.dates[k]
                for i, code in enumerate(panel.node_codes):
                    label = key.get((date, str(code)))
                    if label in sums:
                        sums[label][i] += a[s, i]
                        counts[label][i] += 1
    out = {}
    for r in regimes:
        c = counts[r]
        arr = np.divide(sums[r], c[:, None, None], out=np.zeros_like(sums[r]),
                        where=c[:, None, None] > 0)
        out[f"A_{r}"] = arr.astype(np.float32)
        out[f"n_{r}"] = c
    return out


def train_one(panel, cfg, origin: str, seed: int, *, out: Path | None = None,
              checkpoint: Path | None = None, collect_attention: bool = False,
              labels: pd.DataFrame | None = None):
    glob = cfg["global"]
    model, spec, loaders, device, prior = prepare(panel, cfg, glob, origin, seed, ("val", "test"))
    stats = fit(model, loaders["train"], loaders["val"], device=device, a_prior=prior,
                lr=float(cfg["lr"]), epochs=int(cfg["epochs"]), patience=int(cfg["patience"]),
                grad_clip=float(cfg["grad_clip"]), amp=bool(cfg["amp"]), checkpoint=checkpoint,
                entropy_lambda=float(cfg.get("entropy_lambda", 0.0)))
    prices = asof_prices(panel)
    frames, att = [], None
    for part in ("val", "test"):
        for batch in loaders[part]:
            log_pred, _ = predict(model, batch, device, prior)
            pred = log_pred.float().exp().cpu().numpy()
            for i, k in enumerate(batch["t_index"].tolist()):
                for j, h in enumerate(spec.horizons):
                    frames.append(pd.DataFrame({
                        "model": "module1", "fold": origin, "seed": seed, "part": part,
                        "date": panel.dates[k], "target_date": panel.dates[k + h - 1],
                        "prov_code": list(panel.node_codes), "h": h,
                        "y_true": batch["y"][i, j].numpy(),
                        "y_mask": batch["y_mask"][i, j].numpy(),
                        "y_pred": pred[i, j],
                        "naive_pred": prices.iloc[k].to_numpy(),
                    }))
    preds = pd.concat(frames, ignore_index=True)
    preds.loc[~preds["y_mask"].astype(bool), "y_true"] = np.nan
    if collect_attention:
        if labels is None:
            labels = pd.read_csv(ROOT / "data/interim/regime_labels.csv", dtype={"prov_code": str})
            labels["date"] = pd.to_datetime(labels["date"]).astype("datetime64[ns]")
        att = attention_by_regime(panel, labels, loaders["val"], model, device, prior, spec)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        preds.to_csv(out / "preds.csv", index=False)
        summary = {"model": "module1", "origin": origin, "seed": seed, "prior": cfg["prior"],
                   "split_hash": panel.split_hash, "config": cfg, "training": stats,
                   "metrics": metrics_from_preds(preds), "epochs": int(cfg["epochs"]),
                   "batch_size": int(cfg["batch_size"])}
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if att is not None:
            np.savez_compressed(out / "A_by_regime.npz", **att)
        val_mae = metrics_from_preds(preds)["val_h10_mae"]
        append_registry(out.name, "module1", origin, seed, panel.split_hash, val_mae)
    return preds, stats, att


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("tune", "run"), required=True)
    ap.add_argument("--origin", default="O1")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--prior", choices=("bps", "none"), default="bps")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--hidden", type=int)
    ap.add_argument("--lr", type=float)
    ap.add_argument("--n-lags", type=int)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    path = ROOT / "configs/models/module1.yaml"
    glob = yaml.safe_load((ROOT / "configs/global.yaml").read_text())
    panel = load_panel(ROOT / "data/processed/dataset_v1")
    if args.mode == "tune":
        REPORT.mkdir(parents=True, exist_ok=True)
        rows = []
        for hidden in (32, 64):
            for lr in (1e-3, 3e-4):
                for n_lags in (6, 8):
                    cfg = load_cfg(path, glob, epochs=TUNE_EPOCHS, hidden=hidden, lr=lr,
                                   n_lags=n_lags, prior="bps")
                    cfg["model"] = "module1"
                    _, stats, _ = train_one(panel, cfg, "O1", 0)
                    rows.append({"hidden": hidden, "lr": lr, "n_lags": n_lags,
                                 "val_mae": stats["best_val_mae_rp"],
                                 "best_epoch": stats["best_epoch"]})
                    print(rows[-1], flush=True)
        best = min(rows, key=lambda r: r["val_mae"])
        (REPORT / "h4_module1_tuning.json").write_text(json.dumps({"rows": rows, "best": best}, indent=2))
        print("BEST", best)
        return
    out = args.out or (RUNS / f"h4_module1_{args.origin}_{args.prior}_s{args.seed}")
    cfg = load_cfg(path, glob, epochs=args.epochs, hidden=args.hidden, lr=args.lr,
                   n_lags=args.n_lags, prior=args.prior, batch_size=args.batch_size)
    labels = pd.read_csv(ROOT / "data/interim/regime_labels.csv", dtype={"prov_code": str})
    labels["date"] = pd.to_datetime(labels["date"]).astype("datetime64[ns]")
    train_one(panel, cfg, args.origin, args.seed, out=out,
              checkpoint=out / "best.pt", collect_attention=True, labels=labels)
    print("DONE", out)


if __name__ == "__main__":
    main()
