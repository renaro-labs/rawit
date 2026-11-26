#!/usr/bin/env python3
"""MLE-H5-02: five-variant ablation on validation folds."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

from renaro.data.io import load_panel
from renaro.eval.metrics import mae, rmse, smape
from renaro.models.module1_training import fit, predict, prepare
from renaro.models.module23 import build

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
OUT = ROOT / "reports/ablation"
VARIANTS = ("full", "no_climate", "no_lag", "no_gate", "no_calendar")


def variant_config(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    cfg = copy.deepcopy(yaml.safe_load((ROOT / "configs/models/module23.yaml").read_text()))
    cfg["global"] = yaml.safe_load((ROOT / "configs/global.yaml").read_text())
    cfg["model"] = "module23"
    if variant == "no_climate":
        cfg["zero_climate"] = True
        cfg["no_climate_gate"] = True
    elif variant == "no_lag":
        cfg["n_lags"] = 1
    elif variant == "no_gate":
        cfg["no_gate"] = True
    elif variant == "no_calendar":
        cfg["no_calendar"] = True
    return cfg


def _val_preds(panel, cfg: dict, origin: str, seed: int) -> pd.DataFrame:
    model, spec, loaders, device, prior = prepare(
        panel, cfg, cfg["global"], origin, seed, ("val",), model_factory=build)
    fit(model, loaders["train"], loaders["val"], device=device, a_prior=prior,
        lr=float(cfg["lr"]), epochs=int(cfg["epochs"]), patience=int(cfg["patience"]),
        grad_clip=float(cfg["grad_clip"]), amp=bool(cfg["amp"]),
        entropy_lambda=float(cfg.get("entropy_lambda", 0.0)))
    frames = []
    for batch in loaders["val"]:
        log_pred, _ = predict(model, batch, device, prior)
        pred = log_pred.float().exp().cpu().numpy()
        for i, k in enumerate(batch["t_index"].tolist()):
            for j, h in enumerate(spec.horizons):
                frames.append(pd.DataFrame({
                    "variant": cfg["variant"], "origin": origin, "seed": seed,
                    "part": "val", "date": panel.dates[k],
                    "prov_code": list(panel.node_codes), "h": h,
                    "y_true": batch["y"][i, j].numpy(),
                    "y_mask": batch["y_mask"][i, j].numpy(),
                    "y_pred": pred[i, j],
                }))
    out = pd.concat(frames, ignore_index=True)
    out.loc[~out["y_mask"].astype(bool), "y_true"] = np.nan
    return out


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=VARIANTS, required=True)
    ap.add_argument("--origin", required=True)
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    cfg = variant_config(args.variant)
    cfg["variant"] = args.variant
    panel = load_panel(ROOT / "data/processed/dataset_v1")
    run_id = f"ablation_{args.variant}_{args.origin}_s{args.seed}"
    out = RUNS / run_id
    if out.exists():
        raise FileExistsError(out)
    preds = _val_preds(panel, cfg, args.origin, args.seed)
    out.mkdir(parents=True, exist_ok=True)
    preds.to_csv(out / "preds.csv", index=False)
    split = pd.read_parquet(ROOT / f"data/processed/eval_splits/{args.origin}_val.parquet")
    split["date"] = pd.to_datetime(split["date"]).astype("datetime64[ns]")
    split["prov_code"] = split["prov_code"].astype(str).str.zfill(2)
    merged = preds.merge(split[["date", "prov_code", "label_primary"]],
                         on=["date", "prov_code"], how="left", validate="many_to_one")
    if merged["label_primary"].isna().any():
        raise ValueError("missing regime labels")
    merged = merged.rename(columns={"label_primary": "regime"})
    merged = merged[merged["y_mask"].astype(bool) & np.isfinite(merged["y_true"]) &
                    np.isfinite(merged["y_pred"])]
    rows = []
    for (h, regime), g in merged.groupby(["h", "regime"]):
        rows.append({"variant": args.variant, "origin": args.origin, "horizon": int(h),
                     "seed": args.seed, "regime": regime,
                     "mae": mae(g["y_true"], g["y_pred"]),
                     "rmse": rmse(g["y_true"], g["y_pred"]),
                     "smape": smape(g["y_true"], g["y_pred"]), "n": len(g)})
    pd.DataFrame(rows).to_csv(out / "metrics.csv", index=False)
    print("DONE", out, len(rows), flush=True)


if __name__ == "__main__":
    main()
