# CGS-H1-02 - RONI resmi + vintage

> **H3-02 seal (2026-11-23):** shared `roni.csv` now ends at FMA 2026
> (915 seasons). MAM-ASO 2026 (6 seasons) and the raw 2026 snapshots
> (`roni_raw_20261122.txt`, `roni_episodes.csv`, `comparison_summary.json`,
> `roni_vs_reference.csv`) are in `RENARO_SEALED_DIR`. The 921-season numbers
> below are the pre-seal H1 QA record.

- Sumber: NOAA CPC `RONI.ascii.txt` (ERSSTv6, base 1991-2020), diunduh 2026-11-22.
- Cakupan: 921 musim, DJF 1950 .. ASO 2026.
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

Daftar lengkap episode 1950-2026 ada di `roni_episodes.csv`.

## Status El Nino 2018-2019

**Ya.** RONI >= +0,5 selama 7 musim berturut-turut: SON 2018 (+0.62), OND 2018 (+0.82), NDJ 2018 (+0.78), DJF 2019 (+0.68), JFM 2019 (+0.64), FMA 2019 (+0.57), MAM 2019 (+0.53). Ini memenuhi ambang >= 5 musim, sehingga 2018-19 dihitung sebagai episode El Nino.

## Perbandingan dengan `enso_index (1).csv`

- Overlap: 921 musim.
- Selisih absolut maksimum: 0.000000 derajat C; exact matches: 921/921.
- Kesesuaian fase: 921/921; tidak ada perbedaan label fase pada musim overlap.
- File rinci: `roni_vs_reference.csv`.

## Catatan 2026

- Musim terakhir: ASO 2026 = +1.97. Nilai naik cepat, tetapi belum memenuhi 5 musim berturut-turut; label episode belum diberikan.
- Warming 2026 harus dipantau; jangan memberi label El Nino hanya dari 1-2 musim.

## DoD

- [x] Daftar episode ENSO 2018-2026 menurut RONI tertulis.
- [x] Aturan `available_at` ditetapkan (lag konservatif +3 bulan).
- [x] Status El Nino 2018-19 dijawab eksplisit.
