# Laporan Anomali Run Harian — Sesi H5 (`RL-H4-02` · Pembaruan Pra-Gate 2)

- **Peran & Penyusun**: RL (*Research Lead*) `@alim`
- **Tanggal Audit**: Jumat, 27 November 2026 (Sesi H5 · Pembaruan setelah run baru MLE, CGS, dan MDE)
- **Tugas Playbook**: `RL-H4-02 · Review run harian (H4–H5)` (`docs/playbook/02_RL_Research_Lead.md`)
- **Commit Repo yang Diaudit**: `54791ba` (`merge: mle (H5-02 ablation + H5-01 robustness audit fixes)`)
  - Mencakup `24d9a77` (revisi H4 `lag_graph` & `latent_regime`), `469f440` (`MLE-H5-01 module23`), `28b9add` (`MLE-H5-02 ablation` + `CGS-H5-01 robustness`), `7e5b76d` (`MDE-H4-01/02` priors & perturbasi), dan `ba14722` (`MDE-H5-01/02` pipeline & data card).
  - Catatan branch belum ter-merge: `origin/mde` (`baeea86`, 1 commit `--dry-run` fix, tidak mengubah `dataset_v1` maupun `registry.csv`).
- **Cakupan Audit**: **273 run** = **243 run data riil** di `experiments/registry.csv` (`51` H3 + `60` H4 + `15` H5-01 `module23` + `75` H5-02 `ablation` + `42` CGS-H5-01 `robustness`) + **30 run sintetis/recovery** di `reports/`.
- **Acuan `dataset_v1` Riil**: `split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`
- **Register CSV Terstruktur**: `experiments/anomaly_report_H5.csv`
- **Log Harian & Laporan Sebelumnya**: `experiments/review_log.md`, `experiments/anomaly_report_H4.md`

---

## 1. Ringkasan Eksekutif — Delta Audit H4 (`8b4aac4`) ke H5 (`54791ba`)

- **Integritas Data & Kebocoran (`MAE << seasonal_naive`)**: **LULUS 100%**. Dari **243 run** di `experiments/registry.csv`, ditemukan **0 kasus kebocoran data**, **243/243 (100%)** konsisten memakai `split_hash = 411aec1a...`, **0 duplikat `run_id`**, **100% berstatus `completed`**, dan **holdout tidak disentuh** pada seluruh skrip MLE maupun CGS.
- **Perbaikan Nyata yang Berhasil Dicapai Sejak H4**:
  1. `configs/models/lag_graph.yaml` menyamakan `n_lags: 8 -> 6` (setara `module1`).
  2. `configs/models/latent_regime.yaml` memakai `prior: bps` + `entropy_lambda: 0.01` (`epochs: 10`): **bimodal `O2` hilang total** (`Val CV` turun dari `11,21% -> 2,36%`, `Test CV` anjlok dari `11,60% -> 0,98%`), dan rata-rata Test `h=10` membaik `-Rp547,51/kg` (`7.567,73 -> 7.020,22`).
  3. `MLE-H5-01` (`module23`, 15 run), `MLE-H5-02` (`ablation`, 75 run), dan `CGS-H5-01` (`robustness`, 42 run train-mode + 5.640 baris test-mode) telah terdaftar di `experiments/registry.csv`.
  4. Pada `CGS-H5-01` (`O3`), `robustness_module1_*` sangat stabil (`7/7` mask `CV <= 3,80%`) dan lebih tahan terhadap perturbasi `p = 50%` (`+0,30%` s/d `+1,06%`) dibandingkan `gwn` (`+1,05%` s/d `+2,29%`).
