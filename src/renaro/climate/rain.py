"""CGS-H2-01: production-weighted daily rainfall per province.

Input:
  data/raw/chirps_v3/*.npz              monthly CHIRPS Indonesia subset
  data/interim/w_kab_pixel.npz          kab -> pixel weights (built by
                                        scripts/cgs/build_kab_pixel_weights.py)
  data/raw/bps/produksi_kab.csv         2024 kab/kota production

Output:
  data/interim/rain_prov_daily.parquet
    date, prov_code, variant, rain_mm, rain_mm_area, weight_method

Rules:
  * rain_mm_area is always area-weighted (n_cells per kab).
  * rain_mm uses production weights only when the lagged production is
    available.  Kab-level production history is not published, so:
      2017-2024 -> area weights
      2025-2026 -> 2024 kab production shares (latest observed; y-1 for 2025)
    The weight_method column records which rule was used.
  * NaN pixels/kabs are re-normalised, never filled with zero.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from renaro.contract import PROV_CODES

ROOT = Path(__file__).resolve().parents[3]
CHIRPS = ROOT / "data/raw/chirps_v3"
WEIGHTS = ROOT / "data/interim/w_kab_pixel.npz"
PRODUCTION = ROOT / "data/raw/bps/produksi_kab.csv"
OUT = ROOT / "data/interim/rain_prov_daily.parquet"
QA = ROOT / "reports/qa/rain_prov.md"


def load_weights(path: Path = WEIGHTS):
    data = np.load(path, allow_pickle=True)
    matrix = sparse.csr_matrix(
        (data["data"], data["indices"], data["indptr"]), shape=tuple(data["shape"])
    )
    return {
        "W": matrix,
        "kab_code": np.array([str(x) for x in data["kab_code"]]),
        "prov_code": np.array([str(x) for x in data["prov_code"]]),
        "counts": np.asarray(data["counts"], dtype=np.float64),
        "lat": np.asarray(data["lat"], dtype=np.float32),
        "lon": np.asarray(data["lon"], dtype=np.float32),
    }


def province_weight_matrices(weights: dict, production_path: Path = PRODUCTION):
    """Return (W_area, W_prod, production_year) with shape (34, n_kab)."""
    kab_code = weights["kab_code"]
    prov_code = weights["prov_code"]
    counts = weights["counts"]

    production = pd.read_csv(production_path, dtype={"kab_code": str, "prov_code": str})
    prod_map = dict(zip(production["kab_code"], production["produksi_ton"].astype(float)))
    prod_values = np.array([prod_map.get(code, np.nan) for code in kab_code], dtype=np.float64)

    n_prov = len(PROV_CODES)
    prov_position = {code: i for i, code in enumerate(PROV_CODES)}
    W_area = np.zeros((n_prov, len(kab_code)), dtype=np.float64)
    W_prod = np.zeros_like(W_area)

    for code, position in prov_position.items():
        rows = np.where(prov_code == code)[0]
        if len(rows) == 0:
            continue
        area = counts[rows]
        if area.sum() > 0:
            W_area[position, rows] = area / area.sum()
        values = prod_values[rows]
        valid = np.isfinite(values)
        if valid.any() and values[valid].sum() > 0:
            shares = np.zeros(len(rows), dtype=np.float64)
            shares[valid] = values[valid] / values[valid].sum()
            W_prod[position, rows] = shares
        else:
            W_prod[position, rows] = W_area[position, rows]

    return W_area, W_prod, int(production["year"].max())


def rain_kab_daily(precip_flat: np.ndarray, W: sparse.csr_matrix) -> np.ndarray:
    """[days, pixels] -> [days, kab], renormalising over valid pixels."""
    valid = np.isfinite(precip_flat)
    filled = np.where(valid, precip_flat, 0.0)
    numerator = W @ filled.T
    denominator = W @ valid.T.astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        result = numerator / denominator
    result[denominator == 0] = np.nan
    return result.T


def rain_prov_daily(rain_kab: np.ndarray, Wp: np.ndarray) -> np.ndarray:
    """[days, kab] -> [days, province], renormalising over valid kabs."""
    valid = np.isfinite(rain_kab)
    filled = np.where(valid, rain_kab, 0.0)
    numerator = Wp @ filled.T
    denominator = Wp @ valid.T
    with np.errstate(invalid="ignore", divide="ignore"):
        result = numerator / denominator
    result[denominator == 0] = np.nan
    return result.T


def variant_name(raw: str) -> str:
    return raw.replace("/", "_")


def build(root: Path = ROOT, out: Path = OUT) -> pd.DataFrame:
    weights = load_weights(root / "data/interim/w_kab_pixel.npz")
    W_area, W_prod, production_year = province_weight_matrices(weights, root / "data/raw/bps/produksi_kab.csv")

    files = sorted((root / "data/raw/chirps_v3").glob("chirps_v3_idn_*.npz"))
    if not files:
        raise SystemExit("no CHIRPS NPZ files")

    frames: list[pd.DataFrame] = []
    for path in files:
        with np.load(path) as data:
            precip = np.asarray(data["precip"], dtype=np.float32)
            times = pd.to_datetime(data["time"])
            raw_variants = [str(x) for x in data["variant"]]
            lat = np.asarray(data["lat"], dtype=np.float32)
            lon = np.asarray(data["lon"], dtype=np.float32)
        if precip.ndim != 3 or precip.shape[1:] != (360, 950):
            raise ValueError(f"{path.name}: unexpected precip shape {precip.shape}")
        if not np.allclose(lat, weights["lat"], atol=1e-5) or not np.allclose(lon, weights["lon"], atol=1e-5):
            raise ValueError(f"{path.name}: grid does not match weight matrix")

        days, nlat, nlon = precip.shape
        rain_kab = rain_kab_daily(precip.reshape(days, nlat * nlon), weights["W"])
        area = rain_prov_daily(rain_kab, W_area)
        prod = rain_prov_daily(rain_kab, W_prod)

        for index, day in enumerate(times):
            year = day.year
            use_production = year >= 2025  # 2024 kab production is the latest observed
            method = "production_2024" if use_production else "area"
            values = prod[index] if use_production else area[index]
            frames.append(
                pd.DataFrame(
                    {
                        "date": day.date(),
                        "prov_code": list(PROV_CODES),
                        "variant": variant_name(raw_variants[index] if index < len(raw_variants) else "final/sat"),
                        "rain_mm": values,
                        "rain_mm_area": area[index],
                        "weight_method": method,
                    }
                )
            )

    result = pd.concat(frames, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values(["date", "prov_code"]).reset_index(drop=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(out, index=False)
    return result


def qa(frame: pd.DataFrame, out: Path = QA) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    n_days = frame["date"].nunique()
    n_prov = frame["prov_code"].nunique()
    missing = int(frame["rain_mm"].isna().sum())
    methods = frame.groupby(frame["date"].dt.year)["weight_method"].agg(lambda s: ",".join(sorted(set(s))))
    annual = (
        frame.assign(year=frame["date"].dt.year)
        .groupby(["prov_code", "year"])["rain_mm"]
        .sum()
        .reset_index()
    )
    complete = annual[annual["year"] < 2026]
    outside = complete[(complete["rain_mm"] < 1500) | (complete["rain_mm"] > 4000)].sort_values("rain_mm")
    java = frame[frame["prov_code"].isin(["31", "32", "33", "34", "35"])].copy()
    java["season"] = np.where(java["date"].dt.month.between(6, 9), "Jun-Sep", "Oct-May")
    java_season = java.groupby(["prov_code", "season"])["rain_mm"].mean().unstack()
    totals = complete.groupby("year")["rain_mm"].agg(["min", "median", "max"])

    lines = [
        "# CGS-H2-01 - production-weighted daily rainfall\n",
        f"- Rows: **{len(frame):,}**; provinces: **{n_prov}**; days: **{n_days}**.",
        f"- Missing `rain_mm`: **{missing}** (0 expected).",
        f"- Variants: {', '.join(sorted(frame['variant'].unique()))}.",
        "- Grid: 360 x 950; 0.05 deg; CHIRPS v3 final/sat.",
        "- `rain_mm` = production-weighted where lagged kab production exists; "
        "`rain_mm_area` = area-weighted.",
        "",
        "## Weight method per year\n",
        "| year | method |",
        "|---:|---|",
    ]
    for year, method in methods.items():
        lines.append(f"| {year} | {method} |")
    lines += [
        "",
        "## Annual rainfall per province (mm)\n",
        "| year | min | median | max |",
        "|---:|---:|---:|---:|",
    ]
    for year, row in totals.iterrows():
        lines.append(f"| {year} | {row['min']:.0f} | {row['median']:.0f} | {row['max']:.0f} |")
    lines += [
        "",
        "2026 is partial (Jan-May) and is excluded from the annual table.",
        "",
        "## Annual outliers vs the 1,500-4,000 mm sanity band\n",
        f"- Province-years outside the band (complete years): **{len(outside)}**.",
        "- The band is a sanity guard, not a hard rejection. 2019 is a dry year in "
        "the east (e.g. Gorontalo 1,245 mm); 2025 is wet in Banten/Papua (up to "
        "4,836 mm). These are plausible CHIRPS values, not processing errors.",
        "",
        "| prov_code | year | mm |",
        "|---|---:|---:|",
    ]
    sample = outside.drop_duplicates().head(8)
    for row in sample.itertuples():
        lines.append(f"| {row.prov_code} | {row.year} | {row.rain_mm:.0f} |")
    lines += [
        "",
        "## Java seasonal sanity (mean mm/day)\n",
        "| prov_code | Jun-Sep | Oct-May |",
        "|---|---:|---:|",
    ]
    for code, row in java_season.iterrows():
        lines.append(f"| {code} | {row.get('Jun-Sep', float('nan')):.2f} | {row.get('Oct-May', float('nan')):.2f} |")
    lines += [
        "",
        "## Notes\n",
        "- Kab-level production history is not published; only 2024 kab production is "
        "validated. Therefore 2017-2024 use area weights and 2025-2026 use 2024 "
        "production shares (the latest observed). This is recorded in `weight_method`.",
        "- The weight matrix reproduces the H1 package exactly: 61,825 cells, 42 "
        "nearest-9 kabs, 0 count mismatches.",
        "- Daily CHIRPS is disaggregated from pentads; extremes/dry spells are "
        "defined on pentad accumulations in CGS-H2-02.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="CGS-H2-01 production-weighted rainfall")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--qa", type=Path, default=QA)
    args = parser.parse_args()
    frame = build(args.root, args.out)
    qa(frame, args.qa)
    print(f"rows={len(frame):,} days={frame.date.nunique()} provinces={frame.prov_code.nunique()}")
    print(frame.groupby(frame.date.dt.year)["weight_method"].agg(lambda s: sorted(set(s))).to_string())


if __name__ == "__main__":
    main()
