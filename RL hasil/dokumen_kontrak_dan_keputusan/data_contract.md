# Data Contract v1.0 (Sprint 1 â€” Terkunci pada ALL-H1-01)

- **Status**: **DISAHKAN v1.0** (`2026-11-23`)
- **Persetujuan 4 Peran**:
  - **RL (*Research Lead*)**: `OK â€” 2026-11-23`
  - **MDE (*Market Data Engineer*)**: `OK â€” 2026-11-23`
  - **CGS (*Climate & Geospatial Scientist*)**: `OK â€” 2026-11-23`
  - **MLE (*ML/Graph Modeling Engineer*)**: `OK â€” 2026-11-23`
- **Validator Kode**: `src/renaro/contract.py` (`TABLE_COLUMNS`, `PRIMARY_KEYS`, `check_columns`, `check_unique`, `assert_before_holdout`, `assert_available`)
- **Keputusan Terkait**: `docs/decisions/ALL-H1-01.md`, `configs/global.yaml`

---

## 1. Aturan Emas & Konvensi Global

1. **Resolusi & Format Waktu**: Tanggal berformat ISO `YYYY-MM-DD` (zona waktu WIB, tanpa komponen jam). Hari kerja mengacu pada hari perdagangan PIHPS (Seninâ€“Jumat).
2. **Identitas Node (`prov_code`)**: 34 provinsi Indonesia struktur lama (pra-pemekaran Papua 2022) menggunakan **kode BPS 2 digit (`"11"` s/d `"94"`)** sesuai urutan tetap `PROVINCES` (`0..33`) di `src/renaro/contract.py` dan `data/ref/provinces.csv`.
3. **Anti-Bocor Waktu (`available_at`)**: Setiap tabel fitur wajib memiliki kolom `available_at`. Pada tanggal keputusan $t$, loader hanya boleh memakai baris dengan **`available_at <= t`** (*as-of join*). Revisi/vintage disimpan sebagai baris tambahan dengan `available_at` lebih baru, tidak pernah menimpa nilai lama.
4. **Segel Holdout (`holdout_start = 2026-06-01`)**: Seluruh data dengan `date >= 2026-06-01` disegel oleh CGS (`CGS-H3-02`). Loader wajib memanggil `assert_before_holdout()` dan memotong semua baris $\ge$ `2026-06-01` kecuali saat unseal resmi Gate 3 (`CGS-H6-01`).
5. **Isolasi Label Rezim (`regime_labels`)**: Tabel `regime_labels` adalah **EVAL ONLY** â€” dilarang keras dimasukkan ke `panel.parquet` atau fitur model mana pun.
6. **Orientasi Matriks Graph (`A[i, j]`)**: Pada array `bps_mask.npy` dan seluruh `graph_priors/*.npy` (`34x34`), **`A[i, j]` menyatakan pengaruh dari provinsi asal/pemasok `j` ke provinsi tujuan/pembeli `i`** (`baris = tujuan i`, `kolom = asal j`).

---

## 2. Spesifikasi Tabel per Tabel (`TABLE_COLUMNS` & `PRIMARY_KEYS`)

### 2.1 `prices_clean` (`data/interim/prices_clean.parquet` â€” Pemilik: MDE)
- **Primary Key**: `(date, prov_code, commodity, price_type)`
- **Aturan `available_at`**: Hari kerja berikutnya setelah tanggal observasi (`next_workday`, `lag_days = 1`; harga hari $t$ dipakai mulai $t+1$).

| Kolom | Tipe | Unit | Keterangan |
| :--- | :--- | :--- | :--- |
| `date` | `date` | hari kerja | Tanggal observasi harga PIHPS/SP2KP |
| `prov_code` | `str` | kode BPS 2 digit | `"11"` .. `"94"` (34 provinsi) |
| `commodity` | `str` | â€” | `"cabai_merah_keriting"` |
| `price_type` | `int` | â€” | `1` = pasar tradisional (target utama), `4` = produsen, `2` = SP2KP |
| `price_raw` | `float64` | Rp/kg | Harga mentah sebelum pembersihan (`NaN` bila `-`) |
| `price` | `float64` | Rp/kg | Harga bersih (`NaN` bila missing atau dianulir oleh flag outlier; **tidak diimputasi**) |
| `is_observed` | `bool` | `True/False` | `True` jika harga asli teramati dan bersih |
| `flag_outlier` | `bool` | `True/False` | Lonjakan ekstrem/MAD/jump-revert |
| `flag_post_lebaran` | `bool` | `True/False` | Beku/lompatan pasca-Idulfitri |
| `flag_carry_forward` | `bool` | `True/False` | Harga stagnan beruntun (*stale run*) |
| `source` | `str` | â€” | `"pihps"`, `"sp2kp"`, `"synthetic"` |
| `available_at` | `date` | tanggal | Tanggal pertama nilai boleh dipakai sebagai fitur (`date + 1 BDay`) |