- **Ringkasan 10 Anomali Aktif pada Sesi H5 (`ANOM-01` s/d `ANOM-10`)**:
  - **1 Kritis (Bloker Gate 2)**: `ANOM-05` (`gwn` penuh `O1–O3` × 5 seed, `mtgnn` penuh `O1–O3` × 5 seed, dan `frozen/manifest.yaml` belum ada).
  - **4 Tinggi (Wajib Diperbaiki Sebelum Gate 2)**: `ANOM-02` (ketidaksetaraan 4 anggaran epoch: `10 vs 5 vs 2 vs 1`), `ANOM-03` (varians antar-seed ekstrem `CV = 5,19%–28,34%` di `lag_graph O2`, `module1`, `module23`, 10/15 `ablation`, & 6/7 `robustness_gwn`), `ANOM-04` (`0/192` run non-H3 memanggil `git_sha_clean()`, `ckpt.pt` absen pada `lag_graph`/`latent_regime`/`module23`, `frozen/` belum ada), dan **`ANOM-07` [BARU]** (**bug kode nyata di `scripts/aggregate_ablation.py` baris 116–117** yang salah melaporkan `Ablation full = 9.490,31` alih-alih `8.168,40`).
  - **3 Sedang**: `ANOM-01` (overfitting iklim tabular `O2 Val`, empiris), **`ANOM-08` [BARU]** (polusi kolom `model` di `registry.csv` & inkonsistensi unweighted vs weighted `val_mae`), dan **`ANOM-09` [BARU]** (`module23` 2-epoch kalah di 3/3 origin & `no_calendar` mengalahkan `full` di 3/3 horizon pada ablasi 1-epoch).
  - **2 Rendah (Catatan Jujur)**: `ANOM-06` (`dry-only` Spearman `0,636` & CGS lead-lag `0/4.472` uji lolos BH-FDR `q < 0,05`) dan **`ANOM-10` [BARU]** (duplikasi format mask `masks.npz` vs MDE `index.csv` & catatan limitasi `p=30` / 3 seed).

---

## 2. Bukti Empiris Utama Sesi H5: Korelasi Langsung Anggaran `epochs` vs Instabilitas & Performa

Pembaruan H5 membuktikan secara telak hipotesis audit H4 bahwa **anggaran `epochs` yang terlalu singkat dan tidak setara adalah penyebab dominan instabilitas varians antar-seed dan kekalahan model utama terhadap baseline**:

| Kelompok Model (`54791ba`) | `epochs` Aktual | `n_lags` / `k` | `prior` | Rentang `CV` Val / Test (`O1–O3`) | Rata-rata Test `h=10` 3-Origin (`Rp/kg`) | Kesimpulan Audit |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `latent_regime` (revisi `24d9a77`) | **`10`** | `k=3` | `bps` | **`0,41%` – `2,36%`** (SEMUA LULUS) | **`7.020,22`** | Konvergen & stabil; unggul karena 2x–5x epoch |
| `lag_graph` (revisi `24d9a77`) | **`5`** | `n_lags=6` | `bps` | `1,38%` – **`10,15%`** (`O2` gagal) | `7.128,30` | `n_lags` sudah setara, tapi `5 epoch` masih underfit di `O2` |
| `module1 (bps)` (H4) | **`5`** | `n_lags=6` | `bps` | `1,45%` – **`8,79%`** (`O1/O2` gagal) | `7.320,82` | Belum direfit sejak H4; kalah dari `latent_regime` karena 5 vs 10 ep |
| `module1 (none)` (H4) | **`5`** | `n_lags=6` | `none` | `2,20%` – **`10,91%`** (`O1/O2` gagal) | `7.768,06` | Underfit + tanpa prior BPS |
| `module23` (`MLE-H5-01`) | **`2`** | `n_lags=6` | `bps` | `1,60%` – **`9,24%`** (`O2/O3` gagal) | **`7.581,05`** | **Sangat underfit (`2 epoch`)**; kalah dari `module1` di 3/3 origin (`+Rp260/kg`) |
| `robustness_gwn` (`CGS-H5-01`) | **`2`** | GWN | perturb | **`4,60%` – `7,85%`** (6/7 mask gagal) | `8.552,62` (`clean O3`) | Hanya `O3` × 3 seed (`0..2`), 2 epoch; bukan baseline penuh Gate 2 |
| `ablation_*` (`MLE-H5-02`, 5 varian) | **`1`** | `n_lags=6/1` | `bps` | `2,53%` – **`28,34%`** (10/15 grup gagal) | *(Val-only: `7.731`–`8.716`)* | **Meledak di `O1` (`12,99%`–`28,34%`)**; 10 run `> Rp12.000/kg` |

> **Implikasi Kritis untuk Gate 2**: Membandingkan `latent_regime` (`10 epoch`), `module1`/`lag_graph` (`5 epoch`), dan `module23` (`2 epoch`) dalam satu tabel utama holdout adalah **tidak valid secara metodologis (*confounded by training budget*)**. Seluruh model neural kandidat Gate 2 wajib direfit dengan anggaran `epochs` yang **setara dan terkonvergensi** (minimal `epochs = 20–30` dengan `patience = 10`, atau minimum seragam `>= 10` epoch bila dibatasi waktu GPU 4 GB) pada `MLE-H5-03`.

---

## 3. Rincian Forensik Anomali H4 yang Diperbarui & Anomali Baru H5

