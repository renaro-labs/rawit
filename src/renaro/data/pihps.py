# =============================================================================
#  MDE-H1-01 · Scrape PIHPS 2017–2026 (tipe 1 dan 4)
# -----------------------------------------------------------------------------
#  Role    : MDE — Market Data Engineer (@dio)
#  Ticket  : RAWIT-11 (1/2), RAWIT-12 (2/2)
#  Input   : endpoint publik GetGridDataKomoditas (docs/sources/pihps_endpoint.md)
#  Output  : data/raw/pihps/pt{1|4}_{YYYYMMDD}_{YYYYMMDD}.json + manifest.csv
#            data/raw/pihps/_sealed/pt{1|4}_*.json + _sealed/manifest.csv  (>= 2026-06-01)
#            data/interim/pihps_long.parquet   (hanya < 2026-06-01; lihat pihps_parse.py)
#  Handoff : MDE-H1-03, MDE-H2-01, CGS (file _sealed)
# =============================================================================
"""Unduh panel PIHPS mentah + manifest; parse via ``renaro.data.pihps_parse``.

Pemakaian (dari root repo, PowerShell, ``$env:PYTHONPATH = "src"``):

    python -m renaro.data.pihps --probe                    # 1 request Jan 2024, tidak disimpan
    python -m renaro.data.pihps --price-type 1             # semua jendela tipe 1 (< holdout)
    python -m renaro.data.pihps --price-type 4
    python -m renaro.data.pihps --price-type 1 --include-sealed   # + 2026-06-01..hari ini ke _sealed
    python -m renaro.data.pihps --parse-only               # JSON -> pihps_long.parquet + validasi
    python -m renaro.data.pihps --spotcheck                # 3 tanggal x 3 provinsi untuk dicek di situs
    python -m renaro.data.pihps --crosscheck               # bandingkan dengan CSV tim
    python -m renaro.data.pihps --handoff-sealed --to <folder CGS>

Catatan lisensi: PIHPS "Hak Cipta - Semua Hak Dilindungi". Data mentah tidak
diredistribusi; file ``_sealed`` diserahkan ke CGS lalu dihapus dari drive bersama.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

from renaro.contract import HOLDOUT_START
from renaro.data import pihps_parse as P

# ---------------------------------------------------------------------------
# Endpoint — terverifikasi dengan DevTools 2026-11-24 (docs/sources/pihps_request_example.txt)
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
PRICE_TYPE_TRADITIONAL = P.PRICE_TYPE_TRADITIONAL
PRICE_TYPE_PRODUCER = P.PRICE_TYPE_PRODUCER

HEADERS = {
    "User-Agent": "renaro-research-client (Mozilla/5.0 compatible)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": REFERER,
}
SLEEP_SECONDS = 5.0
MAX_RETRIES = 3

RAW_DIR = Path("data/raw/pihps")
SEALED_SUBDIR = "_sealed"
MANIFEST_NAME = "manifest.csv"
INTERIM = Path("data/interim/pihps_long.parquet")
TEAM_CSV = RAW_DIR / "pihps_cabai_merah_keriting_province.csv"
SEAL_DOC = Path("docs/holdout_seal.md")

#: Kolom wajib playbook dulu, lalu kolom bantu.
MANIFEST_COLUMNS = [
    "file", "price_type", "start", "end", "n_bytes", "sha256", "fetched_at", "http_status",
    "n_rows", "n_date_cols", "url",
]

#: Jadwal playbook (± 1 request/tahun). Tidak ada jendela yang melewati holdout.
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
    """Query string, identik dengan request asli di DevTools."""
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


def fetch(session, price_type: int, start: dt.date, end: dt.date, *, timeout: int = 180):
    """Satu jendela. Retry maks 3x dengan backoff; kembalikan (raw_bytes, payload, status, url)."""
    import requests

    params = {**request_params(price_type, start, end), "_": str(int(time.time() * 1000))}
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(BASE_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, dict) or "data" not in payload:
                raise ValueError("respons tanpa kunci 'data'")
            return resp.content, payload, resp.status_code, resp.url
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
    return f"pt{price_type}_{start:%Y%m%d}_{end:%Y%m%d}.json"


def payload_stats(payload: dict) -> tuple[int, int]:
    """(jumlah baris wilayah, jumlah kolom tanggal) — hitungan saja, tanpa nilai."""
    rows = payload.get("data") or []
    date_cols = {k for row in rows for k in row if P.DATE_KEY_RE.match(str(k))}
    return len(rows), len(date_cols)


def save_raw(raw: bytes, out_dir: Path, price_type: int, start: dt.date, end: dt.date) -> Path:
    """Simpan body respons apa adanya (byte persis dari server)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / file_name(price_type, start, end)
    path.write_bytes(raw)
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
# Perintah
# ---------------------------------------------------------------------------
def run_download(price_type: int, out: Path, include_sealed: bool, force: bool,
                 window: tuple[dt.date, dt.date] | None = None) -> None:
    session = new_session()
    windows = [(price_type, *window)] if window else [w for w in WINDOWS if w[0] == price_type]
    if include_sealed and not window:
        windows.append((price_type, HOLDOUT_START, dt.date.today()))
    for pt, start, end in windows:
        for s, e, sealed in split_at_holdout(start, end):
            if sealed and not include_sealed:
                continue
            target_dir = out / SEALED_SUBDIR if sealed else out
            target = target_dir / file_name(pt, s, e)
            if target.exists() and not force:
                print(f"[ada] {target.name}")
                continue
            raw, payload, status, url = fetch(session, pt, s, e)
            path = save_raw(raw, target_dir, pt, s, e)
            n_rows, n_dates = payload_stats(payload)
            upsert_manifest(target_dir / MANIFEST_NAME, {
                "file": path.name, "price_type": pt, "start": s.isoformat(), "end": e.isoformat(),
                "n_bytes": path.stat().st_size, "sha256": sha256_file(path),
                "fetched_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "http_status": status, "n_rows": n_rows, "n_date_cols": n_dates, "url": url,
            })
            tag = "[sealed]" if sealed else "[ok]"
            print(f"{tag} {path.name} http={status} baris={n_rows} kolom_tanggal={n_dates} bytes={path.stat().st_size:,}")
            time.sleep(SLEEP_SECONDS)


