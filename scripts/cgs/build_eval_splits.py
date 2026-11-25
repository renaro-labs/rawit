#!/usr/bin/env python3
"""Build CGS-H4-01 regime-aware evaluation splits."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from renaro.eval.regimes import build_eval_splits, summary_markdown
from renaro.eval.splits import load_global_config

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser(description="CGS-H4-01 eval splits per regime")
    ap.add_argument("--panel", type=Path, default=ROOT / "data/processed/dataset_v1/panel.parquet")
    ap.add_argument("--regimes", type=Path, default=ROOT / "data/interim/regime_labels.csv")
    ap.add_argument("--config", type=Path, default=ROOT / "configs/global.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "data/processed/eval_splits")
    ap.add_argument("--report", type=Path, default=ROOT / "reports/qa/eval_splits_summary.md")
    ap.add_argument("--summary-csv", type=Path, default=ROOT / "reports/qa/eval_splits_summary.csv")
    args = ap.parse_args()

    panel = pd.read_parquet(args.panel)
    regimes = pd.read_csv(args.regimes)
    cfg = load_global_config(args.config)
    summary, _ = build_eval_splits(panel, regimes, out_dir=args.out, config=cfg)

    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary_csv, index=False)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(summary_markdown(summary), encoding="utf-8")

    print(summary.to_string(index=False))
    print(f"\n[out] {args.out}")
    print(f"[report] {args.report}")
    print(f"[summary] {args.summary_csv}")


if __name__ == "__main__":
    main()
