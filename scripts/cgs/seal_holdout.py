#!/usr/bin/env python3
"""CGS-H3-02: seal the holdout (dates >= 2026-06-01).

What it does:
  1. Copies the full raw data into $RENARO_SEALED_DIR/holdout_v1/raw_merged.
  2. Splits PIHPS (shared CSV + raw JSON) at 2026-06-01; sealed rows go to
     holdout_v1/sealed/pihps and are removed from the shared MDE folder.
  3. Splits RONI at 2026 seasons covering June onward (center_month >= 4);
     sealed rows go to holdout_v1/sealed/enso and are removed from shared.
  4. Merges CHIRPS shared 2017-2026-05 with the sealed 2026-06..10 final and
     2026-11 prelim into raw_merged/chirps_v3 (single manifest).
  5. Writes manifest.json, SHA256SUMS.txt, README.md and docs/holdout_seal.md.

The holdout panel itself is NOT built here: that needs scripts/build_dataset.py
(MDE-H3-01), which is not present in this repository yet.  The seal is complete
for the raw data; the panel build is recorded as a blocker.

No holdout values are printed or described; only counts, ranges, and hashes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "data"
PIHPS_DEFAULT = Path(r"D:\renaro\supplychain\data\raw\pihps")
HOLDOUT_START = pd.Timestamp("2026-06-01")
SEAL_DOC = ROOT / "docs" / "holdout_seal.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_sha256sums(folder: Path) -> Path:
    lines = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS.txt":
            continue
        lines.append(f"{sha256(path)}  {path.relative_to(folder).as_posix()}")
    out = folder / "SHA256SUMS.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def move_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if sha256(src) != sha256(dst):
        raise RuntimeError(f"checksum mismatch after copy: {src}")
    src.unlink()


def split_pihps(shared_dir: Path, raw_merged: Path, sealed: Path) -> dict:
    csv_path = shared_dir / "pihps_cabai_merah_keriting_province.csv"
    frame = pd.read_csv(csv_path)
    frame["date"] = pd.to_datetime(frame["date"])
    holdout = frame[frame["date"] >= HOLDOUT_START].copy()
    shared = frame[frame["date"] < HOLDOUT_START].copy()

    if len(holdout) == 0:
        sealed_csv = sealed / "pihps/pihps_holdout.csv"
        if not sealed_csv.exists():
            raise SystemExit("PIHPS shared has no holdout and no sealed copy exists")
        holdout = pd.read_csv(sealed_csv)
        holdout["date"] = pd.to_datetime(holdout["date"])
        moved_json = [p.name for p in sorted((sealed / "pihps/json").glob("*.json.gz"))]
        return {
            "rows_total": int(len(frame) + len(holdout)),
            "rows_holdout": int(len(holdout)),
            "rows_shared": int(len(frame)),
            "min_holdout": holdout["date"].min().date().isoformat(),
            "max_holdout": holdout["date"].max().date().isoformat(),
            "raw_json_moved": moved_json,
        }

    if len(holdout) + len(shared) != len(frame):
        raise RuntimeError("PIHPS split lost rows")

    # Full copy first, then the sealed subset.
    copy_tree(shared_dir, raw_merged / "pihps")
    sealed_pihps = sealed / "pihps"
    sealed_pihps.mkdir(parents=True, exist_ok=True)
    holdout.to_csv(sealed_pihps / "pihps_holdout.csv", index=False, date_format="%Y-%m-%d")
    shared.to_csv(csv_path, index=False, date_format="%Y-%m-%d")

    moved_json = []
    for path in sorted((shared_dir / "json").glob("*.json.gz")):
        match = re.search(r"_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json\.gz$", path.name)
        if not match:
            continue
        end = pd.Timestamp(match.group(2))
        if end >= HOLDOUT_START:
            move_file(path, sealed_pihps / "json" / path.name)
            moved_json.append(path.name)

    return {
        "rows_total": int(len(frame)),
        "rows_holdout": int(len(holdout)),
        "rows_shared": int(len(shared)),
        "min_holdout": holdout["date"].min().date().isoformat(),
        "max_holdout": holdout["date"].max().date().isoformat(),
        "raw_json_moved": moved_json,
    }


def split_roni(raw_merged: Path, sealed: Path) -> dict:
    enso = SHARED / "raw/enso"
    roni = pd.read_csv(enso / "roni.csv")
    mask = (roni["year"] == 2026) & (roni["center_month"] >= 4)
    holdout = roni[mask].copy()
    shared = roni[~mask].copy()

    if len(holdout) == 0:
        sealed_csv = sealed / "enso/roni_holdout.csv"
        if not sealed_csv.exists():
            raise SystemExit("RONI shared has no holdout and no sealed copy exists")
        holdout = pd.read_csv(sealed_csv)
        moved = [name for name in ["roni_raw_20261122.txt", "roni_episodes.csv", "comparison_summary.json", "roni_vs_reference.csv"]
                 if (sealed / "enso" / name).exists()]
        return {
            "rows_total": int(len(roni) + len(holdout)),
            "rows_holdout": int(len(holdout)),
            "rows_shared": int(len(roni)),
            "seasons_holdout": [f"{int(row.year)}-{row.season}" for row in holdout.itertuples()],
            "raw_files_moved": moved,
        }

    copy_tree(enso, raw_merged / "enso")
    if len(holdout) + len(shared) != len(roni):
        raise RuntimeError("RONI split lost rows")

    sealed_enso = sealed / "enso"
    sealed_enso.mkdir(parents=True, exist_ok=True)
    holdout.to_csv(sealed_enso / "roni_holdout.csv", index=False)
    shared.to_csv(enso / "roni.csv", index=False)

    parquet = SHARED / "interim/roni.parquet"
    if parquet.exists():
        table = pd.read_parquet(parquet)
        pq_mask = (table["year"] == 2026) & (table["center_month"] >= 4)
        table[~pq_mask].to_parquet(parquet, index=False)
        holdout.to_parquet(sealed_enso / "roni_holdout.parquet", index=False)

    moved = []
    for name in ["roni_raw_20261122.txt", "roni_episodes.csv", "comparison_summary.json", "roni_vs_reference.csv"]:
        path = enso / name
        if path.exists():
            move_file(path, sealed_enso / name)
            moved.append(name)

    return {
        "rows_total": int(len(roni)),
        "rows_holdout": int(len(holdout)),
        "rows_shared": int(len(shared)),
        "seasons_holdout": [
            f"{int(row.year)}-{row.season}" for row in holdout.itertuples()
        ],
        "raw_files_moved": moved,
    }


def merge_chirps(raw_merged: Path, sealed_root: Path, sealed: Path) -> dict:
    shared_dir = SHARED / "raw/chirps_v3"
    merged = raw_merged / "chirps_v3"
    copy_tree(shared_dir, merged)

    final_dir = sealed_root / "chirps_v3/final_sat/2026H2"
    prelim_dir = sealed_root / "chirps_v3/prelim_sat/2026H2"
    sealed_chirps = sealed / "chirps_v3"
    sealed_chirps.mkdir(parents=True, exist_ok=True)

    manifests = [pd.read_csv(shared_dir / "manifest.csv")]
    for source, dest in [(final_dir, sealed_chirps / "final_sat"), (prelim_dir, sealed_chirps / "prelim_sat")]:
        dest.mkdir(parents=True, exist_ok=True)
        for npz in sorted(source.glob("*.npz")):
            shutil.copy2(npz, merged / npz.name)
            shutil.copy2(npz, dest / npz.name)
        for name in ("manifest.csv", "download_log.txt"):
            if (source / name).exists():
                shutil.copy2(source / name, dest / name)
        manifests.append(pd.read_csv(source / "manifest.csv"))

    combined = pd.concat(manifests, ignore_index=True).drop_duplicates(subset=["date"], keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)
    combined.to_csv(merged / "manifest.csv", index=False)

    first = pd.read_csv(final_dir / "manifest.csv")
    prelim = pd.read_csv(prelim_dir / "manifest.csv")
    return {
        "shared_days": int(len(manifests[0])),
        "final_holdout_days": int(len(first)),
        "prelim_holdout_days": int(len(prelim)),
        "combined_days": int(len(combined)),
        "combined_min": str(combined["date"].min()),
        "combined_max": str(combined["date"].max()),
        "final_last": str(first["date"].max()),
    }


def check_no_holdout(pihps_dir: Path) -> None:
    csv_path = pihps_dir / "pihps_cabai_merah_keriting_province.csv"
    frame = pd.read_csv(csv_path, usecols=["date"])
    max_date = pd.to_datetime(frame["date"]).max()
    if max_date >= HOLDOUT_START:
        raise SystemExit(f"PIHPS shared still has holdout: max={max_date.date()}")

    roni = pd.read_csv(SHARED / "raw/enso/roni.csv")
    leaked = roni[(roni["year"] == 2026) & (roni["center_month"] >= 4)]
    if len(leaked):
        raise SystemExit(f"RONI shared still has {len(leaked)} holdout seasons")

    manifest = pd.read_csv(SHARED / "raw/chirps_v3/manifest.csv", usecols=["date"])
    if pd.to_datetime(manifest["date"]).max() >= HOLDOUT_START:
        raise SystemExit("CHIRPS shared still has holdout dates")

    for path in [SHARED / "interim/climate_features.parquet", SHARED / "interim/regime_labels.csv"]:
        if not path.exists():
            continue
        table = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, usecols=["date"])
        if pd.to_datetime(table["date"]).max() >= HOLDOUT_START:
            raise SystemExit(f"{path.name} still has holdout dates")

    if (Path(os.environ.get("RENARO_SEALED_DIR", "")) / "HOLDOUT_UNSEALED").exists():
        raise SystemExit("HOLDOUT_UNSEALED exists; do not unseal at H3")


def write_seal_doc(holdout: Path, pihps: dict, roni: dict, chirps: dict) -> None:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()
    sums = (holdout / "SHA256SUMS.txt").read_text(encoding="utf-8").strip().splitlines()
    sealed_lines = [line for line in sums if "sealed/" in line]
    lines = [
        "# Holdout seal (CGS-H3-02)\n",
        f"- Disegel oleh: **CGS**",
        f"- Waktu: **{dt.datetime.now().isoformat(timespec='seconds')}**",
        f"- Commit pipeline: `{commit}`",
        f"- Lokasi: `{holdout}`",
        "- Status: **TERSEGEL**",
        "",
        "## Cakupan (metadata saja)\n",
        f"- PIHPS: **{pihps['rows_holdout']:,} baris**, {pihps['min_holdout']} .. {pihps['max_holdout']}.",
        f"- RONI: **{roni['rows_holdout']} musim** ({', '.join(roni['seasons_holdout'])}).",
        f"- CHIRPS final: **{chirps['final_holdout_days']} hari** (2026-06-01 .. 2026-10-31).",
        f"- CHIRPS prelim: **{chirps['prelim_holdout_days']} hari** (2026-11-01 .. 2026-11-20).",
        f"- `tgl_akhir_holdout` = min(PIHPS, CHIRPS final) = **2026-10-31**.",
        "",
        "## Shared removals\n",
        f"- PIHPS: {pihps['rows_holdout']:,} baris holdout dipindah; shared tersisa {pihps['rows_shared']:,} baris (< 2026-06-01).",
        f"- PIHPS raw JSON dipindah: {', '.join(pihps['raw_json_moved']) or 'tidak ada'}.",
        f"- RONI: {roni['rows_holdout']} musim holdout dipindah; shared tersisa {roni['rows_shared']} musim.",
        f"- RONI raw files dipindah: {', '.join(roni['raw_files_moved']) or 'tidak ada'}.",
        "",
        "## Integritas\n",
        f"- `SHA256SUMS.txt` mencakup {len(sums)} file di `{holdout}`.",
        "- Checksum file holdout (subset tersegel):",
        "```text",
    ]
    lines += sealed_lines
    lines += [
        "```",
        "",
        "`raw_merged/` berisi gabungan data shared + holdout untuk membangun panel holdout; "
        "seluruh folder ini berada di luar repo dan hanya boleh diakses CGS.",
        "",
        "## DoD\n",
        "- [x] SHA-256 semua file holdout dicatat.",
        "- [x] Tidak ada file >= 2026-06-01 di drive bersama (diverifikasi).",
        "- [x] Salinan `_sealed` dipindah dari shared; MDE dikonfirmasi: **pending** (belum ada handoff MDE di repo ini).",
        "- [ ] Bagian < 2026-06-01 identik dengan dataset_v1: **BLOCKED** — `scripts/build_dataset.py` (MDE-H3-01) belum ada.",
        "- [ ] Panel `holdout_v1` dibangun: **BLOCKED** pada MDE-H3-01.",
        "- [ ] RL menerima notifikasi: **pending**.",
        "",
        "## Dibuka\n",
        "_Kosong. Hanya CGS-H6-01 yang boleh mengisi bagian ini setelah Gate 2._",
        "",
    ]
    SEAL_DOC.parent.mkdir(parents=True, exist_ok=True)
    SEAL_DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="CGS-H3-02 seal raw holdout")
    parser.add_argument("--pihps", type=Path, default=PIHPS_DEFAULT)
    parser.add_argument("--sealed", type=Path, default=None)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    sealed_root = args.sealed or Path(os.environ.get("RENARO_SEALED_DIR", ""))
    if not str(sealed_root):
        raise SystemExit("RENARO_SEALED_DIR belum diset")
    sealed_root = sealed_root.resolve()
    holdout = sealed_root / "holdout_v1"
    raw_merged = holdout / "raw_merged"
    sealed = holdout / "sealed"

    if args.check_only:
        check_no_holdout(args.pihps)
        print("shared data clean of holdout dates/seasons")
        return

    for folder in (holdout, raw_merged, sealed):
        folder.mkdir(parents=True, exist_ok=True)

    pihps = split_pihps(args.pihps, raw_merged, sealed)
    roni = split_roni(raw_merged, sealed)
    chirps = merge_chirps(raw_merged, sealed_root, sealed)
    copy_tree(SHARED / "raw/bps", raw_merged / "bps")
    copy_tree(SHARED / "raw/boundaries", raw_merged / "boundaries")

    manifest = {
        "sealed_at": dt.datetime.now().isoformat(timespec="seconds"),
        "holdout_start": str(HOLDOUT_START.date()),
        "holdout_end": "2026-10-31",
        "prelim_end": "2026-11-20",
        "pihps": pihps,
        "roni": roni,
        "chirps": chirps,
        "raw_merged": {
            "chirps_months": len(list((raw_merged / "chirps_v3").glob("*.npz"))),
            "pihps_rows": pihps["rows_total"],
            "roni_rows": roni["rows_total"],
        },
    }
    (holdout / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (holdout / "README.md").write_text(
        "# Holdout v1 (SEALED - CGS only)\n\n"
        "Do not copy into the repo or shared data. Open only with CGS-H6-01 after Gate 2.\n\n"
        "`raw_merged/` contains shared + holdout raw data for building the holdout panel.\n"
        "`sealed/` contains only the holdout rows/files.\n\n"
        "See `docs/holdout_seal.md` for counts, hashes, and the DoD status.\n",
        encoding="utf-8",
    )
    write_sha256sums(holdout)
    write_seal_doc(holdout, pihps, roni, chirps)
    check_no_holdout(args.pihps)
    print(json.dumps({"pihps_holdout_rows": pihps["rows_holdout"], "roni_seasons": roni["rows_holdout"],
                      "chirps_final_days": chirps["final_holdout_days"], "chirps_prelim_days": chirps["prelim_holdout_days"]}, indent=2))


if __name__ == "__main__":
    main()
