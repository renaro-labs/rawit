# SP2KP — hasil tarikan periode shared (MDE-H1-02)

- Sumber: `data/raw/sp2kp/manifest.csv`, `data/interim/sp2kp_long.parquet`; dibuat oleh `python -m renaro.data.sp2kp --report`
- Endpoint: `export-area-daily-json` (lihat `docs/sources/sp2kp_endpoint.md`), variant 2 = Cabai Merah Keriting, level provinsi
- **Peran data: hanya validasi silang di MDE-H2-01. Tidak dipakai sebagai fitur atau target** (tidak masuk `panel.parquet`/`target.parquet`).

## Kesimpulan DoD

**34 dari 34 provinsi kontrak ter-map ke kode BPS (DoD ≥ 30: terpenuhi).**

## Angka

| Item | Nilai |
|---|---|
| Provinsi di master SP2KP | 38 |
| Provinsi sumber yang punya data | 38 |
| Provinsi kontrak (kode BPS lama) ter-map | 34 / 34 |
| File mentah (manifest) | 114 (114 dengan HTTP 200) |
| Baris `sp2kp_long.parquet` | 20,638 (= 34 provinsi × 607 hari kerja) |
| Rentang tanggal | 2024-02-01 .. 2026-05-29 (< holdout 2026-06-01) |
| Harga NaN (`harga` 0/kosong, terutama libur nasional & cuti bersama) | 1,853 (9.0%) |
| SHA256 `data/raw/sp2kp/manifest.csv` | `66c7a992cd7b6afc44a2786e379c5a6bca81df31278ddd9f525c472206c8fb5d` |
| SHA256 `data/interim/sp2kp_long.parquet` | `48006f676b7ff022883cdcb76b091d8eee71ef6d66958a82e7c89aff9a5305cd` |

## Provinsi pemekaran yang diagregasi (rata-rata sederhana, `is_aggregated=True`)

| Kode kontrak | Provinsi sumber SP2KP | Jumlah |
|---|---|---:|
| 91 | Papua Barat, Papua Barat Daya | 2 |
| 94 | Papua, Papua Pegunungan, Papua Selatan, Papua Tengah | 4 |

Kode SP2KP memakai Kemendagri (91 Papua, 92 Papua Barat, 93–96 pemekaran), sehingga pemetaan dilakukan lewat nama. "Daerah Istimewa Yogyakarta" dipetakan ke 34 lewat alias lokal.

## Cakupan per provinsi

Cakupan harga valid terendah: 11 (90.8%), 13 (90.8%), 17 (90.8%), 16 (90.8%), 34 (90.8%). Median 90.9%.

## Serah-terima

Periode sealed (2026-06-01 .. 2026-11-24) sudah diserahkan ke CGS dan divalidasi (`docs/holdout_seal.md`). Data periode shared tidak di-commit (`data/` di-gitignore); dikirim sebagai zip bersama manifest dan checksum di atas.
