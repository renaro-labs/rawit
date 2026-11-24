# Pemetaan Lengkap Fitur Model (Wajib vs Sekunder/Support vs Non-Fitur) & Asal Dataset

Dokumen ini merangkum **seluruh fitur** dalam proyek Sprint 1 (*Climate-Conditioned Dynamic Graph Learning for Food Price Forecasting*), dikelompokkan berdasarkan:
1. **Status Prioritas**: **WAJIB INTI (*Mandatory Core*)**, **SEKUNDER / SUPPORT (*Secondary / Diagnostic*)**, atau **DILARANG MASUK FITUR (*Eval / QA Only*)**.
2. **Asal Dataset Mentah (`data/raw/` atau root)** $\to$ **Tabel Antara (`data/interim/`)** $\to$ **Tabel Final (`data/processed/dataset_v1/`)**.
3. **Padanan Nama Kolom** antara **Kontrak Resmi (`src/renaro/contract.py`)** dan **Prototipe Panel (`panel_dev.parquet` / `feature_dictionary.csv`)**.

---

## 1. FITUR WAJIB INTI (*Mandatory Core Features*)

Fitur-fitur ini **wajib ada** di `panel.parquet` (13 kolom kontrak) dan `bps_mask.npy` / `distance_km.csv` karena menjadi input langsung **Baseline (B1–B5)** dan **Modul 1 (*Climate-Conditioned Directed Lag Graph*)**:

