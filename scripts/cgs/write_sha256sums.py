#!/usr/bin/env python3
"""Write output/SHA256SUMS.txt for the CGS-H1 package.

Excludes secrets (.env), caches, __pycache__ and the checksum file itself.
Paths are relative to output/.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path("output")
EXCLUDE_DIRS = {"cache", "__pycache__", ".pytest_cache"}
EXCLUDE_FILES = {"SHA256SUMS.txt", ".env"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


lines: list[str] = []
for path in sorted(ROOT.rglob("*")):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        continue
    if rel.as_posix() in EXCLUDE_FILES:
        continue
    lines.append(f"{sha256(path)}  {rel.as_posix()}")

(ROOT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {len(lines)} checksums to output/SHA256SUMS.txt")
