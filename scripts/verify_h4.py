#!/usr/bin/env python3
"""Verify H4 run completeness and shared split hashes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"

ORIGINS = ("O1", "O2", "O3")
SEEDS = range(5)
PRIORS = ("bps", "none")


def main() -> None:
    expected = []
    for origin in ORIGINS:
        for seed in SEEDS:
            for prior in PRIORS:
                expected.append(f"h4_module1_{origin}_{prior}_s{seed}")
            expected.append(f"h4_latent_regime_{origin}_s{seed}")
            expected.append(f"h4_lag_graph_{origin}_s{seed}")
    missing = [name for name in expected if not (RUNS / name).is_dir()]
    bad = []
    split_hashes = set()
    for name in expected:
        path = RUNS / name
        if not path.is_dir():
            continue
        summary_path = path / "summary.json"
        if not summary_path.is_file():
            bad.append(f"{name}: summary.json")
            continue
        summary = json.loads(summary_path.read_text())
        split_hashes.add(summary.get("split_hash"))
        if name.startswith("h4_module1"):
            for required in ("best.pt", "A_by_regime.npz", "preds.csv"):
                if not (path / required).is_file():
                    bad.append(f"{name}: {required}")
        elif not (path / "preds.csv").is_file():
            bad.append(f"{name}: preds.csv")
    print(f"expected={len(expected)} missing={len(missing)} bad={len(bad)}")
    if missing:
        print("missing:", missing)
    if bad:
        print("bad:", bad)
    print("split_hashes:", sorted(str(x) for x in split_hashes))
    if missing or bad or len(split_hashes) != 1:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
