#!/usr/bin/env python3
"""Summarize MLE-H5-01 module23 validation runs."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/h5"


def main() -> None:
    rows = []
    for path in sorted((ROOT / "experiments/runs").glob("h5_module23_*")):
        summary_path = path / "summary.json"
        if not summary_path.is_file():
            continue
        s = json.loads(summary_path.read_text())
        m = s.get("metrics") or {}
        rows.append({"run_id": path.name, "origin": s.get("origin"), "seed": s.get("seed"),
                     "val_h10_mae": m.get("val_h10_mae"), "test_h10_mae": m.get("test_h10_mae"),
                     "split_hash": s.get("split_hash"), "epochs": (s.get("config") or {}).get("epochs")})
    if not rows:
        raise SystemExit("no module23 runs")
    frame = pd.DataFrame(rows).sort_values(["origin", "seed"])
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "module23_runs_summary.csv", index=False)
    lines = ["# MLE-H5-01 module23 runs", "",
             "Model: `src/renaro/models/module23.py`; 3 origin x 5 seed; "
             "full configuration `configs/models/module23.yaml`.", "",
             "| run_id | origin | seed | val h10 MAE | test h10 MAE |",
             "|---|---|---:|---:|---:|"]
    for r in frame.itertuples(index=False):
        lines.append(f"| {r.run_id} | {r.origin} | {r.seed} | {r.val_h10_mae:.2f} | "
                     f"{r.test_h10_mae:.2f} |")
    (OUT / "module23_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(len(frame), "runs")


if __name__ == "__main__":
    main()
