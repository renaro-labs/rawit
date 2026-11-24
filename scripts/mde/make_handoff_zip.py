#!/usr/bin/env python3
"""Buat zip serah-terima + SHA256SUMS.txt (MDE).

Contoh (dari root repo):
    python scripts/mde/make_handoff_zip.py ../prices_clean_mde.zip \
        data/interim/prices_clean.parquet reports/qa/prices_clean.md reports/qa/sp2kp_crosscheck.csv
Path di dalam zip = path relatif yang diberikan. Tidak menerima file di _sealed/ atau holdout.
"""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    out, files = Path(argv[0]), [Path(a) for a in argv[1:]]
    for f in files:
        if not f.is_file():
            raise SystemExit(f"tidak ada: {f}")
        if "_sealed" in f.parts or "holdout" in f.as_posix().lower():
            raise SystemExit(f"file holdout tidak boleh masuk zip ini: {f}")
    sums = "".join(f"{sha256(f)}  {f.as_posix()}\n" for f in files)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.as_posix())
        z.writestr("SHA256SUMS.txt", sums)
    print(sums, end="")
    print(f"[ok] {out} ({out.stat().st_size / 1e3:.0f} KB, {len(files)} file + SHA256SUMS.txt)")


if __name__ == "__main__":
    main(sys.argv[1:])
