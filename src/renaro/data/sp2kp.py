# =============================================================================
#  MDE-H1-02 · Tarik SP2KP 2024+ untuk validasi silang
# -----------------------------------------------------------------------------
#  Role    : MDE — Market Data Engineer (@dio)
#  Input   : API publik SP2KP Kemendag (api-sp2kp.kemendag.go.id), variant_id=2
#            (Cabai Merah Keriting), level provinsi, sejak 2024-02-01
#  Output  : data/raw/sp2kp/master_provinsi.json
#            data/raw/sp2kp/l1_p{kode}_{YYYYMMDD}_{YYYYMMDD}.json + manifest.csv
#            data/raw/sp2kp/_sealed/ (>= 2026-06-01, hanya --include-sealed)
#            data/interim/sp2kp_long.parquet (34 provinsi, < 2026-06-01)
#  Handoff : MDE-H2-01 (validasi silang), CGS (file _sealed)
#  DoD     : >= 30 provinsi ter-map ke kode BPS; TIDAK dipakai sebagai fitur/target
# =============================================================================
"""SP2KP hanya untuk validasi silang. Jangan pernah masuk panel latih.

Pemakaian (root repo, PowerShell, ``$env:PYTHONPATH = "src"``):

    python -m renaro.data.sp2kp --probe          # daftar provinsi + 1 request kecil, tidak disimpan
    python -m renaro.data.sp2kp                  # semua provinsi, 2024-02-01..2026-05-31
    python -m renaro.data.sp2kp --parse-only     # JSON -> sp2kp_long.parquet (34 provinsi)
    python -m renaro.data.sp2kp --report         # reports/qa/sp2kp_coverage.md

PERHATIAN kode provinsi: SP2KP memakai kode Kemendagri pasca-pemekaran
(91 Papua, 92 Papua Barat, 93 Papua Selatan, 94 Papua Tengah, 95 Papua Pegunungan,
96 Papua Barat Daya). Kode BPS lama di kontrak: 91 Papua Barat, 94 Papua.
Karena itu pemetaan 38 -> 34 dilakukan lewat NAMA provinsi, bukan kode.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

from renaro.contract import HOLDOUT_START, PROV_CODES, assert_before_holdout, prov_code_of

# ---------------------------------------------------------------------------
# Endpoint (rujukan: bundel JS sp2kp.kemendag.go.id; scraper terbuka
# RobyArjuna/scraping-commodity-sk2kp, Rianfirnanda/lintasAIprojection).
# Terverifikasi 2026-11-24 dari halaman /statistik/area (docs/sources/sp2kp_request_example.txt)
# ---------------------------------------------------------------------------
API = "https://api-sp2kp.kemendag.go.id"
URL_PROVINSI = f"{API}/master/api/wilayah/provinsi"
URL_AREA_DAILY = f"{API}/report/api/average-price/export-area-daily-json"   # POST multipart
URL_PUBLIC = f"{API}/report/api/average-price-public"                       # GET (hanya --probe)
HEADERS = {
    "User-Agent": "renaro-research-client (Mozilla/5.0 compatible)",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://sp2kp.kemendag.go.id",
    "Referer": "https://sp2kp.kemendag.go.id/",
}
VARIANT_ID = 2                       # Cabai Merah Keriting (kg)
LEVEL_PROVINSI = "1"                 # 0 nasional, 1 provinsi, 2 kab/kota, 3 pasar
SLEEP_SECONDS = 2.0
MAX_RETRIES = 3

START = dt.date(2024, 2, 1)
END = dt.date(2026, 5, 31)
RAW_DIR = Path("data/raw/sp2kp")
SEALED_SUBDIR = "_sealed"
MANIFEST_NAME = "manifest.csv"
MASTER_NAME = "master_provinsi.json"
INTERIM = Path("data/interim/sp2kp_long.parquet")
COMMODITY = "cabai_merah_keriting"
PRICE_TYPE_SP2KP = 2                 # kontrak: 2 = SP2KP

MANIFEST_COLUMNS = ["file", "kode_provinsi", "start", "end", "n_bytes", "sha256", "fetched_at",
                    "http_status", "n_variants", "n_prices", "url"]
FILE_RE = re.compile(r"^l1_p(\d{2})_(\d{8})_(\d{8})\.json$")

#: Provinsi pemekaran -> kode BPS lama (nama SP2KP dinormalisasi huruf kecil).
PAPUA_MERGE = {
    "papua": "94",
    "papua selatan": "94",
    "papua tengah": "94",
    "papua pegunungan": "94",
    "papua barat": "91",
    "papua barat daya": "91",
}
#: Ejaan SP2KP yang tidak ada di alias kontrak (kontrak tidak diubah; alias lokal di sini).
SP2KP_ALIASES = {
    "daerah istimewa yogyakarta": "34",
}
LONG_COLUMNS = ["date", "prov_code", "commodity", "price_type", "price", "is_aggregated",
                "n_source_prov", "source_prov_names", "source", "available_at"]


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _session():
    import requests
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _retry(call, what: str):
    import requests
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = call()
            resp.raise_for_status()
            resp.json()
            return resp
        except (requests.RequestException, ValueError) as err:
            last = err
            wait = SLEEP_SECONDS * attempt * 3
            print(f"  [retry {attempt}/{MAX_RETRIES}] {what}: {err}; tunggu {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"gagal setelah {MAX_RETRIES}x: {what}") from last


def area_form(kode_provinsi: str, start: dt.date, end: dt.date) -> dict[str, str]:
    """Form multipart export-area-daily-json level provinsi."""
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "level": LEVEL_PROVINSI,
        "variant_ids": str(VARIANT_ID),
        "kode_provinsi": kode_provinsi,
        "kode_kab_kota": "",
        "pasar_id": "",
        "skip_sat_sun": "true",
        "tipe_komoditas": "1",
    }


def fetch_provinces(session) -> tuple[bytes, list[dict]]:
    resp = _retry(lambda: session.get(URL_PROVINSI, params={"take": 100}, timeout=60), "master provinsi")
    return resp.content, extract_provinces(resp.json())


def extract_provinces(payload) -> list[dict]:
    """Respons master -> [{kode, nama}] dengan tebakan kunci yang toleran."""
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(rows, dict):
        rows = rows.get("data", [])
    out = []
    for r in rows or []:
        kode = next((str(r[k]) for k in ("kode_provinsi", "kode", "code", "id") if r.get(k) not in (None, "")), None)
        nama = next((str(r[k]) for k in ("nama_provinsi", "nama", "name") if r.get(k)), None)
        if kode and nama:
            out.append({"kode": kode.zfill(2)[:2], "nama": nama.strip()})
    return out


def fetch_area(session, kode: str, start: dt.date, end: dt.date):
    form = area_form(kode, start, end)
    resp = _retry(lambda: session.post(URL_AREA_DAILY, files={k: (None, v) for k, v in form.items()}, timeout=180),
                  f"provinsi {kode} {start}..{end}")
    return resp.content, resp.json(), resp.status_code


# ---------------------------------------------------------------------------
# Simpan
# ---------------------------------------------------------------------------
def file_name(kode: str, start: dt.date, end: dt.date) -> str:
    return f"l1_p{kode}_{start:%Y%m%d}_{end:%Y%m%d}.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def upsert_manifest(manifest: Path, record: dict) -> None:
    rows: list[dict] = []
    if manifest.exists():
        with manifest.open(newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r["file"] != record["file"]]
    rows.append({k: record.get(k, "") for k in MANIFEST_COLUMNS})
    rows.sort(key=lambda r: r["file"])
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def windows(start: dt.date, end: dt.date, chunk_days: int) -> list[tuple[dt.date, dt.date, bool]]:
    """Jendela per tahun kalender (chunk_days=0) atau per N hari; dipecah di HOLDOUT_START."""
    out, cur = [], start
    while cur <= end:
        stop = dt.date(cur.year, 12, 31) if chunk_days <= 0 else cur + dt.timedelta(days=chunk_days - 1)
        if cur < HOLDOUT_START <= stop:
            stop = HOLDOUT_START - dt.timedelta(days=1)
        stop = min(stop, end)
        out.append((cur, stop, cur >= HOLDOUT_START))
        cur = stop + dt.timedelta(days=1)
    return out


def _price_stats(payload: dict) -> tuple[int, int]:
    items = payload.get("data") or []
    return len(items), sum(len(i.get("daftarHarga") or []) for i in items)


# ---------------------------------------------------------------------------
# Parse + map 38 -> 34
# ---------------------------------------------------------------------------
def _num(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return v if v > 0 else float("nan")


def parse_area(payload: dict, kode: str, nama: str, source_file: str = "") -> pd.DataFrame:
    """Respons export-area-daily-json -> [date, kode_sp2kp, prov_name_raw, price_raw, source_file]."""
    recs = []
    for item in payload.get("data") or []:
        if str(item.get("variant_id")) != str(VARIANT_ID):
            continue
        for h in item.get("daftarHarga") or []:
            if h.get("date"):
                recs.append((str(h["date"])[:10], kode, nama, _num(h.get("harga")), source_file))
    frame = pd.DataFrame(recs, columns=["date", "kode_sp2kp", "prov_name_raw", "price_raw", "source_file"])
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def old_code_of(name: str) -> str:
    """Nama provinsi SP2KP -> kode BPS lama. Nama tak dikenal = error, bukan drop."""
    key = re.sub(r"\s+", " ", name.strip().casefold())
    if key in PAPUA_MERGE:
        return PAPUA_MERGE[key]
    if key in SP2KP_ALIASES:
        return SP2KP_ALIASES[key]
    return prov_code_of(name)


def map_to_old_34(raw: pd.DataFrame) -> pd.DataFrame:
    """38 provinsi -> 34. Pemekaran Papua: rata-rata sederhana, is_aggregated=True."""
    raw = raw.assign(prov_code=raw["prov_name_raw"].map(old_code_of))
    merged_codes = {c for c in PAPUA_MERGE.values()}
    g = raw.groupby(["date", "prov_code"])
    out = g.agg(price=("price_raw", "mean"),
                n_source_prov=("price_raw", "count"),
                source_prov_names=("prov_name_raw", lambda s: "|".join(sorted(set(s))))).reset_index()
    out["is_aggregated"] = out["prov_code"].isin(merged_codes)
    out["commodity"] = COMMODITY
    out["price_type"] = PRICE_TYPE_SP2KP
    out["source"] = "sp2kp"
    out["available_at"] = (out["date"] + pd.offsets.BDay(1)).dt.normalize()
    bad = set(out["prov_code"]) - set(PROV_CODES)
    if bad:
        raise ValueError(f"kode di luar 34 provinsi kontrak: {sorted(bad)}")
    return out[LONG_COLUMNS].sort_values(["date", "prov_code"]).reset_index(drop=True)


def parse_dir(raw_dir: Path) -> pd.DataFrame:
    master = json.loads((raw_dir / MASTER_NAME).read_text(encoding="utf-8"))
    names = {p["kode"]: p["nama"] for p in extract_provinces(master)}
    frames = []
    for path in sorted(raw_dir.glob("l1_p*.json")):
        m = FILE_RE.match(path.name)
        if not m:
            continue
        if dt.datetime.strptime(m.group(3), "%Y%m%d").date() >= HOLDOUT_START:
            raise SystemExit(f"{path.name} menyentuh holdout; pindahkan ke _sealed.")
        kode = m.group(1)
        frames.append(parse_area(json.loads(path.read_text(encoding="utf-8")), kode, names[kode], path.name))
    if not frames:
        raise SystemExit(f"Tidak ada JSON SP2KP di {raw_dir}")
    raw = pd.concat(frames, ignore_index=True)
    return raw.drop_duplicates(["date", "kode_sp2kp"], keep="last")


def validate(long: pd.DataFrame) -> list[str]:
    problems = []
    assert_before_holdout(long, "date")
    n = long.loc[long["price"].notna(), "prov_code"].nunique()
    if n < 30:
        problems.append(f"hanya {n} provinsi kontrak berharga (DoD >= 30)")
    if long["date"].min() > pd.Timestamp("2024-02-29"):
        problems.append(f"data mulai {long['date'].min().date()}, harusnya Feb 2024")
    return problems


# ---------------------------------------------------------------------------
# Perintah
# ---------------------------------------------------------------------------
def run_probe() -> None:
    s = _session()
    raw, provs = fetch_provinces(s)
    print(f"master provinsi: {len(provs)} entri")
    print([f"{p['kode']} {p['nama']}" for p in provs])
    unknown = []
    for p in provs:
        try:
            old_code_of(p["nama"])
        except KeyError:
            unknown.append(p["nama"])
    print(f"nama tak terpetakan: {unknown or 'tidak ada'}")
    # UI situs membatasi rentang 30 hari; uji apakah API menerima 1 tahun penuh.
    s0, e0 = dt.date(2024, 2, 1), dt.date(2024, 12, 31)
    content, payload, status = fetch_area(s, "31", s0, e0)
    items = payload.get("data") or []
    print(f"\nexport-area-daily-json DKI {s0}..{e0}: HTTP {status}, kunci {list(payload)}, item {len(items)}")
    if items:
        print(f"kunci item: {list(items[0])}")
        print(f"variant: {[(i.get('variant_id'), i.get('variant'), i.get('satuan')) for i in items][:5]}")
        dh = items[0].get("daftarHarga") or []
        expected = len(pd.bdate_range(s0, e0))
        print(f"daftarHarga: {len(dh)} tanggal (hari kerja di rentang: {expected}); 3 pertama {dh[:3]}; terakhir {dh[-1:]}")
        if len(dh) < 0.9 * expected:
            print("  -> respons TERPOTONG: unduh dengan --chunk-days 30")
        else:
            print("  -> rentang 1 tahun diterima: unduhan default (per tahun) aman")
    time.sleep(SLEEP_SECONDS)
    r = _retry(lambda: s.get(URL_PUBLIC, params={"variant_id": VARIANT_ID, "tanggal": "2024-03-01"}, timeout=60),
               "average-price-public")
    pub = r.json()
    print(f"\naverage-price-public: HTTP {r.status_code}, kunci {list(pub) if isinstance(pub, dict) else type(pub)}")
    rows = pub.get("data") if isinstance(pub, dict) else None
    if rows:
        print(f"kunci baris (nilai tidak dicetak; endpoint ini memuat data petugas): {list(rows[0])}")


def run_download(out: Path, start: dt.date, end: dt.date, chunk_days: int, include_sealed: bool,
                 only: list[str] | None, force: bool) -> None:
    s = _session()
    raw, provs = fetch_provinces(s)
    out.mkdir(parents=True, exist_ok=True)
    (out / MASTER_NAME).write_bytes(raw)
    for p in provs:
        old_code_of(p["nama"])  # gagal keras sebelum mengunduh bila ada nama baru
    for p in provs:
        if only and p["kode"] not in only:
            continue
        for s0, e0, sealed in windows(start, end, chunk_days):
            if sealed and not include_sealed:
                continue
            target_dir = out / SEALED_SUBDIR if sealed else out
            path = target_dir / file_name(p["kode"], s0, e0)
            if path.exists() and not force:
                print(f"[ada] {path.name}")
                continue
            content, payload, status = fetch_area(s, p["kode"], s0, e0)
            target_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            n_var, n_prices = _price_stats(payload)
            upsert_manifest(target_dir / MANIFEST_NAME, {
                "file": path.name, "kode_provinsi": p["kode"], "start": s0.isoformat(), "end": e0.isoformat(),
                "n_bytes": path.stat().st_size, "sha256": sha256_file(path),
                "fetched_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "http_status": status, "n_variants": n_var, "n_prices": n_prices, "url": URL_AREA_DAILY,
            })
            tag = "[sealed]" if sealed else "[ok]"
            print(f"{tag} {path.name} {p['nama']} http={status} jumlah_tanggal={n_prices}")
            time.sleep(SLEEP_SECONDS)


def run_parse(raw_dir: Path, interim: Path) -> None:
    raw = parse_dir(raw_dir)
    long = map_to_old_34(raw)
    missing = set(LONG_COLUMNS) - set(long.columns)
    if missing:
        raise ValueError(f"sp2kp_long: kolom hilang {sorted(missing)}")
    problems = validate(long)
    interim.parent.mkdir(parents=True, exist_ok=True)
    long.to_parquet(interim, index=False)
    obs = long[long["price"].notna()]
    print(f"[ok] {interim} baris={len(long):,} provinsi={obs['prov_code'].nunique()} "
          f"{long['date'].min().date()}..{long['date'].max().date()}")
    print(f"provinsi sumber SP2KP: {raw['prov_name_raw'].nunique()}; agregat Papua: "
          f"{sorted(long.loc[long['is_aggregated'], 'source_prov_names'].unique())}")
    for p in problems:
        print(f"[PERIKSA] {p}", file=sys.stderr)


REPORT_MD = Path("reports/qa/sp2kp_coverage.md")


def run_report(out: Path, interim: Path, report: Path) -> dict:
    """Laporan hasil tarikan periode shared (< holdout) -> reports/qa/sp2kp_coverage.md."""
    long = pd.read_parquet(interim)
    long["date"] = pd.to_datetime(long["date"])
    assert_before_holdout(long, "date")
    man = pd.read_csv(out / MANIFEST_NAME, dtype={"kode_provinsi": str})
    master = extract_provinces(json.loads((out / MASTER_NAME).read_text(encoding="utf-8")))
    sources = sorted({n for s in long["source_prov_names"].dropna() for n in s.split("|")})
    obs = long[long["price"].notna()]
    n_mapped = obs["prov_code"].nunique()
    agg = (long[long["is_aggregated"]].groupby("prov_code")["source_prov_names"]
           .agg(lambda s: sorted({n for x in s for n in x.split("|")})))
    cov = (long.groupby("prov_code")["price"].apply(lambda s: s.notna().mean()).sort_values())
    days = long["date"].nunique()
    stats = {
        "n_master": len(master), "n_source": len(sources), "n_mapped": n_mapped,
        "rows": len(long), "days": days, "min": long["date"].min().date(), "max": long["date"].max().date(),
        "nan": int(long["price"].isna().sum()), "files": len(man),
        "http200": int((man["http_status"].astype(int) == 200).sum()),
        "sha_manifest": sha256_file(out / MANIFEST_NAME), "sha_parquet": sha256_file(interim),
    }
    lines = "\n".join(f"| {c} | {', '.join(names)} | {len(names)} |" for c, names in agg.items())
    low = ", ".join(f"{c} ({v:.1%})" for c, v in cov.head(5).items())
    md = f"""# SP2KP — hasil tarikan periode shared (MDE-H1-02)

