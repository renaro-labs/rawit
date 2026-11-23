# =============================================================================
#  MDE-H1-01 · Scrape PIHPS 2017–2026 (tipe 1 dan 4)
# -----------------------------------------------------------------------------
#  Role    : MDE — Market Data Engineer
#  Ticket  : RAWIT-11 (1/2), RAWIT-12 (2/2)
#  Input   : endpoint publik GetGridDataKomoditas (lihat docs/sources/pihps_endpoint.md)
#  Output  : data/raw/pihps/json/pihps_pt{1|4}_{YYYY-MM-DD}_{YYYY-MM-DD}.json
#            data/raw/pihps/manifest.csv
#            data/raw/pihps/_sealed/json/   (>= 2026-06-01, JANGAN DIBUKA; hanya --sealed)
#            data/interim/pihps_long.parquet (hanya < 2026-06-01)
#  Handoff : MDE-H1-03, MDE-H2-01, CGS-H3-02 (file _sealed)
# =============================================================================
"""Ambil panel PIHPS mentah + manifest, lalu parse ke tabel panjang.

Pemakaian (dari root repo, PowerShell):

    $env:PYTHONPATH = "src"
    python -m renaro.data.pihps --probe                       # langkah 3: 1 request kecil
    python -m renaro.data.pihps --price-type 1                # unduh semua jendela tipe 1
    python -m renaro.data.pihps --price-type 4
    python -m renaro.data.pihps --parse-only                  # JSON -> pihps_long.parquet

File JSON disimpan polos (``.json``, sama dengan rilis pihps-extracted tim).
Parser juga tetap membaca ``.json.gz`` lama. Catatan: ``scripts/cgs/seal_holdout.py``
hanya mencari ``*.json.gz``; beri tahu CGS bila penyegelan ulang diperlukan.

Catatan lisensi: PIHPS "Hak Cipta - Semua Hak Dilindungi". Data mentah tidak
diredistribusi; file ``_sealed`` diserahkan ke CGS lalu dihapus dari drive bersama.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

import pandas as pd

from renaro.contract import HOLDOUT_START, assert_before_holdout, prov_code_of

# ---------------------------------------------------------------------------
# Endpoint. Sumber awal: kode pangan.id (src/lib/pihps.ts, scripts/scraper.py).
# WAJIB dicocokkan dengan "Copy as cURL" dari DevTools (docs/sources/).
# ---------------------------------------------------------------------------
SITE_URL = "https://www.bi.go.id/hargapangan"
BASE_URL = f"{SITE_URL}/WebSite/TabelHarga/GetGridDataKomoditas"
REFERER = f"{SITE_URL}/TabelHarga/PasarTradisionalKomoditas"

PARAM_DATE_START = "start_date"      # format YYYY-MM-DD
PARAM_DATE_END = "end_date"
PARAM_PROVINCE = "province_id"       # "" = semua provinsi
PARAM_REPORT_TYPE = "tipe_laporan"   # "1" = harian
DATE_FMT = "%Y-%m-%d"

COMCAT_ID = "com_14"                 # Cabai Merah Keriting
PRICE_TYPE_TRADITIONAL = 1           # target
PRICE_TYPE_PRODUCER = 4              # fitur Sprint 2

HEADERS = {
    "User-Agent": "renaro-research-client (Mozilla/5.0 compatible)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": REFERER,
}
SLEEP_SECONDS = 5.0
MAX_RETRIES = 3

RAW_DIR = Path("data/raw/pihps")
JSON_SUBDIR = "json"
SEALED_SUBDIR = "_sealed"
MANIFEST_NAME = "manifest.csv"
INTERIM = Path("data/interim/pihps_long.parquet")

LONG_COLUMNS = ["date", "prov_name_raw", "price_type", "price_raw", "price_num", "source_file"]
MANIFEST_COLUMNS = [
    "file", "price_type", "start", "end", "sealed", "requested_at", "url",
    "http_status", "n_rows", "n_date_cols", "bytes", "sha256",
]
DATE_KEY_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
FILE_RE = re.compile(r"^pihps_pt(\d)_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json(\.gz)?$")

#: Rencana request: (price_type, start, end). Tidak ada yang melewati holdout.
WINDOWS: tuple[tuple[int, dt.date, dt.date], ...] = (
    (PRICE_TYPE_TRADITIONAL, dt.date(2017, 7, 1), dt.date(2017, 12, 31)),
    *((PRICE_TYPE_TRADITIONAL, dt.date(y, 1, 1), dt.date(y, 12, 31)) for y in range(2018, 2026)),
    (PRICE_TYPE_TRADITIONAL, dt.date(2026, 1, 1), dt.date(2026, 5, 31)),
    *((PRICE_TYPE_PRODUCER, dt.date(y, 1, 1), dt.date(y, 12, 31)) for y in range(2019, 2026)),
    (PRICE_TYPE_PRODUCER, dt.date(2026, 1, 1), dt.date(2026, 5, 31)),
)


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
def request_params(price_type: int, start: dt.date, end: dt.date) -> dict[str, str]:
    """Query string. Harus 100% sama dengan request asli di DevTools."""
    return {
        "price_type_id": str(price_type),
        "comcat_id": COMCAT_ID,
        PARAM_PROVINCE: "",
        "regency_id": "",
        "showKota": "false",
        "showPasar": "false",
        PARAM_REPORT_TYPE: "1",
        PARAM_DATE_START: start.strftime(DATE_FMT),
        PARAM_DATE_END: end.strftime(DATE_FMT),
    }


def new_session():
    """Session dengan cookie dari halaman utama (situs memasang antiforgery cookie)."""
    import requests  # import lokal supaya --help & --parse-only jalan tanpa requests

    session = requests.Session()
    session.headers.update(HEADERS)
    resp = session.get(SITE_URL, timeout=60)
    resp.raise_for_status()
    time.sleep(1)
    return session


def fetch(session, price_type: int, start: dt.date, end: dt.date, *, timeout: int = 120):
    """Satu jendela. Retry maks 3x dengan backoff; kembalikan (payload, status, url)."""
    import requests

    params = {**request_params(price_type, start, end), "_": str(int(time.time() * 1000))}
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(BASE_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, dict) or "data" not in payload:
                raise ValueError(f"respons tanpa kunci 'data': {str(payload)[:200]}")
            return payload, resp.status_code, resp.url
        except (requests.RequestException, ValueError) as err:
            last_err = err
            wait = SLEEP_SECONDS * attempt * 2
            print(f"  [retry {attempt}/{MAX_RETRIES}] tipe={price_type} {start}..{end}: {err}; tunggu {wait:.0f}s",
                  file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"gagal setelah {MAX_RETRIES}x: tipe={price_type} {start}..{end}") from last_err


# ---------------------------------------------------------------------------
# Simpan + manifest
# ---------------------------------------------------------------------------
def file_name(price_type: int, start: dt.date, end: dt.date) -> str:
    return f"pihps_pt{price_type}_{start.isoformat()}_{end.isoformat()}.json"


def _payload_stats(payload: dict) -> tuple[int, int]:
    rows = payload.get("data") or []
    date_cols = {k for row in rows for k in row if DATE_KEY_RE.match(str(k))}
    return len(rows), len(date_cols)


def save_payload(payload: dict, out_dir: Path, price_type: int, start: dt.date, end: dt.date) -> Path:
    """Simpan JSON apa adanya (UTF-8, tanpa reformat) supaya hash deterministik."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / file_name(price_type, start, end)
    path.write_bytes(json.dumps(payload, ensure_ascii=False, sort_keys=False).encode("utf-8"))
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def upsert_manifest(manifest: Path, record: dict) -> None:
    """Satu baris per file; unduhan ulang menimpa baris lama."""
    rows: list[dict] = []
    if manifest.exists():
        with manifest.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if "file" not in (reader.fieldnames or []):
                raise SystemExit(f"{manifest} bukan manifest scraper (kolom {reader.fieldnames}); pindahkan dulu.")
            rows = [r for r in reader if r["file"] != record["file"]]
    rows.append({k: record.get(k, "") for k in MANIFEST_COLUMNS})
    rows.sort(key=lambda r: r["file"])
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def split_at_holdout(start: dt.date, end: dt.date) -> list[tuple[dt.date, dt.date, bool]]:
    """Pecah [start, end] di HOLDOUT_START -> [(s, e, sealed)]."""
    if end < HOLDOUT_START:
        return [(start, end, False)]
    if start >= HOLDOUT_START:
        return [(start, end, True)]
    return [(start, HOLDOUT_START - dt.timedelta(days=1), False), (HOLDOUT_START, end, True)]


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------
_THOUSANDS_RE = re.compile(r"^\d{1,3}([.,]\d{3})+$")


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
    """JSON -> long table [date, prov_name_raw, price_type, price_raw, price_num, source_file].

    Hanya baris level 1 (provinsi). Level 0 = agregat nasional, level >= 2 = kota/pasar.
    Nama provinsi disimpan mentah; pemetaan ke prov_code dilakukan di MDE-H2-01.
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
                None if value is None else str(value), numeric_id(value), source_file,
            ))
    frame = pd.DataFrame.from_records(records, columns=LONG_COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["price_type"] = frame["price_type"].astype("int8")
    frame["price_num"] = frame["price_num"].astype("float64")
    return frame


def load_file(path: Path) -> dict:
    """Baca .json atau .json.gz."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def parse_dir(json_dir: Path) -> pd.DataFrame:
    """Parse semua JSON non-sealed. File yang menyentuh holdout ditolak keras."""
    frames = []
    paths = sorted(p for p in json_dir.glob("pihps_pt*") if p.name.endswith((".json", ".json.gz")))
    stems = [p.name.removesuffix(".gz") for p in paths]
    dup = sorted({s for s in stems if stems.count(s) > 1})
    if dup:
        raise SystemExit(f"Jendela ganda .json dan .json.gz: {dup}. Simpan salah satu saja.")
    for path in paths:
        m = FILE_RE.match(path.name)
        if not m:
            print(f"  [skip] nama file tidak sesuai pola: {path.name}", file=sys.stderr)
            continue
        if dt.date.fromisoformat(m.group(3)) >= HOLDOUT_START:
            raise SystemExit(f"{path.name} menyentuh holdout; pindahkan ke _sealed, jangan di-parse.")
        frames.append(parse_payload(load_file(path), int(m.group(1)), path.name))
    if not frames:
        raise SystemExit(f"Tidak ada JSON di {json_dir}")
    long = pd.concat(frames, ignore_index=True)
    # Jendela tidak tumpang tindih; bila ada (unduhan ulang), ambil file terakhir.
    long = long.drop_duplicates(["date", "prov_name_raw", "price_type"], keep="last")
    return long.sort_values(["price_type", "date", "prov_name_raw"]).reset_index(drop=True)