### A. Pembaruan Status `ANOM-01` s/d `ANOM-06` (dari Laporan H4)

1. **`ANOM-01` [SEDANG — TETAP / EMPIRIS]**: Overfitting fitur iklim tabular `lgbm_b` (`10.221,92`) & `lgbm_c` (`9.906,30`) pada `O2 Val`. Tidak berubah; tetap dicatat sebagai karakteristik empiris, bukan bug.
2. **`ANOM-02` [TINGGI — MEMBURUK SECARA PERBANDINGAN]**: Ketidaksetaraan `n_lags` (`6 vs 8`) telah diselesaikan di `24d9a77`, namun ketidaksetaraan `epochs` meluas menjadi **4 tingkat** (`10` vs `5` vs `2` vs `1` epoch). Lihat Bagian 2 di atas.
3. **`ANOM-03` [TINGGI — TERTUTUP DI `latent_regime`, MELUAS KE `module23`, `ablation`, & `robustness_gwn`]**:
   - **Tertutup**: `latent_regime O2` (`Val CV` `11,21% -> 2,36%`; `Test CV` `11,60% -> 0,98%`).
   - **Tetap Terbuka (H4)**: `lag_graph O2` (`Val CV = 6,41%`, `Test CV = 10,15%`; min `6.550,35` s2 vs max `8.228,07` s1), `module1 bps` (`O2 Val = 8,79%`, `O1 Test = 7,35%`), `module1 none` (`O2 Test = 10,91%`, `O1 Test = 8,84%`, `O2 Val = 8,75%`).
   - **Baru H5 — `h5_module23` (15 run, 2 epoch)**:
     - `O2 Val`: **`8.447,20 ± 774,97`** (`CV = 9,17%`; `s0 = 7.122,14` vs `s3 = 9.040,49`).
     - `O2 Test`: **`7.461,57 ± 689,21`** (`CV = 9,24%`; `s3 = 6.843,78` vs `s4 = 8.554,53`, *val–test inversion* tajam pada `s3`!).
     - `O3 Val`: **`4.481,39 ± 311,19`** (`CV = 6,94%`; `s2 = 4.169,25` vs `s4 = 4.904,87`).
   - **Baru H5 — `ablation_*` (75 run, 1 epoch — 10 dari 15 kelompok `CV > 5%`)**:
     - `ablation_no_lag_O1`: **`11.345,16 ± 3.215,45`** (**`CV = 28,34%`**; min `8.377,53` – max `15.986,80`).
     - `ablation_no_gate_O1`: **`12.403,82 ± 3.366,76`** (**`CV = 27,14%`**; min `7.819,33` – max `16.356,04`).
     - `ablation_no_climate_O1`: **`12.099,81 ± 2.874,32`** (**`CV = 23,76%`**; min `8.487,79` – max `15.951,10`).
     - `ablation_no_lag_O2`: **`8.778,91 ± 1.561,22`** (**`CV = 17,78%`**).
     - `ablation_full_O1`: **`11.080,68 ± 1.736,78`** (**`CV = 15,67%`**; min `9.675,37` – max `12.981,97`).
     - `ablation_no_calendar_O1`: **`10.720,05 ± 1.392,74`** (**`CV = 12,99%`**).
     - Juga melampaui `5%`: `no_gate O2` (`9,89%`), `full O2` (`8,22%`), `no_gate O3` (`7,58%`), `no_climate O2` (`6,58%`), `no_lag O3` (`6,22%`).
     - **10 run ablasi individual melewati `Rp12.000/kg` di `O1 Val`** (`ablation_no_gate_O1_s2 = 16.356,04`, `no_lag_O1_s1 = 15.986,80`, `no_climate_O1_s2 = 15.951,10`, `no_gate_O1_s1 = 14.246,02`, `no_climate_O1_s1 = 13.844,52`, `no_gate_O1_s3 = 13.311,63`, `no_lag_O1_s4 = 13.226,39`, `full_O1_s2 = 12.981,97`, `full_O1_s1 = 12.968,03`, `no_calendar_O1_s2 = 12.766,27`).
   - **Baru H5 — `robustness_gwn_*` (21 run, `O3`, 3 seed `0..2`, 2 epoch — 6 dari 7 mask `CV > 5%`)**:
     - `clean` (`7,85%`: `4.404,66 / 4.786,74 / 4.092,92`), `add_50` (`7,81%`), `drop_10` (`7,03%`), `rewire_10` (`6,65%`), `drop_50` (`6,08%`), `add_10` (`5,19%`). Seed `s1` konsisten paling tinggi di seluruh 7 mask.