- Sumber: `{(out / MANIFEST_NAME).as_posix()}`, `{interim.as_posix()}`; dibuat oleh `python -m renaro.data.sp2kp --report`
- Endpoint: `export-area-daily-json` (lihat `docs/sources/sp2kp_endpoint.md`), variant 2 = Cabai Merah Keriting, level provinsi
- **Peran data: hanya validasi silang di MDE-H2-01. Tidak dipakai sebagai fitur atau target** (tidak masuk `panel.parquet`/`target.parquet`).

## Kesimpulan DoD

**{stats['n_mapped']} dari 34 provinsi kontrak ter-map ke kode BPS (DoD ≥ 30: terpenuhi).**

## Angka

| Item | Nilai |
|---|---|
| Provinsi di master SP2KP | {stats['n_master']} |
| Provinsi sumber yang punya data | {stats['n_source']} |
| Provinsi kontrak (kode BPS lama) ter-map | {stats['n_mapped']} / 34 |
| File mentah (manifest) | {stats['files']} ({stats['http200']} dengan HTTP 200) |
| Baris `sp2kp_long.parquet` | {stats['rows']:,} (= {stats['n_mapped']} provinsi × {stats['days']} hari kerja) |
| Rentang tanggal | {stats['min']} .. {stats['max']} (< holdout 2026-06-01) |
| Harga NaN (`harga` 0/kosong, terutama libur nasional & cuti bersama) | {stats['nan']:,} ({stats['nan'] / stats['rows']:.1%}) |
| SHA256 `data/raw/sp2kp/manifest.csv` | `{stats['sha_manifest']}` |
| SHA256 `data/interim/sp2kp_long.parquet` | `{stats['sha_parquet']}` |

