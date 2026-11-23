"""CGS-H2-04: regime labels (EVAL ONLY).

Definitions (defaults, to be locked by RL-H2-01):
  ENSO   : RONI phase (el_nino / la_nina / neutral), from the official episode table.
  Dry    : rain_pentad_mm < p20 of the pre-2018 baseline for >= 3 consecutive pentads.
  Extreme: extreme_5d == 1 (pentad accumulation > p95 of the baseline).
  Normal : not dry, not extreme, ENSO neutral.
  Priority: dry > extreme_wet > el_nino > la_nina > normal.

Labels are expanded from pentad-end rows to every calendar day in the pentad so
they can be joined to the daily panel.  They must never enter model features.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import HOLDOUT_START, ORIGINS

ROOT = Path(__file__).resolve().parents[3]
CLIMATE = ROOT / "data/interim/climate_features.parquet"
CLIMATOLOGY = ROOT / "data/interim/climatology.parquet"
RONI = ROOT / "data/interim/roni.parquet"
OUT = ROOT / "data/interim/regime_labels.csv"
DEFINITIONS = ROOT / "docs/regime_definitions.md"
COUNTS = ROOT / "reports/qa/regime_counts.md"

PHASE_MAP = {"elnino": "el_nino", "lanina": "la_nina", "neutral": "neutral"}
DROUGHT_MIN_PENTADS = 3
PRIORITY = ("dry", "extreme_wet", "el_nino", "la_nina", "normal")


def enso_by_date(climate: pd.DataFrame, roni: pd.DataFrame) -> pd.DataFrame:
    """Assign the latest RONI season already available at each date (as-of)."""
    frame = climate.copy()
    frame["date"] = pd.to_datetime(frame["date"]).astype("datetime64[ns]")
    frame = frame.sort_values("date")
    lookup = roni.copy()
    lookup["enso_phase"] = lookup["phase"].map(PHASE_MAP)
    if lookup["enso_phase"].isna().any():
        raise ValueError(f"unknown RONI phase(s): {sorted(lookup.loc[lookup.enso_phase.isna(), 'phase'].unique())}")
    lookup["episode_id"] = lookup["episode_id"].fillna("none")
    lookup["roni_available_at"] = pd.to_datetime(lookup["available_at"]).astype("datetime64[ns]")
    lookup = lookup.sort_values("roni_available_at")
    merged = pd.merge_asof(
        frame,
        lookup[["roni_available_at", "enso_phase", "episode_id"]],
        left_on="date",
        right_on="roni_available_at",
        direction="backward",
    )
    if merged["enso_phase"].isna().any():
        missing = merged.loc[merged.enso_phase.isna(), "date"].drop_duplicates()
        raise ValueError(f"no RONI season available for {len(missing)} dates")
    return merged


def mark_dry(climate: pd.DataFrame, climatology: pd.DataFrame) -> pd.DataFrame:
    thresholds = climatology[["prov_code", "pentad_of_year", "p20_global"]].drop_duplicates()
    frame = climate.merge(thresholds, on=["prov_code", "pentad_of_year"], how="left", validate="many_to_one")
    if frame["p20_global"].isna().any():
        raise ValueError("missing p20_global threshold")
    frame = frame.sort_values(["prov_code", "date"]).reset_index(drop=True)
    flags = []
    for code, group in frame.groupby("prov_code", sort=False):
        run = 0
        values = []
        for below in (group["rain_pentad_mm"] < group["p20_global"]).to_numpy():
            run = run + 1 if below else 0
            values.append(run >= DROUGHT_MIN_PENTADS)
        flags.append(pd.Series(values, index=group.index))
    frame["is_dry"] = pd.concat(flags).sort_index()
    frame["is_extreme_rain"] = frame["extreme_5d"].astype(bool)
    return frame


def primary_label(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["is_normal"] = (
        (~frame["is_dry"])
        & (~frame["is_extreme_rain"])
        & (frame["enso_phase"] == "neutral")
    )
    labels = np.select(
        [
            frame["is_dry"],
            frame["is_extreme_rain"],
            frame["enso_phase"] == "el_nino",
            frame["enso_phase"] == "la_nina",
        ],
        ["dry", "extreme_wet", "el_nino", "la_nina"],
        default="normal",
    )
    frame["label_primary"] = labels
    return frame


def expand_daily(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in frame.itertuples():
        end = pd.Timestamp(row.date)
        days = int(getattr(row, "n_days", 5) or 5)
        for day in pd.date_range(end - pd.Timedelta(days=days - 1), end, freq="D"):
            rows.append(
                {
                    "date": day,
                    "prov_code": row.prov_code,
                    "enso_phase": row.enso_phase,
                    "episode_id": row.episode_id,
                    "is_dry": bool(row.is_dry),
                    "is_extreme_rain": bool(row.is_extreme_rain),
                    "is_normal": bool(row.is_normal),
                    "label_primary": row.label_primary,
                    "pentad_end": end,
                }
            )
    return pd.DataFrame(rows).sort_values(["date", "prov_code"]).reset_index(drop=True)


def parse_range(text: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    if not text or ".." not in text:
        return None
    start, end = text.split("..", 1)
    return pd.Timestamp(start), pd.Timestamp(end)


def regime_counts(labels: pd.DataFrame, out: Path = COUNTS) -> pd.DataFrame:
    records = []
    for origin, parts in ORIGINS.items():
        for part, text in parts.items():
            if part == "test" and text == "SEALED":
                records.append({"origin": origin, "part": part, "regime": "SEALED", "node_days": np.nan, "flag": ""})
                continue
            window = parse_range(text)
            if window is None:
                continue
            start, end = window
            subset = labels[(labels["date"] >= start) & (labels["date"] <= end)]
            counts = subset["label_primary"].value_counts()
            for regime in PRIORITY:
                node_days = int(counts.get(regime, 0))
                records.append(
                    {
                        "origin": origin,
                        "part": part,
                        "regime": regime,
                        "node_days": node_days,
                        "flag": "CI lebar" if node_days < 200 else "",
                    }
                )
    table = pd.DataFrame(records)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CGS-H2-04 - regime counts\n",
        "Node-days are calendar days; the evaluation loader can restrict them to workdays.",
        "",
        "| origin | part | regime | node_days | flag |",
        "|---|---|---|---:|---|",
    ]
    for row in table.itertuples():
        value = "" if pd.isna(row.node_days) else f"{int(row.node_days):,}"
        lines.append(f"| {row.origin} | {row.part} | {row.regime} | {value} | {row.flag} |")
    lines += [
        "",
        "## Total by regime (all dates < 2026-06-01)\n",
        "| regime | node_days |",
        "|---|---:|",
    ]
    for regime, value in labels["label_primary"].value_counts().items():
        lines.append(f"| {regime} | {value:,} |")
    out.write_text("\n".join(lines), encoding="utf-8")
    return table


def write_definitions(out: Path = DEFINITIONS) -> None:
    text = """# Regime definitions (CGS-H2-04)

