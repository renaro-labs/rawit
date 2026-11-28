#!/usr/bin/env python3
"""CGS/MLE-H6-01: origin-conditioned Module 1 attention on validation.

The saved ``A_by_regime.npz`` artefacts from H4-01 are conditioned on the
*destination* province's regime.  Task MLE-H6-01 asks for ``A`` when the
*origin* province is dry vs normal.  This script recomputes that diagnostic
from the 15 H4 Module 1 checkpoints (O1-O3 x 5 seeds) on the official
validation windows.

Outputs
-------
``reports/holdout/attention_origin_by_run.csv``
    origin, seed, regime, lag, mean_mass, n_origins
``reports/holdout/attention_origin_dry_normal.csv``
    regime, lag, mean_mass, std_mass, n_runs
``reports/holdout/fig_A_dry_vs_normal.png``

For a sample at decision date d and origin j, ``mass[j, lag]`` is
``sum_i A[d, i, j, lag]``: the total attention that all destination
provinces allocate to origin j at that lag.  The script averages this
mass over validation samples for each origin, then equally over origins.
This is a predictive-dependency diagnostic, not a supply-flow estimate.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
OUT = ROOT / "reports/holdout"
REGIMES = ("dry", "normal")
ORIGINS = ("O1", "O2", "O3")
SEEDS = (0, 1, 2, 3, 4)


def load_cfg() -> tuple[dict, dict]:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    cfg = yaml.safe_load((ROOT / "configs/models/module1.yaml").read_text(encoding="utf-8"))
    cfg["global"] = yaml.safe_load((ROOT / "configs/global.yaml").read_text(encoding="utf-8"))
    cfg["model"] = "module1"
    cfg["prior"] = "bps"
    cfg["zero_climate"] = False
    return cfg, cfg["global"]


def run_one(panel, cfg, glob, origin: str, seed: int, labels: pd.DataFrame) -> list[dict]:
    from renaro.models.module1_training import predict, prepare

    model, spec, loaders, device, prior = prepare(
        panel, cfg, glob, origin, seed, ("val",)
    )
    ckpt = torch.load(RUNS / f"h4_module1_{origin}_bps_s{seed}/best.pt",
                      map_location=device, weights_only=True)
    state = ckpt.get("model_state_dict", ckpt)
    model.load_state_dict(state)
    model = model.to(device).eval()

    key = labels.set_index(["date", "prov_code"])["label_primary"]
    n = len(panel.node_codes)
    n_lags = int(model.n_lags)
    mass = {r: np.zeros((n, n_lags), dtype=np.float64) for r in REGIMES}
    count = {r: np.zeros(n, dtype=np.int64) for r in REGIMES}

    with torch.no_grad():
        for batch in loaders["val"]:
            _, attention = predict(model, batch, device, prior)
            attention = attention.detach().cpu().numpy()
            for s, k in enumerate(batch["t_index"].tolist()):
                date = panel.dates[int(k)]
                for j, code in enumerate(panel.node_codes):
                    label = key.get((date, str(code)))
                    if label in mass:
                        mass[label][j] += attention[s, :, j, :].sum(axis=0)
                        count[label][j] += 1

    rows = []
    for regime in REGIMES:
        per_origin = []
        for j in range(n):
            if count[regime][j] > 0:
                per_origin.append(mass[regime][j] / count[regime][j])
        if per_origin:
            mean = np.mean(per_origin, axis=0)
            for lag in range(n_lags):
                rows.append({
                    "origin": origin, "seed": seed, "regime": regime,
                    "lag": lag + 1, "mean_mass": float(mean[lag]),
                    "n_origins": int(len(per_origin)),
                })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from renaro.data.io import load_panel

    cfg, glob = load_cfg()
    panel = load_panel(ROOT / "data/processed/dataset_v1")
    labels = pd.read_csv(ROOT / "data/interim/regime_labels.csv", dtype={"prov_code": str})
    labels["date"] = pd.to_datetime(labels["date"]).astype("datetime64[ns]")

    rows: list[dict] = []
    for origin in ORIGINS:
        for seed in SEEDS:
            print(f"[run] {origin} s{seed}", flush=True)
            rows.extend(run_one(panel, cfg, glob, origin, seed, labels))
    per_run = pd.DataFrame(rows)
    per_run.to_csv(out / "attention_origin_by_run.csv", index=False)

    agg = (per_run.groupby(["regime", "lag"])["mean_mass"]
           .agg(["mean", "std", "count"]).reset_index()
           .rename(columns={"mean": "mean_mass", "std": "std_mass", "count": "n_runs"}))
    agg.to_csv(out / "attention_origin_dry_normal.csv", index=False)
    print(agg.to_string(index=False))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=170)
    width = 0.38
    lags = np.arange(1, int(per_run.lag.max()) + 1)
    for idx, regime in enumerate(REGIMES):
        part = agg[agg.regime == regime].set_index("lag").reindex(lags)
        ax.bar(lags + (idx - 0.5) * width, part["mean_mass"], width,
               yerr=part["std_mass"], capsize=3,
               label=f"Asal {regime}", color=("#8c6d46" if regime == "dry" else "#4f7cac"))
    ax.set_xticks(lags)
    ax.set_xlabel("Bin jeda pentad")
    ax.set_ylabel("Massa perhatian rata-rata dari provinsi asal\n(sum atas 34 tujuan)")
    ax.set_title("Modul 1 — perhatian dari provinsi asal saat asal kering vs normal\n(validasi O1–O3, 5 seed; dependensi prediktif, bukan arus pasokan)")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "fig_A_dry_vs_normal.png", bbox_inches="tight")
    print(f"[out] {out/'attention_origin_by_run.csv'}")
    print(f"[out] {out/'attention_origin_dry_normal.csv'}")
    print(f"[out] {out/'fig_A_dry_vs_normal.png'}")


if __name__ == "__main__":
    main()
