#!/usr/bin/env python3
"""H4-02/H4-03: run simplified RCSGNet/MillGNN baselines on real data."""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from renaro.baselines.lag_graph import build as lag_build
from renaro.baselines.latent_regime import build as latent_build
from renaro.data.io import load_panel
from renaro.models.module1_training import run_registered

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
REGISTRY = ROOT / "experiments/registry.csv"


def metrics(preds: pd.DataFrame) -> dict:
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=("latent_regime", "lag_graph"), required=True)
    ap.add_argument("--origin", default="O1")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=10)
    args = ap.parse_args()
    cfg = copy.deepcopy(yaml.safe_load(
        (ROOT / f"configs/models/{args.model}.yaml").read_text()))
    cfg["global"] = yaml.safe_load((ROOT / "configs/global.yaml").read_text())
    cfg["epochs"] = args.epochs
    cfg["model"] = args.model
    panel = load_panel(ROOT / "data/processed/dataset_v1")
    factory = latent_build if args.model == "latent_regime" else lag_build
    run_id = f"h4_{args.model}_{args.origin}_s{args.seed}"
    out = RUNS / run_id
    if out.exists():
        raise FileExistsError(out)
    preds = run_registered(panel, cfg, args.origin, args.seed, model_factory=factory)
    out.mkdir(parents=True, exist_ok=True)
    preds.to_csv(out / "preds.csv", index=False)
    summary = {"model": args.model, "origin": args.origin, "seed": args.seed,
               "split_hash": panel.split_hash, "config": cfg,
               "training": preds.attrs.get("training"),
               "metrics": metrics(preds), "note": "simplified baseline, not a reproduction"}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    append_registry(run_id, args.model, args.origin, args.seed, panel.split_hash,
                    summary["metrics"]["val_h10_mae"])
    print("DONE", out, summary["metrics"]["val_h10_mae"], flush=True)


if __name__ == "__main__":
    main()
