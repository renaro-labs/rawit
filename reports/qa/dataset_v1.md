# QA — dataset v1 (`MDE-H3-01`)

_Dibuat otomatis oleh `python scripts/build_dataset.py`. Kode: `src/renaro/data/dataset_v1.py`._

## Ringkasan

| Item | Nilai |
|---|---|
| Folder | `data/processed/dataset_v1/` |
| Versi / commit kode | `v1` / `74a694b` |
| Rentang tanggal | 2017-07-03 .. 2026-05-29 (diminta 2017-07-01 .. 2026-05-31) |
| Hari kerja PIHPS | 2,242 |
| Baris panel | 76,228 (= 2,242 × 34), 36 kolom |
| Target teramati | 74,929 / 76,228 (98.3%); sisanya NaN, tidak diimputasi |
| Node include | 34/34 |
| content_hash panel | `fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de` |
| content_hash target | `82ae4682f0a68e6f3b13446774c1e0e9c947b243544fbc902f91443c3f64c624` |
| content_hash nodes | `f09b2776026f77813619c8e5ee1f7d95f8c6d79ce04a1546e66922142981e47a` |
| sha256 bps_mask (bytes) | `c3719e4e79f1156d8f32ae5d92f4f061a2e06cfdeee6013c4a60634cde817226` |
| Iklim | data/interim/climate_features.parquet |
| Lib | python 3.14.0, pandas 3.1.1, numpy 2.4.3, pyarrow 26.0.1 |

Reproduksi: `content_hash` (hash isi setelah sort, `renaro.contract.content_hash`) sama di pandas 2.3 / 3.0 / 3.1; byte parquet boleh berbeda antar versi pyarrow. Cek `SHA256SUMS` untuk file yang dikirim.

## Uji kebocoran

**SEMUA LULUS ✅** — sama dengan `tests/test_no_leakage.py`.

| Uji | Hasil |
|---|---|
| `avail<=date:price_lag__avail` | ✅ |
| `avail<=date:prod_price__avail` | ✅ |
| `avail<=date:climate__avail` | ✅ |
| `avail<=date:roni__avail` | ✅ |
| `max_date<holdout` | ✅ |
| `no_regime_label_cols` | ✅ |
| `truncation:T=2018-03-21` | ✅ |
| `truncation:T=2019-07-22` | ✅ |
| `truncation:T=2022-05-10` | ✅ |
| `truncation:T=2025-03-13` | ✅ |

Catatan uji:
- `*__avail` = `available_at` baris sumber yang dipakai merge_asof (harga t1, produsen t4, iklim, RONI); harus ≤ `date`.
- Truncation: input (harga, iklim, RONI) dipotong di T, panel dibangun ulang, semua kolom baris ≤ T identik. T acak seed 2026 + T tetap 2022-05-10.
- `price`/`is_observed` di panel = observasi **hari itu** (kontrak §2.7; loader MLE menggeser 1 hari kerja). Bukan kolom fitur as-of; fitur harga yang aman: `price_lag1`, `price_logret*`, `price_logmean20`, `price_logstd20`.

## Missing per fitur

Matriks lengkap fitur × provinsi: [`dataset_v1_missing.csv`](dataset_v1_missing.csv).