def run_probe(price_type: int) -> None:
    """Langkah 3 (1/2): satu request 1 bulan, cetak struktur tanpa menyimpan."""
    start, end = dt.date(2024, 1, 1), dt.date(2024, 1, 31)
    session = new_session()
    _raw, payload, status, url = fetch(session, price_type, start, end)
    rows = payload["data"]
    print(f"URL     : {url}\nHTTP    : {status}\nkunci   : {list(payload)}\nbaris   : {len(rows)}")
    if rows:
        print(f"kolom baris[0] (10 pertama): {list(rows[0])[:10]}")
    levels: dict = {}
    for r in rows:
        levels[r.get("level")] = levels.get(r.get("level"), 0) + 1
    print(f"level   : {levels}")
    long = P.parse_payload(payload, price_type)
    print(f"provinsi level 1: {long['prov_name_raw'].nunique()}")
    print(sorted(long["prov_name_raw"].unique()))
    print(f"tanggal : {long['date'].min().date()} .. {long['date'].max().date()} ({long['date'].nunique()} hari)")
    print(long.head(8).to_string(index=False))


def run_parse(raw_dir: Path, interim: Path) -> None:
    long = P.parse_dir(raw_dir)
    problems = P.validate_long(long)
    P.write_parquet(long, interim)
    print(f"[ok] {interim} baris={len(long):,} max(date)={long['date'].max().date()} (< {HOLDOUT_START})")
    print(P.summary_by_file(long).to_string(index=False))
    for p in problems:
        print(f"[PERIKSA] {p}", file=sys.stderr)


