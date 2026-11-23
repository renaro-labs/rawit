# =============================================================================
#  MDE-H1-01 (2/2) · Parser PIHPS: JSON mentah -> long table
# -----------------------------------------------------------------------------
#  Input   : data/raw/pihps/pt{1|4}_{YYYYMMDD}_{YYYYMMDD}.json   (format playbook)
#            data/raw/pihps/json/pihps_pt{1|4}_{YYYY-MM-DD}_{YYYY-MM-DD}.json[.gz]
#            (format unduhan tim 2026-11-22; dibaca bila diminta lewat --parse-dir)
#  Output  : data/interim/pihps_long.parquet  [date, prov_name_raw, price_type, price_raw]
#            + kolom bantu: price_str (teks asli), source_file
#  Aturan  : tidak pernah membaca file yang menyentuh >= 2026-06-01 (_sealed).
# =============================================================================
"""JSON PIHPS GetGridDataKomoditas -> long table.

`price_raw` = harga mentah sebagai float (Rp/kg, sesuai kontrak `prices_clean`);
teks aslinya disimpan di `price_str` untuk audit. "-"/kosong/"0" -> NaN, bukan 0.
Nama provinsi disimpan mentah; pemetaan ke `prov_code` dilakukan di MDE-H2-01.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

from renaro.contract import HOLDOUT_START, assert_before_holdout, prov_code_of

PRICE_TYPE_TRADITIONAL = 1
PRICE_TYPE_PRODUCER = 4

LONG_COLUMNS = ["date", "prov_name_raw", "price_type", "price_raw", "price_str", "source_file"]
DATE_KEY_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_THOUSANDS_RE = re.compile(r"^\d{1,3}([.,]\d{3})+$")

#: Format playbook: pt1_20180101_20181231.json
FILE_RE = re.compile(r"^pt(\d)_(\d{8})_(\d{8})\.json$")
#: Format unduhan tim: pihps_pt1_2018-07-01_2019-06-30.json(.gz)
LEGACY_FILE_RE = re.compile(r"^pihps_pt(\d)_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json(\.gz)?$")


def parse_file_name(name: str) -> tuple[int, dt.date, dt.date] | None:
    """Nama file -> (price_type, start, end); None bila bukan file PIHPS."""
    m = FILE_RE.match(name)
    if m:
        to_date = lambda s: dt.datetime.strptime(s, "%Y%m%d").date()  # noqa: E731
        return int(m.group(1)), to_date(m.group(2)), to_date(m.group(3))
    m = LEGACY_FILE_RE.match(name)
    if m:
        return int(m.group(1)), dt.date.fromisoformat(m.group(2)), dt.date.fromisoformat(m.group(3))
    return None


def numeric_id(price_raw: object) -> float:
    """'45.250'/'45,250'/'45250'/45250 -> 45250.0; '-', '', None, '0' -> NaN.

    PIHPS melaporkan rupiah bulat, jadi '.' dan ',' hanya pemisah ribuan.
    Pola lain (mis. '45,25') sengaja menjadi NaN agar terlihat di QA, bukan ditebak.
    """
    if price_raw is None:
        return math.nan
    if isinstance(price_raw, (int, float)) and not isinstance(price_raw, bool):
        value = float(price_raw)
        return value if value > 0 else math.nan
    text = str(price_raw).strip()
    if text in {"", "-", "0"}:
        return math.nan
    if text.isdigit():
        return float(text)
    if _THOUSANDS_RE.match(text):
        return float(re.sub(r"[.,]", "", text))
    return math.nan


def parse_payload(payload: dict, price_type: int, source_file: str = "") -> pd.DataFrame:
    """Satu respons -> long table. Hanya baris level 1 (provinsi).

    Level 0 = agregat nasional ("Semua Provinsi"), level >= 2 = kota/pasar.
    """
    records = []
    for row in payload.get("data") or []:
        if int(row.get("level", -1) or 0) != 1:
            continue
        name = str(row.get("name", "")).strip()
        for key, value in row.items():
            m = DATE_KEY_RE.match(str(key))
            if not m:
                continue
            dd, mm, yyyy = m.groups()
            records.append((
                dt.date(int(yyyy), int(mm), int(dd)), name, price_type,
                numeric_id(value), None if value is None else str(value), source_file,
            ))
    frame = pd.DataFrame.from_records(records, columns=LONG_COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["price_type"] = frame["price_type"].astype("int8")
    frame["price_raw"] = frame["price_raw"].astype("float64")
    return frame


def load_file(path: Path) -> dict:
    """Baca .json atau .json.gz."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def list_files(raw_dir: Path) -> list[tuple[Path, int, dt.date, dt.date]]:
    """File PIHPS langsung di bawah raw_dir (tidak rekursif; _sealed/ tidak tersentuh)."""
    out = []
    for path in sorted(p for p in raw_dir.iterdir() if p.is_file()):
        meta = parse_file_name(path.name)
        if meta:
            out.append((path, *meta))
    return out


