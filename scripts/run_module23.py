#!/usr/bin/env python3
"""Run MLE-H5-01 Module 2-3 on 3 origins x 5 seeds."""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from renaro.data.io import load_panel
from renaro.models.module1_training import run_registered
from renaro.models.module23 import build

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
REGISTRY = ROOT / "experiments/registry.csv"


def metrics(preds: pd.DataFrame) -> dict:
    out = {}
    for (part, h), group in preds.groupby(["part", "h"]):
        valid = group[group["y_mask"].astype(bool) & np.isfinite(group["y_true"]) &
                      np.isfinite(group["y_pred"])]
        out[f"{part}_h{int(h)}_mae"] = float((valid["y_true"] - valid["y_pred"]).abs().mean())
        out[f"{part}_h{int(h)}_n"] = int(len(valid))
    return out


def append_registry(run_id: str, origin: str, seed: int, split_hash: str, val_mae: float) -> None:
    fields = ["run_id", "model", "origin", "seed", "split_hash", "val_mae", "status"]
    exists = REGISTRY.exists() and REGISTRY.stat().st_size > 0
    with REGISTRY.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({"run_id": run_id, "model": "module23", "origin": origin,
                         "seed": seed, "split_hash": split_hash, "val_mae": val_mae,
                         "status": "completed"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", required=True)
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    cfg = copy.deepcopy(yaml.safe_load((ROOT / "configs/models/module23.yaml").read_text()))
    cfg["global"] = yaml.safe_load((ROOT / "configs/global.yaml").read_text())
    panel = load_panel(ROOT / "data/processed/dataset_v1")
    run_id = f"h5_module23_{args.origin}_s{args.seed}"
    out = RUNS / run_id
    if out.exists():
        raise FileExistsError(out)
    preds = run_registered(panel, cfg, args.origin, args.seed, model_factory=build)
    out.mkdir(parents=True, exist_ok=True)
    preds.to_csv(out / "preds.csv", index=False)
    summary = {"model": "module23", "origin": args.origin, "seed": args.seed,
               "split_hash": panel.split_hash, "config": cfg,
               "training": preds.attrs.get("training"), "metrics": metrics(preds)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    append_registry(run_id, args.origin, args.seed, panel.split_hash,
                    summary["metrics"]["val_h10_mae"])
    print("DONE", out, summary["metrics"]["val_h10_mae"], flush=True)


if __name__ == "__main__":
    main()