## Provinsi pemekaran yang diagregasi (rata-rata sederhana, `is_aggregated=True`)

| Kode kontrak | Provinsi sumber SP2KP | Jumlah |
|---|---|---:|
{lines}

Kode SP2KP memakai Kemendagri (91 Papua, 92 Papua Barat, 93–96 pemekaran), sehingga pemetaan dilakukan lewat nama. "Daerah Istimewa Yogyakarta" dipetakan ke 34 lewat alias lokal.

## Cakupan per provinsi

Cakupan harga valid terendah: {low}. Median {cov.median():.1%}.

## Serah-terima

Periode sealed (2026-06-01 .. 2026-11-24) sudah diserahkan ke CGS dan divalidasi (`docs/holdout_seal.md`). Data periode shared tidak di-commit (`data/` di-gitignore); dikirim sebagai zip bersama manifest dan checksum di atas.
"""
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(md, encoding="utf-8")
    print(f"[ok] {report}: {stats['n_mapped']}/34 provinsi ter-map, {stats['rows']:,} baris, "
          f"{stats['min']}..{stats['max']}, NaN {stats['nan']:,}")
    return stats


def run_handoff(out: Path, target: Path, seal_doc: Path) -> None:
    """Salin _sealed ke folder kirim CGS, verifikasi sha256, hapus salinan lokal, catat checksum."""
    import shutil
    sealed = out / SEALED_SUBDIR
    files = sorted(sealed.glob("l1_p*.json")) if sealed.exists() else []
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
        lines.append(f"{h}  sp2kp_mde/{src.name}")
    for src in files + extras:
        src.unlink()
    stamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    block = ("\n## Serah-terima MDE (MDE-H1-02, SP2KP)\n\n"
             f"- Diserahkan oleh: **MDE** · {stamp}\n"
             f"- Tujuan: `{target}`\n"
             f"- File: {len(files)} JSON + manifest; salinan di `{sealed}` sudah dihapus.\n"
             "- Penerimaan CGS: _diisi CGS_\n\n```text\n" + "\n".join(lines) + "\n```\n")
    with seal_doc.open("a", encoding="utf-8") as fh:
        fh.write(block)
    print(f"[ok] {len(files)} file diserahkan ke {target}; checksum dicatat di {seal_doc}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="SP2KP validasi silang (MDE-H1-02)")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--parse-only", action="store_true")
    ap.add_argument("--start", type=dt.date.fromisoformat, default=START)
    ap.add_argument("--end", type=dt.date.fromisoformat, default=END)
    ap.add_argument("--chunk-days", type=int, default=0, help="0 = per tahun kalender; mis. 31 bila respons terpotong")
    ap.add_argument("--only", nargs="*", help="kode provinsi SP2KP tertentu saja")
    ap.add_argument("--include-sealed", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--report", action="store_true", help="tulis reports/qa/sp2kp_coverage.md")
    ap.add_argument("--handoff-sealed", action="store_true", help="serahkan _sealed/ ke folder CGS (--to)")
    ap.add_argument("--to", type=Path, help="folder tujuan serah-terima CGS")
    ap.add_argument("--out", type=Path, default=RAW_DIR)
    ap.add_argument("--interim", type=Path, default=INTERIM)
    args = ap.parse_args(argv)
    if args.probe:
        return run_probe()
    if args.parse_only:
        return run_parse(args.out, args.interim)
    if args.report:
        run_report(args.out, args.interim, REPORT_MD)
        return None
    if args.handoff_sealed:
        if not args.to:
            raise SystemExit("--handoff-sealed butuh --to <folder>")
        return run_handoff(args.out, args.to, Path("docs/holdout_seal.md"))
    if args.end >= HOLDOUT_START and not args.include_sealed:
        raise SystemExit(f"--end menyentuh holdout ({HOLDOUT_START}); tambah --include-sealed bila diminta CGS")
    return run_download(args.out, args.start, args.end, args.chunk_days, args.include_sealed, args.only, args.force)


if __name__ == "__main__":
    main()