| Fitur | % missing (semua) | Provinsi terburuk |
|---|---:|---|
| `price` | 1.70 | Maluku Utara (4.2%) |
| `is_observed` | 0.00 | — |
| `price_lag1` | 0.28 | DI Yogyakarta (3.0%) |
| `price_obs_date` | 0.28 | DI Yogyakarta (3.0%) |
| `price_logret5` | 0.52 | DI Yogyakarta (3.3%) |
| `price_logret20` | 1.24 | DI Yogyakarta (4.0%) |
| `price_logmean20` | 0.73 | DI Yogyakarta (3.4%) |
| `price_logstd20` | 0.73 | DI Yogyakarta (3.4%) |
| `prod_price_lag1` | 23.78 | DKI Jakarta (100.0%) |
| `prod_price_obs_date` | 23.78 | DKI Jakarta (100.0%) |
| `rain_mm` | 0.00 | — |
| `rain_pentad_mm` | 0.00 | — |
| `rain_pentad_anom` | 0.00 | — |
| `rain_30d_anom` | 4.28 | Aceh (4.3%) |
| `dry_spell_days` | 0.00 | — |
| `extreme_5d` | 0.00 | — |
| `climate_pentad_date` | 0.00 | — |
| `roni` | 0.00 | — |
| `roni_delta` | 0.00 | — |
| `roni_season_month` | 0.00 | — |
| `is_holiday` | 0.00 | — |
| `is_cuti_bersama` | 0.00 | — |
| `is_ramadan` | 0.00 | — |
| `days_to_lebaran` | 0.00 | — |
| `days_to_iduladha` | 0.00 | — |
| `is_natal_tahunbaru` | 0.00 | — |
| `is_post_lebaran` | 0.00 | — |
| `dow` | 0.00 | — |
| `month` | 0.00 | — |
| `doy` | 0.00 | — |

### % missing fitur kunci per provinsi

| Kode | Provinsi | price | price_lag1 | price_logret20 | prod_price_lag1 | rain_pentad_anom | rain_30d_anom | dry_spell_days | extreme_5d | roni |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 11 | Aceh | 1.8 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 12 | Sumatera Utara | 1.3 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 13 | Sumatera Barat | 1.5 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 14 | Riau | 1.0 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 15 | Jambi | 2.6 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 16 | Sumatera Selatan | 2.1 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 17 | Bengkulu | 1.0 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 18 | Lampung | 1.4 | 0.1 | 1.0 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 19 | Kepulauan Bangka Belitung | 1.0 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 21 | Kepulauan Riau | 1.5 | 0.5 | 1.3 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 31 | DKI Jakarta | 1.6 | 0.3 | 1.2 | 100.0 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 32 | Jawa Barat | 0.8 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 33 | Jawa Tengah | 0.8 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 34 | DI Yogyakarta | 3.9 | 3.0 | 4.0 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 35 | Jawa Timur | 0.7 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 36 | Banten | 1.0 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 51 | Bali | 1.8 | 0.0 | 0.9 | 100.0 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 52 | Nusa Tenggara Barat | 1.0 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 53 | Nusa Tenggara Timur | 3.6 | 1.4 | 3.5 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 61 | Kalimantan Barat | 2.5 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 62 | Kalimantan Tengah | 2.0 | 0.1 | 1.0 | 23.6 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 63 | Kalimantan Selatan | 0.8 | 0.0 | 1.0 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 64 | Kalimantan Timur | 2.0 | 0.4 | 1.6 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 65 | Kalimantan Utara | 1.2 | 0.0 | 1.0 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 71 | Sulawesi Utara | 2.3 | 0.0 | 1.0 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 72 | Sulawesi Tengah | 1.5 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 73 | Sulawesi Selatan | 1.3 | 0.1 | 1.1 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 74 | Sulawesi Tenggara | 1.5 | 0.2 | 1.1 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 75 | Gorontalo | 1.2 | 0.0 | 1.1 | 24.4 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 76 | Sulawesi Barat | 1.6 | 0.3 | 1.2 | 17.3 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 81 | Maluku | 2.8 | 0.5 | 1.4 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 82 | Maluku Utara | 4.2 | 1.5 | 2.6 | 82.3 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 91 | Papua Barat | 1.3 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |
| 94 | Papua | 1.4 | 0.0 | 0.9 | 16.5 | 0.0 | 4.3 | 0.0 | 0.0 | 0.0 |

Penyebab missing yang diketahui: `price` = hari tanpa laporan PIHPS / spike dibuang cleaning; `price_logret20` = 20 observasi pertama; `prod_price_lag1` = provinsi tanpa harga produsen (tipe 4, mis. DKI) atau sebelum 2019; `rain_30d_anom` = jendela 30 hari tanpa baseline lengkap (CGS-H2-02, sedang dikonfirmasi CGS).