def _is_contract_province(name: str) -> bool:
    try:
        prov_code_of(name)
        return True
    except KeyError:
        return False


def validate_long(long: pd.DataFrame) -> list[str]:
    """Cek DoD; kembalikan daftar masalah (kosong = lulus)."""
    problems = []
    assert_before_holdout(long, "date")
    t1 = long[(long["price_type"] == PRICE_TYPE_TRADITIONAL) & long["price_num"].notna()]
    if t1.empty:
        return ["tipe 1 kosong"]
    if t1["date"].min() > pd.Timestamp("2017-07-31"):
        problems.append(f"tipe 1 mulai {t1['date'].min().date()}, harusnya Jul 2017")
    if t1["date"].max() < pd.Timestamp("2026-05-25"):
        problems.append(f"tipe 1 berakhir {t1['date'].max().date()}, harusnya akhir Mei 2026")
    unknown = sorted(n for n in long["prov_name_raw"].unique() if not _is_contract_province(n))
    if unknown:
        n_bad = int(long["prov_name_raw"].isin(unknown).sum())
        problems.append(f"nama di luar 34 provinsi kontrak (dibuang di MDE-H2-01): {unknown} ({n_bad} baris)")
    # Cakupan = baris provinsi yang dilaporkan per hari (harga '-' tetap dihitung hadir).
    rows_t1 = long[(long["price_type"] == PRICE_TYPE_TRADITIONAL) & ~long["prov_name_raw"].isin(unknown)]
    since_2018 = rows_t1[rows_t1["date"] >= pd.Timestamp("2018-01-02")]
    per_day = since_2018.groupby("date")["prov_name_raw"].nunique()
    if (per_day < 34).any():
        problems.append(f"{int((per_day < 34).sum())} hari kerja sejak 2018 punya < 34 baris provinsi")
    bad_num = long["price_num"].isna() & ~long["price_raw"].fillna("").str.strip().isin(["", "-", "0"])
    if bad_num.any():
        sample = long.loc[bad_num, "price_raw"].unique()[:10].tolist()
        problems.append(f"{int(bad_num.sum())} nilai tak terbaca sebagai angka, contoh: {sample}")
    return problems


