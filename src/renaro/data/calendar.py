# =============================================================================
#  MDE-H2-02 · Kalender Lebaran/Ramadan/libur
# -----------------------------------------------------------------------------
#  Role    : MDE — Market Data Engineer (@dio)
#  Input   : library `holidays` (ID), data/ref/religious_dates.csv, data/ref/cuti_bersama.csv,
#            data/interim/pihps_long.parquet (untuk is_workday_pihps)
#  Output  : data/interim/calendar.csv (skema kontrak `calendar`) + reports/qa/calendar.md
#  Handoff : MDE-H2-01 (flag pasca-Lebaran), MDE-H3-01
# =============================================================================
"""Kalender deterministik. Tidak ada isu `available_at`: semua diketahui di muka (SKB, isbat).

Aturan:
- Prioritas sumber: religious_dates.csv / cuti_bersama.csv (resmi, ada source_url) >
  holidays.ID(). Perbedaan dicatat di reports/qa/calendar.md, dan yang dipakai sumber resmi.
- is_holiday      = libur nasional (holidays.ID) dengan Idulfitri (hari 1–2) dan Iduladha
                    diganti tanggal resmi.
- is_cuti_bersama = cuti_bersama.csv (SKB final setelah semua revisi).
- is_ramadan      = ramadan_start <= date < idulfitri.
- days_to_lebaran / days_to_iduladha = hari kalender ke Idulfitri/Iduladha berikutnya (0 pada harinya).
- is_natal_tahunbaru = 20 Des .. 5 Jan.
- is_workday_pihps = tanggal dengan harga valid dari >= 50% provinsi (tipe 1) di rentang data PIHPS
                    (< holdout). Di luar rentang itu (holdout & masa depan) dipakai aturan
                    Senin–Jumat dan bukan libur nasional; ditandai di kolom `workday_source`.
- Jendela pasca-Lebaran (dipakai MDE-H2-01): Idulfitri s/d +10 hari kalender (`post_lebaran_days`).

Pemakaian: ``python -m renaro.data.calendar``
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import HOLDOUT_START, PROV_CODES, TABLE_COLUMNS, check_columns

START = "2017-01-01"          # mencakup panel_start 2017-07-01 (DoD minimal 2017-09-01)
END = "2026-12-31"
OUT = Path("data/interim/calendar.csv")
RELIGIOUS = Path("data/ref/religious_dates.csv")
CUTI = Path("data/ref/cuti_bersama.csv")
PIHPS_LONG = Path("data/interim/pihps_long.parquet")
REPORT = Path("reports/qa/calendar.md")
POST_LEBARAN_DAYS = 10
WORKDAY_SHARE = 0.5
BOOL_COLS = ["is_workday_pihps", "is_holiday", "is_cuti_bersama", "is_ramadan", "is_natal_tahunbaru",
             "is_post_lebaran"]


def load_refs(religious: Path = RELIGIOUS, cuti: Path = CUTI) -> tuple[pd.DataFrame, pd.DataFrame]:
    rel = pd.read_csv(religious, dtype=str)
    for c in ["ramadan_start", "idulfitri", "iduladha"]:
        rel[c] = pd.to_datetime(rel[c])
    missing_url = rel.loc[rel["idulfitri"].notna() & rel["source_url"].fillna("").eq(""), "year"]
    if len(missing_url):
        raise ValueError(f"Idulfitri tanpa source_url: tahun {missing_url.tolist()}")
    cb = pd.read_csv(cuti, dtype=str)
    cb["date"] = pd.to_datetime(cb["date"])
    if cb["date"].duplicated().any():
        raise ValueError("cuti_bersama.csv berisi tanggal ganda")
    return rel, cb


def library_holidays(years: range) -> dict[pd.Timestamp, str]:
    try:
        import holidays
    except ImportError as err:  # pragma: no cover
        raise SystemExit("Library `holidays` belum terpasang: pip install holidays") from err
    return {pd.Timestamp(d): name for d, name in holidays.ID(years=years).items()}


def official_holidays(lib: dict[pd.Timestamp, str], rel: pd.DataFrame) -> tuple[set[pd.Timestamp], list[dict]]:
    """Libur nasional library, dengan Idulfitri (2 hari) & Iduladha diganti tanggal resmi."""
    diffs = []
    out = set(lib)
    for _, r in rel.iterrows():
        y = int(r["year"])
        checks = []
        if pd.notna(r["idulfitri"]):
            checks.append(("Idulfitri", "Idul Fitri", [r["idulfitri"], r["idulfitri"] + pd.Timedelta(days=1)]))
        if pd.notna(r["iduladha"]):
            checks.append(("Iduladha", "Idul Adha", [r["iduladha"]]))
        for label, key, official in checks:
            lib_dates = sorted(d for d, n in lib.items() if d.year == y and key in n)
            if lib_dates and lib_dates != sorted(official):
                diffs.append({"year": y, "item": label, "holidays_lib": [d.date().isoformat() for d in lib_dates],
                              "resmi": [d.date().isoformat() for d in official], "dipakai": "resmi"})
            out -= set(lib_dates)
            out |= set(official)
    return out, diffs


def days_to_next(dates: pd.DatetimeIndex, events: list[pd.Timestamp]) -> np.ndarray:
    ev = np.array(sorted(events), dtype="datetime64[ns]")
    pos = np.searchsorted(ev, dates.to_numpy(), side="left")
    if (pos >= len(ev)).any():
        raise ValueError("Tidak ada tanggal acuan berikutnya untuk sebagian tanggal; tambah tahun di religious_dates.csv")
    return ((ev[pos] - dates.to_numpy()) / np.timedelta64(1, "D")).astype(int)


def pihps_workdays(path: Path, share: float = WORKDAY_SHARE) -> tuple[pd.DatetimeIndex, pd.Timestamp, pd.Timestamp]:
    long = pd.read_parquet(path)
    long["date"] = pd.to_datetime(long["date"])
    if long["date"].max() >= pd.Timestamp(HOLDOUT_START):
        raise SystemExit("pihps_long memuat tanggal holdout")
    t1 = long[(long["price_type"] == 1) & long["price_raw"].notna()]
    per_day = t1.groupby("date")["prov_name_raw"].nunique()
    wd = pd.DatetimeIndex(per_day[per_day >= share * len(PROV_CODES)].index)
    return wd, long["date"].min(), long["date"].max()


def build_calendar(start: str, end: str, rel: pd.DataFrame, cb: pd.DataFrame, lib: dict,
                   workdays: pd.DatetimeIndex | None, pihps_range: tuple | None) -> tuple[pd.DataFrame, list[dict]]:
    dates = pd.date_range(start, end, freq="D")
    hol, diffs = official_holidays(lib, rel)
    cal = pd.DataFrame({"date": dates})
    cal["is_holiday"] = cal["date"].isin(hol)
    cal["is_cuti_bersama"] = cal["date"].isin(set(cb["date"]))
    ram = np.zeros(len(cal), dtype=bool)
    for _, r in rel.dropna(subset=["ramadan_start", "idulfitri"]).iterrows():
        ram |= ((cal["date"] >= r["ramadan_start"]) & (cal["date"] < r["idulfitri"])).to_numpy()
    cal["is_ramadan"] = ram
    lebaran = rel["idulfitri"].dropna().tolist()
    cal["days_to_lebaran"] = days_to_next(dates, lebaran)
    cal["days_to_iduladha"] = days_to_next(dates, rel["iduladha"].dropna().tolist())
    md = cal["date"].dt.month * 100 + cal["date"].dt.day
    cal["is_natal_tahunbaru"] = (md >= 1220) | (md <= 105)
    cal["dow"] = cal["date"].dt.day_of_week
    cal["month"] = cal["date"].dt.month
    cal["doy"] = cal["date"].dt.day_of_year
    post = np.zeros(len(cal), dtype=bool)
    for d in lebaran:
        post |= cal["date"].between(d, d + pd.Timedelta(days=POST_LEBARAN_DAYS)).to_numpy()
    cal["is_post_lebaran"] = post
    rule = (cal["dow"] < 5) & ~cal["is_holiday"]
    if workdays is not None and pihps_range is not None:
        lo, hi = pihps_range
        inside = cal["date"].between(lo, hi)
        cal["is_workday_pihps"] = np.where(inside, cal["date"].isin(set(workdays)), rule)
        cal["workday_source"] = np.where(inside, "pihps", "rule")
    else:
        cal["is_workday_pihps"] = rule
        cal["workday_source"] = "rule"
    for c in BOOL_COLS:
        cal[c] = cal[c].astype(bool)
    for c in ["days_to_lebaran", "days_to_iduladha", "dow", "month", "doy"]:
        cal[c] = cal[c].astype("int64")
    cols = list(TABLE_COLUMNS["calendar"]) + ["is_post_lebaran", "workday_source"]
    return cal[cols], diffs


def validate(cal: pd.DataFrame, rel: pd.DataFrame, start: str, end: str) -> None:
    check_columns(cal, "calendar")
    if cal["date"].duplicated().any():
        raise ValueError("tanggal ganda")
    expected = pd.date_range(start, end, freq="D")
    if len(cal) != len(expected) or not (cal["date"].to_numpy() == expected.to_numpy()).all():
        raise ValueError("kalender bercelah atau tidak urut")
    lebaran_days = set(cal.loc[cal["days_to_lebaran"] == 0, "date"])
    official = {d for d in rel["idulfitri"].dropna() if pd.Timestamp(start) <= d <= pd.Timestamp(end)}
    if lebaran_days != official:
        raise ValueError(f"days_to_lebaran == 0 tidak cocok dengan Idulfitri resmi: {lebaran_days ^ official}")


def write_report(cal: pd.DataFrame, rel: pd.DataFrame, cb: pd.DataFrame, diffs: list[dict],
                 lib: dict, path: Path) -> None:
    lib_on_cuti = sorted(d.date().isoformat() for d in cb["date"] if d in lib)
    inside = cal[cal["workday_source"] == "pihps"]
    rule = (inside["dow"] < 5) & ~inside["is_holiday"]
    agree = (rule == inside["is_workday_pihps"]).mean() if len(inside) else float("nan")
    cuti_wd = inside[inside["is_cuti_bersama"] & (inside["dow"] < 5)]
    hol_wd = inside[inside["is_holiday"] & (inside["dow"] < 5)]
    rows = "\n".join(f"| {int(r.year)} | {r.ramadan_start.date() if pd.notna(r.ramadan_start) else '-'} | "
                     f"{r.idulfitri.date()} | {r.iduladha.date()} | {r.note} |" for r in rel.itertuples())
    diff_rows = "\n".join(f"| {d['year']} | {d['item']} | {', '.join(d['holidays_lib'])} | {', '.join(d['resmi'])} |"
                          for d in diffs) or "| - | tidak ada perbedaan | | |"
    md = f"""# Kalender (MDE-H2-02)

