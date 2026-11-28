#!/usr/bin/env python3
"""Verify CGS-H6-01 holdout/dataset integrity without reading data values.

Checks (only bytes/checksums, never parquet contents):

1. ``data/processed/dataset_v1/SHA256SUMS``      -> 6/6
2. ``RENARO_SEALED_DIR/holdout_v1/panel_v1/SHA256SUMS`` -> 6/6
3. ``RENARO_SEALED_DIR/holdout_v1/SHA256SUMS.txt``      -> 196/196
4. ``frozen/manifest.yaml`` checkpoint paths and SHA-256
   (report only by default; ``--require-checkpoints`` makes missing/mismatch fatal)

Exit codes: 0 = all required checks pass; 1 = a checksum mismatch/missing file;
2 = prerequisite path missing.  The script never creates ``HOLDOUT_UNSEALED``
and never writes into the sealed directory.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sums(folder: Path, sums_name: str = "SHA256SUMS") -> tuple[int, int, list[str]]:
    sums = folder / sums_name
    if not sums.is_file():
        raise FileNotFoundError(sums)
    total = ok = 0
    bad: list[str] = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        want, name = line.split(None, 1)
        name = name.lstrip("*").strip()
        path = folder / name
        total += 1
        if not path.is_file():
            bad.append(f"{name}: missing")
            continue
        got = sha256_file(path)
        if got == want:
            ok += 1
        else:
            bad.append(f"{name}: {got[:16]}... != {want[:16]}...")
    return ok, total, bad


def verify_manifest(root: Path, manifest_path: Path) -> tuple[int, int, list[str], list[str]]:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    total = ok = 0
    missing: list[str] = []
    mismatched: list[str] = []
    for entry in manifest.get("models", []):
        for ckpt, want in zip(entry["checkpoints"], entry["sha256"]):
            total += 1
            path = root / ckpt
            if not path.is_file():
                missing.append(ckpt)
            elif sha256_file(path) != want:
                mismatched.append(ckpt)
            else:
                ok += 1
    return ok, total, missing, mismatched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT, help="repo root")
    ap.add_argument("--sealed", type=Path,
                    default=Path(os.environ.get("RENARO_SEALED_DIR", "")) if os.environ.get("RENARO_SEALED_DIR") else None,
                    help="RENARO_SEALED_DIR (default: env)")
    ap.add_argument("--manifest", type=Path, default=Path("frozen/manifest.yaml"))
    ap.add_argument("--require-checkpoints", action="store_true",
                    help="fail if any manifest checkpoint is missing/mismatched")
    args = ap.parse_args()

    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    if not manifest_path.is_file():
        print(f"[FAIL] manifest tidak ada: {manifest_path}")
        return 2
    if args.sealed is None or not str(args.sealed):
        print("[FAIL] RENARO_SEALED_DIR belum diset (atau pakai --sealed)")
        return 2
    sealed = args.sealed.resolve()
    panel = sealed / "holdout_v1" / "panel_v1"

    failed = False
    for label, folder, sums_name in (
        ("dataset_v1", root / "data/processed/dataset_v1", "SHA256SUMS"),
        ("holdout panel_v1", panel, "SHA256SUMS"),
        ("holdout 196-file manifest", sealed / "holdout_v1", "SHA256SUMS.txt"),
    ):
        try:
            ok, total, bad = verify_sums(folder, sums_name)
        except FileNotFoundError as exc:
            print(f"[FAIL] {label}: {exc}")
            failed = True
            continue
        print(f"[{'ok' if not bad else 'FAIL'}] {label}: {ok}/{total} checksum cocok")
        for row in bad:
            print(f"       - {row}")
        failed = failed or bool(bad)

    try:
        ok, total, missing, mismatched = verify_manifest(root, manifest_path)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"[FAIL] manifest checkpoint: {exc}")
        return 2
    print(f"[{'ok' if ok == total else 'GAP'}] checkpoint manifest: {ok}/{total} SHA-256 cocok")
    if missing:
        print(f"       missing: {len(missing)} (contoh: {missing[0]})")
    if mismatched:
        print(f"       mismatch: {len(mismatched)} (contoh: {mismatched[0]})")
    if args.require_checkpoints and (missing or mismatched):
        failed = True

    unseal = sealed / "HOLDOUT_UNSEALED"
    print(f"[info] HOLDOUT_UNSEALED: {'ADA' if unseal.is_file() else 'tidak ada (tersegel)'}")
    print(f"[info] output prediksi: {'ADA' if (root / 'reports/holdout/predictions').exists() else 'belum ada'}")

    if failed:
        print("HASIL: GAGAL — perbaiki item di atas sebelum membuka holdout.")
        return 1
    if missing or mismatched:
        print(f"HASIL: integritas data OK, tetapi checkpoint belum lengkap "
              f"({ok}/{total}) — HOLD, jangan buka holdout.")
        return 0
    print("HASIL: OK — integritas data dan 50/50 checkpoint lolos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