def summary(long: pd.DataFrame) -> pd.DataFrame:
    obs = long[long["price_num"].notna()]
    return (obs.assign(year=obs["date"].dt.year)
               .groupby(["price_type", "year"])
               .agg(n_prov=("prov_name_raw", "nunique"), n_days=("date", "nunique"), n_obs=("price_num", "size"))
               .reset_index())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def run_download(price_type: int, out: Path, sealed_out: Path, include_sealed: bool, force: bool,
                 window: tuple[dt.date, dt.date] | None = None) -> None:
    manifest = out / MANIFEST_NAME
    session = new_session()
    windows = [(price_type, *window)] if window else [w for w in WINDOWS if w[0] == price_type]
    if include_sealed:
        windows.append((price_type, HOLDOUT_START, dt.date.today()))
    for pt, start, end in windows:
        for s, e, sealed in split_at_holdout(start, end):
            if sealed and not include_sealed:
                continue
            target_dir = (sealed_out if sealed else out) / JSON_SUBDIR
            target = target_dir / file_name(pt, s, e)
            if target.exists() and not force:
                print(f"[ada] {target.name}")
                continue
            payload, status, url = fetch(session, pt, s, e)
            path = save_payload(payload, target_dir, pt, s, e)
            n_rows, n_dates = _payload_stats(payload)
            upsert_manifest(manifest, {
                "file": path.relative_to(out).as_posix(), "price_type": pt,
                "start": s.isoformat(), "end": e.isoformat(), "sealed": int(sealed),
                "requested_at": dt.datetime.now().isoformat(timespec="seconds"),
                "url": url, "http_status": status, "n_rows": n_rows, "n_date_cols": n_dates,
                "bytes": path.stat().st_size, "sha256": sha256_file(path),
            })
            # Isi file sealed tidak pernah dicetak; hanya nama file.
            info = "" if sealed else f" baris={n_rows} kolom_tanggal={n_dates}"
            print(f"[ok] {path.name}{info}")
            time.sleep(SLEEP_SECONDS)


