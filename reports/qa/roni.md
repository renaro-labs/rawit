# CGS-H1-02 - RONI resmi + vintage

> **H3-02 seal (2026-11-23; corrected 2026-11-25):** shared `roni.csv` and
> `roni.parquet` contain **915 seasons**, DJF 1950 .. FMA 2026. The six seasons
> after FMA 2026 and the raw 2026 snapshots are in `RENARO_SEALED_DIR`; no
> holdout values are shown here.

- Sumber: NOAA CPC `RONI.ascii.txt` (ERSSTv6, base 1991-2020), diunduh 2026-11-22.
- Cakupan shared: **915 musim**, DJF 1950 .. FMA 2026.
- Aturan `available_at`: tidak ada arsip vintage historis -> lag konservatif +3 bulan dari center month; `available_at = awal bulan (center_month + 3)`.
- Nilai RONI dapat direvisi ~2 bulan; 2-3 musim terakhir bersifat provisional.

## Episode ENSO 2017-2026 (aturan NOAA: |RONI| >= 0.5 selama >= 5 musim berturut-turut)

| episode | fase | musim | n | RONI min | RONI max |
|---|---|---|---:|---:|---:|
| `lanina_2016_17` | lanina | 2016-2017 | 7 | -0.96 | -0.60 |
| `lanina_2017_18` | lanina | 2017-2018 | 8 | -1.14 | -0.62 |
| `elnino_2018_19` | elnino | 2018-2019 | 7 | +0.53 | +0.82 |
| `lanina_2020_23` | lanina | 2020-2023 | 35 | -1.46 | -0.55 |
| `elnino_2023_24` | elnino | 2023-2024 | 8 | +0.54 | +1.42 |
| `lanina_2024_25` | lanina | 2024-2025 | 9 | -1.10 | -0.50 |
| `lanina_2025_26` | lanina | 2025-2026 | 7 | -1.04 | -0.59 |

Daftar lengkap episode 1950-2026 disimpan di `RENARO_SEALED_DIR`; tabel di atas hanya memuat episode yang seluruhnya berada di shared.

## Status El Nino 2018-2019

**Ya.** RONI >= +0,5 selama 7 musim berturut-turut: SON 2018 (+0.62), OND 2018 (+0.82), NDJ 2018 (+0.78), DJF 2019 (+0.68), JFM 2019 (+0.64), FMA 2019 (+0.57), MAM 2019 (+0.53). Ini memenuhi ambang >= 5 musim, sehingga 2018-19 dihitung sebagai episode El Nino.

## Perbandingan dengan `enso_index (1).csv`

- Overlap shared: **915 musim** (subset dari 921 musim pre-seal).
- Pre-seal: selisih absolut maksimum 0.000000 derajat C; exact matches 921/921.
- File rinci `roni_vs_reference.csv` dan 6 musim holdout ada di `RENARO_SEALED_DIR`; tidak ditampilkan di shared.
- Untuk subset shared, `roni.csv` dan `roni.parquet` identik (max abs diff 0.0).

## Catatan 2026

- Musim setelah FMA 2026 tersegel dan tidak dianalisis di shared; status episode belum ditetapkan.
- Jangan memberi label El Nino dari musim yang belum memenuhi aturan 5 musim; evaluasi holdout hanya di Gate 2.

## DoD

- [x] Daftar episode ENSO 2018-2025/26 (shared) tertulis.
- [x] Aturan `available_at` ditetapkan (lag konservatif +3 bulan).
- [x] Status El Nino 2018-19 dijawab eksplisit.
- [x] `roni.csv` dan `roni.parquet` shared sama-sama 915 baris; tidak ada `center_month >= 4` untuk 2026.