4. **`ANOM-04` [TINGGI — MASIH TERBUKA & MELUAS]**:
   - Audit `scripts/*.py` membuktikan **0 dari 8 runner aktif** (`run_rq0.py`, `run_h4_module1.py`, `run_h4_baselines.py`, `run_module23.py`, `run_ablation.py`, `robustness.py`, `aggregate_ablation.py`, `finalize_robustness.py`) memanggil `git_sha_clean()`; hanya `scripts/train.py` yang memilikinya. `experiments/registry.csv` (`243` baris) tetap tidak memiliki kolom `git_sha`.
   - `lag_graph` (15 run), `latent_regime` (15 run), dan `h5_module23` (15 run) **tidak menyimpan `ckpt.pt`/`best.pt`**, serta direktori **`frozen/` (`frozen/manifest.yaml`) belum ada** di repo (`MLE-H5-03` belum dijalankan).
5. **`ANOM-05` [KRITIS — BLOKER GATE 2 MASIH TERBUKA: `6 / 8` MODEL WAJIB]**:
   - `module23` sudah masuk (`15 run`), tetapi **2 model wajib Gate 2 masih belum punya baseline penuh `O1–O3` × 5 seed (`0..4`) pada `dataset_v1`**:
     - **`gwn` (penuh riil)**: 21 baris `gwn` di `registry.csv` seluruhnya adalah `robustness_gwn_*` (`O3` saja, 3 seed `0..2`, 2 epoch) — **0 run** untuk `O1`, `O2`, dan `seed 3..4`.
     - **`mtgnn` (penuh riil)**: **0 run** di `registry.csv` (baru ada 5 run sintetis `8a551a68...`).
6. **`ANOM-06` [RENDAH — TETAP + TAMBAHAN CGS-H4-02]**:
   - Uji recovery sintetis `dry-only` Spearman `0,636 < 0,70` & `delta_lag = 0,813 < 2,0`.
   - Tambahan jujur dari `reports/leadlag/leadlag_summary.md` (`CGS-H4-02`): **0 dari 4.472 uji korelasi lead-lag lolos BH-FDR `q < 0,05`** (terkuat `35->73`, lag 11, `r = 0,528`, `q = 0,1488`), dan `reports/qa/eval_splits_summary.md` menandai `O1 Val dry` (`n = 43`) serta `O2 Val extreme_wet` (`n = 64`) ber-CI lebar.

---

### B. Empat Anomali Baru yang Ditemukan pada Sesi H5 (`ANOM-07` s/d `ANOM-10`)

#### `ANOM-07` [TINGGI — BUG KODE] — Kesalahan Kalkulasi Sanity Check pada `scripts/aggregate_ablation.py` (Baris 116–117)
- **Lokasi**: `scripts/aggregate_ablation.py` baris 116–117 dan output `reports/ablation/ablation_summary.md` baris 120.
- **Kode Bermasalah**:
  ```python
  abl_h10 = float(rows[rows["horizon"] == 10]
                  .groupby(["origin", "seed"])["mae"].mean().mean())
  ```
- **Dua Kesalahan Sekaligus**:
  1. Tidak memfilter `rows["variant"] == "full"`, sehingga merata-ratakan **seluruh 5 varian ablasi** (`full`, `no_climate`, `no_lag`, `no_gate`, `no_calendar`).
  2. Menggunakan *unweighted mean* antar-rezim (`["mae"].mean()`), bukan rata-rata berbobot jumlah node-hari (`n`) seperti yang dipakai di tabel baris 11, `ablation_overall.csv`, dan `experiments/registry.csv`.
- **Dampak Numerik Terverifikasi**:
  - Nilai salah yang tercetak di `ablation_summary.md` baris 120: **`9.490,31`** (`delta +2.625,50` vs H5-01 `6.864,81`).
  - Nilai `full` unweighted (seandainya terfilter): `9.306,06`.
  - Nilai `full` weighted aktual (konsisten dengan `ablation_overall.csv` & `registry.csv`): **`8.168,40`** (`delta +1.303,59` vs H5-01 `6.864,81`) — **selisih kesalahan lapor `+Rp1.321,91/kg`!**
- **Tindakan Wajib (`MLE`, segera sebelum Gate 2)**: Ambil `abl_h10` langsung dari `overall[(overall["variant"] == "full") & (overall["horizon"] == 10)]["mean_mae"].iloc[0]` (`8.168,40`) dan regenerasi `reports/ablation/ablation_summary.md`.

