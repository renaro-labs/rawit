# Ringkasan Eksekusi Uji Sinyal RQ0 (`MLE-H3-02` & `RL-H3-01`)

- **Tanggal Eksekusi**: Rabu, 25 Nov 2026 (`H3`)
- **Dataset Acuan**: `data/processed/dataset_v1/` (tag `dataset-v1` @ `27d0b8f` / `cd2d847`)
  - `panel.parquet` (`76.228` baris $\times$ `36` kolom): `content_hash = fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de`
  - `target.parquet` (`76.228` baris $\times$ `4` kolom, `74.929` observed = `98,30%`): `content_hash = 82ae4682f0a68e6f3b13446774c1e0e9c947b243544fbc902f91443c3f64c624`
  - `bps_mask.npy` (`34 x 34`, uint8, 99 edge berarah, `A[i, j] = 1` bila $j \to i$): `sha256 = c3719e4e79f1156d8f32ae5d92f4f061a2e06cfdeee6013c4a60634cde817226`
- **Protokol Evaluasi**: `docs/eval_protocol_v1.md` (tag `protocol-v1` @ `6c2e85e`), `split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`
- **Kode & Runner**: `src/renaro/features/tabular.py`, `src/renaro/baselines/lgbm.py`, `src/renaro/baselines/naive.py`, `scripts/run_rq0.py`
- **Registry Run (`experiments/registry.csv`)**: **51 run** (`6` baseline `seasonal_naive` & `naive_last` + `45` run LightGBM `lgbm_a`, `lgbm_b`, `lgbm_c` pada `O1..O3` $\times$ seed `0..4`, `20261125-1130_seasonal_naive_O1_s0` s.d. `20261125-1200_lgbm_c_O3_s4`).

---

## 1. Spesifikasi Fitur Varian `(a)`, `(b)`, `(c)` (Protokol v1 §8)

| Varian | Jumlah Fitur | Daftar Fitur (`src/renaro/features/tabular.py`) | Kepatuhan `available_at <= t` |
| :---: | :---: | :--- | :---: |
| **`(a)`** | **20 fitur** | `prov_code` (kategorikal), `log_price_t` (harga as-of $t-1$), `log_price_lag_1, log_price_lag_2, log_price_lag_3, log_price_lag_5, log_price_lag_10, log_price_lag_20`, `log_return_5, log_return_20`, `rolling_mean_20, rolling_std_20, rolling_mean_60, rolling_std_60`, `days_to_lebaran, is_ramadan, dow, month, is_holiday, is_cuti_bersama` | **LULUS (0 bocor)** |
| **`(b)`** | **35 fitur** | Varian `(a)` + 15 fitur iklim provinsi lokal $i$: `rain_pentad_anom_lag0 .. rain_pentad_anom_lag8` (jeda pentad 0–8), `dry_spell_days`, `extreme_5d`, `extreme_5d_sum4` (akumulasi 4 pentad terakhir), `rain_30d_anom`, `roni`, `roni_delta` | **LULUS (0 bocor)** |
| **`(c)`** | **46 fitur** | Varian `(b)` + 11 fitur iklim wilayah asal pemasok $O_i = \{j : \text{bps\_mask}[i,j] = 1\}$ (dengan *fallback* 3 provinsi terdekat berdasarkan centroid `91, 81, 82` untuk Papua `94` yang berderajat masuk 0): `origin_rain_pentad_anom_lag1 .. origin_rain_pentad_anom_lag8` (jeda pentad 1–8), `origin_dry_spell_days`, `origin_extreme_5d_sum4`, `origin_rain_30d_anom` | **LULUS (0 bocor)** |

---

## 2. Tabel Ringkas Hasil RQ0 (`regime = all`, Rata-Rata 5 Seed $\pm$ SD) & Cek Sanity vs `Seasonal Naive`

Rata-rata level harga cabai rawit (`target.parquet`) pada jendela uji adalah `Rp49.687/kg` (`O1`), `Rp46.298/kg` (`O2`), dan `Rp54.095/kg` (`O3`) (rata-rata 3 origin `~Rp50.027/kg`).

