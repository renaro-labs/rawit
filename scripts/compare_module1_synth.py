#!/usr/bin/env python3
"""Compare Module 1 and GWN on the same synthetic split, with real GWN runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from renaro.data.io import load_panel

ROOT = Path(__file__).resolve().parents[1]


def score(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    mask = d["y_mask"].astype(bool) & np.isfinite(d["y_true"]) & np.isfinite(d["y_pred"])
    d = d[mask]
    return d.groupby("h", as_index=False).apply(
        lambda g: pd.Series({"mae": float((g["y_true"] - g["y_pred"]).abs().mean()), "n": len(g)}),
        include_groups=False,
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module1-prefix", default="experiments/runs/module1_synth_O1_s")
    ap.add_argument("--gwn-prefix", default="experiments/runs/gwn_synth_O1_s")
    ap.add_argument("--dataset", type=Path, default=ROOT / "data/synth/default")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/module1/synth_default_O1_benchmark.json")
    ap.add_argument("--manifest", type=Path, default=ROOT / "reports/module1/synth_default_manifest.json")
    ap.add_argument("--split-csv", type=Path, default=ROOT / "reports/module1/synth_default_split_verification.csv")
    args = ap.parse_args()
    panel = load_panel(args.dataset)
    rows, per_seed = [], []
    for seed in range(5):
        mpath = ROOT / f"{args.module1_prefix}{seed}/preds.csv"
        gpath = ROOT / f"{args.gwn_prefix}{seed}/preds.csv"
        if not mpath.is_file() or not gpath.is_file():
            raise FileNotFoundError(f"missing seed {seed}: {mpath} {gpath}")
        m = score(mpath); g = score(gpath)
        m_by = m.set_index("h")["mae"]; g_by = g.set_index("h")["mae"]
        for h in sorted(set(m_by.index) & set(g_by.index)):
            rows.append({"seed": seed, "h": int(h), "module1_mae": float(m_by[h]),
                         "gwn_mae": float(g_by[h]), "module1_beats_gwn": bool(m_by[h] < g_by[h])})
        per_seed.append({"seed": seed, "module1_mean": float(m_by.mean()),
                         "gwn_mean": float(g_by.mean()),
                         "module1_beats_gwn": bool(m_by.mean() < g_by.mean())})
    by_h = pd.DataFrame(rows)
    means = pd.DataFrame(per_seed)
    horizon_means = by_h.groupby("h")[["module1_mae", "gwn_mae"]].mean().reset_index()
    result = {
        "dataset": "data/synth/default",
        "split_hash": panel.split_hash,
        "origin": "O1",
        "seeds": list(range(5)),
        "module1_run_prefix": args.module1_prefix,
        "gwn_run_prefix": args.gwn_prefix,
        "config": {
            "module1": yaml.safe_load((ROOT / "configs/models/module1.yaml").read_text()),
            "gwn": yaml.safe_load((ROOT / "configs/models/gwn.yaml").read_text()),
        },
        "validation_average_across_horizons": {
            "module1_mae": float(means["module1_mean"].mean()),
            "gwn_mae": float(means["gwn_mean"].mean()),
        },
        "validation_mae_dod_pass": bool(means["module1_mean"].mean() < means["gwn_mean"].mean()),
        "validation_each_horizon_pass": bool((horizon_means["module1_mae"] < horizon_means["gwn_mae"]).all()),
        "mae_by_horizon": horizon_means.to_dict("records"),
        "per_seed": per_seed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    means.assign(split_hash=panel.split_hash).to_csv(args.split_csv, index=False)

    files = {}
    for name in ("panel.parquet", "target.parquet", "nodes.csv", "bps_mask.npy", "truth.npz"):
        p = args.dataset / name
        files[name] = {"size_bytes": p.stat().st_size, "sha256": sha256(p)}
    manifest = {
        "dataset": "synth/default",
        "path": "data/synth/default",
        "generator_command": "python -m renaro.synth.generator --mode conditioned --out data/synth --bps-mask data/interim/bps_mask.npy",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "verification_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "split_hash": panel.split_hash,
        "panel_shape": list(panel.panel.shape),
        "target_shape": list(panel.target.shape),
        "n_nodes": len(panel.node_codes),
        "node_codes": list(panel.node_codes),
        "n_dates": len(panel.dates),
        "date_start": str(panel.dates.min().date()),
        "date_end": str(panel.dates.max().date()),
        "synthetic": True,
        "files": files,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result["validation_average_across_horizons"], indent=2))
    print("each horizon pass:", result["validation_each_horizon_pass"])
    print("wrote", args.out)
    print("wrote", args.manifest)


if __name__ == "__main__":
    main()