- Output: `data/interim/calendar.csv`, {len(cal):,} hari, {cal['date'].min().date()} .. {cal['date'].max().date()}, tanpa celah (DoD 2017-09-01 .. 2026-12-31 tercakup).
- Kode: `src/renaro/data/calendar.py` (`python -m renaro.data.calendar`). Sumber manual: `data/ref/religious_dates.csv` (setiap Idulfitri punya `source_url`), `data/ref/cuti_bersama.csv` ({len(cb)} hari cuti bersama 2017–2026, versi final setelah revisi SKB).
- Kolom kontrak `calendar` + 2 kolom bantu: `is_post_lebaran` (Idulfitri s/d +{POST_LEBARAN_DAYS} hari kalender, jendela flag MDE-H2-01) dan `workday_source`.
- `available_at` tidak diperlukan: semua tanggal diketahui di muka (SKB terbit ±1 tahun sebelumnya; tanggal hari raya via sidang isbat).

## Tanggal hari raya resmi

| Tahun | 1 Ramadan | Idulfitri | Iduladha | Catatan |
|---|---|---|---|---|
{rows}

## Perbandingan dengan library `holidays`

| Tahun | Item | holidays.ID() | Resmi (dipakai) |
|---|---|---|---|
{diff_rows}

Tanggal cuti bersama yang juga tercantum sebagai libur di `holidays`: {', '.join(lib_on_cuti) or 'tidak ada'}. Library `holidays` tidak memuat cuti bersama, sehingga kolom `is_cuti_bersama` sepenuhnya dari SKB.

