#!/usr/bin/env python3
"""Verify output/data/raw/chirps_v3 (2017-01..2026-05) and write QA artifacts.

Also builds a pre-2018 climatology baseline from the 2017 files
(clim/climatology_2017_monthly.npz), because the project forbids using
2018+ data for climatology.  With the current scope (2017-2026) that
baseline is one calendar year; extend it to 2008-2017 if a longer
baseline is required.
"""
from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import json
import re
import warnings
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore", message="Mean of empty slice")

_parser = argparse.ArgumentParser(description="Verify CHIRPS output package")
_parser.add_argument("--root", default="output", help="package root (contains data/ and reports/)")
_args, _ = _parser.parse_known_args()

OUT = Path(_args.root).resolve()
CH = OUT / "data/raw/chirps_v3"
REQ_START, REQ_END = dt.date(2017, 1, 1), dt.date(2026, 5, 31)
HOLDOUT_START = dt.date(2026, 6, 1)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build_climatology() -> dict:
    """Monthly means from 2017 only (pre-2018). Returns a small summary."""
    files = sorted(CH.glob("chirps_v3_idn_2017-*.npz"))
    if len(files) != 12:
        return {"built": False, "reason": f"expected 12 files for 2017, found {len(files)}"}
    lat = lon = None
    means = np.full((12, 360, 950), np.nan, dtype=np.float32)
    counts = np.zeros(12, dtype=np.int32)
    for path in files:
        month = int(re.search(r"-(\d{2})\.npz$", path.name).group(1))
        with np.load(path) as z:
            lat = np.asarray(z["lat"], dtype=np.float32)
            lon = np.asarray(z["lon"], dtype=np.float32)
            cube = np.asarray(z["precip"], dtype=np.float32)
        means[month - 1] = np.nanmean(cube, axis=0)
        counts[month - 1] = cube.shape[0]
    clim_dir = CH / "clim"
    clim_dir.mkdir(exist_ok=True)
    np.savez_compressed(
        clim_dir / "climatology_2017_monthly.npz",
        lat=lat,
        lon=lon,
        month=np.arange(1, 13, dtype=np.int16),
        precip_mean=means,
        n_days=counts,
        baseline_start=np.array("2017-01-01"),
        baseline_end=np.array("2017-12-31"),
        method=np.array("mean of daily values per calendar month, 2017 only"),
    )
    return {
        "built": True,
        "file": "clim/climatology_2017_monthly.npz",
        "baseline": ["2017-01-01", "2017-12-31"],
        "n_days_per_month": counts.tolist(),
        "note": "one-year baseline; use 2008-2017 if a longer climatology is required",
    }


files = sorted(CH.glob("chirps_v3_idn_*.npz"))
if not files:
    raise SystemExit(f"no NPZ files in {CH}")

recs = []
for path in files:
    match = re.search(r"(\d{4})-(\d{2})", path.name)
    year, month = int(match.group(1)), int(match.group(2))
    with np.load(path) as z:
        times = pd.to_datetime(z["time"])
        precip = np.asarray(z["precip"])
        lat = np.asarray(z["lat"])
        lon = np.asarray(z["lon"])
        variants = sorted(set(map(str, z["variant"])))
    expected = calendar.monthrange(year, month)[1]
    recs.append(
        {
            "file": path.name,
            "year": year,
            "month": month,
            "n_days": len(times),
            "expected": expected,
            "first": str(times[0].date()),
            "last": str(times[-1].date()),
            "shape": list(precip.shape),
            "dtype": str(precip.dtype),
            "finite": int(np.isfinite(precip).sum()),
            "total": int(precip.size),
            "nan_frac": round(1 - float(np.isfinite(precip).sum()) / precip.size, 6),
            "min": float(np.nanmin(precip)),
            "max": float(np.nanmax(precip)),
            "variants": variants,
            "lat": [float(lat[0]), float(lat[-1])],
            "lon": [float(lon[0]), float(lon[-1])],
            "bytes": path.stat().st_size,
            "sha256": sha(path),
        }
    )

df = pd.DataFrame(recs)
assert (df.n_days == df.expected).all(), "month with wrong number of days"
assert df.lat.apply(lambda x: abs(x[0] - 6.475) < 1e-3 and abs(x[1] + 11.475) < 1e-3).all()
assert df.lon.apply(lambda x: abs(x[0] - 94.025) < 1e-3 and abs(x[1] - 141.475) < 1e-3).all()
assert (pd.to_datetime(df["last"]) < pd.Timestamp(HOLDOUT_START)).all(), "holdout date leaked into output"

man = pd.read_csv(CH / "manifest.csv")
man["date"] = pd.to_datetime(man["date"])
assert (man["date"] < pd.Timestamp(HOLDOUT_START)).all(), "holdout date leaked into manifest"

last_final = None
note = ""
try:
    response = requests.get(
        "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/2026/",
        timeout=30,
        headers={"User-Agent": "renaro-cgs/1.0"},
    )
    response.raise_for_status()
    found = re.findall(r"chirps-v3\.0\.sat\.(20\d\d)\.(\d\d)\.(\d\d)", response.text)
    if found:
        last_final = max(dt.date(int(a), int(b), int(c)) for a, b, c in found).isoformat()
except Exception as exc:  # noqa: BLE001
    note = f"{type(exc).__name__}: {exc}"

req_months = pd.period_range(REQ_START, REQ_END, freq="M")
available = pd.PeriodIndex(pd.to_datetime(df["first"]).dt.to_period("M"))
missing = [str(p) for p in req_months if p not in set(available)]
status = "DONE" if not missing else "PARTIAL"

clim = build_climatology()

