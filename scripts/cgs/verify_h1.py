#!/usr/bin/env python3
"""End-to-end verification for the CGS-H1 package in output/.

Checks H1-01 (CHIRPS), H1-02 (RONI) and H1-03 (production + boundaries),
writes output/verification_h1.json and output/reports/qa/CGS-H1_summary.md,
and exits non-zero if any check fails.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import re
import sqlite3
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

_parser = argparse.ArgumentParser(description="Verify CGS-H1 package")
_parser.add_argument("--root", default="output", help="package root (contains data/ and reports/)")
_args, _ = _parser.parse_known_args()

OUT = Path(_args.root).resolve()
CH = OUT / "data/raw/chirps_v3"
ENSO = OUT / "data/raw/enso"
BPS = OUT / "data/raw/bps"
BND = OUT / "data/raw/boundaries"
REPORT_DIR = OUT / "reports/qa"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

checks: list[dict] = []


def check(name: str, condition: bool, detail: str) -> None:
    checks.append({"check": name, "ok": bool(condition), "detail": detail})
    if not condition:
        raise SystemExit(f"FAIL: {name} -> {detail}")


# ------------------------------------------------------------------ H1-01
files = sorted(CH.glob("chirps_v3_idn_*.npz"))
months = sorted({re.search(r"(\d{4}-\d{2})", p.name).group(1) for p in files})
expected_months = [str(p) for p in pd.period_range("2017-01", "2026-05", freq="M")]
check("h1-01 files", len(files) == 113, f"{len(files)} files (expected 113)")
check("h1-01 months", months == expected_months, f"{len(months)} months, gaps={sorted(set(expected_months)-set(months))}")

days_total = 0
for path in files:
    year, month = map(int, re.search(r"(\d{4})-(\d{2})", path.name).groups())
    with np.load(path) as z:
        times = pd.to_datetime(z["time"])
        precip = z["precip"]
        lat = z["lat"]
        lon = z["lon"]
    check(f"h1-01 days {year}-{month:02d}", len(times) == calendar.monthrange(year, month)[1], f"{len(times)} days")
    check(f"h1-01 shape {year}-{month:02d}", precip.shape == (len(times), 360, 950), str(precip.shape))
    check(f"h1-01 lat {year}-{month:02d}", abs(float(lat[0]) - 6.475) < 1e-3 and abs(float(lat[-1]) + 11.475) < 1e-3, "lat bounds")
    check(f"h1-01 lon {year}-{month:02d}", abs(float(lon[0]) - 94.025) < 1e-3 and abs(float(lon[-1]) - 141.475) < 1e-3, "lon bounds")
    check(f"h1-01 holdout {year}-{month:02d}", times.max() < pd.Timestamp("2026-06-01"), "no holdout dates")
    days_total += len(times)
check("h1-01 days total", days_total == 3438, f"{days_total} days (expected 3438)")

manifest = pd.read_csv(CH / "manifest.csv")
check("h1-01 manifest rows", len(manifest) == 3438, f"{len(manifest)} rows")
check("h1-01 manifest status", (manifest.status == "ok").all(), str(manifest.status.value_counts().to_dict()))
check("h1-01 manifest holdout", (pd.to_datetime(manifest.date) < pd.Timestamp("2026-06-01")).all(), "no holdout dates")
clim_path = CH / "clim/climatology_2017_monthly.npz"
check("h1-01 climatology", clim_path.is_file(), str(clim_path))
if clim_path.is_file():
    with np.load(clim_path) as z:
        check("h1-01 climatology shape", z["precip_mean"].shape == (12, 360, 950), str(z["precip_mean"].shape))

# ------------------------------------------------------------------ H1-02
roni = pd.read_csv(ENSO / "roni.csv")
check("h1-02 rows", len(roni) == 915, f"{len(roni)} shared rows (6 seasons sealed at H3-02)")
check("h1-02 years", (roni.year.min(), roni.year.max()) == (1950, 2026), f"{roni.year.min()}..{roni.year.max()}")
check("h1-02 seasons", roni.season.nunique() == 12, f"{roni.season.nunique()} seasons")
check("h1-02 available_at", roni.available_at.notna().all(), "no null available_at")
check("h1-02 no sealed seasons", not (((roni.year == 2026) & (roni.center_month >= 4)).any()), "center_month < 4 for 2026")
roni_pq = pd.read_parquet(ENSO / "roni.parquet")
merged = roni.merge(roni_pq, on=["year", "season"], suffixes=("_csv", "_pq"))
check("h1-02 parquet rows", len(merged) == 915, f"{len(merged)} matched rows")
check("h1-02 parquet values", float((merged.roni_csv - merged.roni_pq).abs().max()) == 0.0, "exact match")

# ------------------------------------------------------------------ H1-03
kab = pd.read_csv(BPS / "produksi_kab.csv")
prov = pd.read_csv(BPS / "produksi_prov.csv")
check("h1-03 kab rows", len(kab) == 514, f"{len(kab)} rows")
check("h1-03 kab year", set(kab.year.unique()) == {2024}, str(sorted(kab.year.unique())))
check("h1-03 kab provinces", kab.prov_name.nunique() == 34, f"{kab.prov_name.nunique()} provinces")
check("h1-03 prov years", sorted(prov.year.unique().tolist()) == list(range(2017, 2025)), str(sorted(prov.year.unique().tolist())))
check("h1-03 totals", abs(kab.produksi_ton.sum() - prov[prov.year == 2024].produksi_ton.sum()) < 1e-6, "kab vs prov 2024 sum")
check("h1-03 no negative", (kab.produksi_ton >= 0).all(), "no negative production")
connection = sqlite3.connect(BND / "idn_adm2.gpkg")
try:
    count = connection.execute("select count(*) from adm2").fetchone()[0]
finally:
    connection.close()
check("h1-03 gpkg", count == 514, f"{count} features")

# ------------------------------------------------------------------ report
result = {
    "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    "ok": all(c["ok"] for c in checks),
    "n_checks": len(checks),
    "h1_01": {
        "months": len(files),
        "days": days_total,
        "range": ["2017-01-01", "2026-05-31"],
        "manifest_status": manifest.status.value_counts().to_dict(),
    },
    "h1_02": {"rows": len(roni), "years": [int(roni.year.min()), int(roni.year.max())]},
    "h1_03": {
        "kab_rows": len(kab),
        "province_rows": len(prov),
        "production_2024_ton": round(float(kab.produksi_ton.sum()), 3),
        "years_province": sorted(prov.year.unique().tolist()),
    },
    "checks": checks,
}
(REPORT_DIR / "CGS-H1_verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

lines = [
    "# CGS-H1 - verification summary\n",
    f"Generated: {result['generated_at']}  ",
    f"Result: **{'PASS' if result['ok'] else 'FAIL'}** ({len(checks)} checks)\n",
    "## H1-01 CHIRPS\n",
    f"- {len(files)} bulan, {days_total} hari (2017-01 .. 2026-05).",
    f"- Manifest: {manifest.status.value_counts().to_dict()}.",
    f"- Klimatologi: `{clim_path.relative_to(OUT).as_posix()}`.",
    "",
    "## H1-02 RONI\n",
    f"- {len(roni)} musim, {int(roni.year.min())}-{int(roni.year.max())}; parquet identik.",
    "",
    "## H1-03 Produksi + batas\n",
    f"- Kab/kota 2024: {len(kab)} baris, {kab.prov_name.nunique()} provinsi, "
    f"{kab.produksi_ton.sum():,.0f} ton.",
    f"- Provinsi: {sorted(prov.year.unique().tolist())}.",
    f"- GeoPackage: {count} fitur.",
    "",
    "## Checks\n",
    f"- Total: **{len(checks)}**; gagal: **{sum(1 for c in checks if not c['ok'])}**.",
]
failed = [c for c in checks if not c["ok"]]
if failed:
    lines += ["", "| check gagal | detail |", "|---|---|"]
    for item in failed:
        lines.append(f"| {item['check']} | {item['detail']} |")
else:
    lines += ["", "Semua check lulus (bulan, hari, grid, holdout, manifest, RONI, produksi, batas)."]
(REPORT_DIR / "CGS-H1_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

print(json.dumps({"ok": result["ok"], "n_checks": len(checks)}, indent=2))