| No | Kelompok | Nama Fitur di Kontrak (`contract.py`) | Nama Kolom di `panel_dev.parquet` | Fungsi di Model & Loss | Asal Dataset Mentah (`data/raw/` & Root) | File Interim / Processed Tujuan | Status Saat Ini |
| :-: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Kunci Panel** | `date`, `prov_code` | `date`, `province`, `node_id` | Indeks waktu ($t$, hari kerja Senin–Jumat) dan indeks simpul provinsi ($i \in \{0..33\}$, kode BPS `11..94`). | `data/raw/pihps/pihps_cabai_merah_keriting_province.csv` & `data/raw/boundaries/geoBoundaries-IDN-ADM1_simplified.geojson` | `data/ref/provinces.csv`, `data/processed/dataset_v1/nodes.csv` | **100% Siap** (34 provinsi $\times$ 2.195 hari kerja) |
| **2** | **Target & Autoregresif Harga Eceran** | `price` | `target_price` (target), `trad_price_ff` (fitur lag $t-k$) | **Target prediksi** $y_{i,t+h} = \log P_{i,t+h}^{\text{trad}}$ dan **fitur histori harga** $\mathbf{x}_{i, t-\ell:t}^{(p)}$ di pasar tradisional. | `data/raw/pihps/pihps_cabai_merah_keriting_province.csv` & `data/raw/pihps/json/pihps_pt1_2018_2026.json.gz` (PIHPS BI `price_type=1`, `com_13` Cabai Merah Keriting) | `data/interim/prices_clean.parquet`, `data/processed/dataset_v1/target.parquet` | **100% Siap** (98,87% teramati asli) |
| **3** | **Mask Observasi Target** | `is_observed` | `target_mask` (target), `trad_obs_today`, `trad_price_age_days` | **Mask evaluasi & loss**: metrik MAE/RMSE/sMAPE **hanya** boleh dihitung pada $(i, t+h)$ dengan `is_observed == True` (bukan hasil interpolasi/forward-fill). | Diturunkan langsung dari status observasi harian `data/raw/pihps/pihps_cabai_merah_keriting_province.csv` (sebelum forward-fill) + filter QA (`qa_flag_* == 0`). | `data/interim/prices_clean.parquet`, `data/processed/dataset_v1/target.parquet` | **100% Siap** |
| **4** | **Iklim Provinsi (Anomali Hujan)** | `rain_pentad_anom`, `rain_30d_anom` | `rain_pentad_last`, `rain_30d`, `rain_30d_anom_z` | **Fitur eksogen iklim $\mathbf{c}_{j,t}$** di Modul 1: anomali curah hujan pentad (5 hari) dan 30 hari terhadap klimatologi DOY 2018–2023 untuk mendeteksi guncangan pasokan di provinsi sentra $j$. | `data/raw/chirps_v3/chirps_v3_idn_{2018..2026}.npz` (UCSB CHIRPS v3.0 Daily $0.05^\circ$) + mask grid provinsi `data/raw/boundaries/chirps_grid_province34.npz` | `data/interim/climate_features.parquet` | **Bloker H2 (CGS)**: Di `panel_dev.parquet` masih 100% `NaN` karena `.npz` tahunan baru akan ditarik di H2 |
| **5** | **Iklim Provinsi (Kekeringan & Ekstrem Basah)** | `dry_spell_days`, `extreme_5d` | `dry_spell_days`, `extreme_pentads_30d` | **Fitur eksogen iklim $\mathbf{c}_{j,t}$** di Modul 1: jumlah hari berturut-turut hujan $<1\text{ mm}$ (maks 90) dan indikator/jumlah curah hujan 5-hari di atas persentil ke-95 ($P_{95}$ baseline 2018–2023). | `data/raw/chirps_v3/chirps_v3_idn_{2018..2026}.npz` + `data/raw/boundaries/chirps_grid_province34.npz` | `data/interim/climate_features.parquet` | **Bloker H2 (CGS)**: Di `panel_dev.parquet` masih 100% `NaN` |
| **6** | **Iklim Makro ENSO** | `roni` | `enso_roni` | **Fitur rezim iklim makro** di $\mathbf{c}_t$: *Relative Oceanic Niño Index* (RONI) 3-bulanan NOAA CPC dengan aturan rilis *day-10 bulan $m+1$* (0% kebocoran masa depan). | `data/raw/enso/RONI.ascii.txt` & `data/raw/enso/enso_indices_tidy.csv` (serta file seed root `enso_index (1).csv`) | `data/interim/roni.parquet` | **100% Siap & Terisi** (74.630/74.630 baris valid) |
| **7** | **Kalender Hari Raya & Musiman** | `is_ramadan`, `days_to_lebaran`, `dow`, `month` | `is_ramadan`, `days_to_idulfitri`, `dow`, `doy_sin`, `doy_cos` | **Kontrol lonjakan permintaan (*demand shock*)**: memisahkan kenaikan harga akibat Ramadan/Idulfitri & pola hari-dalam-minggu dari guncangan pasokan akibat cuaca ekstrem. | **SKB 3 Menteri (Kemenag/Kemnaker/PANRB) 2018–2026** $\to$ `data/ref/religious_dates.csv` & `data/ref/cuti_bersama.csv` | `data/interim/calendar.csv` | **100% Siap & Terisi** |
| **8** | **Struktur Graf & Prior Spasial ($s_{ij}$)** | `bps_mask` ($M_{ij}^{\text{BPS}}$), `distance_km` ($d_{ij}$) | File terpisah: `bps_mask.npy` / `edges_bps_2022.csv` & `distance_km.csv` | **Prior struktur graf berarah** di Modul 1: menentukan pasangan koridor perdagangan cabai merah $(j \to i)$ yang diizinkan aktif serta peluruhan jarak spasial antar-ibu kota provinsi. | 1) `BPS0000-distribusi_perdagangan_komoditas_cabai_merah_di_indonesia_2022.pdf` (Hal. 32–164, 34 peta alur provinsi)<br>2) `data/raw/boundaries/geoBoundaries-IDN-ADM1_simplified.geojson` (koordinat sentroid/ibu kota) | `data/interim/bps_mask_2022.csv`, `data/interim/bps_mask.npy` (99 directed edges), `data/processed/dataset_v1/distance_km.csv` | **100% Siap & Terverifikasi** |

---

## 2. FITUR SEKUNDER / SUPPORT (*Secondary / Supporting / Diagnostic Features*)