## Node

Kriteria: cakupan ≥ 90% pada ≥ 5 tahun dalam 2018–2025 (`reports/qa/coverage_pihps.csv`, MDE-H1-03).

| Kode | Provinsi | Tahun lolos | include |
|---|---|---:|:---:|
| 11 | Aceh | 8 | ✅ |
| 12 | Sumatera Utara | 8 | ✅ |
| 13 | Sumatera Barat | 8 | ✅ |
| 14 | Riau | 8 | ✅ |
| 15 | Jambi | 8 | ✅ |
| 16 | Sumatera Selatan | 8 | ✅ |
| 17 | Bengkulu | 8 | ✅ |
| 18 | Lampung | 8 | ✅ |
| 19 | Kepulauan Bangka Belitung | 8 | ✅ |
| 21 | Kepulauan Riau | 8 | ✅ |
| 31 | DKI Jakarta | 8 | ✅ |
| 32 | Jawa Barat | 8 | ✅ |
| 33 | Jawa Tengah | 8 | ✅ |
| 34 | DI Yogyakarta | 8 | ✅ |
| 35 | Jawa Timur | 8 | ✅ |
| 36 | Banten | 8 | ✅ |
| 51 | Bali | 8 | ✅ |
| 52 | Nusa Tenggara Barat | 8 | ✅ |
| 53 | Nusa Tenggara Timur | 8 | ✅ |
| 61 | Kalimantan Barat | 8 | ✅ |
| 62 | Kalimantan Tengah | 8 | ✅ |
| 63 | Kalimantan Selatan | 8 | ✅ |
| 64 | Kalimantan Timur | 8 | ✅ |
| 65 | Kalimantan Utara | 8 | ✅ |
| 71 | Sulawesi Utara | 8 | ✅ |
| 72 | Sulawesi Tengah | 8 | ✅ |
| 73 | Sulawesi Selatan | 8 | ✅ |
| 74 | Sulawesi Tenggara | 8 | ✅ |
| 75 | Gorontalo | 8 | ✅ |
| 76 | Sulawesi Barat | 8 | ✅ |
| 81 | Maluku | 8 | ✅ |
| 82 | Maluku Utara | 8 | ✅ |
| 91 | Papua Barat | 8 | ✅ |
| 94 | Papua | 8 | ✅ |

## Input

| Input | sha256 |
|---|---|
| prices (`data/interim/prices_clean.parquet`) | `145fca2110a029f7…` |
| calendar (`data/interim/calendar.csv`) | `068081699ea814b0…` |
| climate (`data/interim/climate_features.parquet`) | `a99f20dc60046bf9…` |
| roni (`data/interim/roni.parquet`) | `1b6551b5cc764c6b…` |
| provinces (`data/ref/provinces.csv`) | `fee67ff62a8aab71…` |
| mask (`data/interim/bps_mask.npy`) | `846ec6174353c1e8…` |
| coverage (`reports/qa/coverage_pihps.csv`) | `b42365a46b944420…` |

## Keputusan desain (konfirmasi MLE/RL)

1. `target.parquet` = grid penuh tanggal × 34 (`is_observed=False` bila kosong) karena loader MLE mewajibkan grid lengkap.
2. Flag cleaning (outlier/carry-forward/post-Lebaran) **tidak** masuk target: loader MLE akan membuang target berflag, padahal perlakuannya keputusan terbuka RL (MDE-H2-01).
3. Iklim varian `final_sat` (Opsi B, lag 2 hari, `availability.csv`). RONI nasional, kolom fase/episode dibuang.
4. Label regime tidak pernah masuk panel.

## Tanda tangan QA

| Peran | Nama | Bagian | Status | Tanggal |
|---|---|---|---|---|
| MDE | Dio | harga, kalender, mask, merge, uji bocor | ✅ ditandatangani | 2026-11-25 |
| CGS | ______ | iklim (`available_at`, join pentad, RONI) | ☐ menunggu | |
