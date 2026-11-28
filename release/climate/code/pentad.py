"""CGS-H2-02: pentad climate indices per province.

Input:
  data/interim/rain_prov_daily.parquet
Output:
  data/interim/climate_features.parquet
  data/interim/climatology.parquet
  reports/qa/climate_features.md

Baseline is pre-2018 only.  With the requested 2017-2026 scope the baseline is
one calendar year (2017); this is documented in the QA report.  A longer
baseline (2008-2017 or 1998-2017 pentads) can be plugged in without changing
the feature definitions.
"""
from __future__ import annotations

import argparse
import calendar
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import DRY_PENTAD_MM, EXTREME_QUANTILE

ROOT = Path(__file__).resolve().parents[3]
RAIN = ROOT / "data/interim/rain_prov_daily.parquet"
CLIMATOLOGY = ROOT / "data/interim/climatology.parquet"
OUT = ROOT / "data/interim/climate_features.parquet"
QA = ROOT / "reports/qa/climate_features.md"
BASELINE_START = pd.Timestamp("2017-01-01")
BASELINE_END = pd.Timestamp("2017-12-31")
HALF_WINDOW = 2
DROUGHT_QUANTILE = 0.20


def pentad_index(day: pd.Timestamp) -> int:
    """Pentad-of-year 1..72 (month blocks of 5 days, last block 26-end)."""
    block = min((day.day - 1) // 5, 5)
    return (day.month - 1) * 6 + block + 1


def pentad_end(day: pd.Timestamp) -> pd.Timestamp:
    month_days = calendar.monthrange(day.year, day.month)[1]
    block = min((day.day - 1) // 5, 5)
    end_day = month_days if block == 5 else block * 5 + 5
    return pd.Timestamp(day.year, day.month, end_day)


def to_pentad(rain: pd.DataFrame) -> pd.DataFrame:
    rain = rain.copy()
    rain["date"] = pd.to_datetime(rain["date"])
    rain["pentad_of_year"] = rain["date"].map(pentad_index)
    rain["pentad_end"] = rain["date"].map(pentad_end)
    grouped = (
        rain.groupby(["prov_code", "variant", "pentad_end", "pentad_of_year"], as_index=False)
        .agg(
            rain_mm=("rain_mm", "mean"),
            rain_pentad_mm=("rain_mm", "sum"),
            rain_mm_area=("rain_mm_area", "mean"),
            n_days=("rain_mm", "size"),
        )
        .rename(columns={"pentad_end": "date"})
        .sort_values(["prov_code", "date"])
        .reset_index(drop=True)
    )
    return grouped


def window_pentads(pentad: int, half: int = HALF_WINDOW) -> list[int]:
    return [((pentad - 1 + offset) % 72) + 1 for offset in range(-half, half + 1)]


def add_rolling_30d(pentad: pd.DataFrame) -> pd.DataFrame:
    """6-pentad (30-day) accumulation, per province."""
    pieces = []
    for code, group in pentad.groupby("prov_code", sort=False):
        group = group.sort_values("date").copy()
        group["rain_30d_mm"] = group["rain_pentad_mm"].rolling(6, min_periods=6).sum()
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def build_climatology(pentad: pd.DataFrame) -> pd.DataFrame:
    baseline = pentad[(pentad["date"] >= BASELINE_START) & (pentad["date"] <= BASELINE_END)].copy()
    if baseline.empty:
        raise SystemExit("baseline is empty")
    rows = []
    for code, group in baseline.groupby("prov_code", sort=False):
        overall = group["rain_pentad_mm"].to_numpy(dtype=float)
        p20_global = float(np.nanpercentile(overall, 100 * DROUGHT_QUANTILE))
        p95_global = float(np.nanpercentile(overall, 100 * EXTREME_QUANTILE))
        for p in range(1, 73):
            window = group[group["pentad_of_year"].isin(window_pentads(p))]
            values = window["rain_pentad_mm"].to_numpy(dtype=float)
            values30 = window["rain_30d_mm"].to_numpy(dtype=float)
            rows.append(
                {
                    "prov_code": code,
                    "pentad_of_year": p,
                    "mean_pentad": float(np.nanmean(values)) if np.isfinite(values).any() else np.nan,
                    "std_pentad": float(np.nanstd(values, ddof=0)) if np.isfinite(values).sum() > 1 else np.nan,
                    "p20_pentad": float(np.nanpercentile(values, 100 * DROUGHT_QUANTILE)) if np.isfinite(values).any() else np.nan,
                    "p95_pentad": float(np.nanpercentile(values, 100 * EXTREME_QUANTILE)) if np.isfinite(values).any() else np.nan,
                    "mean_30d": float(np.nanmean(values30)) if np.isfinite(values30).any() else np.nan,
                    "std_30d": float(np.nanstd(values30, ddof=0)) if np.isfinite(values30).sum() > 1 else np.nan,
                    "n_samples": int(np.isfinite(values).sum()),
                    "p20_global": p20_global,
                    "p95_global": p95_global,
                }
            )
    return pd.DataFrame(rows)


def add_features(pentad: pd.DataFrame, climatology: pd.DataFrame) -> pd.DataFrame:
    frame = pentad.merge(climatology, on=["prov_code", "pentad_of_year"], how="left")
    with np.errstate(invalid="ignore", divide="ignore"):
        frame["rain_pentad_anom"] = (frame["rain_pentad_mm"] - frame["mean_pentad"]) / frame["std_pentad"]
        frame["rain_30d_anom"] = (frame["rain_30d_mm"] - frame["mean_30d"]) / frame["std_30d"]
    frame.loc[~np.isfinite(frame["rain_pentad_anom"]), "rain_pentad_anom"] = np.nan
    frame.loc[~np.isfinite(frame["rain_30d_anom"]), "rain_30d_anom"] = np.nan
    frame["extreme_5d"] = (frame["rain_pentad_mm"] > frame["p95_global"]).astype(int)

    dry_runs = []
    for code, group in frame.groupby("prov_code", sort=False):
        group = group.sort_values("date")
        run = 0
        values = []
        for value in group["rain_pentad_mm"].to_numpy(dtype=float):
            if value < DRY_PENTAD_MM:
                run += 1
            else:
                run = 0
            values.append(run)
        dry_runs.append(pd.Series(values, index=group.index))
    frame["dry_run_pentads"] = pd.concat(dry_runs).sort_index()
    frame["dry_spell_days"] = 5.0 * frame["dry_run_pentads"]

    frame["available_at"] = frame["date"] + pd.Timedelta(days=2)
    frame["variant"] = frame["variant"].replace({"final/sat": "final_sat", "prelim/sat": "prelim_sat"})
    columns = [
        "date", "prov_code", "variant", "rain_mm", "rain_pentad_mm",
        "rain_pentad_anom", "rain_30d_anom", "dry_spell_days", "extreme_5d",
        "available_at", "pentad_of_year", "rain_30d_mm", "n_days",
    ]
    return frame[columns].sort_values(["date", "prov_code"]).reset_index(drop=True)


def qa(features: pd.DataFrame, climatology: pd.DataFrame, out: Path = QA) -> None:
    baseline = features[features["date"] < "2018-01-01"]
    extreme_rate = float(baseline["extreme_5d"].mean())
    dry_rate = float((baseline["dry_spell_days"] > 0).mean())
    lines = [
        "# CGS-H2-02 - pentad climate indices\n",
        f"- Rows: **{len(features):,}**, provinces: **{features['prov_code'].nunique()}**, "
        f"pentads: **{features['date'].nunique()}**.",
        f"- Coverage: **{features['date'].min().date()} .. {features['date'].max().date()}**.",
        f"- Missing `rain_pentad_anom`: **{int(features['rain_pentad_anom'].isna().sum())}**; "
        f"`rain_30d_anom`: **{int(features['rain_30d_anom'].isna().sum())}** "
        "(edge: pentad 1-5 in 2017, pentad 2-4 in 2018+).",
        f"- Baseline: **{BASELINE_START.date()} .. {BASELINE_END.date()}** "
        f"({climatology['n_samples'].min()}–{climatology['n_samples'].max()} samples/window).",
        f"- `extreme_5d` rate in baseline: **{extreme_rate*100:.2f}%** (target ~5%).",
        f"- `dry_spell_days > 0` rate in baseline: **{dry_rate*100:.2f}%**.",
        "- `extreme_5d` uses the per-province p95 of all baseline pentads; this keeps "
        "the baseline rate near 5% with a one-year baseline. `p20_global` is used for "
        "the dry flag in CGS-H2-04.",
        "",
        "## Per year\n",
        "| year | pentads | rain_30d_anom NaN | missing pentads | extreme_5d % | dry-spell rows |",
        "|---:|---:|---:|---|---:|---:|",
    ]
    for year, group in features.groupby(features["date"].dt.year):
        missing_pentads = sorted(group.loc[group["rain_30d_anom"].isna(), "pentad_of_year"].unique())
        missing_text = ", ".join(str(int(p)) for p in missing_pentads) if missing_pentads else "-"
        lines.append(
            f"| {year} | {group['date'].nunique()} | {int(group['rain_30d_anom'].isna().sum())} | "
            f"{missing_text} | {group['extreme_5d'].mean()*100:.2f}% | "
            f"{int((group['dry_spell_days'] > 0).sum())} |"
        )
    lines += [
        "",
        "## Notes\n",
        "- Pentad = days 1-5, 6-10, 11-15, 16-20, 21-25, 26-end (72 per year).",
        "- `rain_pentad_mm` is the sum; `rain_mm` is the daily mean in the pentad.",
        "- `dry_spell_days` = 5 x consecutive pentads with `rain_pentad_mm < 5 mm`.",
        "- `rain_30d_anom` NaNs are edge-of-baseline, not a failed 30-day sum: "
        "`rain_30d_mm` is present for every 2018+ pentad, but the 2017-only baseline "
        "has fewer than 2 finite 30-day values in the +/-2 pentad window for pentads "
        "2-4. 2017 pentads 1-5 also lack the 2016 lead-in for the 30-day sum.",
        "- Baseline is 2017 only because the requested scope starts in 2017. Extend to "
        "2008-2017 for a more robust climatology; the feature code is unchanged.",
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="CGS-H2-02 pentad features")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--rain", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--climatology", type=Path)
    parser.add_argument("--qa", type=Path)
    args = parser.parse_args()
    root = args.root
    rain_path = args.rain or root / "data/interim/rain_prov_daily.parquet"
    out_path = args.out or root / "data/interim/climate_features.parquet"
    clim_path = args.climatology or root / "data/interim/climatology.parquet"
    qa_path = args.qa or root / "reports/qa/climate_features.md"

    rain = pd.read_parquet(rain_path)
    pentad = add_rolling_30d(to_pentad(rain))
    climatology = build_climatology(pentad)
    features = add_features(pentad, climatology)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(out_path, index=False)
    climatology.to_parquet(clim_path, index=False)
    qa(features, climatology, qa_path)
    print(f"rows={len(features):,} pentads={features.date.nunique()} provinces={features.prov_code.nunique()}")
    print(f"extreme baseline={features[features.date<'2018-01-01'].extreme_5d.mean()*100:.2f}%")


if __name__ == "__main__":
    main()
