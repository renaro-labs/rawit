# Kalender (MDE-H2-02)

- Output: `data/interim/calendar.csv`, 3,652 hari, 2017-01-01 .. 2026-12-31, tanpa celah (DoD 2017-09-01 .. 2026-12-31 tercakup).
- Kode: `src/renaro/data/calendar.py` (`python -m renaro.data.calendar`). Sumber manual: `data/ref/religious_dates.csv` (setiap Idulfitri punya `source_url`), `data/ref/cuti_bersama.csv` (69 hari cuti bersama 2017–2026, versi final setelah revisi SKB).
- Kolom kontrak `calendar` + 2 kolom bantu: `is_post_lebaran` (Idulfitri s/d +10 hari kalender, jendela flag MDE-H2-01) dan `workday_source`.
- `available_at` tidak diperlukan: semua tanggal diketahui di muka (SKB terbit ±1 tahun sebelumnya; tanggal hari raya via sidang isbat).

## Tanggal hari raya resmi

| Tahun | 1 Ramadan | Idulfitri | Iduladha | Catatan |
|---|---|---|---|---|
| 2017 | 2017-05-27 | 2017-06-25 | 2017-09-01 | Idulfitri: sidang isbat 24 Jun 2017 |
| 2018 | 2018-05-17 | 2018-06-15 | 2018-08-22 | Idulfitri 15-16 Jun (SKB perubahan 18 Apr 2018) |
| 2019 | 2019-05-06 | 2019-06-05 | 2019-08-11 | Idulfitri 5-6 Jun (SKB 617/2018) |
| 2020 | 2020-04-24 | 2020-05-24 | 2020-07-31 | Idulfitri: sidang isbat 22 Mei 2020 |
| 2021 | 2021-04-13 | 2021-05-13 | 2021-07-20 | SKB 712/2021 |
| 2022 | 2022-04-03 | 2022-05-02 | 2022-07-10 | Iduladha: SKB menulis 9 Jul; sidang isbat 29 Jun 2022 menetapkan 10 Jul (dipakai) |
| 2023 | 2023-03-23 | 2023-04-22 | 2023-06-29 | Iduladha 29 Jun (SKB perubahan kedua 2023) |
| 2024 | 2024-03-12 | 2024-04-10 | 2024-06-17 | SKB 855/2023 |
| 2025 | 2025-03-01 | 2025-03-31 | 2025-06-06 | SKB 1017/2024 |
| 2026 | 2026-02-19 | 2026-03-21 | 2026-05-27 | Idulfitri: sidang isbat 19 Mar 2026 |
| 2027 | - | 2027-03-10 | 2027-05-17 | RENCANA SKB 1205/2026; hanya untuk days_to_* di akhir 2026; awal Ramadan 2027 belum ditetapkan |

## Perbandingan dengan library `holidays`

| Tahun | Item | holidays.ID() | Resmi (dipakai) |
|---|---|---|---|
| - | tidak ada perbedaan | | |

Tanggal cuti bersama yang juga tercantum sebagai libur di `holidays`: tidak ada. Library `holidays` tidak memuat cuti bersama, sehingga kolom `is_cuti_bersama` sepenuhnya dari SKB.

## Hari kerja PIHPS

- 3,253 tanggal diisi dari data PIHPS (≥ 50% provinsi melapor), 399 tanggal dari aturan Senin–Jumat bukan libur nasional (sebelum data PIHPS, periode holdout, dan masa depan; data holdout tidak dibuka).
- Kecocokan aturan dengan data PIHPS pada rentang yang ada datanya: 98.2%.
- PIHPS tetap melapor pada 47 dari 62 hari cuti bersama (Senin–Jumat) dan 44 dari 111 libur nasional (Senin–Jumat). Karena itu cuti bersama tidak dianggap hari libur PIHPS.
