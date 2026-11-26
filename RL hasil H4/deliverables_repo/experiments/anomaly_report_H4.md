# Laporan Anomali Run Harian — Sesi H4 (`RL-H4-02`)

- **Peran & Penyusun**: RL (*Research Lead*) `@alim`
- **Tanggal Audit**: Kamis, 26 November 2026 (Sesi H4 · 15.00 WIB)
- **Tugas Playbook**: `RL-H4-02 · Review run harian (H4–H5)` (`docs/playbook/02_RL_Research_Lead.md`)
- **Commit Repo yang Diaudit**: `8b4aac4` (`merge: mle (RAWIT#45 module1 H4)`, mencakup `ad237e0 mle: complete H4 module1 and baseline runs`)
- **Cakupan Audit**: **141 run** = **111 run data riil** di `experiments/registry.csv` (`51` run H3 + `60` run neural baru H4) + **30 run sintetis/recovery** di `reports/baselines/`, `reports/module1/`, dan `reports/synth/`
- **Acuan `dataset_v1` Riil**: `split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`
- **Acuan Data Sintetis**: `split_hash = 8a551a68b996326eef075e5c44eb22bcd3f4cb0662d82f4ba40447df68b26c6d`
- **Register CSV Terstruktur**: `experiments/anomaly_report_H4.csv`
- **Log Harian Terkait**: `experiments/review_log.md`

---

## 1. Ringkasan Eksekutif Audit Anomali

Dari 141 run yang diaudit pada commit `8b4aac4`:
- **Kebocoran Data (`MAE << seasonal_naive`)**: **0 kasus (NIHIL)**. Seluruh 111 run data riil memiliki skala `MAE` wajar terhadap level harga cabai rawit merah (`~Rp50.027/kg`) dan berada dalam rentang realistis terhadap jangkar `seasonal_naive` (`Rp17.389,27/kg`) serta `naive_last` (`Rp6.782,78/kg`).
- **Integritas `split_hash` & Seed**: **111 / 111 run (100%)** di `experiments/registry.csv` memakai `split_hash` resmi `dataset_v1`, 0 duplikat `run_id`, 100% berstatus `completed`, dan 100% model stokastik yang terdaftar telah lengkap 5 seed (`0..4`).
- **Total Anomali Teridentifikasi**: **6 anomali aktif (`ANOM-01` s/d `ANOM-06`)** dengan rincian tingkat keparahan:
  - **1 Kritis (Bloker Gate 2)**: `ANOM-05` (3 dari 8 model wajib Gate 2 belum terdaftar di `registry.csv` data riil).
  - **3 Tinggi (Perlu Perbaikan Sebelum Gate 2)**: `ANOM-02` (*underfitting* `epochs=5` & ketidaksetaraan config `n_lags: 6 vs 8`, `epochs: 5 vs 10`), `ANOM-03` (varians antar-seed ekstrem `CV = 5,85%–12,11%` pada 6 kelompok run neural H4), dan `ANOM-04` (ketidakpatuhan `git_sha_clean()`, absennya kolom `git_sha` di `registry.csv`, serta `checkpoint=False` pada 30 run baseline neural H4).
  - **1 Sedang (Karakteristik Empiris, Bukan Bug)**: `ANOM-01` (lonjakan *overfitting* iklim tabular `lgbm_b`/`lgbm_c` di `O2 Val`).
  - **1 Rendah (Catatan Jujur Laporan)**: `ANOM-06` (sub-rezim `dry-only` pada uji recovery sintetis `MLE-H3-01` memiliki Spearman `0,636 < 0,70`).

---

## 2. Matriks Cek Enam Kriteria Wajib `RL-H4-02`

