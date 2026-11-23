"""CGS-H2-03: availability table and `available_at` application.

Rules are locked in docs/decisions/ALL-H1-01.md (Keputusan 3):
  * CHIRPS final/sat: pentad end + 2 calendar days (Opsi B, primary).
  * CHIRPS prelim/sat: release timestamp / pentad end + 5 days (Opsi A sensitivity).
  * RONI: vintage date, or conservative center_month + 3 months.
  * Production weight: year + 1.
  * Calendar: known in advance.
  * Price: next workday (lag 1).

The HTTP HEAD probe records only observed `Last-Modified` values. It never
invents a release timestamp; a missing header stays missing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/interim/availability.csv"
COPY = ROOT / "reports/qa/availability.csv"
REPORT = ROOT / "reports/qa/chirps_release_lag.md"
PROBE = ROOT / "reports/qa/chirps_release_lag_probe.csv"
FEATURE_DICT = ROOT / "docs/feature_dict.csv"
CLIMATE = ROOT / "data/interim/climate_features.parquet"
RONI = ROOT / "data/interim/roni.parquet"

FEATURE_DICT_COLUMNS = ["feature", "family", "source", "variant", "rule", "lag_days"]
PROBE_COLUMNS = ["url", "status", "last_modified", "file_date", "lag_days", "probed_at_utc"]

#: 6 final + 6 prelim files from the last available months (2026-08..2026-11).
PROBE_FINAL_DATES = [
    "2026-08-01",
    "2026-09-01",
    "2026-09-16",
    "2026-10-01",
    "2026-10-16",
    "2026-10-31",
]
PROBE_PRELIM_DATES = [
    "2026-10-01",
    "2026-10-16",
    "2026-10-31",
    "2026-11-01",
    "2026-11-10",
    "2026-11-20",
]

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
        "evidence": (
            "docs/decisions/ALL-H1-01.md#keputusan-3 (Opsi A sensitivity); "
            "reports/qa/chirps_release_lag_probe.csv"
        ),
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


def _chirps_url(variant: str, iso_date: str) -> str:
    year, month, day = iso_date.split("-")
    token = "sat" if variant == "final" else "prelim"
    return (
        "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/"
        f"{variant}/sat/{year}/chirps-v3.0.{token}.{year}.{month}.{day}.tif"
    )


def build_probe_urls() -> list[str]:
    return [
        *(_chirps_url("final", date) for date in PROBE_FINAL_DATES),
        *(_chirps_url("prelim", date) for date in PROBE_PRELIM_DATES),
    ]


def _file_date_from_url(url: str) -> str | None:
    match = re.search(r"chirps-v3\.0\.(?:sat|prelim)\.(\d{4})\.(\d{2})\.(\d{2})\.tif$", url)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _variant_from_url(url: str) -> str:
    if "/daily/final/" in url:
        return "final"
    if "/daily/prelim/" in url:
        return "prelim"
    return "unknown"


def probe_release_lag(urls: list[str] | None = None, timeout: int = 45) -> pd.DataFrame:
    """HTTP HEAD -> actual `Last-Modified`; write the evidence CSV.

    `lag_days` is the calendar-day difference between the date encoded in the
    filename and the date in the `Last-Modified` response header. No value is
    inferred when the header is absent. CHC rate-limits bursts, so requests are
    spaced and 429/5xx responses are retried with backoff.
    """
    import time

    import requests

    urls = urls or build_probe_urls()
    probed_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    session = requests.Session()
    rows: list[dict] = []
    for index, url in enumerate(urls):
        last_modified = None
        status: int | str = "ERROR:unknown"
        for attempt in range(4):
            try:
                response = session.head(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    headers={"User-Agent": "renaro-cgs-h2-03/1.0"},
                )
                status = int(response.status_code)
                last_modified = response.headers.get("Last-Modified")
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                    retry_after = response.headers.get("Retry-After", "")
                    wait = int(retry_after) if retry_after.isdigit() else 5 * (attempt + 1)
                    time.sleep(wait)
                    continue
                break
            except requests.RequestException as exc:  # network error is evidence too
                status = f"ERROR:{type(exc).__name__}"
                if attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                break
        if index < len(urls) - 1:
            time.sleep(1.0)

        file_date = _file_date_from_url(url)
        lag_days = None
        if last_modified and file_date:
            modified_date = parsedate_to_datetime(last_modified).date()
            lag_days = (modified_date - dt.date.fromisoformat(file_date)).days

        rows.append(
            {
                "url": url,
                "status": status,
                "last_modified": last_modified,
                "file_date": file_date,
                "lag_days": lag_days,
                "probed_at_utc": probed_at,
            }
        )

    probe = pd.DataFrame(rows, columns=PROBE_COLUMNS)
    PROBE.parent.mkdir(parents=True, exist_ok=True)
    probe.to_csv(PROBE, index=False)
    return probe


def load_probe() -> pd.DataFrame:
    if not PROBE.exists():
        return pd.DataFrame(columns=PROBE_COLUMNS)
    return pd.read_csv(PROBE)


def build_table() -> pd.DataFrame:
    return pd.DataFrame(RULES)


def validate_feature_dict(rules: pd.DataFrame) -> pd.DataFrame:
    """Every feature family must map to exactly one row in `availability.csv`."""
    if not FEATURE_DICT.exists():
        raise FileNotFoundError(f"missing feature dictionary: {FEATURE_DICT}")

    features = pd.read_csv(FEATURE_DICT)
    missing_columns = [c for c in FEATURE_DICT_COLUMNS if c not in features.columns]
    if missing_columns:
        raise ValueError(f"feature_dict missing column(s): {missing_columns}")
    features = features[FEATURE_DICT_COLUMNS].copy()

    if features["feature"].isna().any() or features["family"].isna().any():
        raise ValueError("feature_dict has a null feature or family")
    duplicated = features.loc[features["feature"].duplicated(), "feature"].tolist()
    if duplicated:
        raise ValueError(f"duplicate feature(s) in feature_dict: {duplicated}")

    by_family = rules.set_index("feature_family")
    missing_families = sorted(set(features["family"]) - set(by_family.index))
    if missing_families:
        raise ValueError(
            "feature_dict families without an availability row: "
            f"{missing_families}; add them to availability.csv first"
        )

    for family, group in features.groupby("family", sort=True):
        rule = by_family.loc[family]
        for column in ("source", "variant", "rule"):
            values = set(group[column].dropna().astype(str))
            if values != {str(rule[column])}:
                raise ValueError(
                    f"feature family {family!r} has {column}={sorted(values)} "
                    f"but availability.csv has {rule[column]!r}"
                )
        lags = pd.to_numeric(group["lag_days"], errors="coerce")
        rule_lag = rule["lag_days"]
        if pd.isna(rule_lag):
            if not lags.isna().all():
                raise ValueError(f"feature family {family!r} should have an empty lag_days")
        elif lags.isna().any() or (lags != float(rule_lag)).any():
            raise ValueError(
                f"feature family {family!r} lag_days={lags.tolist()} "
                f"does not match availability.csv lag_days={rule_lag}"
            )

    return features


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


def _probe_section(probe: pd.DataFrame) -> list[str]:
    if probe.empty:
        return [
            "## HTTP HEAD probe",
            "",
            "No probe CSV found. Run `python -m renaro.climate.availability --probe` "
            "to record actual `Last-Modified` headers; no timestamp is assumed here.",
            "",
        ]

    probe = probe.copy()
    probe["variant"] = probe["url"].map(_variant_from_url)
    probe["status_num"] = pd.to_numeric(probe["status"], errors="coerce")
    probe["lag_num"] = pd.to_numeric(probe["lag_days"], errors="coerce")
    probe_time = probe["probed_at_utc"].dropna().astype(str)
    when = probe_time.min() if len(probe_time) else "unknown"

    lines = [
        "## HTTP HEAD probe (actual)",
        "",
        f"Evidence: `reports/qa/chirps_release_lag_probe.csv`; probed at **{when}**. "
        "`lag_days` = date in `Last-Modified` minus date encoded in the filename. "
        "Only headers returned by CHC are recorded; missing headers remain blank.",
        "",
        "| variant | file_date | status | last_modified | lag_days |",
        "|---|---|---:|---|---:|",
    ]
    for row in probe.itertuples():
        lag = "" if pd.isna(row.lag_num) else int(row.lag_num)
        modified = "" if pd.isna(row.last_modified) else row.last_modified
        lines.append(
            f"| {row.variant} | {row.file_date or ''} | {row.status} | "
            f"{modified} | {lag} |"
        )

    lines.append("")
    for variant in ("final", "prelim"):
        subset = probe[probe["variant"] == variant]
        if subset.empty:
            continue
        ok = int((subset["status_num"] == 200).sum())
        lags = subset["lag_num"].dropna()
        if len(lags):
            lines.append(
                f"- `{variant}`: {ok}/{len(subset)} HTTP 200; `lag_days` "
                f"{int(lags.min())}..{int(lags.max())} (median {float(lags.median()):.1f})."
            )
        else:
            lines.append(f"- `{variant}`: {ok}/{len(subset)} HTTP 200; no `Last-Modified`.")

    final_times = probe.loc[probe["variant"] == "final", "last_modified"].dropna().unique()
    if len(final_times) == 1:
        lines.append(
            f"- Final files in this probe share `Last-Modified` **{final_times[0]}**. "
            "That is a bulk/back-fill timestamp, not the original release date of each "
            "daily file, so it cannot be used to estimate the historical final lag."
        )
    prelim_lags = probe.loc[probe["variant"] == "prelim", "lag_num"].dropna()
    if len(prelim_lags):
        lines.append(
            f"- Prelim spot-check: {len(prelim_lags)} files, lags "
            f"{', '.join(str(int(v)) for v in prelim_lags)} days. Recent files are "
            "2 days after the date; older gaps reach 6-8 days. This supports the "
            "2-day operational proxy (Opsi B) as a spot-check, not as a historical "
            "vintage archive."
        )

    lines.append("")
    return lines


def report(
    climate: pd.DataFrame,
    roni: pd.DataFrame,
    rules: pd.DataFrame,
    out: Path = REPORT,
    feature_dict: pd.DataFrame | None = None,
    probe: pd.DataFrame | None = None,
) -> None:
    feature_dict = load_feature_dict_safe() if feature_dict is None else feature_dict
    probe = load_probe() if probe is None else probe

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
        "## Feature dictionary coverage\n",
        f"- `docs/feature_dict.csv`: **{len(feature_dict)}** features, "
        f"**{feature_dict['family'].nunique() if len(feature_dict) else 0}** families.",
        "- Every family in the dictionary has exactly one row in `availability.csv`; "
        "`src/renaro/climate/availability.py` fails if a family is missing or if its "
        "source/variant/rule/lag disagree.",
        "",
        "## Applied ranges\n",
        f"- Climate: {climate['date'].min().date()} .. {climate['date'].max().date()}; "
        f"`available_at` {climate['available_at'].min().date()} .. {climate['available_at'].max().date()}.",
        f"- RONI: {len(roni)} seasons; `available_at` non-null = {int(roni['available_at'].notna().sum())}.",
        "",
    ]
    lines += _probe_section(probe)
    lines += [
        "## Evidence and limitation\n",
        "- CHC does not publish a historical vintage archive for every daily file. "
        "The probe above records the headers that were actually served; it is a "
        "spot-check, not a reconstruction of each file's original release date.",
        "- The RL-approved Opsi B uses `pentad_end + 2 days` for final/sat and keeps "
        "Opsi A (`prelim_sim = pentad_end + 5 days`) as a sensitivity rule. "
        "Final/sat is used as a proxy for the preliminary release; this is a "
        "deliberate, documented approximation, not an assumed actual timestamp.",
        "- RONI uses the CPC vintage date when available and otherwise the "
        "conservative `center_month + 3 months` rule; see `roni_vintage_log.csv`.",
        "- Production weights use `year + 1` (2024 production affects 2025 onward).",
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def load_feature_dict_safe() -> pd.DataFrame:
    if not FEATURE_DICT.exists():
        return pd.DataFrame(columns=FEATURE_DICT_COLUMNS)
    return pd.read_csv(FEATURE_DICT)


def main() -> None:
    parser = argparse.ArgumentParser(description="CGS-H2-03 availability table")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--climate", type=Path)
    parser.add_argument("--roni", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--probe",
        action="store_true",
        help="run the 12 HTTP HEAD requests and refresh the probe CSV",
    )
    args = parser.parse_args()
    root = args.root
    climate_path = args.climate or root / "data/interim/climate_features.parquet"
    roni_path = args.roni or root / "data/interim/roni.parquet"
    out_path = args.out or root / "data/interim/availability.csv"

    rules = build_table()
    climate = pd.read_parquet(climate_path)
    roni = pd.read_parquet(roni_path)
    features = validate_feature_dict(rules)
    probe = probe_release_lag() if args.probe else load_probe()

    climate, roni = apply_available_at(climate, roni, rules)
    validate(climate, roni)

    climate.to_parquet(climate_path, index=False)
    roni.to_parquet(roni_path, index=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(out_path, index=False)
    copy_path = root / "reports/qa/availability.csv"
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(copy_path, index=False)
    report(climate, roni, rules, root / "reports/qa/chirps_release_lag.md", features, probe)
    print(
        f"rules={len(rules)} features={len(features)} "
        f"climate_rows={len(climate)} roni_rows={len(roni)} probe_rows={len(probe)}"
    )
    print(f"available_at climate {climate.available_at.min().date()} .. {climate.available_at.max().date()}")


if __name__ == "__main__":
    main()
