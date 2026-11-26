#!/usr/bin/env python3
"""Summarize H4 Module1 and baseline runs for the MLE handoff."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
OUT = ROOT / "reports/mle"


def main() -> None:
    rows = []
    for path in sorted(RUNS.glob("h4_*")):
        summary = path / "summary.json"
        if not summary.is_file():
            continue
        d = json.loads(summary.read_text())
        m = d.get("metrics") or {}
        rows.append({
            "run_id": path.name, "model": d.get("model"), "origin": d.get("origin"),
            "seed": d.get("seed"), "prior": (d.get("config") or {}).get("prior", d.get("prior")),
            "split_hash": d.get("split_hash"), "val_h10_mae": m.get("val_h10_mae"),
            "test_h10_mae": m.get("test_h10_mae"),
            "checkpoint": (path / "best.pt").is_file(),
            "a_by_regime": (path / "A_by_regime.npz").is_file(),
        })
    if not rows:
        raise SystemExit("no H4 runs yet")
    frame = pd.DataFrame(rows).sort_values(["model", "origin", "prior", "seed"], na_position="last")
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "h4_runs_summary.csv", index=False)
    lines = ["# MLE H4 run summary", "",
             "| model | origin | prior | seed | val h10 MAE | ckpt | A_by_regime |",
             "|---|---|---|---:|---:|---|---|"]
    for r in frame.itertuples(index=False):
        lines.append(f"| {r.model} | {r.origin} | {r.prior} | {r.seed} | "
                     f"{r.val_h10_mae:.2f} | {r.checkpoint} | {r.a_by_regime} |")
    (OUT / "h4_runs_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(frame.to_string(index=False))
    print(len(frame), "runs")


if __name__ == "__main__":
    main()