#### `ANOM-08` [SEDANG — TATA KELOLA REGISTRY] — Polusi Kolom `model` & Inkonsistensi Bobot `val_mae` di `experiments/registry.csv`
- **Temuan 1 (Pencampuran Keluarga Run)**: `experiments/registry.csv` (`243` baris) hanya memiliki 7 kolom (`run_id, model, origin, seed, split_hash, val_mae, status`). Skrip `run_ablation.py` menulis 75 run 1-epoch 5-varian dengan `model = module23`, sedangkan `robustness.py` menulis 42 run perturbasi `O3` dengan `model = module1` (21) dan `model = gwn` (21). Akibatnya, agregasi naif per kolom `model` menghasilkan angka kacau (`module23 O1 = 10.885,89`, `CV = 24,83%`; `gwn` tampak punya 21 run padahal 0 run penuh `O1–O3`).
- **Temuan 2 (Perbedaan Definisi `val_mae`)**: `scripts/robustness.py` baris 107 menulis `val_mae = float(primary["mae"].mean())` (**unweighted** antar-rezim), berbeda dari `scripts/run_ablation.py` baris 125 yang memakai **weighted mean by node-days** (`np.average(primary["mae"], weights=primary["n"])`). Contoh verifikasi pada `O3`:
  - `robustness_gwn_clean_s0`: `registry.csv = 4.404,66` (unweighted) vs weighted aktual = **`4.239,21`** (selisih `+Rp165,45/kg`).
  - `robustness_module1_clean_s0`: `registry.csv = 4.105,03` (unweighted) vs weighted aktual = **`3.985,78`** (selisih `+Rp119,25/kg`).
- **Tindakan Wajib (`MLE` & `CGS`)**: Ubah baris 107 `scripts/robustness.py` menjadi rata-rata berbobot `n` agar konsisten dengan `run_ablation.py` dan `eval`, serta selalu filter `run_id` per prefiks eksperimen (`h3/h4/h5_module23` vs `ablation_` vs `robustness_`) pada tabel Gate 2.

#### `ANOM-09` [SEDANG — ANOMALI EMPIRIS `module23` & `ablation`] — Degradasi `module23` 2-Epoch & Unggulnya `no_calendar` di 3/3 Horizon
- **Temuan 1 (`module23` vs `ablation_full` pada `O2`)**: Pada `O2 s0` dan `O2 s4`, `h5_module23` (2 epoch) dan `ablation_full` (1 epoch) identik hingga 2 desimal (`7.122,14` & `8.882,81`, artinya `best_epoch = 1`). Namun pada `O2 s1..s3`, 2-epoch `h5_module23` justru memiliki `val_h10_mae` lebih buruk daripada 1-epoch `ablation_full` (`8.420,77 vs 8.153,69`, `8.769,80 vs 8.403,06`, `9.040,49 vs 8.606,12`, selisih `+Rp267` s/d `+Rp434/kg`) karena seleksi checkpoint memantau multi-horizon log-loss, bukan `h=10` Rp/kg.
- **Temuan 2 (`no_calendar` & `no_climate` pada Ablasi 1-Epoch)**:
  - `no_gate` (+6,71% pada `h=10`) dan `no_lag` (+4,81% pada `h=10`, +7,35% pada `h=20`) memperburuk MAE (mendukung nilai tambah gate dan lag), **namun** `no_calendar` justru **mengungguli `full` di 3/3 horizon** (`h=5: -2,22%`, `h=10: -5,35% / -Rp437,08`, `h=20: -2,17%`) dan `no_climate` mengungguli `full` di rezim `el_nino` (`h=10: -Rp2.166,04`, `h=20: -Rp3.233,72`).
- **Tindakan Wajib (`MLE`, sebelum `MLE-H5-03`)**: Uji apakah kekalahan fitur kalender & iklim di `el_nino` hilang setelah pelatihan terkonvergensi (`>= 10–30 epoch`) atau apakah fitur kalender pada `module23` memang perlu dimatikan/diregularisasi sebelum pembekuan Gate 2.