def run_handoff(out: Path, target: Path, seal_doc: Path) -> None:
    """Salin _sealed ke folder CGS, verifikasi sha256, hapus salinan lokal, catat checksum."""
    sealed = out / SEALED_SUBDIR
    files = sorted(sealed.glob("pt*.json")) if sealed.exists() else []
    if not files:
        raise SystemExit(f"Tidak ada file di {sealed}")
    extras = [p for p in [sealed / MANIFEST_NAME] if p.exists()]
    target.mkdir(parents=True, exist_ok=True)
    lines = []
    for src in files + extras:
        dst = target / src.name
        shutil.copy2(src, dst)
        h = sha256_file(src)
        if sha256_file(dst) != h:
            raise SystemExit(f"checksum beda setelah salin: {src.name}")
        lines.append(f"{h}  pihps_mde/{src.name}")
    for src in files + extras:
        src.unlink()
    stamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    block = ("\n## Serah-terima MDE (MDE-H1-01)\n\n"
             f"- Diserahkan oleh: **MDE** · {stamp}\n"
             f"- Tujuan: `{target}`\n"
             f"- File: {len(files)} JSON + manifest; salinan di `{sealed}` sudah dihapus.\n"
             "- Penerimaan CGS: _diisi CGS_\n\n```text\n" + "\n".join(lines) + "\n```\n")
    with seal_doc.open("a", encoding="utf-8") as fh:
        fh.write(block)
    print(f"[ok] {len(files)} file diserahkan ke {target}; checksum dicatat di {seal_doc}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Scrape PIHPS GetGridDataKomoditas (MDE-H1-01)")
    ap.add_argument("--price-type", type=int, choices=[1, 4], default=1)
    ap.add_argument("--out", type=Path, default=RAW_DIR)
    ap.add_argument("--interim", type=Path, default=INTERIM)
    ap.add_argument("--probe", action="store_true", help="1 request Jan 2024, cetak struktur, tidak menyimpan")
    ap.add_argument("--parse-only", action="store_true", help="lewati download, parse JSON yang ada")
    ap.add_argument("--parse-dir", type=Path, help="folder JSON untuk --parse-only (default: --out)")
    ap.add_argument("--spotcheck", action="store_true", help="3 tanggal x 3 provinsi dari parquet")
    ap.add_argument("--crosscheck", action="store_true", help="bandingkan parquet dengan CSV tim")
    ap.add_argument("--include-sealed", action="store_true", help="ikut unduh >= holdout ke _sealed/")
    ap.add_argument("--handoff-sealed", action="store_true", help="serahkan _sealed/ ke folder CGS (--to)")
    ap.add_argument("--to", type=Path, help="folder tujuan serah-terima CGS")
    ap.add_argument("--force", action="store_true", help="unduh ulang walau file sudah ada")
    ap.add_argument("--start", type=dt.date.fromisoformat, help="jendela kustom (pakai bersama --end)")
    ap.add_argument("--end", type=dt.date.fromisoformat, help="jendela kustom")
    args = ap.parse_args(argv)

    if args.probe:
        return run_probe(args.price_type)
    if args.parse_only:
        return run_parse(args.parse_dir or args.out, args.interim)
    if args.spotcheck or args.crosscheck:
        import pandas as pd
        long = pd.read_parquet(args.interim)
        if args.spotcheck:
            print("Cocokkan dengan situs (Pasar Tradisional, Cabai Merah Keriting, Harian):")
            print(P.spot_check_sample(long).to_string(index=False))
        if args.crosscheck:
            print(json.dumps(P.crosscheck_csv(long, TEAM_CSV), indent=2, ensure_ascii=False))
        return None
    if args.handoff_sealed:
        if not args.to:
            raise SystemExit("--handoff-sealed butuh --to <folder CGS>")
        return run_handoff(args.out, args.to, SEAL_DOC)

    window = None
    if args.start or args.end:
        if not (args.start and args.end) or args.start > args.end:
            raise SystemExit("--start dan --end harus diisi berdua, start <= end")
        if args.end >= HOLDOUT_START and not args.include_sealed:
            raise SystemExit(f"--end menyentuh holdout ({HOLDOUT_START}); tambah --include-sealed bila memang diminta")
        window = (args.start, args.end)
    run_download(args.price_type, args.out, args.include_sealed, args.force, window)
    return None


if __name__ == "__main__":
    main()
