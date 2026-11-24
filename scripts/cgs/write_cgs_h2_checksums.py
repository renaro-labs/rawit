#!/usr/bin/env python3
"""Write SHA-256 checksums for the CGS-H2 package."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(".").resolve()
TARGETS = [
    "data/interim/w_kab_pixel.npz",
    "data/interim/rain_prov_daily.parquet",
    "data/interim/climate_features.parquet",
    "data/interim/climatology.parquet",
    "data/interim/availability.csv",
    "data/interim/regime_labels.csv",
    "src/renaro/climate",
    "scripts/cgs/build_kab_pixel_weights.py",
    "scripts/cgs/verify_cgs_h2.py",
    "reports/qa/rain_prov.md",
    "reports/qa/climate_features.md",
    "reports/qa/chirps_release_lag.md",
    "reports/qa/chirps_release_lag_probe.csv",
    "reports/qa/availability.csv",
    "reports/qa/regime_counts.md",
    "reports/qa/CGS-H2_summary.md",
    "reports/qa/CGS-H2_verification.json",
    "docs/regime_definitions.md",
    "docs/cgs_h2_data.md",
    "docs/feature_dict.csv",
]
OUT = ROOT / "reports/qa/CGS-H2_SHA256SUMS.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


lines = []
for target in TARGETS:
    path = ROOT / target
    if not path.exists():
        raise SystemExit(f"missing target: {target}")
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    for file in files:
        if "__pycache__" in file.parts or file.name.endswith(".pyc"):
            continue
        lines.append(f"{sha256(file)}  {file.relative_to(ROOT).as_posix()}")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {len(lines)} checksums -> {OUT.relative_to(ROOT).as_posix()}")
