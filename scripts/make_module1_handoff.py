#!/usr/bin/env python3
"""Write the Module 1 H4 handoff manifest for CGS-H5-01."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
OUT = ROOT / "experiments/handoff/module1_for_robustness.yaml"


def main() -> None:
    selected = []
    for seed in range(5):
        path = RUNS / f"h4_module1_O3_bps_s{seed}/best.pt"
        if not path.is_file():
            raise FileNotFoundError(path)
        selected.append({"seed": seed, "checkpoint": path.relative_to(ROOT).as_posix(),
                         "prior": "bps", "origin": "O3"})
    payload = {
        "model": "module1",
        "config": "configs/models/module1.yaml",
        "split_hash": json.loads((RUNS / "h4_module1_O3_bps_s0/summary.json").read_text())["split_hash"],
        "selection": "O3 seed 0-4, BPS prior; final configuration from H4-01 tuning",
        "checkpoints": selected,
        "usage": "CGS-H5-01 robustness experiments; do not use sealed holdout values",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
