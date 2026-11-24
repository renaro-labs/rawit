# Cakupan harga PIHPS per provinsi-tahun (MDE-H1-03)

- Sumber: `data/interim/pihps_long.parquet` (tipe 1, pasar tradisional, Cabai Merah Keriting), dibuat oleh `src/renaro/data/coverage.py`
- Rentang data: 2017-07-03 .. 2026-05-29 (< holdout 2026-06-01)
- Definisi hari kerja PIHPS: tanggal dengan harga valid dari ≥ 50% dari 34 provinsi (≥ 17). Total 2242 hari kerja.
- Laporan = harga valid; nilai "-" tidak dihitung. Baris di luar 34 provinsi kontrak dibuang: ['Dum'].
- Kriteria Gate 1 (brief §10.1): cakupan ≥ 90% pada ≥ 5 tahun dalam 2018–2025; ambang 20 provinsi.

## Kesimpulan

**34 dari 34 provinsi memenuhi kriteria data Gate 1 (ambang 20).** Data memenuhi syarat Gate 1.

Versi ketat (≥ 90% di **semua** 8 tahun 2018–2025): 34 dari 34 provinsi.

## Provinsi yang gagal

Tidak ada provinsi yang gagal.

## Cakupan (%) per provinsi-tahun, 2018–2025

| Kode | Provinsi | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Tahun ≥90% | Lolos |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 11 | Aceh | 100.0 | 99.6 | 100.0 | 100.0 | 100.0 | 98.8 | 100.0 | 100.0 | 8/8 | ✓ |
| 12 | Sumatera Utara | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 8/8 | ✓ |
| 13 | Sumatera Barat | 100.0 | 99.6 | 100.0 | 100.0 | 100.0 | 95.7 | 96.9 | 99.6 | 8/8 | ✓ |
| 14 | Riau | 100.0 | 99.6 | 100.0 | 100.0 | 100.0 | 98.8 | 99.2 | 99.6 | 8/8 | ✓ |
| 15 | Jambi | 100.0 | 99.6 | 100.0 | 100.0 | 100.0 | 93.0 | 100.0 | 100.0 | 8/8 | ✓ |
| 16 | Sumatera Selatan | 98.8 | 100.0 | 100.0 | 99.6 | 100.0 | 94.6 | 98.9 | 100.0 | 8/8 | ✓ |
| 17 | Bengkulu | 100.0 | 99.6 | 100.0 | 100.0 | 100.0 | 99.2 | 97.3 | 100.0 | 8/8 | ✓ |
| 18 | Lampung | 100.0 | 99.6 | 100.0 | 100.0 | 100.0 | 100.0 | 99.2 | 100.0 | 8/8 | ✓ |
| 19 | Kepulauan Bangka Belitung | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 97.3 | 100.0 | 99.6 | 8/8 | ✓ |
| 21 | Kepulauan Riau | 100.0 | 99.6 | 100.0 | 98.8 | 99.6 | 99.2 | 97.7 | 99.6 | 8/8 | ✓ |
| 31 | DKI Jakarta | 98.8 | 99.2 | 100.0 | 100.0 | 100.0 | 99.2 | 98.9 | 99.6 | 8/8 | ✓ |
| 32 | Jawa Barat | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 8/8 | ✓ |
| 33 | Jawa Tengah | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 8/8 | ✓ |
| 34 | DI Yogyakarta | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 99.6 | 100.0 | 8/8 | ✓ |
| 35 | Jawa Timur | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 8/8 | ✓ |
| 36 | Banten | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 99.6 | 100.0 | 99.2 | 8/8 | ✓ |
| 51 | Bali | 98.8 | 96.8 | 97.9 | 99.6 | 100.0 | 99.6 | 100.0 | 100.0 | 8/8 | ✓ |
| 52 | Nusa Tenggara Barat | 99.6 | 99.2 | 100.0 | 100.0 | 100.0 | 99.6 | 100.0 | 100.0 | 8/8 | ✓ |
| 53 | Nusa Tenggara Timur | 100.0 | 99.6 | 99.6 | 100.0 | 99.6 | 98.1 | 99.6 | 100.0 | 8/8 | ✓ |
| 61 | Kalimantan Barat | 98.4 | 99.6 | 100.0 | 100.0 | 100.0 | 98.8 | 96.6 | 98.9 | 8/8 | ✓ |
| 62 | Kalimantan Tengah | 98.0 | 99.6 | 100.0 | 100.0 | 100.0 | 98.4 | 98.9 | 99.2 | 8/8 | ✓ |
| 63 | Kalimantan Selatan | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 99.6 | 99.6 | 100.0 | 8/8 | ✓ |
| 64 | Kalimantan Timur | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 96.5 | 99.2 | 100.0 | 8/8 | ✓ |
| 65 | Kalimantan Utara | 100.0 | 100.0 | 100.0 | 98.0 | 100.0 | 96.9 | 98.5 | 100.0 | 8/8 | ✓ |
| 71 | Sulawesi Utara | 97.6 | 98.4 | 100.0 | 99.6 | 100.0 | 99.6 | 100.0 | 100.0 | 8/8 | ✓ |
| 72 | Sulawesi Tengah | 98.4 | 99.6 | 100.0 | 99.6 | 100.0 | 99.6 | 98.9 | 99.2 | 8/8 | ✓ |
| 73 | Sulawesi Selatan | 100.0 | 97.6 | 98.3 | 100.0 | 100.0 | 100.0 | 98.9 | 100.0 | 8/8 | ✓ |
| 74 | Sulawesi Tenggara | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 99.6 | 100.0 | 8/8 | ✓ |
| 75 | Gorontalo | 100.0 | 100.0 | 100.0 | 100.0 | 99.6 | 100.0 | 100.0 | 100.0 | 8/8 | ✓ |
| 76 | Sulawesi Barat | 99.2 | 100.0 | 100.0 | 100.0 | 100.0 | 99.6 | 99.6 | 100.0 | 8/8 | ✓ |
| 81 | Maluku | 100.0 | 98.0 | 100.0 | 100.0 | 100.0 | 98.4 | 97.3 | 99.2 | 8/8 | ✓ |
| 82 | Maluku Utara | 98.8 | 100.0 | 100.0 | 100.0 | 99.6 | 100.0 | 97.3 | 96.9 | 8/8 | ✓ |
| 91 | Papua Barat | 100.0 | 99.6 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 8/8 | ✓ |
| 94 | Papua | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 98.8 | 98.5 | 100.0 | 8/8 | ✓ |