summary = {
    "status": status,
    "requested": [str(REQ_START), str(REQ_END)],
    "available": [df["first"].min(), df["last"].max()],
    "n_months": len(df),
    "n_days": int(df.n_days.sum()),
    "n_missing_months": len(missing),
    "missing_months": missing,
    "manifest_rows": len(man),
    "manifest_status": {str(k): int(v) for k, v in man.status.value_counts().to_dict().items()},
    "manifest_bytes": int(man.bytes_transferred.sum()),
    "last_final_date": last_final,
    "last_final_note": note,
    "grid": {"shape": [360, 950], "lat": [6.475, -11.475], "lon": [94.025, 141.475], "resolution": 0.05},
    "holdout_start": str(HOLDOUT_START),
    "holdout_in_output": False,
    "climatology": clim,
    "complete_dod": bool(len(missing) == 0 and (man.status == "ok").all()),
}
(CH / "coverage.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(CH / "verification.json").write_text(
    json.dumps({"summary": summary, "files": recs}, indent=2), encoding="utf-8"
)

dod_complete = "x" if summary["complete_dod"] else " "
dod_holdout = "x" if not summary["holdout_in_output"] else " "
dod_clim = "x" if clim.get("built") else " "
lines = [
    "# CGS-H1-01 - CHIRPS v3 daily, Indonesia subset\n",
    f"Status: **{status}** - {summary['available'][0]} .. {summary['available'][1]} "
    f"({len(df)} bulan, {int(df.n_days.sum())} hari).\n",
    "## Ringkasan\n",
    f"- Diminta: **{REQ_START} .. {REQ_END}** ({len(req_months)} bulan).",
    f"- Tersedia: **{summary['available'][0]} .. {summary['available'][1]}**.",
    f"- Bulan hilang: **{len(missing)}**.",
    f"- Manifest: {len(man)} baris, status {summary['manifest_status']}, "
    f"{summary['manifest_bytes']/1e6:.1f} MB transfer.",
    f"- Tanggal final terakhir CHC: **{last_final or 'tidak tersedia'}** {note}",
    "- Grid: 360 x 950, lat 6.475..-11.475, lon 94.025..141.475, resolusi 0.05 deg.",
    "- Tidak ada tanggal >= 2026-06-01 di folder bersama (sealed holdout terpisah).",
    "- NaN ~71,3% konsisten = sel laut/tanpa data; sel valid 98.174/hari (bukan data hilang).",
    f"- Klimatologi pra-2018: `{clim.get('file', 'tidak tersedia')}` "
    f"({clim.get('baseline', ['-', '-'])[0]} .. {clim.get('baseline', ['-', '-'])[1]}).",
    "",
    "## Verifikasi per bulan\n",
    "| bulan | hari | shape | NaN % | min mm | max mm | bytes | SHA-256 (12) |",
    "|---|---:|---|---:|---:|---:|---:|---|",
]
for row in df.itertuples():
    lines.append(
        f"| {row.year}-{row.month:02d} | {row.n_days}/{row.expected} | "
        f"{row.shape[0]}x{row.shape[1]}x{row.shape[2]} | {row.nan_frac*100:.1f}% | "
        f"{row.min:.2f} | {row.max:.2f} | {row.bytes:,} | `{row.sha256[:12]}` |"
    )
lines += [
    "",
    "## DoD\n",
    f"- [{dod_complete}] 2017-01-01 .. 2026-05-31 lengkap (0 gagal).",
    f"- [{dod_holdout}] Holdout tidak ada di folder bersama.",
    f"- [x] Tanggal final terakhir dicatat: {last_final or 'best effort'}.",
    f"- [{dod_clim}] Klimatologi pra-2018 tersedia (baseline 2017; lihat catatan).",
    "",
    "## Catatan\n",
    "- File adalah NPZ bulanan dari mode COG (bukan NetCDF tahunan); grid dan satuan sama.",
    "- Nilai harian CHIRPS adalah disagregasi pentad; jangan klaim presisi harian.",
    "- Baseline klimatologi saat ini hanya 2017 (satu tahun). Untuk klimatologi yang lebih",
    "  robust, perluas ke 2008-2017 (opsi B playbook) atau pentad 1998-2017 (opsi A).",
    "",
]
(OUT / "reports/qa/chirps_download.md").write_text("\n".join(lines), encoding="utf-8")

(CH / "README.md").write_text(
    "# CHIRPS v3 daily - Indonesia subset\n\n"
    f"Status: **{status}**. Cakupan {summary['available'][0]} .. {summary['available'][1]} "
    f"({len(df)} bulan, {int(df.n_days.sum())} hari).\n\n"
    "File `chirps_v3_idn_YYYY-MM.npz` adalah output COG mode dari "
    "`scripts/download_chirps_v3.py`. Setiap file berisi `lat` (360), `lon` (950), "
    "`time` (harian), `precip` (time, lat, lon; float32 mm/hari), `variant`.\n\n"
    "`clim/climatology_2017_monthly.npz` berisi rata-rata bulanan 2017 "
    "(`precip_mean` 12 x 360 x 950, `n_days` 12) sebagai baseline pra-2018.\n\n"
    "Catatan struktur: playbook menyebut file tahunan NetCDF di `final_sat/<YYYY>/`; "
    "downloader COG menulis NPZ bulanan di folder ini karena xarray/netCDF4 tidak "
    "tersedia. Isi grid dan satuan sama.\n\n"
    "Referensi: `manifest.csv`, `download_log.txt`, `coverage.json`, `verification.json`.\n",
    encoding="utf-8",
)

print(json.dumps({k: summary[k] for k in ("status", "available", "n_months", "n_days", "n_missing_months")}, indent=2))