#### `ANOM-10` [RENDAH — KONSISTENSI ARTEFAK PERTURBASI] — Dua Format Mask di `data/processed/perturbations/` & Catatan Limitasi `CGS-H5-01`
- **Temuan**: Folder `data/processed/perturbations/` kini berisi dua sistem file terpisah: `manifest.csv` + `masks.npz` (lokal dari `src/renaro/graph_perturb.py` milik CGS/MLE) dan `index.csv` + `src/renaro/graph/perturb.py` (paket MDE-H4-02 yang baru masuk di `7e5b76d`). Baris 88 `reports/robustness/robustness_summary.md` masih menulis bahwa paket MDE-H4-02 belum tersedia. Selain itu, train-mode `CGS-H5-01` memakai 3 seed (`0..2`) dan subset `p={10,50}` tanpa `p=30` (sudah dicatat transparan di bagian Limitasi).
- **Tindakan Wajib (`CGS` & `MDE`)**: Klarifikasi satu sumber kebenaran mask perturbasi di laporan akhir H7 (atau catat bahwa evaluasi `CGS-H5-01` dijalankan sebelum merge `7e5b76d` menggunakan `masks.npz`).

---

## 4. Pesan Eskalasi Siap Kirim ke MLE (`@agusprasetya`) & CGS — Pra-Gate 2 (H5 · 16.30 WIB)

> **Subjek**: `[RL-H4-02 · Sesi H5] Audit 243 Run (commit 54791ba) — Bug Aggregate Ablation & 4 Bloker Wajib Sebelum Gate 2 (16.30 WIB)`
>
> Audit RL Sesi H5 atas 243 run `experiments/registry.csv` (+30 sintetis) pada commit `54791ba` mencatat **0 kebocoran data**, **100% `split_hash` seragam**, **0 holdout disentuh**, perbaikan dramatis pada `latent_regime` (`O2 Test CV` anjlok `11,60% -> 0,98%`), serta stabilitas tinggi `module1` di `CGS-H5-01` (`7/7` mask `CV <= 3,80%`, degradasi `p=50` jauh lebih rendah dari `gwn`).
>
> Namun masih terdapat **5 temuan wajib diselesaikan sebelum Gate 2 (Jumat 27 Nov 2026, 16.30 WIB)**:
> 1. **[BUG KODE — `ANOM-07`] Perbaiki `scripts/aggregate_ablation.py` L116–117**: baris sanity check lupa memfilter `variant == "full"` dan tidak berbobot `n`, sehingga `ablation_summary.md` L120 salah mencetak `9.490,31` padahal `full` berbobot aktual = `8.168,40` (selisih `+Rp1.322/kg`). Mohon perbaiki dan regenerasi `ablation_summary.md`.
> 2. **[KRITIS — `ANOM-02`, `ANOM-03`, `ANOM-09`] Samakan `epochs` pada refit `MLE-H5-03`**: saat ini `latent_regime` (`10 ep`, `CV <= 2,36%`, Test `7.020`) vs `lag_graph`/`module1` (`5 ep`, `CV 6,4%–10,9%`, Test `7.128–7.321`) vs `module23` (`2 ep`, `CV 6,9%–9,2%`, Test `7.581`) vs `ablation` (`1 ep`, `O1 CV 13%–28,3%`) sangat timpang anggaran latihnya. Mohon samakan `epochs` (minimal seragam `>= 10–30` dengan early stopping) dan cek efek fitur kalender (`no_calendar` mengalahkan `full` `-5,35%` di 1 epoch).
> 3. **[KRITIS BLOKER GATE 2 — `ANOM-05`] Lengkapi baseline penuh `gwn` & `mtgnn` (`O1–O3` × 5 seed `0..4`)**: 21 run `gwn` di `registry.csv` hanyalah `robustness_gwn_*` di `O3` (3 seed, 2 epoch), sedangkan `mtgnn` masih `0 run` riil. Model yang belum lengkap pada 16.30 WIB akan dikeluarkan dari holdout sesuai protokol Gate 2.
> 4. **[TINGGI — `ANOM-04`] Tegakkan `git_sha_clean()`, simpan `ckpt.pt`, & buat `frozen/manifest.yaml`**: `lag_graph`, `latent_regime`, dan `module23` saat ini belum menyimpan `ckpt.pt`, dan `0/8` runner non-`train.py` memanggil `git_sha_clean()`.
> 5. **[SEDANG — `ANOM-08`, `ANOM-10`] Konsistensi bobot `val_mae` & catatan mask `CGS-H5-01`**: ubah `scripts/robustness.py` L107 ke rata-rata berbobot `n` agar konsisten dengan `run_ablation.py`, dan selaraskan catatan sumber mask (`masks.npz` vs MDE `index.csv`) di `reports/robustness/robustness_summary.md`.
