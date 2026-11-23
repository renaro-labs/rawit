"""CGS-H2-03: availability table and `available_at` application.

Rules are locked in docs/decisions/ALL-H1-01.md (Keputusan 3):
  * CHIRPS final/sat: pentad end + 2 calendar days (Opsi B, primary).
  * CHIRPS prelim/sat: release timestamp / pentad end + 5 days (Opsi A sensitivity).
  * RONI: vintage date, or conservative center_month + 3 months.
  * Production weight: year + 1.
  * Calendar: known in advance.
  * Price: next workday (lag 1).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/interim/availability.csv"
COPY = ROOT / "reports/qa/availability.csv"
REPORT = ROOT / "reports/qa/chirps_release_lag.md"
CLIMATE = ROOT / "data/interim/climate_features.parquet"
RONI = ROOT / "data/interim/roni.parquet"

RULES = [
    {
        "feature_family": "rain_daily_final",
        "source": "CHIRPS v3.0 daily final/sat",
        "variant": "final_sat",
        "rule": "pentad_end_plus_lag",
        "lag_days": 2,
        "evidence": "docs/decisions/ALL-H1-01.md#keputusan-3; reports/qa/chirps_release_lag.md",
        "decided_by": "RL",
    },
    {
        "feature_family": "rain_pentad_final",
        "source": "CHIRPS v3.0 daily final/sat",
        "variant": "final_sat",
        "rule": "pentad_end_plus_lag",
        "lag_days": 2,
        "evidence": "docs/decisions/ALL-H1-01.md#keputusan-3; reports/qa/chirps_release_lag.md",
        "decided_by": "RL",
    },
    {
        "feature_family": "rain_prelim",
        "source": "CHIRPS v3.0 daily prelim/sat",
        "variant": "prelim_sat",
        "rule": "release_timestamp",
        "lag_days": 5,
        "evidence": "docs/decisions/ALL-H1-01.md#keputusan-3 (Opsi A sensitivity)",
        "decided_by": "CGS",
    },
    {
        "feature_family": "roni",
        "source": "CPC NOAA RONI (ERSSTv6)",
        "variant": "all",
        "rule": "vintage_or_conservative_3m",
        "lag_days": None,
        "evidence": "data/raw/enso/roni_vintage_log.csv; reports/qa/roni.md",
        "decided_by": "CGS",
    },
    {
        "feature_family": "production_weight",
        "source": "Satudata Pertanian / BPS",
        "variant": "all",
        "rule": "year_plus_1",
        "lag_days": None,
        "evidence": "data/raw/bps/README.md",
        "decided_by": "protocol",
    },
    {
        "feature_family": "calendar",
        "source": "SKB 3 Menteri",
        "variant": "all",
        "rule": "known_in_advance",
        "lag_days": None,
        "evidence": "docs/data_contract.md §2.2",
        "decided_by": "protocol",
    },
    {
        "feature_family": "price",
        "source": "PIHPS / SP2KP",
        "variant": "all",
        "rule": "next_workday",
        "lag_days": 1,
        "evidence": "docs/data_contract.md §2.1",
        "decided_by": "protocol",
    },
]


def build_table() -> pd.DataFrame:
    return pd.DataFrame(RULES)


def apply_available_at(climate: pd.DataFrame, roni: pd.DataFrame, rules: pd.DataFrame):
    climate = climate.copy()
    lag = {"final_sat": 2, "prelim_sat": 5}
    unknown = set(climate["variant"].unique()) - set(lag)
    if unknown:
        raise ValueError(f"unknown climate variant(s): {sorted(unknown)}")
    climate["available_at"] = pd.to_datetime(climate["date"]) + pd.to_timedelta(
        climate["variant"].map(lag), unit="D"
    )

    roni = roni.copy()
    roni["available_at"] = pd.to_datetime(roni["available_at"], errors="coerce")
    if roni["available_at"].isna().any():
        center = pd.to_datetime(
            roni.assign(month=roni["center_month"], day=1)[["year", "month", "day"]]
        )
        fallback = center + pd.DateOffset(months=3)
        roni["available_at"] = roni["available_at"].fillna(fallback)
    return climate, roni


def validate(climate: pd.DataFrame, roni: pd.DataFrame) -> None:
    if climate["available_at"].isna().any():
        raise ValueError("climate available_at contains NaT")
    if (climate["available_at"] < pd.to_datetime(climate["date"])).any():
        raise ValueError("climate available_at < date")
    if roni["available_at"].isna().any():
        raise ValueError("roni available_at contains NaT")
    center = pd.to_datetime(
        roni.assign(month=roni["center_month"], day=1)[["year", "month", "day"]]
    )
    if (roni["available_at"] < center).any():
        raise ValueError("roni available_at before season center")


def report(climate: pd.DataFrame, roni: pd.DataFrame, rules: pd.DataFrame, out: Path = REPORT) -> None:
    lines = [
        "# CHIRPS / RONI release lag and availability rules\n",
        "Sumber keputusan: `docs/decisions/ALL-H1-01.md` (Keputusan 3) dan "
        "`docs/data_contract.md` v1.0.",
        "",
        "## Rule table\n",
        "| feature_family | source | variant | rule | lag_days | decided_by |",
        "|---|---|---|---|---:|---|",
    ]
    for row in rules.itertuples():
        lines.append(
            f"| {row.feature_family} | {row.source} | {row.variant} | {row.rule} | "
            f"{'' if row.lag_days is None else row.lag_days} | {row.decided_by} |"
        )
    lines += [
        "",
        "## Applied ranges\n",
        f"- Climate: {climate['date'].min().date()} .. {climate['date'].max().date()}; "
        f"`available_at` {climate['available_at'].min().date()} .. {climate['available_at'].max().date()}.",
        f"- RONI: {len(roni)} seasons; `available_at` non-null = {int(roni['available_at'].notna().sum())}.",
        "",
        "## Evidence and limitation\n",
        "- CHC does not publish a historical vintage archive for every daily file; "
        "the operational preliminary files appear about 2 days after the pentad end. "
        "The RL-approved Opsi B uses `pentad_end + 2 days` for final/sat and keeps "
        "Opsi A (`prelim_sim = pentad_end + 5 days`) as a sensitivity rule.",
        "- Final/sat is used as a proxy for the preliminary release; this is a "
        "deliberate, documented approximation, not an assumed actual timestamp.",
        "- RONI uses the CPC vintage date when available and otherwise the "
        "conservative `center_month + 3 months` rule; see `roni_vintage_log.csv`.",
        "- Production weights use `year + 1` (2024 production affects 2025 onward).",
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="CGS-H2-03 availability table")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--climate", type=Path)
    parser.add_argument("--roni", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = args.root
    climate_path = args.climate or root / "data/interim/climate_features.parquet"
    roni_path = args.roni or root / "data/interim/roni.parquet"
    out_path = args.out or root / "data/interim/availability.csv"

    rules = build_table()
    climate = pd.read_parquet(climate_path)
    roni = pd.read_parquet(roni_path)
    climate, roni = apply_available_at(climate, roni, rules)
    validate(climate, roni)

    climate.to_parquet(climate_path, index=False)
    roni.to_parquet(roni_path, index=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(out_path, index=False)
    copy_path = root / "reports/qa/availability.csv"
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(copy_path, index=False)
    report(climate, roni, rules, root / "reports/qa/chirps_release_lag.md")
    print(f"rules={len(rules)} climate_rows={len(climate)} roni_rows={len(roni)}")
    print(f"available_at climate {climate.available_at.min().date()} .. {climate.available_at.max().date()}")


if __name__ == "__main__":
    main()