### 2.2 `calendar` (`data/interim/calendar.csv` â€” Pemilik: MDE)
- **Primary Key**: `(date,)` (semua hari kalender)
- **Aturan `available_at`**: Diketahui di muka (`known_in_advance` dari SKB 3 Menteri tahun sebelumnya).

| Kolom | Tipe | Unit | Keterangan |
| :--- | :--- | :--- | :--- |
| `date` | `date` | hari kalender | Tanggal ISO `YYYY-MM-DD` |
| `is_workday_pihps` | `bool` | `0/1` | Hari kerja Seninâ€“Jumat |
| `is_holiday` | `bool` | `0/1` | Hari libur nasional resmi SKB |
| `is_cuti_bersama` | `bool` | `0/1` | Hari cuti bersama resmi SKB |
| `is_ramadan` | `bool` | `0/1` | Bulan Ramadan |
| `days_to_lebaran` | `int` | hari | Selisih hari menuju Idulfitri berikutnya |
| `days_to_iduladha` | `int` | hari | Selisih hari menuju Iduladha berikutnya |
| `is_natal_tahunbaru` | `bool` | `0/1` | Jendela Natal & Tahun Baru (20 Des â€“ 5 Jan) |
| `dow` | `int` | `0..6` | Hari dalam minggu (`0 = Senin`) |
| `month` | `int` | `1..12` | Bulan (`1..12`) |
| `doy` | `int` | `1..366` | Hari dalam tahun (*day of year*) |

### 2.3 `climate_features` (`data/interim/climate_features.parquet` â€” Pemilik: CGS)
- **Primary Key**: `(date, prov_code, variant)`
- **Aturan `available_at`**:
  - **Utama (Opsi B)**: Akhir pentad + 2 hari kalender (`pentad_end + 2d`, menggunakan `final_sat` sebagai proksi *prelim*).
  - **Sensitivitas (Opsi A)**: Jeda rilis aktual (`prelim_sim`: `pentad_end + 5d`; `final`: `month_end + 21d`).

| Kolom | Tipe | Unit | Keterangan |
| :--- | :--- | :--- | :--- |
| `date` | `date` | tanggal | Tanggal akhir pentad / observasi |
| `prov_code` | `str` | kode BPS 2 digit | `"11"` .. `"94"` |
| `variant` | `str` | â€” | `"final_sat"` atau `"prelim_sat"` |
| `rain_mm` | `float64` | mm/hari | Hujan harian rata-rata provinsi (dibobot produksi kab/kota atau fallback uniform) |
| `rain_pentad_mm` | `float64` | mm/pentad | Akumulasi hujan 1 pentad penuh |
| `rain_pentad_anom` | `float64` | z-score | Anomali pentad terstandarisasi klimatologi periode latih |
| `rain_30d_anom` | `float64` | z-score | Anomali akumulasi 30 hari terstandarisasi klimatologi DOY periode latih |
| `dry_spell_days` | `float64` | hari / pentad | Jumlah hari/pentad kering beruntun ($< 5{,}0\text{ mm/pentad}$) |
| `extreme_5d` | `int` | `0/1` | Indikator akumulasi pentad/5-hari $> \text{p95}$ periode latih |
| `available_at` | `date` | tanggal | Tanggal ketersediaan sesuai aturan Opsi B / Opsi A |

### 2.4 `roni` (`data/interim/roni.parquet` & `data/raw/enso/roni.csv` â€” Pemilik: CGS)
- **Primary Key**: `(season, year, vintage_date)`
- **Aturan `available_at`**: Tanggal rilis vintage CPC NOAA (`vintage_date`), atau aturan konservatif tanggal 10 bulan $m+2$ (awal bulan `center_month + 3`).

| Kolom | Tipe | Unit | Keterangan |
| :--- | :--- | :--- | :--- |
| `season` | `str` | 3-bulan | `"DJF"`, `"JFM"`, ..., `"NDJ"` |
| `year` | `int` | tahun | Tahun dari bulan tengah musim (`center_month`) |
| `center_month` | `int` | `1..12` | Bulan tengah musim (`DJF` $\to 1$) |
| `roni` | `float64` | $^\circ\text{C}$ | Nilai *Relative Oceanic NiÃ±o Index* (CPC NOAA ERSSTv6) |
| `vintage_date` | `date` | tanggal | Tanggal unduh/rilis versi tabel CPC |
| `available_at` | `date` | tanggal | Tanggal pertama nilai musim ini boleh dipakai pada prediksi |

