#!/usr/bin/env python3
"""Write SHA-256 checksums for the CGS-H1 package inside rawit.

Covers data/raw/{chirps_v3,enso,bps,boundaries}, data/interim/roni.parquet,
CGS QA reports, CGS scripts, and docs/cgs_h1_data.md. Data files are gitignored,
but the checksum file is tracked so the local bundle can be audited.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(".").resolve()
TARGETS = [
    "data/raw/chirps_v3",
    "data/raw/enso",
    "data/raw/bps",
    "data/raw/boundaries",
    "data/interim/roni.parquet",
    "reports/qa/chirps_download.md",
    "reports/qa/roni.md",
    "reports/qa/produksi_kab.md",
    "reports/qa/CGS-H1_summary.md",
    "reports/qa/CGS-H1_verification.json",
    "scripts/cgs",
    "docs/cgs_h1_data.md",
]
OUT = ROOT / "reports/qa/CGS-H1_SHA256SUMS.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


lines: list[str] = []
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