| No | Kriteria Audit `RL-H4-02` | Ambang Batas Resmi | Hasil Audit Commit `8b4aac4` | Status | ID Anomali |
| :-: | :--- | :--- | :--- | :---: | :---: |
| 1 | Indikasi kebocoran data (`MAE` terlalu rendah) | Tidak wajar jauh di bawah `seasonal_naive` (`Rp17.389`) & `naive_last` (`Rp6.783`) | **0 / 111 run**; seluruh model neural H4 berada di `Rp6.905`–`Rp8.240/kg` (Test) dan `Rp3.954`–`Rp8.133/kg` (Val) | **LULUS** | — |
| 2 | Kewajaran skala MAE vs `naive_last` & konvergensi | Model neural/tabular tidak melonjak jauh di atas `naive_last` karena *underfitting*/*overfitting* | `lgbm_b` (`+56,26%`) & `lgbm_c` (`+51,43%`) melonjak di `O2 Val`; seluruh 60 run neural H4 masih di atas `lgbm_a` (`Rp6.482`) & `naive_last` (`Rp6.783`) karena `epochs=5` & config tidak setara | **ANOMALI** | `ANOM-01`, `ANOM-02` |
| 3 | Stabilitas varians antar-seed (`5 seed`) | Koefisien variasi `CV = sd / mean <= 5,0%` | **6 kelompok run neural H4 (30 run)** melampaui `CV > 5%` (`5,85%` hingga `12,11%`), dengan distribusi bimodal di `latent_regime O2` | **ANOMALI** | `ANOM-03` |
| 4 | Kepatuhan `git_sha` bersih & artefak `ckpt.pt` | Runner wajib memanggil `git_sha_clean()`, mencatat `git_sha`, dan menyimpan `ckpt.pt` | `run_h4_module1.py` & `run_h4_baselines.py` tidak memanggil `git_sha_clean()`; `registry.csv` tidak punya kolom `git_sha`; **30 run** (`lag_graph`, `latent_regime`) berstatus `checkpoint=False` | **ANOMALI** | `ANOM-04` |
| 5 | Konsistensi `split_hash` & kelengkapan 8 model wajib Gate 2 | `100%` cocok `411aec1a...`, lengkap 5 seed untuk 8 model wajib | `split_hash` & 5 seed model terdaftar **100% LULUS**; namun **3 / 8 model wajib Gate 2 belum ada di `registry.csv` riil** (`gwn`, `mtgnn`, `module23` = 45 run) | **BLOKER GATE 2** | `ANOM-05` |
| 6 | Validitas sub-rezim uji recovery sintetis (`MLE-H3-01`) | Spearman `>= 0,70`, AUROC `>= 0,80`, kontrol `|delta_lag| ~ 0` | Agregat & `normal` **LULUS** (`Spearman=0,854`, `AUROC=1,000`, kontrol `0,026`), namun sub-rezim `dry-only` `Spearman=0,636 < 0,70` dan `delta_lag=0,813 < 2,0` | **CATATAN JUJUR** | `ANOM-06` |

---

## 3. Rincian Forensik Setiap Anomali (`ANOM-01` s/d `ANOM-06`)

### `ANOM-01` [SEDANG] — Overfitting Fitur Iklim Tabular pada `O2 Val` (`lgbm_b`, `lgbm_c`)
- **Run Terdampak (10 run)**: `20261125-1200_lgbm_b_O2_s0..4` dan `20261125-1200_lgbm_c_O2_s0..4`.
- **Bukti Metrik**:
  - `naive_last O2 Val`: `Rp6.541,76/kg` (jangkar).
  - `lgbm_a O2 Val`: `Rp7.711,82 ± 22,27/kg` (`CV = 0,29%`).
  - `lgbm_b O2 Val`: **`Rp10.221,92 ± 88,37/kg`** (`+56,26%` vs `naive_last`, `CV = 0,86%`; rentang `10.139,27`–`10.346,18`).
  - `lgbm_c O2 Val`: **`Rp9.906,30 ± 207,65/kg`** (`+51,43%` vs `naive_last`, `CV = 2,10%`; rentang `9.593,00`–`10.158,68`).
- **Akar Penyebab**: Jendela validasi `O2` (`2023-H2`) bertepatan dengan puncak rezim El Nino ekstrem yang belum banyak muncul pada jendela latih `O2` (`2018–2023-H1`), sehingga pohon keputusan tabular tanpa *gating* rentan mengekstrapolasi fitur iklim mentah secara berlebihan.
- **Evaluasi & Tindakan**: **Bukan bug dan bukan kebocoran** (dibuktikan dengan `CV <= 2,10%` dan `lgbm_c` menurunkan galat `-3,09%` vs `lgbm_b` serta signifikan di rezim `el_nino` dengan `p = 0,0001`). Pertahankan apa adanya sebagai bukti empiris mengapa regulasi iklim & *reliability gate* Modul 2–3 dibutuhkan.

---

### `ANOM-02` [TINGGI] — Underfitting Pelatihan Terlalu Singkat (`epochs = 5`) & Ketidaksetaraan Konfigurasi Head-to-Head Model Neural H4
- **Run Terdampak (60 run)**: Seluruh run `h4_module1_*` (30 run), `h4_lag_graph_*` (15 run), dan `h4_latent_regime_*` (15 run).
- **Bukti Konfigurasi (`configs/models/*.yaml` & `reports/mle/h4_module1_tuning.csv`)**:

| File Konfigurasi | `hidden` | `n_lags` / `k_states` | `lr` | `batch_size` | `epochs` | `patience` | `prior` | `zero_climate` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `configs/models/module1.yaml` | `64` | **`n_lags: 6`** | `0.001` | `64` | **`5`** | `10` | `bps` | `false` |
| `configs/models/lag_graph.yaml` | `64` | **`n_lags: 8`** | `0.001` | `64` | **`5`** | `10` | `bps` | `true` |
| `configs/models/latent_regime.yaml` | `64` | `k_states: 3` | `0.001` | `64` | **`10`** | `10` | `none` | `true` |

- **Dua Temuan Kritis pada `ANOM-02`**:
  1. **Underfitting Sistematis**: Pada `reports/mle/h4_module1_tuning.csv` (`TUNE_EPOCHS = 5`), **8 dari 8 kombinasi** grid tuning berhenti di `best_epoch = 4` atau `5` dari maksimum `5` epoch — artinya kurva validasi masih turun dan *early stopping* (`patience = 10`) tidak pernah sempat bekerja. Akibatnya, rata-rata 3 origin Test `h=10` seluruh model neural H4 masih berada di atas `lgbm_a` (`Rp6.481,95/kg`) dan `naive_last` (`Rp6.782,78/kg`):
     - `lag_graph (bps)`: `Rp7.284,20/kg`
     - `module1 (bps)`: `Rp7.320,82/kg`
     - `latent_regime (none)`: `Rp7.567,73/kg`
     - `module1 (none)`: `Rp7.768,06/kg`
  2. **Ketidaksetaraan Perbandingan (*Unfair Head-to-Head*)**:
     - `latent_regime.yaml` diberi anggaran **`epochs: 10`** (2x lipat dari `module1` dan `lag_graph` yang hanya `epochs: 5`).
     - `lag_graph.yaml` memakai **`n_lags: 8`** sedangkan `module1.yaml` memakai **`n_lags: 6`**, sehingga perbandingan langsung `module1` vs `lag_graph` (menguji efek pengondisian iklim pada graf ber-lag) tercampur oleh perbedaan jumlah lag!
     - `scripts/run_h4_module1.py` memiliki default CLI `--epochs 15` (menimpa YAML), sedangkan `scripts/run_h4_baselines.py` memiliki default CLI `--epochs 10` (menimpa YAML); karena `experiments/runs/*/summary.json` tidak di-commit ke git, anggaran epoch aktual per run tidak dapat diaudit 100% tanpa menyamakan YAML & menyimpan log ringkasnya.
- **Catatan Sinyal Positif (Tetap Menjanjikan)**: Meskipun dalam kondisi *underfit* 5 epoch, **`module1 (bps)` sudah mengalahkan `latent_regime` sebesar `-3,26%`** pada rata-rata 3 origin (`-10,29%` di `O2` El Nino), **mengalahkan `lag_graph` di `O2` sebesar `-4,04%`**, serta **mengalahkan `module1 (none)` di 3/3 origin sebesar `-5,76%`** (`-Rp447,25/kg`, mendukung nilai tambah prior BPS pada `RQ3`).
- **Tindakan Wajib (`MLE`, sebelum Gate 2)**:
  1. Samakan anggaran pelatihan & arsitektur pembanding pada semua model neural (`epochs: 30–50`, `patience: 10–15`, `n_lags: 6` yang seragam antara `module1` dan `lag_graph`).
  2. Pertimbangkan penambahan *residual anchor* ke `log_price_t` agar model neural tidak perlu mempelajari ulang level harga absolut dari nol dalam sedikit epoch.
  3. Catat `epochs`, `best_epoch`, dan `stop_epoch` eksplisit di ringkasan CSV agar audit konvergensi dapat diverifikasi dari git.

---

### `ANOM-03` [TINGGI] — Varians Antar-Seed Ekstrem (`CV > 5%`) pada 6 Kelompok Run Neural H4 (30 Run Terdampak)
- **Kriteria**: Ambang batas kestabilan `RL-H4-02` adalah `CV = sd / mean <= 5,0%`.
- **Ringkasan 6 Kelompok yang Melampaui Ambang Batas**:

| Kelompok Run (5 Seed `0..4`) | Model (`prior`) | Origin | `val_h10_mae` mean ± sd [`CV%`] | `test_h10_mae` mean ± sd [`CV%`] | Rentang Min–Maks Test (`Rp/kg`) | Pola Anomali |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `h4_lag_graph_O2_s0..4` | `lag_graph` (`bps`) | `O2` | `7.626,67 ± 445,91` [**`5,85%`**] | `7.542,46 ± 913,10` [**`12,11%`**] | `6.568,70` (s2) – `8.737,05` (s0) | Dispersi ekstrem `Rp2.168/kg` antar seed |
| `h4_latent_regime_O2_s0..4` | `latent_regime` (`none`) | `O2` | `7.313,91 ± 820,05` [**`11,21%`**] | `8.068,48 ± 936,21` [**`11,60%`**] | `6.533,46` (s1) – `9.016,53` (s4) | **Bimodal Val** (`~6.700` vs `~8.200`) + *val–test inversion* pada s1 |
| `h4_module1_O2_none_s0..4` | `module1` (`none`) | `O2` | `7.685,02 ± 672,52` [**`8,75%`**] | `7.967,29 ± 869,20` [**`10,91%`**] | `7.068,10` (s3) – `9.151,46` (s1) | Tanpa prior BPS, dispersi Test `Rp2.083/kg` |
| `h4_module1_O1_none_s0..4` | `module1` (`none`) | `O1` | `7.394,93 ± 280,52` [`3,79%`] | `7.096,65 ± 627,64` [**`8,84%`**] | `6.677,57` (s2) – `8.131,58` (s1) | Outlier tajam pada seed `s1` (`8.131,58`) |
| `h4_module1_O2_bps_s0..4` | `module1` (`bps`) | `O2` | `8.132,92 ± 714,99` [**`8,79%`**] | `7.238,03 ± 348,21` [`4,81%`] | `6.914,63` (s2) – `7.759,25` (s0) | Outlier rendah Val pada `s0` (`6.927,78`) tetapi Test tertinggi (`7.759,25`) |
| `h4_module1_O1_bps_s0..4` | `module1` (`bps`) | `O1` | `7.241,70 ± 105,07` [`1,45%`] | `6.905,15 ± 507,40` [**`7,35%`**] | `6.523,83` (s2) – `7.782,90` (s1) | Outlier tajam pada seed `s1` (`7.782,90`) |

- **Tabel Rincian 30 Run Individual pada 6 Kelompok Ber-CV Tinggi**:

| `run_id` | Model (`prior`) | Origin | Seed | `val_h10_mae` (`Rp/kg`) | `test_h10_mae` (`Rp/kg`) | `checkpoint` | Catatan Outlier |
| :--- | :--- | :---: | :---: | ---: | ---: | :---: | :--- |
| `h4_lag_graph_O2_s0` | `lag_graph` (`bps`) | `O2` | 0 | 7.377,92 | **8.737,05** | `False` | Test tertinggi (+15,8% di atas mean) |
| `h4_lag_graph_O2_s1` | `lag_graph` (`bps`) | `O2` | 1 | **8.262,26** | 7.861,50 | `False` | Val tertinggi |
| `h4_lag_graph_O2_s2` | `lag_graph` (`bps`) | `O2` | 2 | 7.721,93 | **6.568,70** | `False` | Test terendah (-12,9% di bawah mean) |
| `h4_lag_graph_O2_s3` | `lag_graph` (`bps`) | `O2` | 3 | **7.066,08** | 7.869,27 | `False` | Val terendah, namun Test tinggi |
| `h4_lag_graph_O2_s4` | `lag_graph` (`bps`) | `O2` | 4 | 7.705,18 | 6.675,78 | `False` | — |
| `h4_latent_regime_O2_s0` | `latent_regime` (`none`) | `O2` | 0 | 6.684,20 | 8.117,06 | `False` | Klaster Val rendah (`~6.700`) |
| `h4_latent_regime_O2_s1` | `latent_regime` (`none`) | `O2` | 1 | **8.193,31** | **6.533,46** | `False` | Klaster Val tinggi, tetapi Test terendah (*val–test inversion*) |
| `h4_latent_regime_O2_s2` | `latent_regime` (`none`) | `O2` | 2 | 6.741,38 | 8.565,22 | `False` | Klaster Val rendah (`~6.700`) |
| `h4_latent_regime_O2_s3` | `latent_regime` (`none`) | `O2` | 3 | 6.720,31 | 8.110,11 | `False` | Klaster Val rendah (`~6.700`) |
| `h4_latent_regime_O2_s4` | `latent_regime` (`none`) | `O2` | 4 | **8.230,37** | **9.016,53** | `False` | Klaster Val tinggi & Test tertinggi |
| `h4_module1_O1_bps_s0` | `module1` (`bps`) | `O1` | 0 | 7.184,39 | 6.794,93 | `True` | — |
| `h4_module1_O1_bps_s1` | `module1` (`bps`) | `O1` | 1 | 7.244,82 | **7.782,90** | `True` | Outlier Test tertinggi (+12,7% di atas mean) |
| `h4_module1_O1_bps_s2` | `module1` (`bps`) | `O1` | 2 | 7.250,48 | 6.523,83 | `True` | Test terendah |
| `h4_module1_O1_bps_s3` | `module1` (`bps`) | `O1` | 3 | 7.405,40 | 6.828,72 | `True` | — |
| `h4_module1_O1_bps_s4` | `module1` (`bps`) | `O1` | 4 | 7.123,42 | 6.595,36 | `True` | — |
| `h4_module1_O2_bps_s0` | `module1` (`bps`) | `O2` | 0 | **6.927,78** | **7.759,25** | `True` | Val terendah (-14,8%), namun Test tertinggi |
| `h4_module1_O2_bps_s1` | `module1` (`bps`) | `O2` | 1 | **8.838,74** | 7.424,70 | `True` | Val tertinggi (+8,7%) |
| `h4_module1_O2_bps_s2` | `module1` (`bps`) | `O2` | 2 | 8.369,31 | 6.914,63 | `True` | — |
| `h4_module1_O2_bps_s3` | `module1` (`bps`) | `O2` | 3 | 8.308,30 | 7.044,63 | `True` | — |
| `h4_module1_O2_bps_s4` | `module1` (`bps`) | `O2` | 4 | 8.220,46 | 7.046,95 | `True` | — |
| `h4_module1_O1_none_s0` | `module1` (`none`) | `O1` | 0 | 7.178,47 | 6.710,13 | `True` | — |
| `h4_module1_O1_none_s1` | `module1` (`none`) | `O1` | 1 | 7.488,01 | **8.131,58** | `True` | Outlier Test tertinggi (+14,6% di atas mean) |
| `h4_module1_O1_none_s2` | `module1` (`none`) | `O1` | 2 | 7.398,90 | 6.677,57 | `True` | — |
| `h4_module1_O1_none_s3` | `module1` (`none`) | `O1` | 3 | 7.809,67 | 7.258,89 | `True` | — |
| `h4_module1_O1_none_s4` | `module1` (`none`) | `O1` | 4 | 7.099,59 | 6.705,10 | `True` | — |
| `h4_module1_O2_none_s0` | `module1` (`none`) | `O2` | 0 | **6.865,97** | 8.241,80 | `True` | Val terendah, Test tinggi |
| `h4_module1_O2_none_s1` | `module1` (`none`) | `O2` | 1 | 7.217,01 | **9.151,46** | `True` | Outlier Test tertinggi (+14,9% di atas mean) |
| `h4_module1_O2_none_s2` | `module1` (`none`) | `O2` | 2 | 7.627,65 | 7.149,32 | `True` | — |
| `h4_module1_O2_none_s3` | `module1` (`none`) | `O2` | 3 | **8.435,31** | **7.068,10** | `True` | Val tertinggi, Test terendah |
| `h4_module1_O2_none_s4` | `module1` (`none`) | `O2` | 4 | 8.279,17 | 8.225,77 | `True` | — |

- **Akar Penyebab**: Kombinasi (a) pelatihan yang berhenti sebelum konvergen (`epochs = 5`, sangat sensitif terhadap inisialisasi bobot awal), (b) ketidakselarasan distribusi `O2 Val` (El Nino 2023-H2) vs `O2 Test` (2024-H1), dan (c) ketiadaan *residual anchor* / *weight decay* yang cukup.
- **Tindakan Wajib**: (1) **DILARANG memilih seed terbaik** (*cherry-picking*); wajib laporkan `mean ± sd` 5 seed penuh. (2) Lakukan refit terkonvergensi (`epochs >= 30`, `patience >= 10`) dengan target `CV < 5%` di `O1–O3` sebelum Gate 2 (`MLE-H5-03`).

---

### `ANOM-04` [TINGGI] — Kepatuhan Auditability (`git_sha_clean()`, Skema `registry.csv`) & `checkpoint = False` pada 30 Run Baseline Neural H4
- **Run Terdampak**:
  - **60 run H4** (`h4_module1_*`, `h4_lag_graph_*`, `h4_latent_regime_*`) tidak melewati validasi `scripts/train.py:git_sha_clean()` dan tidak menuliskan `git_sha.txt`.
  - **30 run baseline H4** (`h4_lag_graph_O1..O3_s0..4` dan `h4_latent_regime_O1..O3_s0..4`) berstatus **`checkpoint = False`** di `reports/mle/h4_runs_summary.csv` karena `scripts/run_h4_baselines.py` memanggil `run_registered(...)` tanpa meneruskan argumen penyimpanan checkpoint.
  - **111 / 111 baris `experiments/registry.csv`** saat ini hanya punya 7 kolom (`run_id, model, origin, seed, split_hash, val_mae, status`) tanpa kolom `git_sha`.
- **Risiko Gate 2**: Tanpa `ckpt.pt` + SHA-256 yang terekam dari commit git bersih, `lag_graph` dan `latent_regime` tidak memenuhi syarat *freeze* `MLE-H5-03` dan tidak dapat dievaluasi ulang pada holdout yang disegel (`CGS-H6-01`).
- **Tindakan Wajib (`MLE`, sebelum Gate 2)**:
  1. Tambahkan pemeriksaan `git_sha_clean()` (dan kolom `git_sha` di `registry.csv` atau `frozen/manifest.yaml`) pada semua runner refit H5 (`MLE-H5-01`, `MLE-H5-02`, `MLE-H5-03`).
  2. Wajibkan penyimpanan `best.pt` / `ckpt.pt` + checksum SHA-256 untuk `lag_graph` dan `latent_regime` (serta `gwn`, `mtgnn`, `module1`, `module23`) saat pembekuan `MLE-H5-03`.

---

### `ANOM-05` [KRITIS — BLOKER GATE 2] — 3 dari 8 Model Wajib Gate 2 Belum Terdaftar di `experiments/registry.csv` Data Riil
- **Model Terdampak (45 run belum ada)**:
  1. **`gwn` (Graph WaveNet) pada `dataset_v1`** (`O1–O3` × 5 seed = 15 run) — saat ini baru ada 5 run sintetis (`8a551a68...`) di `reports/baselines/graph_run_metrics.csv`.
  2. **`mtgnn` pada `dataset_v1`** (`O1–O3` × 5 seed = 15 run) — saat ini baru ada 5 run sintetis (`8a551a68...`) di `reports/baselines/graph_run_metrics.csv`.
  3. **`module23` (Modul 1 + Reliability Gate `MLE-H5-01`) pada `dataset_v1`** (`O1–O3` × 5 seed = 15 run) — dijadwalkan pada H5.
- **Status Kelengkapan Gate 2 Saat Ini (`5 / 8` Terdaftar di Data Riil)**:
  - Sudah terdaftar di `registry.csv`: `seasonal_naive`, `lgbm_c` (plus `naive_last`, `lgbm_a`, `lgbm_b`), `module1` (`bps` & `none`), `latent_regime`, `lag_graph`.
  - Belum terdaftar di `registry.csv`: **`gwn` (riil)**, **`mtgnn` (riil)**, **`module23`**.
- **Tindakan Wajib (Keputusan Gate 2 — H5 · Jumat 27 Nov 2026, 16.30 WIB)**:
  - Eskalasi langsung ke MLE (`@agusprasetya`) untuk menyelesaikan `gwn`, `mtgnn`, dan `module23` pada `dataset_v1` (`split_hash = 411aec1a...`, 5 seed, `git_sha_clean()`, simpan `ckpt.pt`) sebelum H5 16.30 WIB.
  - Sesuai aturan Gate 2 (`docs/playbook/02_RL_Research_Lead.md`), model wajib yang belum lulus prasyarat hingga batas Gate 2 akan **dikeluarkan dari tabel holdout** dan dicatat eksplisit pada `docs/decisions/GATE2.md`.

---

### `ANOM-06` [RENDAH — CATATAN JUJUR] — Sub-Rezim `dry-only` pada Uji Recovery Sintetis (`MLE-H3-01`)
- **Sumber**: `reports/synth/recovery_metrics.csv` (15 run sintetis = 3 varian × 5 seed, commit `4b1df03`).
- **Bukti Metrik**:
  - `module1_default` (`normal`): Spearman `0,854 ± 0,012` (5/5 seed `>= 0,842`), `lag_acc = 0,826`, `lag_mae = 0,408`, `AUROC = 1,000` — **LULUS**.
  - `module1_default` (`dry`): Spearman **`0,636 ± 0,045`** (4/5 seed `< 0,70`: s0 `0,599`, s1 `0,612`, s2 `0,662`, s4 `0,605`; hanya s3 `= 0,704`), `lag_acc = 0,616`, `lag_mae = 0,644`, `delta_lag = 0,813 ± 0,053` (lebih kecil dari pergeseran sintetis `delta_true = 2,0`).
  - Kontrol negatif (`module1_no_climate` & `module1_unconditioned`): `|delta_lag| = 0,011` dan `0,041` (`~ 0`) — **LULUS** (tidak ada pergeseran palsu).
- **Tindakan Wajib (`RL`, H5 & H7)**: Bukan bloker kode, tetapi wajib dilaporkan secara transparan sebagai keterbatasan sensitivitas sub-rezim `dry` pada figur `RL-H5-01` dan bagian keterbatasan laporan `RL-H7-01` (hindari klaim *over-claiming* bahwa recovery sempurna di semua sub-rezim).

---

## 4. Ringkasan Eskalasi Siap Kirim ke MLE (`@agusprasetya`) — Pra-Gate 2 (H5)

> **Subjek**: `[RL-H4-02] Laporan Anomali Audit Run H4 (commit 8b4aac4) — 4 Aksi Wajib Sebelum Gate 2 (H5 16.30 WIB)`
>
> Hasil audit RL atas 111 run `experiments/registry.csv` (+30 run sintetis) pada commit `8b4aac4`:
> - **Status baik**: 0 kebocoran data, `split_hash` 100% seragam (`411aec1a...`), 5/5 seed lengkap untuk semua model terdaftar, handoff `module1_for_robustness.yaml` tersedia, dan `module1 (bps)` sudah unggul atas `latent_regime` (`-3,26%` rata-rata; `-10,29%` di `O2`) serta `module1 (none)` (`-5,76%`, 3/3 origin).
> - **4 tindakan wajib sebelum Gate 2 (Jumat 27 Nov 2026, 16.30 WIB)**:
>   1. **Samakan & naikkan `epochs` + seragamkan `n_lags` (`ANOM-02`, `ANOM-03`)**: `module1.yaml` (`epochs=5, n_lags=6`), `lag_graph.yaml` (`epochs=5, n_lags=8`), dan `latent_regime.yaml` (`epochs=10`) tidak setara dan *underfit* (`best_epoch = 4–5/5`), memicu `CV` antar-seed `5,85%–12,11%` di `O2` & `O1`. Mohon samakan `epochs >= 30` (`patience >= 10`), seragamkan `n_lags = 6` antara `module1` dan `lag_graph`, serta pertimbangkan *residual anchor* ke `log_price_t` pada refit `MLE-H5-03`.
>   2. **Simpan checkpoint semua baseline neural (`ANOM-04`)**: Seluruh 30 run `lag_graph` dan `latent_regime` saat ini `checkpoint=False`. Mohon simpan `ckpt.pt` + SHA-256 ke `frozen/manifest.yaml`.
>   3. **Tegakkan `git_sha_clean()` & catat `git_sha` (`ANOM-04`)**: Runner H5 wajib mengecek working tree bersih dan mencatat `git_sha` agar dapat diaudit di Gate 2.
>   4. **Lengkapi 3 model wajib Gate 2 pada `dataset_v1` riil (`ANOM-05`)**: `gwn` (15 run), `mtgnn` (15 run), dan `module23` (`MLE-H5-01`, 15 run) wajib masuk `experiments/registry.csv` sebelum H5 16.30 WIB; yang belum lengkap akan dikeluarkan dari holdout sesuai protokol Gate 2.