def parse_dir(raw_dir: Path) -> pd.DataFrame:
    """Parse semua JSON non-sealed di raw_dir. File yang menyentuh holdout ditolak keras."""
    files = list_files(raw_dir)
    if not files:
        raise SystemExit(f"Tidak ada JSON PIHPS di {raw_dir}")
    frames = []
    for path, price_type, _start, end in files:
        if end >= HOLDOUT_START:
            raise SystemExit(f"{path.name} menyentuh holdout; pindahkan ke _sealed, jangan di-parse.")
        frames.append(parse_payload(load_file(path), price_type, path.name))
    long = pd.concat(frames, ignore_index=True)
    dup = long.duplicated(["date", "prov_name_raw", "price_type"], keep=False)
    if dup.any():
        clash = long[dup].groupby(["date", "prov_name_raw", "price_type"])["price_raw"].nunique(dropna=False)
        if (clash > 1).any():
            raise SystemExit(f"{int((clash > 1).sum())} kunci punya nilai berbeda antar-file; cek jendela tumpang tindih.")
        long = long.drop_duplicates(["date", "prov_name_raw", "price_type"], keep="first")
    return long.sort_values(["price_type", "date", "prov_name_raw"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Validasi & ringkasan
# ---------------------------------------------------------------------------
def _is_contract_province(name: str) -> bool:
    try:
        prov_code_of(name)
        return True
    except KeyError:
        return False


def unknown_names(long: pd.DataFrame) -> list[str]:
    return sorted(n for n in long["prov_name_raw"].unique() if not _is_contract_province(n))


def validate_long(long: pd.DataFrame) -> list[str]:
    """Cek DoD; kembalikan daftar masalah (kosong = lulus)."""
    problems = []
    assert_before_holdout(long, "date")
    unknown = unknown_names(long)
    if unknown:
        n_bad = int(long["prov_name_raw"].isin(unknown).sum())
        problems.append(f"nama di luar 34 provinsi kontrak (dibuang di MDE-H2-01): {unknown} ({n_bad} baris)")
    t1 = long[(long["price_type"] == PRICE_TYPE_TRADITIONAL) & ~long["prov_name_raw"].isin(unknown)]
    valid = t1[t1["price_raw"].notna()]
    if valid.empty:
        return problems + ["tipe 1 kosong"]
    if valid["date"].min() > pd.Timestamp("2017-07-31"):
        problems.append(f"tipe 1 mulai {valid['date'].min().date()}, harusnya Jul 2017")
    if valid["date"].max() < pd.Timestamp("2026-05-25"):
        problems.append(f"tipe 1 berakhir {valid['date'].max().date()}, harusnya akhir Mei 2026")
    jul17 = valid[valid["date"].dt.to_period("M") == pd.Period("2017-07")]["prov_name_raw"].nunique()
    if jul17 < 27:
        problems.append(f"Jul 2017 hanya {jul17} provinsi berharga (brief: >= 27)")
    since_2018 = t1[t1["date"] >= pd.Timestamp("2018-01-02")]
    per_day = since_2018.groupby("date")["prov_name_raw"].nunique()
    if (per_day < 34).any():
        problems.append(f"{int((per_day < 34).sum())} hari kerja sejak 2018 punya < 34 baris provinsi")
    unparsed = long["price_raw"].isna() & ~long["price_str"].fillna("").str.strip().isin(["", "-", "0"])
    if unparsed.any():
        sample = long.loc[unparsed, "price_str"].unique()[:10].tolist()
        problems.append(f"{int(unparsed.sum())} nilai tak terbaca sebagai angka, contoh: {sample}")
    return problems


def summary_by_file(long: pd.DataFrame) -> pd.DataFrame:
    """Per file: rentang tanggal, provinsi berharga, hari, observasi valid."""
    obs = long[long["price_raw"].notna()]
    return (obs.groupby("source_file")
               .agg(price_type=("price_type", "first"), first=("date", "min"), last=("date", "max"),
                    n_prov=("prov_name_raw", "nunique"), n_days=("date", "nunique"), n_obs=("price_raw", "size"))
               .reset_index()
               .assign(first=lambda d: d["first"].dt.date, last=lambda d: d["last"].dt.date))


def spot_check_sample(long: pd.DataFrame, n_dates: int = 3, n_prov: int = 3, seed: int = 0) -> pd.DataFrame:
    """n_dates tanggal acak x n_prov provinsi (tipe 1), semuanya berharga, untuk dicek manual di situs."""
    t1 = long[(long["price_type"] == PRICE_TYPE_TRADITIONAL) & long["price_raw"].notna()
              & ~long["prov_name_raw"].isin(unknown_names(long))]
    provs = pd.Series(sorted(t1["prov_name_raw"].unique())).sample(n_prov, random_state=seed)
    sub = t1[t1["prov_name_raw"].isin(provs)]
    full = sub.groupby("date")["prov_name_raw"].nunique()
    dates = pd.Series(full[full == n_prov].index).sample(n_dates, random_state=seed)
    pick = sub[sub["date"].isin(dates)]
    return pick[["date", "prov_name_raw", "price_str", "price_raw"]].sort_values(["date", "prov_name_raw"])


def crosscheck_csv(long: pd.DataFrame, csv_path: Path) -> dict:
    """Bandingkan dengan CSV tim (pihps_cabai_merah_keriting_province.csv)."""
    ref = pd.read_csv(csv_path, parse_dates=["date"])
    ref = ref[ref["province_name"] != "Semua Provinsi"].copy()
    ref["pt"] = ref["price_type"].map({"tradisional": 1, "produsen": 4})
    merged = long.merge(ref, left_on=["date", "prov_name_raw", "price_type"],
                        right_on=["date", "province_name", "pt"], how="outer",
                        indicator=True, suffixes=("", "_ref"))
    both = merged[merged["_merge"] == "both"]
    same = (both["price_raw"] == both["price_idr"]) | (both["price_raw"].isna() & both["price_idr"].isna())
    lo = merged[merged["_merge"] == "left_only"]
    ro = merged[merged["_merge"] == "right_only"]
    return {
        "matched": int(len(both)), "value_mismatch": int((~same).sum()),
        "only_scraped": int(len(lo)), "only_scraped_names": sorted(lo["prov_name_raw"].dropna().unique())[:10],
        "only_csv": int(len(ro)),
        "only_csv_range": (str(ro["date"].min().date()), str(ro["date"].max().date())) if len(ro) else None,
    }


def write_parquet(long: pd.DataFrame, out: Path) -> None:
    assert_before_holdout(long, "date")
    out.parent.mkdir(parents=True, exist_ok=True)
    long.to_parquet(out, index=False)


if __name__ == "__main__":  # pragma: no cover
    print("Pakai: python -m renaro.data.pihps --parse-only", file=sys.stderr)
