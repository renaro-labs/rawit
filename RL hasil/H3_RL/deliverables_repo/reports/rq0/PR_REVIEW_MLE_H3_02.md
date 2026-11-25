# Komentar Review PR `job/MLE-H3-02` — RL-H3-01 (`@alim`)

- **Reviewer**: RL (*Research Lead*, `@alim`)
- **PR / Branch yang Direview**: `job/MLE-H3-02` (`MLE-H3-02 · Uji sinyal RQ0`)
- **Status Review**: **APPROVED (LULUS AUDIT PRA-RUN & PASCA-RUN — SIAP GATE 1 GO PENUH)**
- **Commit & Hash Acuan**:
  - `dataset_v1`: `panel.parquet` `content_hash = fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de` (`tag: dataset-v1` @ `27d0b8f` / `cd2d847`)
  - `protocol-v1`: `6c2e85e50b319fc7215dbac6d46c847fbf27b2f5`
  - `split_hash`: `411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`
  - `experiments/registry.csv`: `51` run (`20261125-1130_seasonal_naive_O1_s0` s.d. `20261125-1200_lgbm_c_O3_s4`)

---

## 1. Cek Pra-Run (11.00–11.30): Spesifikasi Fitur `(a)/(b)/(c)` (§8), Mask BPS, & `available_at <= t`

1. **Spesifikasi Fitur `(a)`, `(b)`, `(c)` (`src/renaro/features/tabular.py` & `src/renaro/baselines/lgbm.py`)**:
   - **`(a)` (20 fitur)**: `prov_code` (kategorikal), `log_price_t` (harga as-of $t-1$), lag log-harga sendiri `log_price_lag_{1,2,3,5,10,20}`, return `log_return_{5,20}`, rata-rata & std bergulir `rolling_{mean,std}_{20,60}`, serta kalender (`days_to_lebaran, is_ramadan, dow, month, is_holiday, is_cuti_bersama`).
   - **`(b)` (35 fitur)**: `(a)` + iklim provinsi sendiri (`rain_pentad_anom_lag0..8` pada jeda pentad 0–8, `dry_spell_days`, `extreme_5d`, `extreme_5d_sum4` dalam 4 pentad terakhir, `rain_30d_anom`, `roni`, `roni_delta`).
   - **`(c)` (46 fitur)**: `(b)` + iklim wilayah asal pemasok (`origin_rain_pentad_anom_lag1..8` pada jeda pentad 1–8, `origin_dry_spell_days`, `origin_extreme_5d_sum4`, `origin_rain_30d_anom`).
2. **Pemakaian Mask BPS (`bps_mask.npy`) di `dataset_v1`**:
   - Matriks `data/processed/dataset_v1/bps_mask.npy` (`34 x 34`, uint8, 99 edge berarah, `A[i, j] = 1` bila $j \to i$) dipakai langsung oleh `build_origin_weight_matrix(data.mask, data.nodes)` dengan normalisasi baris $w_{ij} = A_{ij} / \sum_k A_{ik}$.
   - Untuk satu-satunya provinsi tanpa pemasok antarprovinsi di BPS 2022 (**Papua `94`**, in-degree = 0), diterapkan *fallback* 3 provinsi terdekat berdasarkan centroid (`Papua Barat 91, Maluku 81, Maluku Utara 82`) sesuai Protokol v1 §8 & `reports/qa/bps_mask.md`.
3. **Verifikasi `available_at <= t` (0 Kebocoran Waktu)**:
   - Seluruh kolom `*__avail` di `dataset_v1/panel.parquet` (`price_lag__avail`, `prod_price__avail`, `climate__avail`, `roni__avail`) memenuhi `available_at <= date` pada 100% baris (`76.228` baris), dan diverifikasi otomatis oleh `tests/test_no_leakage.py` serta `tests/test_rq0_features.py`.

---

## 2. Cek Pasca-Run (15.00–15.30): Sanity Check `(a)` vs `Seasonal Naive` & Skala Level Harga (`Rp/kg`)