### 2.5 `regime_labels` (`data/interim/regime_labels.csv` â€” Pemilik: CGS, **EVAL ONLY**)
- **Primary Key**: `(date, prov_code)`
- **Aturan**: **Hanya untuk stratifikasi evaluasi metrik**. Tidak memiliki `available_at` karena dilarang masuk fitur model.

| Kolom | Tipe | Unit | Keterangan |
| :--- | :--- | :--- | :--- |
| `date` | `date` | hari kerja | Tanggal evaluasi |
| `prov_code` | `str` | kode BPS 2 digit | `"11"` .. `"94"` |
| `enso_phase` | `str` | kategori | `"el_nino"`, `"la_nina"`, `"neutral"` |
| `episode_id` | `str` | ID episode | Pengenal episode OOD (mis. `"el_nino_2023_2024"`) |
| `is_dry` | `bool` | `0/1` | Kekeringan ($\ge 3$ pentad beruntun $< \text{p20}$) |
| `is_extreme_rain` | `bool` | `0/1` | Hujan ekstrem ($> \text{p95}$ provinsi) |
| `is_normal` | `bool` | `0/1` | Bukan kering, bukan hujan ekstrem, dan ENSO netral |
| `label_primary` | `str` | kategori | Label rezim utama setelah aturan prioritas |

### 2.6 `bps_mask` (`data/interim/bps_mask.npy`, `bps_mask.csv`, `bps_mask_2022.csv` â€” Pemilik: MDE)
- **Sumber**: Publikasi BPS *Distribusi Perdagangan Komoditas Cabai Merah di Indonesia 2022* (terbit 2023), halaman PDF 45â€“177.
- **Format**:
  - `data/interim/bps_mask_2022.csv`: Matriks $34 \times 34$ dengan baris = pemasok (`src`), kolom = pembeli (`dst`), berisi **99 directed edges** bernilai `1` (dan halaman sumber di `bps_mask_2022_pages.csv`).
  - `data/interim/bps_mask_entry.csv` & `data/interim/bps_mask.csv`: Tabel entri panjang dengan kode BPS 2 digit (`dest_code, origin_code, share_pct, relation, page, method, entered_by`).
  - `data/interim/bps_mask.npy`: Array `uint8` ukuran `(34, 34)` sesuai urutan `PROVINCES` di `src/renaro/contract.py`, dengan **`A[i, j] = 1` bila `j -> i`** (`baris = tujuan i`, `kolom = asal j`).

### 2.7 `panel` & `target` (`data/processed/dataset_v1/` â€” Pemilik: MDE)
- **`panel` (`panel.parquet`)**: Primary Key `(date, prov_code)`, kolom wajib:
  `date, prov_code, price, is_observed, rain_pentad_anom, rain_30d_anom, dry_spell_days, extreme_5d, roni, is_ramadan, days_to_lebaran, dow, month`.
- **`target` (`target.parquet`)**: Primary Key `(date, prov_code)`, kolom wajib:
  `date, prov_code, price, is_observed` (tanpa interpolasi/imputasi).
- **Catatan Kompatibilitas Bundle Parsial (`panel_dev.parquet`)**: File `data/processed/dataset_v1/panel_dev.parquet` yang sudah ada di bundle saat ini adalah output *scaffold* prototipe (52 kolom, menggunakan `node_id` `0..33` dan nama `province`). Jembatan pemetaan lengkap `prov_code (BPS) <-> node_id (panel_dev) <-> adm1_shapeISO` tersedia di `data/ref/provinces.csv`.

### 2.8 `preds` (`experiments/runs/<run_id>/preds.parquet` â€” Pemilik: MLE)
- **Primary Key**: `(model, fold, seed, date, prov_code, h)`
- **Kolom Wajib**: `model, fold, seed, date, prov_code, h, y_true, y_pred` (`y_true` dan `y_pred` dalam satuan level harga **Rp/kg** setelah transformasi invers $\exp$).

### 2.9 `availability` (`data/interim/availability.csv` â€” Pemilik: CGS)
- **Primary Key**: `(feature_family, source, variant)`
- **Kolom Wajib**: `feature_family, source, variant, rule, lag_days, evidence, decided_by`.