## Hari kerja PIHPS

- {cal['workday_source'].eq('pihps').sum():,} tanggal diisi dari data PIHPS (≥ 50% provinsi melapor), {cal['workday_source'].eq('rule').sum():,} tanggal dari aturan Senin–Jumat bukan libur nasional (sebelum data PIHPS, periode holdout, dan masa depan; data holdout tidak dibuka).
- Kecocokan aturan dengan data PIHPS pada rentang yang ada datanya: {agree:.1%}.
- PIHPS tetap melapor pada {int(cuti_wd['is_workday_pihps'].sum())} dari {len(cuti_wd)} hari cuti bersama (Senin–Jumat) dan {int(hol_wd['is_workday_pihps'].sum())} dari {len(hol_wd)} libur nasional (Senin–Jumat). Karena itu cuti bersama tidak dianggap hari libur PIHPS.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Kalender (MDE-H2-02)")
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--pihps", type=Path, default=PIHPS_LONG)
    args = ap.parse_args(argv)

    rel, cb = load_refs()
    years = range(pd.Timestamp(args.start).year, pd.Timestamp(args.end).year + 2)
    lib = library_holidays(years)
    wd, rng = (None, None)
    if args.pihps.exists():
        wd, lo, hi = pihps_workdays(args.pihps)
        rng = (lo, hi)
    cal, diffs = build_calendar(args.start, args.end, rel, cb, lib, wd, rng)
    validate(cal, rel, args.start, args.end)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out = cal.assign(date=cal["date"].dt.strftime("%Y-%m-%d"))
    out.to_csv(args.out, index=False)
    write_report(cal, rel, cb, diffs, lib, REPORT)
    print(f"[ok] {args.out} {len(cal):,} hari {args.start}..{args.end}; libur={int(cal['is_holiday'].sum())} "
          f"cuti_bersama={int(cal['is_cuti_bersama'].sum())} ramadan={int(cal['is_ramadan'].sum())} "
          f"workday_pihps={int(cal['is_workday_pihps'].sum())}")
    for d in diffs:
        print(f"     beda holidays vs resmi: {d['year']} {d['item']}: {d['holidays_lib']} -> {d['resmi']}")
    print(f"[ok] {REPORT}")


if __name__ == "__main__":
    main()