Fitur-fitur ini **sudah tersedia atau disiapkan di pipeline** sebagai fitur pengaya (*enrichment*), analisis sensitivitas, atau pendukung **Modul 2–3 (*Adaptive Graph + Reliability Gate*)**, namun **bukan syarat minimum Gate 1 / Kontrak 13 Kolom**:

| No | Kelompok | Nama Fitur / File | Fungsi Pendukung / Kenapa Berstatus Sekunder | Asal Dataset Mentah (`data/raw/` & Root) | File Interim / Processed | Status Saat Ini |
| :-: | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Harga Produsen (Farm-Gate)** | `prod_price_ff`, `prod_price_age_days`, `prod_obs_valid_today`, `prod_cov_120d` | Sinyal dini transmisi harga dari tingkat petani/produsen di provinsi sentra. **Sekunder** karena DKI Jakarta & Bali kosong `0%` dan Maluku Utara hanya `15,13%` (wajib memakai *reliability gate* `prod_cov_120d` jika diaktifkan). | `data/raw/pihps/json/pihps_pt4_2018_2026.json.gz` (PIHPS BI `price_type=4` Harga Produsen, `com_13` Cabai Merah Keriting) | `data/processed/dataset_v1/panel_dev.parquet` | **Tersedia di `panel_dev.parquet`** (32/34 provinsi terisi) |
| **2** | **Harga Rata-Rata Nasional** | `nat_trad_price_ff`, `nat_trad_price_age_days` | Jangkar (*anchor*) tren inflasi cabai nasional pada hari $t$. **Sekunder** karena informasi utamanya sudah terwakili oleh rata-rata lintas 34 simpul provinsi. | Baris `"Semua Provinsi"` (`I0`) pada `data/raw/pihps/pihps_cabai_merah_keriting_province.csv` / `pihps_pt1_*.json.gz` | `data/processed/dataset_v1/panel_dev.parquet` | **100% Terisi di `panel_dev.parquet`** |
| **3** | **Bobot Produksi Cabai Kab/Kota** | `w_kab_pixel.npz` (skema agregasi `prod_weighted` vs `uniform`) | Pembobot spasial saat mengagregasi piksel CHIRPS $0.05^\circ$ ke level provinsi agar curah hujan di kabupaten sentra cabai (mis. Garut, Malang, Brebes, Karo) berbobot lebih besar daripada piksel hutan/kota. **Fallback wajib**: `uniform` (`chirps_grid_province34.npz`). | `data/raw/bps/produksi_kab.csv` (BPS Statistik Hortikultura) + poligon Kab/Kota `data/raw/boundaries/geoBoundaries-IDN-ADM2_simplified.geojson` + jembatan `data/raw/boundaries/adm2_to_adm1.csv` | `data/interim/w_kab_pixel.npz` (tugas CGS-H1-03) | **Menunggu `produksi_kab.csv` (CGS)**; mask `uniform` sudah 100% siap |
| **4** | **Iklim & ENSO Tambahan (Multi-Skala)** | `rain_1d`, `rain_5d`, `rain_90d`, `rain_90d_anom_z`, `extreme_pentads_60d`, `clim_age_days`, `enso_roni_delta` | Variasi skala jendela waktu curah hujan (harian, 60 hari, 90 hari), umur latensi rilis data CHIRPS (`clim_age_days`), dan kecepatan perubahan fase ENSO (`enso_roni_delta` bulan-ke-bulan). | `data/raw/chirps_v3/chirps_v3_idn_*.npz` (CHIRPS) & `data/raw/enso/enso_indices_tidy.csv` (NOAA RONI/ONI) | `data/processed/dataset_v1/panel_dev.parquet` | `enso_roni_delta` siap; kolom `rain_*` tambahan menunggu tarik CHIRPS H2 |
| **5** | **Kalender Tambahan & Hari Kerja** | `days_since_idulfitri`, `is_holiday`, `is_cuti_bersama`, `is_trading_day`, `gap_days_prev_trading`, `days_to_iduladha`, `is_natal_tahunbaru` | Menangkap efek *post-Lebaran decay* (penurunan harga pasca-Idulfitri), panjang jeda libur panjang (`gap_days_prev_trading`), Iduladha, dan Natal/Tahun Baru. | **SKB 3 Menteri 2018–2026** + kalender hari aktif pelaporan PIHPS BI | `data/processed/dataset_v1/panel_dev.parquet` & `data/interim/calendar.csv` | **100% Terisi di `panel_dev.parquet`** |
| **6** | **Graph Prior Pembanding (Ablasi Struktur)** | `edges_knn.csv`, `edges_distance_threshold.csv`, `surplus_deficit.npy` | Graf pembanding untuk membuktikan bahwa **prior perdagangan BPS Poldis 2022 (`bps_mask.npy`)** lebih unggul daripada graf kedekatan geografis murni ($k$-NN / ambang jarak km). | `data/processed/dataset_v1/distance_km.csv` (dari `geoBoundaries-IDN-ADM1_simplified.geojson`) & Tabel 3 Hal. 33 PDF `BPS0000-..._2022.pdf` | `data/processed/dataset_v1/edges_knn.csv`, `edges_distance_threshold.csv` | **`edges_knn.csv` & `edges_distance_threshold.csv` sudah siap** |
| **7** | **Dataset Pembanding Harga SP2KP Kemendag** | `sp2kp_long.parquet` | **Hanya untuk validasi silang (*cross-check* QA)** terhadap lonjakan ekstrem harga PIHPS BI, **bukan** fitur input model saat inferensi. | `data/raw/sp2kp/` (Data SP2KP Kementerian Perdagangan) | `data/interim/sp2kp_long.parquet` (opsional, MDE-H2-03) | Opsional / Pendukung QA |
| **8** | **File Seed / Sampel Awal Tahun 2022 di Root** | `Tabel Harga Berdasarkan Daerah (6).xlsx`, `link_chirps_sat_2022 (1).txt`, `enso_index (1).csv` | File contoh/rujukan awal (tahun 2022) di folder root yang sudah **digantikan sepenuhnya** oleh dataset penuh 2018–2026 di `data/raw/`. | Folder root workspace (`c:\Users\ALIM\Downloads\rawit_sprint1_datasets_partial\`) | Tidak dipakai langsung oleh model karena sudah digantikan oleh `data/raw/pihps/`, `data/raw/chirps_v3/`, dan `data/raw/enso/` | **Arsip Rujukan Awal** |

---

## 3. KOLOM KHUSUS EVALUASI & QA (*DILARANG Masuk Fitur Model*)

Kolom-kolom ini ada di dalam dataset (`panel_dev.parquet` atau `regime_labels.csv`), tetapi **TIDAK BOLEH dimasukkan ke matriks fitur $X_t$** karena berfungsi sebagai stratifikasi evaluasi atau audit pembersihan data:

| No | Kelompok | Nama Kolom / File | Kenapa DILARANG Masuk Fitur Model ($X_t$) | Asal Dataset Mentah | File Lokasi |
| :-: | :--- | :--- | :--- | :--- | :--- |
| **1** | **Label Rezim Evaluasi** | `enso_phase`, `episode_id`, `is_dry`, `is_extreme_rain`, `is_normal`, `label_primary` | Digunakan **khusus oleh evaluator (`src/renaro/eval/metrics.py`)** untuk mengelompokkan error prediksi pada hari target $t+h$ ke dalam rezim Normal vs El Niño/Kekeringan vs La Niña/Hujan Ekstrem. Memasukkannya sebagai fitur berisiko mencampur label rezim evaluasi dengan sinyal input. | Diturunkan dari `data/raw/enso/RONI.ascii.txt` ($+0.5$ El Niño / $-0.5$ La Niña, aturan 5 musim) + `data/interim/climate_features.parquet` (CHIRPS v3) | `data/processed/dataset_v1/regime_labels.csv` |
| **2** | **Timestamp Audit Anti-Leakage** | `split`, `clim_valid_date`, `clim_available_at`, `enso_valid_month`, `enso_available_at` | Digunakan oleh *leakage checker* (`check_env.py` / `build_dataset_v1.py`) untuk memastikan `available_at <= t` pada setiap baris sebelum fitur digabungkan ke tanggal `date = t`. | Metadata aturan rilis `data/interim/availability.csv` | `data/processed/dataset_v1/panel_dev.parquet` |
| **3** | **Harga Mentah & Bendera QA (*Quality Assurance*)** | `price_trad_raw`, `price_prod_raw`, `qa_flag_mad`, `qa_flag_jump_revert`, `qa_flag_spike1d`, `qa_flag_stale`, `qa_prod_flag_range`, `qa_prod_flag_ratio`, `qa_prod_flag_jump`, `target_mask_strict` | Digunakan untuk mendeteksi salah ketik (*typo*), lonjakan 1 hari yang langsung kembali (*jump-revert*), atau harga beku $\ge 60$ hari (*stale*) sebelum membentuk `is_observed` / `target_mask`. | Dihitung dari seri mentah `data/raw/pihps/pihps_cabai_merah_keriting_province.csv` & `pihps_pt4_2018_2026.json.gz` | `data/processed/dataset_v1/panel_dev.parquet` & `data/interim/prices_clean.parquet` |

---

## 4. Ringkasan Alur "Dataset Mentah $\to$ Fitur Model"

```
[1] data/raw/pihps/pihps_cabai_merah_keriting_province.csv (+ json/pihps_pt1_*.json.gz)
    └──> data/interim/prices_clean.parquet
         ├──> FITUR WAJIB   : price (target_price & trad_price_ff), is_observed (target_mask & trad_obs_today)
         └──> FITUR SEKUNDER: nat_trad_price_ff (dari baris "Semua Provinsi")

[2] data/raw/pihps/json/pihps_pt4_2018_2026.json.gz (Harga Produsen PIHPS)
    └──> data/processed/dataset_v1/panel_dev.parquet
         └──> FITUR SEKUNDER: prod_price_ff, prod_price_age_days, prod_obs_valid_today, prod_cov_120d

[3] data/raw/chirps_v3/chirps_v3_idn_*.npz + data/raw/boundaries/chirps_grid_province34.npz
    (+ opsional sekunder: data/raw/bps/produksi_kab.csv + geoBoundaries-IDN-ADM2_simplified.geojson)
    └──> data/interim/climate_features.parquet
         ├──> FITUR WAJIB   : rain_pentad_anom, rain_30d_anom, dry_spell_days, extreme_5d
         └──> FITUR SEKUNDER: rain_1d, rain_5d, rain_90d, rain_90d_anom_z, extreme_pentads_60d, clim_age_days

[4] data/raw/enso/RONI.ascii.txt & data/raw/enso/enso_indices_tidy.csv
    └──> data/interim/roni.parquet
         ├──> FITUR WAJIB   : roni (enso_roni)
         └──> FITUR SEKUNDER: enso_roni_delta

[5] SKB 3 Menteri (data/ref/religious_dates.csv & cuti_bersama.csv)
    └──> data/interim/calendar.csv
         ├──> FITUR WAJIB   : is_ramadan, days_to_lebaran (days_to_idulfitri), dow, month (doy_sin, doy_cos)
         └──> FITUR SEKUNDER: days_since_idulfitri, is_holiday, is_cuti_bersama, gap_days_prev_trading

[6] BPS0000-distribusi_perdagangan_komoditas_cabai_merah_di_indonesia_2022.pdf
    + data/raw/boundaries/geoBoundaries-IDN-ADM1_simplified.geojson
    └──> data/interim/bps_mask_2022.csv (bps_mask.npy) & data/processed/dataset_v1/distance_km.csv
         ├──> FITUR WAJIB   : bps_mask (99 koridor perdagangan antarprovinsi), distance_km (jarak antar-ibu kota)
         └──> FITUR SEKUNDER: edges_knn.csv, edges_distance_threshold.csv, surplus_deficit.npy
```
