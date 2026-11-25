#!/usr/bin/env python3
"""CGS-H4-02: lead-lag diagnostics on O3 train only."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import parse_range
from renaro.eval.leadlag import (correlation_table, edges_from_mask, peak_table,
                                 pentadize, summary_markdown, write_figures)
from renaro.eval.splits import load_global_config

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser(description="CGS-H4-02 lead-lag rain -> price")
    ap.add_argument("--panel", type=Path, default=ROOT / "data/processed/dataset_v1/panel.parquet")
    ap.add_argument("--mask", type=Path, default=ROOT / "data/interim/bps_mask.npy")
    ap.add_argument("--regimes", type=Path, default=ROOT / "data/interim/regime_labels.csv")
    ap.add_argument("--config", type=Path, default=ROOT / "configs/global.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/leadlag")
    args = ap.parse_args()

    cfg = load_global_config(args.config)
    start, end = parse_range(cfg["origins"]["O3"]["train"])
    panel = pd.read_parquet(args.panel)
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel["prov_code"] = panel["prov_code"].astype(str).str.zfill(2)
    panel = panel[(panel["date"] >= pd.Timestamp(start)) & (panel["date"] <= pd.Timestamp(end))].copy()
    if (panel["date"] >= pd.Timestamp(cfg["holdout_start"])).any():
        raise SystemExit("train filter contains holdout dates")

    regimes = pd.read_csv(args.regimes)
    regimes["date"] = pd.to_datetime(regimes["date"]).astype("datetime64[ns]")
    regimes["prov_code"] = regimes["prov_code"].astype(str).str.zfill(2)
    pentad = pentadize(panel, regimes)
    mask = np.load(args.mask, allow_pickle=False)
    edges = edges_from_mask(mask)
    corr = correlation_table(pentad, edges)
    peaks = peak_table(corr)
    args.out.mkdir(parents=True, exist_ok=True)
    corr.to_csv(args.out / "leadlag_edges.csv", index=False)
    peaks.to_csv(args.out / "leadlag_peak.csv", index=False)
    write_figures(peaks, args.out)
    (args.out / "leadlag_summary.md").write_text(summary_markdown(corr, peaks), encoding="utf-8")
    print(f"[edges] {len(edges)}; tests={len(corr):,}; significant={int(corr['significant'].sum()) if len(corr) else 0}")
    print(peaks.head(6).to_string(index=False))
    print(f"[out] {args.out}")


if __name__ == "__main__":
    main()