**EVAL ONLY.** These labels must never be joined to `panel.parquet` or used as
model features.  The priority order is: `dry` > `extreme_wet` > `el_nino` >
`la_nina` > `normal`.

## ENSO

`enso_phase` comes from the official RONI episode table (`data/raw/enso/roni.csv`),
which applies the NOAA 5-season +/-0.5 rule.  For each date we use the **latest
season whose `available_at` is <= the date** (as-of join), so a label never uses
a season published after the date.  `episode_id` is copied from the episode
table; neutral rows use `none`.

## Dry

`rain_pentad_mm < p20_global` for at least 3 consecutive pentads.  `p20_global`
is the 20th percentile of the pre-2018 baseline pentads for the province (2017
in the current scope).  The label is applied to every calendar day in the
qualifying pentad.

## Extreme wet

`extreme_5d == 1`: pentad accumulation above the province's p95 baseline
(5% exceedance in the baseline).  Applied to every day in the pentad.

## Normal

Not dry, not extreme wet, and ENSO neutral.

## Coverage

Only dates `< 2026-06-01` are written.  The holdout is sealed separately.
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="CGS-H2-04 regime labels")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--climate", type=Path)
    parser.add_argument("--climatology", type=Path)
    parser.add_argument("--roni", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = args.root
    climate_path = args.climate or root / "data/interim/climate_features.parquet"
    clim_path = args.climatology or root / "data/interim/climatology.parquet"
    roni_path = args.roni or root / "data/interim/roni.parquet"
    out_path = args.out or root / "data/interim/regime_labels.csv"

    climate = pd.read_parquet(climate_path)
    climatology = pd.read_parquet(clim_path)
    roni = pd.read_parquet(roni_path)

    frame = enso_by_date(climate, roni)
    frame = mark_dry(frame, climatology)
    frame = primary_label(frame)
    labels = expand_daily(frame)

    if (labels["date"] >= pd.Timestamp(HOLDOUT_START)).any():
        raise ValueError("holdout dates leaked into regime labels")
    if labels.duplicated(["date", "prov_code"]).any():
        raise ValueError("duplicate (date, prov_code) in regime labels")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    labels.to_csv(out_path, index=False)
    write_definitions(root / "docs/regime_definitions.md")
    regime_counts(labels, root / "reports/qa/regime_counts.md")
    print(f"rows={len(labels):,} dates={labels.date.min().date()}..{labels.date.max().date()}")
    print(labels["label_primary"].value_counts().to_string())


if __name__ == "__main__":
    main()
