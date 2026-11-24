"""MDE-H3-01 · Merge -> dataset v1 (panel date x prov_code dengan fitur as-of).

Aturan join (tidak boleh diganti):
  * fitur (harga lag, iklim, RONI) -> pd.merge_asof(left_on="date",
    right_on="available_at", by="prov_code", direction="backward"); kolom
    `<sumber>__avail` menyimpan available_at baris yang terpakai.
  * kalender -> join langsung pada date (diketahui di muka).
  * target -> price_type=1; NaN TIDAK diimputasi.
  * label regime / fase ENSO TIDAK PERNAH masuk panel.

Catatan kolom `price` di panel: sesuai kontrak §2.7 dan loader MLE
(`renaro.data.datasets.WindowDataset` menggeser `price` 1 hari kerja), `panel.price`
adalah harga observasi HARI ITU (= target), bukan fitur as-of. Fitur harga yang
aman dipakai langsung adalah kolom `price_lag1`, `price_logret5`, dst.

CLI: scripts/build_dataset.py
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import (
    HOLDOUT_START, PROV_CODES, TABLE_COLUMNS, check_columns, check_unique,
    content_hash, write_sha256sums,
)

PRICE_TYPE_TARGET = 1
PRICE_TYPE_PRODUCER = 4
CLIMATE_VARIANT = "final_sat"          # availability.csv: rain_pentad_final (Opsi B)
CLIMATE_COLS = ("rain_mm", "rain_pentad_mm", "rain_pentad_anom", "rain_30d_anom",
                "dry_spell_days", "extreme_5d")
CALENDAR_COLS = ("is_holiday", "is_cuti_bersama", "is_ramadan", "days_to_lebaran",
                 "days_to_iduladha", "is_natal_tahunbaru", "is_post_lebaran",
                 "dow", "month", "doy")
#: Kriteria cakupan node (MDE-H1-03 / brief §10.1).
COVERAGE_MIN = 0.90
COVERAGE_MIN_YEARS = 5
COVERAGE_YEARS = (2018, 2025)
#: Nama kolom yang dilarang di panel (eval-only / bocor label).
FORBIDDEN_TOKENS = ("regime", "label", "phase", "episode", "is_dry", "is_normal", "is_extreme")
VERSION = "v1"
#: Pembulatan fitur turunan (log) supaya hash reproducible lintas versi pandas/numpy.
FLOAT_DECIMALS = 10


@dataclass
class Inputs:
    prices: pd.DataFrame
    calendar: pd.DataFrame
    provinces: pd.DataFrame
    coverage: pd.DataFrame
    mask: np.ndarray
    roni: pd.DataFrame | None
    climate: pd.DataFrame | None
    paths: dict = field(default_factory=dict)


# ----------------------------------------------------------------------- input
def input_paths(raw_root: Path, coverage: Path | None = None) -> dict[str, Path]:
    raw_root = Path(raw_root)
    interim = raw_root / "interim"
    roni = interim / "roni.parquet"
    if not roni.exists():  # CGS menyimpan salinan bersama di data/raw/enso/
        roni = raw_root / "raw" / "enso" / "roni.parquet"
    return {
        "prices": interim / "prices_clean.parquet",
        "calendar": interim / "calendar.csv",
        "climate": interim / "climate_features.parquet",
        "roni": roni,
        "availability": interim / "availability.csv",
        "provinces": raw_root / "ref" / "provinces.csv",
        "mask": interim / "bps_mask.npy",
        "coverage": coverage or Path("reports/qa/coverage_pihps.csv"),
    }


def read_inputs(paths: dict[str, Path], *, allow_missing_climate: bool = False) -> Inputs:
    need = ["prices", "calendar", "provinces", "mask", "coverage", "roni"]
    if not allow_missing_climate:
        need.append("climate")
    missing = [f"{k}: {paths[k]}" for k in need if not Path(paths[k]).exists()]
    if missing:
        raise FileNotFoundError("Input hilang:\n  " + "\n  ".join(missing))
    prices = pd.read_parquet(paths["prices"])
    prices["prov_code"] = prices["prov_code"].astype(str)
    cal = pd.read_csv(paths["calendar"], parse_dates=["date"])
    for c in ("is_workday_pihps", "is_holiday", "is_cuti_bersama", "is_ramadan",
              "is_natal_tahunbaru", "is_post_lebaran"):
        if c in cal and cal[c].dtype != bool:
            cal[c] = cal[c].astype(str).str.lower().map({"true": True, "false": False})
    prov = pd.read_csv(paths["provinces"], dtype={"prov_code": str})
    cov = pd.read_csv(paths["coverage"], dtype={"prov_code": str})
    mask = np.load(paths["mask"], allow_pickle=False)
    roni = pd.read_parquet(paths["roni"]) if Path(paths["roni"]).exists() else None
    clim = None
    if Path(paths["climate"]).exists():
        clim = pd.read_parquet(paths["climate"])
        clim["prov_code"] = clim["prov_code"].astype(str)
    return Inputs(prices, cal, prov, cov, mask, roni, clim, dict(paths))


def truncate_inputs(inp: Inputs, cutoff: pd.Timestamp) -> Inputs:
    """Hapus semua observasi input dengan tanggal > cutoff (uji truncation)."""
    cut = pd.Timestamp(cutoff)
    roni = None
    if inp.roni is not None:
        r = inp.roni
        center = pd.to_datetime(dict(year=r["year"], month=r["center_month"], day=1))
        roni = r[center <= cut].copy()
    clim = None if inp.climate is None else inp.climate[pd.to_datetime(inp.climate["date"]) <= cut].copy()
    return Inputs(inp.prices[inp.prices["date"] <= cut].copy(), inp.calendar, inp.provinces,
                  inp.coverage, inp.mask, roni, clim, inp.paths)


# -------------------------------------------------------------------- langkah
def build_skeleton(calendar: pd.DataFrame, start, end) -> pd.DataFrame:
    """Semua hari kerja PIHPS (Senin–Jumat) dalam [start, end] x 34 prov_code (urutan kontrak)."""
    c = calendar
    sel = c["is_workday_pihps"].astype(bool) & (c["date"] >= pd.Timestamp(start)) & (c["date"] <= pd.Timestamp(end))
    days = pd.DatetimeIndex(sorted(c.loc[sel, "date"].unique()))
    days = days[days.day_of_week < 5]
    idx = pd.MultiIndex.from_product([days, list(PROV_CODES)], names=["date", "prov_code"])
    return idx.to_frame(index=False)


def join_target(panel: pd.DataFrame, prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """price & is_observed hari itu (price_type 1). Grid penuh; NaN tidak diimputasi."""
    p = prices.loc[prices["price_type"] == PRICE_TYPE_TARGET, ["date", "prov_code", "price"]]
    out = panel.merge(p, on=["date", "prov_code"], how="left", validate="one_to_one")
    out["price"] = out["price"].astype("float64")
    out["is_observed"] = (out["price"].notna() & (out["price"] > 0)).astype(bool)
    out.loc[~out["is_observed"], "price"] = np.nan
    target = out[["date", "prov_code", "price", "is_observed"]].copy()
    return out, target


def asof_join(panel: pd.DataFrame, features: pd.DataFrame, name: str,
              cols: list[str] | tuple[str, ...], *, by: str | None = "prov_code") -> pd.DataFrame:
    """merge_asof(date <- available_at, backward). Tambah kolom `<name>__avail`."""
    need = {"available_at", *cols} | ({by} if by else set())
    missing = need - set(features.columns)
    if missing:
        raise ValueError(f"{name}: kolom hilang {sorted(missing)}")
    right = features[[*([by] if by else []), "available_at", *cols]].copy()
    right["available_at"] = pd.to_datetime(right["available_at"]).astype("datetime64[ns]")
    if right["available_at"].isna().any():
        raise ValueError(f"{name}: available_at NaT")
    keys = [by, "available_at"] if by else ["available_at"]
    if right.duplicated(keys).any():
        raise ValueError(f"{name}: duplikat pada {keys}")
    right = right.rename(columns={"available_at": f"{name}__avail"}).sort_values(f"{name}__avail")
    left = panel.copy()
    left["date"] = left["date"].astype("datetime64[ns]")
    order = left.index
    left = left.sort_values("date")
    merged = pd.merge_asof(left, right, left_on="date", right_on=f"{name}__avail",
                           by=by, direction="backward", allow_exact_matches=True)
    merged.index = left.index
    return merged.loc[order].reset_index(drop=True)


def _rolling_mean_std(x: np.ndarray, groups: np.ndarray, window: int, min_periods: int):
    """Rolling mean & std (ddof=1) per grup memakai numpy jendela penuh.
    Bukan pandas .rolling(): algoritma online pandas 2 vs 3 berbeda sampai ~1e-7,
    sehingga content_hash tidak reproducible lintas versi."""
    from numpy.lib.stride_tricks import sliding_window_view
    mean = np.full(len(x), np.nan)
    std = np.full(len(x), np.nan)
    # groups sudah terurut (sort prov_code, date)
    bounds = np.flatnonzero(np.r_[True, groups[1:] != groups[:-1], True])
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = np.r_[np.full(window - 1, np.nan), x[a:b]]
        win = sliding_window_view(seg, window)
        n = np.sum(~np.isnan(win), axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            m = np.nansum(win, axis=1) / n
            v = np.nansum((win - m[:, None]) ** 2, axis=1) / (n - 1)
        ok = n >= min_periods
        mean[a:b] = np.where(ok, m, np.nan)
        std[a:b] = np.where(ok, np.sqrt(v), np.nan)
    return mean, std


def price_features(prices: pd.DataFrame, price_type: int, prefix: str) -> pd.DataFrame:
    """Fitur dari deret observasi (tanpa NaN) per provinsi; tiap baris hanya memakai
    observasi <= dirinya, tersedia pada available_at baris itu."""
    p = prices.loc[(prices["price_type"] == price_type) & prices["price"].notna() & (prices["price"] > 0),
                   ["date", "prov_code", "price", "available_at"]].sort_values(["prov_code", "date"]).copy()
    lp = np.log(p["price"])
    g = lp.groupby(p["prov_code"])
    out = p[["prov_code", "available_at"]].copy()
    out[f"{prefix}_lag1"] = p["price"].values
    out[f"{prefix}_obs_date"] = p["date"].values
    if price_type == PRICE_TYPE_TARGET:
        out[f"{prefix}_logret5"] = (lp - g.shift(5)).values
        out[f"{prefix}_logret20"] = (lp - g.shift(20)).values
        mean, std = _rolling_mean_std(lp.to_numpy(), p["prov_code"].to_numpy(), 20, 10)
        out[f"{prefix}_logmean20"] = mean
        out[f"{prefix}_logstd20"] = std
        # dibulatkan agar content_hash sama lintas versi pandas (rolling std pandas 2 vs 3
        # berbeda di digit ke-15/16)
        for c in ("logret5", "logret20", "logmean20", "logstd20"):
            out[f"{prefix}_{c}"] = out[f"{prefix}_{c}"].round(FLOAT_DECIMALS)
    # available_at berbeda per tanggal observasi; jika dua observasi tersedia di hari yang
    # sama (mis. setelah libur) pakai yang terbaru.
    out = out.drop_duplicates(["prov_code", "available_at"], keep="last")
    return out


def add_market_features(panel: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    trad = price_features(prices, PRICE_TYPE_TARGET, "price")
    cols = [c for c in trad.columns if c not in ("prov_code", "available_at")]
    panel = asof_join(panel, trad, "price_lag", cols)
    prod = price_features(prices, PRICE_TYPE_PRODUCER, "prod_price")
    panel = asof_join(panel, prod, "prod_price", ["prod_price_lag1", "prod_price_obs_date"])
    return panel


def add_climate(panel: pd.DataFrame, climate: pd.DataFrame | None) -> pd.DataFrame:
    if climate is None:
        for c in CLIMATE_COLS:
            panel[c] = np.nan
        panel["climate__avail"] = pd.NaT
        return panel
    check_columns(climate, "climate_features")
    c = climate.loc[climate["variant"] == CLIMATE_VARIANT].copy()
    if c.empty:
        raise ValueError(f"climate_features tanpa variant {CLIMATE_VARIANT!r}")
    c["climate_pentad_date"] = pd.to_datetime(c["date"])
    for col in CLIMATE_COLS:
        if c[col].dtype == bool:
            c[col] = c[col].astype("float64")
    return asof_join(panel, c, "climate", [*CLIMATE_COLS, "climate_pentad_date"])


def roni_table(roni: pd.DataFrame) -> pd.DataFrame:
    """RONI nasional; hanya nilai + delta musim sebelumnya. Kolom fase/episode dibuang."""
    r = roni[["year", "center_month", "roni", "available_at"]].copy()
    r["available_at"] = pd.to_datetime(r["available_at"])
    r = r.sort_values(["year", "center_month"])
    r["roni_delta"] = r["roni"].diff()
    r["roni_season_month"] = pd.to_datetime(dict(year=r["year"], month=r["center_month"], day=1))
    # beberapa musim bisa tersedia di hari yang sama -> pakai musim terbaru
    return r.drop_duplicates("available_at", keep="last")


def add_roni(panel: pd.DataFrame, roni: pd.DataFrame | None) -> pd.DataFrame:
    if roni is None:
        raise FileNotFoundError("roni.parquet tidak ada")
    r = roni_table(roni)
    return asof_join(panel, r, "roni", ["roni", "roni_delta", "roni_season_month"], by=None)


def join_calendar(panel: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in CALENDAR_COLS if c in calendar.columns]
    out = panel.merge(calendar[["date", *cols]], on="date", how="left", validate="many_to_one")
    if out[cols].isna().any().any():
        raise ValueError("kalender tidak lengkap untuk tanggal panel")
    return out


def node_flags(provinces: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    """nodes.csv = provinces.csv + years_ok + include (cakupan >=90% pada >=5 tahun 2018–2025)."""
    y0, y1 = COVERAGE_YEARS
    w = coverage[(coverage["year"] >= y0) & (coverage["year"] <= y1)]
    ok = (w.assign(ok=w["coverage"] >= COVERAGE_MIN).groupby("prov_code")["ok"].sum()
          .reindex(list(PROV_CODES)).fillna(0).astype(int))
    nodes = provinces.set_index("prov_code").reindex(list(PROV_CODES)).reset_index()
    nodes["years_ok"] = ok.values
    nodes["include"] = (nodes["years_ok"] >= COVERAGE_MIN_YEARS).astype(bool)
    first = ["prov_code", "prov_name", "include", "years_ok"]
    return nodes[first + [c for c in nodes.columns if c not in first]]


# ----------------------------------------------------------------------- build
def build(inp: Inputs, start, end, *, allow_holdout: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    end = pd.Timestamp(end)
    if not allow_holdout and end >= pd.Timestamp(HOLDOUT_START):
        raise ValueError(f"end {end.date()} >= holdout {HOLDOUT_START}")
    panel = build_skeleton(inp.calendar, start, end)
    if panel.empty:
        raise ValueError("skeleton kosong")
    panel, target = join_target(panel, inp.prices)
    panel = add_market_features(panel, inp.prices)
    panel = add_climate(panel, inp.climate)
    panel = add_roni(panel, inp.roni)
    panel = join_calendar(panel, inp.calendar)
    # konvensi tim: datetime64[ns] + prov_code str -> content_hash sama di semua versi pandas
    for frame in (panel, target):
        for c in frame.columns:
            if pd.api.types.is_datetime64_any_dtype(frame[c]):
                frame[c] = frame[c].astype("datetime64[ns]")
        frame["prov_code"] = frame["prov_code"].astype(str)
    panel = panel.sort_values(["date", "prov_code"], key=_prov_order).reset_index(drop=True)
    target = target.sort_values(["date", "prov_code"], key=_prov_order).reset_index(drop=True)
    for name, frame in (("panel", panel), ("target", target)):
        check_columns(frame, name)
        check_unique(frame, name)
    nodes = node_flags(inp.provinces, inp.coverage)
    return panel, target, nodes


def _prov_order(s: pd.Series) -> pd.Series:
    if s.name == "prov_code":
        return s.map({c: i for i, c in enumerate(PROV_CODES)})
    return s


def avail_columns(panel: pd.DataFrame) -> list[str]:
    return [c for c in panel.columns if c.endswith("__avail")]


def feature_columns(panel: pd.DataFrame) -> list[str]:
    skip = {"date", "prov_code", "price", "is_observed"}
    return [c for c in panel.columns if c not in skip and not c.endswith("__avail")]


def quick_checks(panel: pd.DataFrame) -> dict[str, bool]:
    """Uji 1–3 (uji 4 truncation ada di tests/test_no_leakage.py, MDE-H3-01 2/2)."""
    d = panel["date"]
    av = {c: bool((panel[c].isna() | (panel[c] <= d)).all()) for c in avail_columns(panel)}
    bad_names = [c for c in panel.columns if any(t in c.lower() for t in FORBIDDEN_TOKENS)]
    return {
        **{f"avail<=date:{c}": v for c, v in av.items()},
        "max_date<holdout": bool(d.max() < pd.Timestamp(HOLDOUT_START)),
        "no_regime_label_cols": not bad_names,
    }


# --------------------------------------------------------------------- outputs
FEATURE_META = {
    "price": ("target_same_day", "Rp/kg", "PIHPS t1", "observasi hari itu; loader MLE menggeser H+1", "harga hari date (BUKAN fitur as-of)"),
    "is_observed": ("target_mask", "bool", "PIHPS t1", "observasi hari itu", "harga asli ada pada date"),
    "price_lag1": ("feature", "Rp/kg", "PIHPS t1", "as-of next_workday", "harga observasi terakhir yang sudah tersedia"),
    "price_obs_date": ("meta", "date", "PIHPS t1", "as-of next_workday", "tanggal observasi price_lag1"),
    "price_logret5": ("feature", "log", "PIHPS t1", "as-of next_workday", "log return 5 observasi"),
    "price_logret20": ("feature", "log", "PIHPS t1", "as-of next_workday", "log return 20 observasi"),
    "price_logmean20": ("feature", "log Rp/kg", "PIHPS t1", "as-of next_workday", "rata-rata log harga 20 observasi"),
    "price_logstd20": ("feature", "log", "PIHPS t1", "as-of next_workday", "std log harga 20 observasi"),
    "prod_price_lag1": ("feature", "Rp/kg", "PIHPS t4 produsen", "as-of next_workday", "harga produsen terakhir tersedia"),
    "prod_price_obs_date": ("meta", "date", "PIHPS t4 produsen", "as-of next_workday", "tanggal observasi prod_price_lag1"),
    "rain_mm": ("feature", "mm/hari", "CHIRPS v3 final_sat (CGS)", "pentad_end_plus_lag 2", "rata-rata harian pentad terakhir tersedia"),
    "rain_pentad_mm": ("feature", "mm", "CHIRPS v3 final_sat (CGS)", "pentad_end_plus_lag 2", "total pentad"),
    "rain_pentad_anom": ("feature", "z", "CHIRPS v3 final_sat (CGS)", "pentad_end_plus_lag 2", "anomali pentad"),
    "rain_30d_anom": ("feature", "z", "CHIRPS v3 final_sat (CGS)", "pentad_end_plus_lag 2", "anomali 30 hari"),
    "dry_spell_days": ("feature", "hari", "CHIRPS v3 final_sat (CGS)", "pentad_end_plus_lag 2", "hari kering beruntun"),
    "extreme_5d": ("feature", "0/1", "CHIRPS v3 final_sat (CGS)", "pentad_end_plus_lag 2", "pentad > p95"),
    "climate_pentad_date": ("meta", "date", "CHIRPS v3 final_sat (CGS)", "pentad_end_plus_lag 2", "akhir pentad yang terpakai"),
    "roni": ("feature", "°C", "CPC NOAA RONI (CGS)", "vintage_or_conservative_3m", "RONI musim terakhir tersedia (nasional)"),
    "roni_delta": ("feature", "°C", "CPC NOAA RONI (CGS)", "vintage_or_conservative_3m", "selisih RONI vs musim sebelumnya"),
    "roni_season_month": ("meta", "date", "CPC NOAA RONI (CGS)", "vintage_or_conservative_3m", "bulan tengah musim terpakai"),
}


def feature_dictionary(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in panel.columns:
        if c in ("date", "prov_code"):
            continue
        if c.endswith("__avail"):
            rows.append((c, "avail", "date", "-", "-", "available_at baris sumber yang terpakai (uji bocor)"))
        elif c in FEATURE_META:
            rows.append((c, *FEATURE_META[c]))
        elif c in CALENDAR_COLS:
            rows.append((c, "feature", "-", "calendar.csv (MDE-H2-02)", "known_in_advance", "kalender, join langsung pada date"))
        else:
            rows.append((c, "feature", "-", "?", "?", ""))
    return pd.DataFrame(rows, columns=["name", "role", "unit", "source", "available_at_rule", "description"])


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def write_outputs(out: Path, panel, target, nodes, mask, meta: dict) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(out / "panel.parquet", index=False)
    target.to_parquet(out / "target.parquet", index=False)
    nodes.to_csv(out / "nodes.csv", index=False)
    np.save(out / "bps_mask.npy", mask.astype(np.uint8))
    feature_dictionary(panel).to_csv(out / "feature_dict.csv", index=False)
    hashes = {
        "panel": content_hash(panel, ("date", "prov_code")),
        "target": content_hash(target, ("date", "prov_code")),
        "nodes": content_hash(nodes, ("prov_code",)),
    }
    version = {
        "version": meta.get("version", VERSION),
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "start": str(meta["start"]), "end": str(meta["end"]),
        "rows_panel": len(panel), "n_dates": int(panel["date"].nunique()),
        "date_min": str(panel["date"].min().date()), "date_max": str(panel["date"].max().date()),
        "climate": meta.get("climate", "climate_features.parquet"),
        "content_hash": hashes,
    }
    (out / "VERSION").write_text(json.dumps(version, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_sha256sums(out)
    return version