Lima sel terendah: 15 Jambi 2023 (93.0%, gap 5), 16 Sumatera Selatan 2023 (94.6%, gap 5), 13 Sumatera Barat 2023 (95.7%, gap 2), 64 Kalimantan Timur 2023 (96.5%, gap 5), 61 Kalimantan Barat 2024 (96.6%, gap 1).

## Catatan 2017 (periode pemanasan lag, Jul–Des)

Provinsi di bawah 90% pada Jul–Des 2017 (tidak memengaruhi Gate 1; relevan untuk jendela lag 60 hari kerja di awal 2018):

- 34 DI Yogyakarta: 46.0%, gap terpanjang 67 hari kerja, laporan pertama 2017-10-09
- 53 Nusa Tenggara Timur: 54.8%, gap terpanjang 31 hari kerja, laporan pertama 2017-08-15
- 82 Maluku Utara: 62.1%, gap terpanjang 32 hari kerja, laporan pertama 2017-08-16
- 62 Kalimantan Tengah: 87.9%, gap terpanjang 2 hari kerja, laporan pertama 2017-07-04
- 64 Kalimantan Timur: 89.5%, gap terpanjang 8 hari kerja, laporan pertama 2017-07-13

Hari kerja PIHPS per tahun: 2017: 124, 2018: 245, 2019: 249, 2020: 242, 2021: 248, 2022: 246, 2023: 258, 2024: 262, 2025: 261, 2026: 107. Tahun 2017 (mulai Juli) dan 2026 (s/d Mei) parsial; keduanya ada di CSV tetapi tidak dihitung untuk Gate 1.

Heatmap: `reports/qa/coverage_heatmap.png`. Angka lengkap tanpa pembulatan: `reports/qa/coverage_pihps.csv`.