Level harga rata-rata cabai rawit (`target.parquet`) pada jendela uji adalah `Rp49.687/kg` (`O1`), `Rp46.298/kg` (`O2`), dan `Rp54.095/kg` (`O3`) (rata-rata 3 origin `~Rp50.027/kg`):
- **$h = 5$ (rata-rata 3 origin)**: `seasonal_naive` = `Rp17.059,97/kg` (`34,15%`) | `naive_last` = `Rp4.543,35/kg` (`9,13%`) | **Varian `(a)` = `Rp4.408,75/kg` (`8,87%`)** (**`-74,16%` vs `seasonal_naive`**, $t_{\text{DM}} = +18,6814, p < 0,0001$; **`-2,96%` vs `naive_last`**).
- **$h = 10$ (horizon utama, rata-rata 3 origin)**: `seasonal_naive` = `Rp17.389,27/kg` (`34,62%`) | `naive_last` = `Rp6.782,78/kg` (`13,71%`) | **Varian `(a)` = `Rp6.481,95/kg` (`13,16%`)** (**`-62,72%` vs `seasonal_naive`**, $t_{\text{DM}} = +11,4358, p < 0,0001$; **`-4,44%` vs `naive_last`**).
- **$h = 20$ (rata-rata 3 origin)**: `seasonal_naive` = `Rp17.824,02/kg` (`35,22%`) | `naive_last` = `Rp9.338,49/kg` (`18,77%`) | **Varian `(a)` = `Rp8.974,39/kg` (`18,25%`)** (**`-49,65%` vs `seasonal_naive`**, $t_{\text{DM}} = +7,0182, p < 0,0001$; **`-3,90%` vs `naive_last`**).
- **Verdict Sanity Check**: **LULUS 100%** di seluruh 9/9 kombinasi `origin x horizon`; skala MAE (`8,87%`–`18,25%` dari level harga `~Rp50.027/kg`) sangat masuk akal dan bebas dari bug skala maupun kebocoran target.

---

## 3. Evaluasi Sinyal RQ0 (`c vs b`) & Keputusan Gate 1 (`docs/decisions/GATE1.md`)

- **Perbandingan `(c)` vs `(b)` pada $h = 10$**:
  - `O1`: `(b) = Rp7.319,38` vs `(c) = Rp7.178,59` (**`+1,92%` / `-Rp140,79/kg`, $t_{\text{DM}} = +2,9635, p = 0,001676 < 0,01$**).
  - `O2`: `(b) = Rp6.638,81` vs `(c) = Rp6.567,58` (**`+1,07%` / `-Rp71,22/kg`, $t_{\text{DM}} = +1,5684, p = 0,0591$**).
  - `O3`: `(b) = Rp7.507,59` vs `(c) = Rp7.536,94` (`-0,39%`).
  - **Gabungan 3 origin (`all`, 828 hari)**: `(c)` mengalahkan `(b)` di **2/3 origin (`O1, O2`)** dan signifikan secara statistik pada uji Diebold–Mariano gabungan (**$t_{\text{DM}} = +1,8638, p = 0,031355 < 0,05$**; pada $h=5$ juga signifikan **$t_{\text{DM}} = +3,3323, p = 0,000451 < 0,001$**).
- **Uji Diebold–Mariano (`c vs b`) per Rezim Iklim ($h = 10$)**:
  - **Rezim `el_nino` (`153` hari, $n = 4.144$)**: **`t_DM = +3,7687`, `p = 0,000117 < 0,001`** (`-Rp230,16/kg` atau `+2,09%`; juga signifikan di `O1 el_nino` $p = 0,0011$, `O2 el_nino` $p = 0,0069$, dan $h=5$ `el_nino` $p = 0,000004$).
  - **Rezim `dry` (`424` hari, $n = 2.008$)**: penurunan MAE gabungan **`-Rp265,03/kg` (`+3,63% >= 3%`)**, dan signifikan secara statistik pada **`O1 dry` ($t_{\text{DM}} = +2,3390, p = 0,010379 < 0,05$)**.
  - **Rezim `normal` (`O1`, 65 hari)**: signifikan secara statistik (**$t_{\text{DM}} = +2,5076, p = 0,007351 < 0,01$**).
- **Feature Importance (Gain) Varian `(c)` ($h = 10$)**:
  - **6 fitur wilayah asal pemasok (`origin_*`) masuk Top-20**: `#6 origin_dry_spell_days`, `#10 origin_rain_pentad_anom_lag7`, `#11 origin_rain_pentad_anom_lag5`, `#12 origin_rain_30d_anom`, `#16 origin_rain_pentad_anom_lag6`, dan `#17 origin_rain_pentad_anom_lag4`.
- **Keputusan Gate 1 (`RL-H3-02`)**: **GO PENUH (Jalur A)** telah dikunci di `docs/decisions/GATE1.md` dan `docs/decisions/GATE1.tex`.