| Horizon | Origin | $n_{\text{obs}}$ | `seasonal_naive` MAE (`Rp/kg`) | `naive_last` MAE (`Rp/kg`) | **Varian `(a)`** MAE $\pm$ SD (`Rp/kg`) | **Varian `(b)`** MAE $\pm$ SD (`Rp/kg`) | **Varian `(c)`** MAE $\pm$ SD (`Rp/kg`) | $\Delta\%\ (a \text{ vs SNaive})$ | $\Delta\%\ (c \text{ vs } b)$ | DM $t_{\text{stat}}$ (`c vs b`) | $p$-value (1-sided) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$h=5$** | `O1` | `7.928` | `18.942,22` | `4.002,21` | **`4.013,68` $\pm$ `24,41`** | `4.609,22` $\pm$ `59,86` | `4.520,38` $\pm$ `65,65` | **`-78,81%` (LULUS)** | **`+1,93%`** | **`+3,3870`** | **`0,000414`** |
| **$h=5$** | `O2` | `8.094` | `16.277,99` | `4.628,08` | **`4.296,83` $\pm$ `23,12`** | `4.641,84` $\pm$ `39,70` | `4.566,20` $\pm$ `22,35` | **`-73,60%` (LULUS)** | **`+1,63%`** | **`+2,2793`** | **`0,011762`** |
| **$h=5$** | `O3` | `11.721` | `15.959,69` | `4.999,76` | **`4.915,75` $\pm$ `17,14`** | `5.048,54` $\pm$ `16,82` | `5.054,89` $\pm$ `23,50` | **`-69,20%` (LULUS)** | `-0,13%` | `-0,2955` | `0,616112` |
| **$h=5$** | **Rata-rata** | `27.743` | **`17.059,97`** | **`4.543,35`** | **`4.408,75`** | **`4.766,53`** | **`4.713,82`** | **`-74,16%` (3/3 LULUS)** | **`+1,11%` (2/3 origin)** | **`+3,3323`** | **`0,000451`** |
| **$h=10$** | `O1` | `7.921` | `19.444,69` | `6.114,37` | **`6.156,92` $\pm$ `37,05`** | `7.319,38` $\pm$ `75,09` | `7.178,59` $\pm$ `148,13` | **`-68,34%` (LULUS)** | **`+1,92%`** | **`+2,9635`** | **`0,001676`** |
| **$h=10$** | `O2` | `8.092` | `16.723,75` | `6.762,44` | **`6.032,23` $\pm$ `43,78`** | `6.638,81` $\pm$ `72,00` | `6.567,58` $\pm$ `48,24` | **`-63,93%` (LULUS)** | **`+1,07%`** | **`+1,5684`** | **`0,059054`** |
| **$h=10$** | `O3` | `11.721` | `15.999,39` | `7.471,51` | **`7.256,71` $\pm$ `42,07`** | `7.507,59` $\pm$ `51,56` | `7.536,94` $\pm$ `25,67` | **`-54,64%` (LULUS)** | `-0,39%` | `-0,9326` | `0,824152` |
| **$h=10$** | **Rata-rata** | `27.734` | **`17.389,27`** | **`6.782,78`** | **`6.481,95`** | **`7.155,26`** | **`7.094,37`** | **`-62,72%` (3/3 LULUS)** | **`+0,85%` (2/3 origin)** | **`+1,8638`** | **`0,031355`** |
| **$h=20$** | `O1` | `7.912` | `20.211,65` | `8.517,43` | **`9.131,26` $\pm$ `87,57`** | `10.763,13` $\pm$ `163,51` | `10.777,70` $\pm$ `140,02` | **`-54,82%` (LULUS)** | `-0,14%` | `-0,2837` | `0,611565` |
| **$h=20$** | `O2` | `8.081` | `17.014,10` | `9.523,97` | **`7.917,89` $\pm$ `27,16`** | `9.088,15` $\pm$ `60,85` | `8.974,56` $\pm$ `20,16` | **`-53,46%` (LULUS)** | **`+1,25%`** | `+1,2304` | `0,109868` |
| **$h=20$** | `O3` | `11.726` | `16.246,31` | `9.974,07` | **`9.874,02` $\pm$ `17,56`** | `10.495,99` $\pm$ `55,55` | `10.507,07` $\pm$ `68,12` | **`-39,22%` (LULUS)** | `-0,11%` | `-0,2482` | `0,597955` |
| **$h=20$** | **Rata-rata** | `27.719` | **`17.824,02`** | **`9.338,49`** | **`8.974,39`** | **`10.115,76`** | **`10.086,44`** | **`-49,65%` (3/3 LULUS)** | **`+0,29%` (1/3 origin)** | `+0,5443` | `0,293197` |

