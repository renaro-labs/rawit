#!/usr/bin/env python3
"""Verify the CGS-H2 package (H2-01..H2-04) against the rawit contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import (
    HOLDOUT_START,
    assert_before_holdout,
    check_columns,
    check_unique,
)

_parser = argparse.ArgumentParser(description="Verify CGS-H2 package")
_parser.add_argument("--root", default=".")
_args, _ = _parser.parse_known_args()

ROOT = Path(_args.root).resolve()
INTERIM = ROOT / "data/interim"
REPORTS = ROOT / "reports/qa"
REPORTS.mkdir(parents=True, exist_ok=True)

checks: list[dict] = []


def check(name: str, condition: bool, detail: str) -> None:
    checks.append({"check": name, "ok": bool(condition), "detail": str(detail)})
    if not condition:
        raise SystemExit(f"FAIL: {name} -> {detail}")


# ------------------------------------------------------------------ inputs
rain = pd.read_parquet(INTERIM / "rain_prov_daily.parquet")
climate = pd.read_parquet(INTERIM / "climate_features.parquet")
climatology = pd.read_parquet(INTERIM / "climatology.parquet")
availability = pd.read_csv(INTERIM / "availability.csv")
regime = pd.read_csv(INTERIM / "regime_labels.csv")
roni = pd.read_parquet(INTERIM / "roni.parquet")

rain["date"] = pd.to_datetime(rain["date"])
climate["date"] = pd.to_datetime(climate["date"])
climate["available_at"] = pd.to_datetime(climate["available_at"])
regime["date"] = pd.to_datetime(regime["date"])
roni["available_at"] = pd.to_datetime(roni["available_at"])

# ------------------------------------------------------- contract columns
check_columns(climate, "climate_features")
check_unique(climate, "climate_features")
check_columns(regime, "regime_labels")
check_unique(regime, "regime_labels")
check_columns(roni, "roni")
check_unique(roni, "roni")
check_columns(availability, "availability")
check_unique(availability, "availability")
assert_before_holdout(climate)
assert_before_holdout(regime)
check("climate available_at >= date", (climate["available_at"] >= climate["date"]).all(), "release lag")
check("roni available_at not null", roni["available_at"].notna().all(), "ron.parquet")
check("regime no holdout", (regime["date"] < pd.Timestamp(HOLDOUT_START)).all(), "date < 2026-06-01")

# ------------------------------------------------------------------ H2-01
weights = np.load(INTERIM / "w_kab_pixel.npz", allow_pickle=True)
area = pd.read_csv(ROOT / "data/raw/bps/kab_area_weights.csv")
matrix_shape = tuple(int(x) for x in weights["shape"])
check("h2-01 weight shape", matrix_shape == (514, 342000), str(matrix_shape))
check("h2-01 weight cells", int(weights["counts"].sum()) == 61825, str(int(weights["counts"].sum())))
check(
    "h2-01 weight counts match H1",
    int((np.asarray(weights["counts"]) != area["n_cells"].to_numpy()).sum()) == 0,
    "0 mismatches",
)
check("h2-01 rows", len(rain) == 116892, f"{len(rain)} rows")
check("h2-01 days", rain["date"].nunique() == 3438, f"{rain['date'].nunique()} days")
check("h2-01 provinces", rain["prov_code"].nunique() == 34, f"{rain['prov_code'].nunique()}")
check("h2-01 no NaN", rain[["rain_mm", "rain_mm_area"]].notna().all().all(), "rain columns")
check("h2-01 no holdout", (rain["date"] < pd.Timestamp(HOLDOUT_START)).all(), "date < holdout")
methods = rain.groupby(rain["date"].dt.year)["weight_method"].agg(lambda s: set(s)).to_dict()
check("h2-01 area before 2025", all(methods[y] == {"area"} for y in range(2017, 2025)), str(methods))
check("h2-01 production 2025+", all(methods[y] == {"production_2024"} for y in (2025, 2026)), str(methods))

# ------------------------------------------------------------------ H2-02
check("h2-02 rows", len(climate) == 23052, f"{len(climate)} rows")
check("h2-02 pentads", climate["date"].nunique() == 678, f"{climate['date'].nunique()} pentads")
check("h2-02 provinces", climate["prov_code"].nunique() == 34, f"{climate['prov_code'].nunique()}")
check("h2-02 no duplicate", not climate.duplicated(["date", "prov_code"]).any(), "unique (date, prov)")
per_year = climate.groupby(climate["date"].dt.year)["date"].nunique().to_dict()
check("h2-02 72 pentads/year", all(v == 72 for y, v in per_year.items() if y < 2026), str(per_year))
baseline = climate[climate["date"] < pd.Timestamp("2018-01-01")]
extreme_rate = float(baseline["extreme_5d"].mean())
check("h2-02 extreme baseline", 0.04 <= extreme_rate <= 0.07, f"{extreme_rate*100:.2f}%")
check("h2-02 climatology rows", len(climatology) == 2448, f"{len(climatology)} rows")
check("h2-02 climatology finite", climatology[["p20_global", "p95_global"]].notna().all().all(), "p20/p95")
check("h2-02 rain non-negative", (climate["rain_pentad_mm"] >= 0).all(), "rain >= 0")
check("h2-02 30d NaN edge only", int(climate["rain_30d_anom"].isna().sum()) <= 34 * 40, "edge pentads")

# ------------------------------------------------------------------ H2-03
check("h2-03 rules", len(availability) == 7, f"{len(availability)} rows")
required_families = {"rain_daily_final", "rain_pentad_final", "rain_prelim", "roni", "production_weight", "calendar", "price"}
check("h2-03 families", required_families.issubset(set(availability["feature_family"])), "coverage")
check("h2-03 final lag", int(availability.loc[availability.feature_family == "rain_daily_final", "lag_days"].iloc[0]) == 2, "2 days")
check("h2-03 no NaT", climate["available_at"].notna().all(), "available_at")

# ------------------------------------------------------------------ H2-04
check("h2-04 rows", len(regime) == 116892, f"{len(regime)} rows")
check("h2-04 dates", (regime["date"].min(), regime["date"].max()) == (pd.Timestamp("2017-01-01"), pd.Timestamp("2026-05-31")), "2017-01-01..2026-05-31")
check("h2-04 provinces", regime["prov_code"].nunique() == 34, f"{regime['prov_code'].nunique()}")
check("h2-04 no duplicate", not regime.duplicated(["date", "prov_code"]).any(), "unique (date, prov)")
check("h2-04 phases", set(regime["enso_phase"]) <= {"el_nino", "la_nina", "neutral"}, str(set(regime["enso_phase"])))
check("h2-04 labels", set(regime["label_primary"]) <= {"dry", "extreme_wet", "el_nino", "la_nina", "normal"}, str(set(regime["label_primary"])))
check("h2-04 episode", regime["episode_id"].notna().all(), "no null episode")
dry = regime["is_dry"].astype(bool)
ext = regime["is_extreme_rain"].astype(bool)
phase = regime["enso_phase"]
expected = np.select(
    [dry, ext, phase == "el_nino", phase == "la_nina"],
    ["dry", "extreme_wet", "el_nino", "la_nina"],
    default="normal",
)
check("h2-04 priority", (regime["label_primary"].to_numpy() == expected).all(), "dry > extreme > ENSO > normal")
expected_normal = (~dry) & (~ext) & (phase == "neutral")
check("h2-04 normal flag", (regime["is_normal"].astype(bool) == expected_normal).all(), "normal definition")

# ------------------------------------------------------------------ report
result = {
    "ok": all(item["ok"] for item in checks),
    "n_checks": len(checks),
    "h2_01": {"rows": len(rain), "days": int(rain.date.nunique()), "provinces": int(rain.prov_code.nunique())},
    "h2_02": {"rows": len(climate), "pentads": int(climate.date.nunique()), "extreme_baseline_pct": round(extreme_rate * 100, 2)},
    "h2_03": {"rules": len(availability)},
    "h2_04": {"rows": len(regime), "counts": regime.label_primary.value_counts().to_dict()},
    "checks": checks,
}
(REPORTS / "CGS-H2_verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

lines = [
    "# CGS-H2 - verification summary\n",
    f"Result: **{'PASS' if result['ok'] else 'FAIL'}** ({len(checks)} checks)\n",
    "## H2-01 production-weighted rainfall\n",
    f"- {len(rain):,} rows, {rain.date.nunique():,} days, {rain.prov_code.nunique()} provinces.",
    "- Weight matrix 514 x 342,000; 61,825 cells; 0 count mismatch vs H1.",
    "- Area weights 2017-2024; production_2024 weights 2025-2026.",
    "",
    "## H2-02 pentad indices\n",
    f"- {len(climate):,} rows, {climate.date.nunique()} pentads, 34 provinces.",
    f"- extreme_5d baseline rate: {extreme_rate*100:.2f}%.",
    "",
    "## H2-03 availability\n",
    f"- {len(availability)} rules; climate `available_at` non-null and >= date.",
    "",
    "## H2-04 regime labels (EVAL ONLY)\n",
    f"- {len(regime):,} daily rows, 2017-01-01..2026-05-31.",
    f"- Counts: {regime.label_primary.value_counts().to_dict()}.",
    "",
    "## Checks\n",
    f"- Total: **{len(checks)}**; failed: **{sum(1 for c in checks if not c['ok'])}**.",
]
(REPORTS / "CGS-H2_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"ok": result["ok"], "n_checks": len(checks)}, indent=2))