def run_probe(price_type: int) -> None:
    """Langkah 3: satu request 1 bulan, cetak struktur tanpa menyimpan."""
    start, end = dt.date(2024, 1, 1), dt.date(2024, 1, 31)
    session = new_session()
    payload, status, url = fetch(session, price_type, start, end)
    rows = payload["data"]
    print(f"URL     : {url}\nHTTP    : {status}\nkunci   : {list(payload)}\nbaris   : {len(rows)}")
    if rows:
        keys = list(rows[0])
        print(f"kolom baris[0] (10 pertama): {keys[:10]}")
    levels = pd.Series([r.get("level") for r in rows]).value_counts().to_dict()
    print(f"level   : {levels}")
    long = parse_payload(payload, price_type)
    print(f"provinsi level 1: {long['prov_name_raw'].nunique()}")
    print(sorted(long["prov_name_raw"].unique()))
    print(f"tanggal : {long['date'].min().date()} .. {long['date'].max().date()} ({long['date'].nunique()} hari)")
    print(long.head(8).to_string(index=False))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Scrape PIHPS GetGridDataKomoditas (MDE-H1-01)")
    ap.add_argument("--price-type", type=int, choices=[1, 4], default=1)
    ap.add_argument("--out", type=Path, default=RAW_DIR)
    ap.add_argument("--sealed-out", type=Path, default=RAW_DIR / SEALED_SUBDIR)
    ap.add_argument("--interim", type=Path, default=INTERIM)
    ap.add_argument("--probe", action="store_true", help="1 request Jan 2024, cetak struktur, tidak menyimpan")
    ap.add_argument("--parse-only", action="store_true", help="lewati download, parse JSON yang ada")
    ap.add_argument("--include-sealed", action="store_true",
                    help="ikut unduh >= holdout ke --sealed-out (hanya bila CGS meminta)")
    ap.add_argument("--force", action="store_true", help="unduh ulang walau file sudah ada")
    ap.add_argument("--start", type=dt.date.fromisoformat, help="jendela kustom (pakai bersama --end)")
    ap.add_argument("--end", type=dt.date.fromisoformat, help="jendela kustom; harus < 2026-06-01")
    args = ap.parse_args(argv)

    if args.probe:
        run_probe(args.price_type)
        return
    if not args.parse_only:
        window = None
        if args.start or args.end:
            if not (args.start and args.end) or args.start > args.end:
                raise SystemExit("--start dan --end harus diisi berdua, start <= end")
            if args.end >= HOLDOUT_START and not args.include_sealed:
                raise SystemExit(f"--end menyentuh holdout ({HOLDOUT_START}); jendela berhenti di 2026-05-31")
            window = (args.start, args.end)
        run_download(args.price_type, args.out, args.sealed_out, args.include_sealed, args.force, window)
        return

    long = parse_dir(args.out / JSON_SUBDIR)
    problems = validate_long(long)
    args.interim.parent.mkdir(parents=True, exist_ok=True)
    long.to_parquet(args.interim, index=False)
    print(f"[ok] {args.interim} baris={len(long):,} max(date)={long['date'].max().date()}")
    print(summary(long).to_string(index=False))
    for p in problems:
        print(f"[PERIKSA] {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