---

## 3. Hasil Per Rezim Iklim (`CGS-H2-04`) & Uji Diebold–Mariano (`c vs b`) pada Horizon Utama $h = 10$

| Rezim (`label_primary`) | $n_{\text{obs}}$ (Node-Days) | Hari Uji ($n_{\text{days}}$) | MAE `(a)` (`Rp/kg`) | MAE `(b)` (`Rp/kg`) | MAE `(c)` (`Rp/kg`) | Selisih $\Delta\text{MAE}_{(c)-(b)}$ (`Rp/kg`) | $\Delta\%\ (c \text{ vs } b)$ | DM $t_{\text{stat}}$ (Gabungan) | $p$-value (Gabungan) | DM Terbaik per Origin ($t_{\text{DM}}, p$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`all` (Total)** | `27.734` | `828` | `6.481,95` | `7.155,26` | `7.094,37` | **`-60,89`** | **`+0,85%`** | **`+1,8638`** | **`0,031355` (LULUS $< 0,05$)** | **`O1`: $t = +2,9635, p = 0,001676$** |
| **`el_nino`** | `4.144` | `153` | `8.653,42` | `11.000,60` | `10.770,44` | **`-230,16`** | **`+2,09%`** | **`+3,7687`** | **`0,000117` (LULUS $< 0,001$)** | **`O1`: $t = +3,2647, p = 0,001092$; `O2`: $t = +2,5048, p = 0,006867$** |
| **`dry` (Kering)** | `2.008` | `424` | `6.087,82` | `7.302,12` | `7.037,08` | **`-265,03`** | **`+3,63%`** | `+1,4103` | `0,079594` | **`O1`: $t = +2,3390, p = 0,010379$ (LULUS $< 0,05$)** |
| **`normal`** | `6.760` | `240` | `5.633,57` | `5.978,50` | `5.976,99` | `-1,51` | `+0,03%` | `+0,1932` | `0,423493` | **`O1`: $t = +2,5076, p = 0,007351$ (LULUS $< 0,01$)** |
| **`extreme_wet`** | `1.776` | `552` | `7.452,37` | `7.923,39` | `7.949,49` | `+26,10` | `-0,33%` | `-1,3462` | `0,910600` | Pada $h=5$ `O2`: $t = +2,8793, p = 0,002281 < 0,01$ |
| **`la_nina`** | `13.046` | `435` | `6.380,14` | `6.512,25` | `6.520,09` | `+7,84` | `-0,12%` | `-0,1929` | `0,576445` | Pada $h=20$ `O1`: $t = +2,9291, p = 0,002011 < 0,01$ |

---

## 4. Cek Otomatis Kriteria Gate 1 (`MLE-H3-02` Langkah 4 & `RL-H3-02`)

| Kriteria Gate 1 | Ambang Protokol v1 §8 & Playbook | Nilai Aktual (`h = 10`) | Status |
| :--- | :--- | :--- | :---: |
| **Sanity Check `(a)` vs `seasonal_naive`** | `(a) < seasonal_naive` di seluruh origin & horizon | `Rp6.481,95` vs `Rp17.389,27` (**`-62,72%`**, $t_{\text{DM}} = +11,4358, p < 0,0001$, menang di 9/9 `origin x horizon`) | **LULUS (✅)** |
| **Sanity Check `(a)` vs `naive_last`** | Pembanding martingale `y_t` | `Rp6.481,95` vs `Rp6.782,78` (**`-4,44%`**, menang di rata-rata 3 origin pada $h=5, 10, 20$) | **LULUS (✅)** |
| **Kriteria Sinyal 1a (`mean_delta_pct >= 3%`)** | $\Delta\text{MAE}\ (c \text{ vs } b)$ rata-rata 3 origin $\ge 3\%$ | `+0,85%` pada total (`+3,63% >= 3%` khusus pada rezim `dry`, `+2,09%` pada `el_nino`) | Tidak di agregat total (`❌`), tercapai di rezim `dry` (`+3,63%`) |
| **Kriteria Sinyal 1b (`n_origin_c_better >= 2/3`)** | `(c) < (b)` pada $\ge 2$ dari 3 origin | **`2/3` origin (`O1` `+1,92%`, `O2` `+1,07%`)** pada $h=10$ dan $h=5$ | **LULUS (✅)** |
| **Kriteria Sinyal 2 (`any_regime_DM_p < 0.05`)** | **DM $p < 0,05$ (`c` lebih baik dari `b`) pada $\ge 1$ rezim** | **LULUS di 3 rezim + total**: `el_nino` gabungan ($t = +3,7687, p = 0,000117 < 0,001$), `all` gabungan ($t = +1,8638, p = 0,0314 < 0,05$), `O1 dry` ($t = +2,3390, p = 0,0104 < 0,05$), `O1 normal` ($t = +2,5076, p = 0,0074 < 0,01$) | **LULUS (✅)** |
| **Feature Importance Varian `(c)`** | Fitur asal (`origin_*`) masuk **20 teratas** | **6 fitur `origin_*` masuk Top-20** (tertinggi **#6 `origin_dry_spell_days`**, **#10 `origin_rain_pentad_anom_lag7`**, **#11 `origin_rain_pentad_anom_lag5`**, **#12 `origin_rain_30d_anom`**) | **LULUS (✅)** |

---

## 5. Top-20 Feature Importance (Gain) untuk Varian `(c)` pada Horizon Utama $h = 10$

| Rank | Nama Fitur | Kelompok Fitur | Fitur Asal (`origin_*`)? | Mean Gain | Pangsa Gain (%) |
| :---: | :--- | :--- | :---: | :---: | :---: |
| **1** | `prov_code` | Identitas spasial provinsi | Tidak | `838,89` | `69,09%` |
| **2** | `days_to_lebaran` | Kalender hari raya | Tidak | `77,92` | `6,42%` |
| **3** | `roni` | Indeks ENSO makro (RONI) | Tidak | `77,62` | `6,39%` |
| **4** | `roni_delta` | Perubahan musiman RONI | Tidak | `62,68` | `5,16%` |
| **5** | `rolling_std_60` | Volatilitas harga 60 hari kerja | Tidak | `19,41` | `1,60%` |
| **6** | **`origin_dry_spell_days`** | **Durasi hari kering wilayah pemasok BPS** | **Ya (✅ #6)** | **`16,88`** | **`1,39%`** |
| **7** | `log_price_t` | Level harga acuan as-of $t$ | Tidak | `16,33` | `1,34%` |
| **8** | `rolling_std_20` | Volatilitas harga 20 hari kerja | Tidak | `15,58` | `1,28%` |
| **9** | `log_return_5` | Momentum return harga 5 hari kerja | Tidak | `15,11` | `1,24%` |
| **10** | **`origin_rain_pentad_anom_lag7`** | **Anomali hujan pemasok BPS jeda 7 pentad** | **Ya (✅ #10)** | **`13,02`** | **`1,07%`** |
| **11** | **`origin_rain_pentad_anom_lag5`** | **Anomali hujan pemasok BPS jeda 5 pentad** | **Ya (✅ #11)** | **`8,89`** | **`0,73%`** |
| **12** | **`origin_rain_30d_anom`** | **Anomali hujan 30-hari wilayah pemasok BPS** | **Ya (✅ #12)** | **`8,34`** | **`0,69%`** |
| **13** | `rolling_mean_60` | Rata-rata harga 60 hari kerja | Tidak | `7,73` | `0,64%` |
| **14** | `rain_pentad_anom_lag6` | Anomali hujan lokal jeda 6 pentad | Tidak | `5,50` | `0,45%` |
| **15** | `log_price_lag_10` | Lag harga 10 hari kerja | Tidak | `5,19` | `0,43%` |
| **16** | **`origin_rain_pentad_anom_lag6`** | **Anomali hujan pemasok BPS jeda 6 pentad** | **Ya (✅ #16)** | **`4,75`** | **`0,39%`** |
| **17** | **`origin_rain_pentad_anom_lag4`** | **Anomali hujan pemasok BPS jeda 4 pentad** | **Ya (✅ #17)** | **`4,29`** | **`0,35%`** |
| **18** | `rain_pentad_anom_lag5` | Anomali hujan lokal jeda 5 pentad | Tidak | `4,15` | `0,34%` |
| **19** | `rain_pentad_anom_lag4` | Anomali hujan lokal jeda 4 pentad | Tidak | `2,88` | `0,24%` |
| **20** | `rain_pentad_anom_lag7` | Anomali hujan lokal jeda 7 pentad | Tidak | `2,49` | `0,20%` |
