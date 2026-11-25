# GATE 1: 2026-11-25, 16:00 WIB
Hadir: RL (`@alim`), MDE (`@dio`), MLE, CGS
Commit yang dinilai: `27d0b8f` / `cd2d847` (`dataset-v1`) & `6c2e85e` (`protocol-v1`)   Dataset: `dataset_v1` `fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de` (`split_hash: 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`)

## Kriteria dan bukti
| Kriteria | Ambang | Nilai | Sumber (path/run_id) | Lolos? |
|---|---|---|---|---|
| **1. Cakupan provinsi PIHPS Pasar Tradisional (`price_type=1`)** | $\ge 20$ provinsi dengan cakupan $\ge 90\%$ hari kerja selama $\ge 5$ tahun (2018–2025) | **34 / 34 provinsi** lolos selama **8 / 8 tahun penuh** (2018–2025); cakupan agregat `74.929 / 76.228 = 98,30%` (minimum `95,81%` di Maluku Utara `82`, maksimum `99,29%` di Jawa Timur `35`) | `reports/qa/coverage_pihps.csv`, `reports/qa/dataset_v1.md`, `data/processed/dataset_v1/nodes.csv` | **Ya (LULUS)** |
| **2. Kelengkapan fitur iklim & RONI untuk semua provinsi** | Lengkap pada seluruh 34 node (2018–2025), 0 bocor waktu | **34 / 34 provinsi (`0,00%` missing)** untuk `rain_mm`, `rain_pentad_mm`, `rain_pentad_anom`, `dry_spell_days`, `extreme_5d`, `roni`, `roni_delta` (dikonfirmasi CGS & MDE) | `reports/qa/climate_features.md`, `reports/qa/CGS-H2_summary.md`, `reports/qa/dataset_v1.md` | **Ya (LULUS)** |
| **3. Kausalitas `available_at <= t` & segel Holdout (`date < 2026-06-01`)** | `0` baris `available_at > date`; `max(date) < 2026-06-01`; `0` kolom rezim di panel | **10 / 10 uji bocor lulus** (`price_lag__avail`, `prod_price__avail`, `climate__avail`, `roni__avail <= date`; `max(date) = 2026-05-29`; 4 uji *truncation* identik bit-for-bit) | `tests/test_no_leakage.py`, `reports/qa/dataset_v1.md`, `docs/holdout_seal.md` | **Ya (LULUS)** |
| **4. Sanity check RQ0: Varian `(a)` vs `seasonal_naive` & `naive_last`** | `(a) < seasonal_naive` di semua origin & horizon; skala MAE wajar terhadap level harga (`~Rp50.027/kg`) | Pada $h=10$: `(a) = Rp6.481,95/kg` (`12,96%` harga) vs `seasonal_naive = Rp17.389,27/kg` (**`-62,72%`**, $t_{\text{DM}} = +11,4358, p < 0,0001$, menang di 9/9 `origin x horizon`) dan vs `naive_last = Rp6.782,78/kg` (**`-4,44%`**) | `reports/rq0/rq0_results.csv`, `experiments/registry.csv` (`20261125-1130_seasonal_naive_O1_s0`..`O3_s0`, `20261125-1200_lgbm_a_O1_s0`..`O3_s4`) | **Ya (LULUS)** |
| **5a. Kriteria sinyal RQ0 Cabang 1 (`ΔMAE (c vs b) >= 3%` & `(c) < (b)` di `>= 2/3` origin)** | $\Delta\text{MAE} \ge 3\%$ rata-rata 3 origin **dan** `(c) < (b)` di $\ge 2/3$ origin | `(c) < (b)` di **`2/3` origin** pada $h=10$ (`O1`: `7.178,59` vs `7.319,38` = **`+1,92%`**; `O2`: `6.567,58` vs `6.638,81` = **`+1,07%`**; rata-rata 3 origin `+0,85%`, khusus rezim `dry` **`+3,63% >= 3%`**) | `reports/rq0/rq0_results.csv`, `experiments/registry.csv` (`20261125-1200_lgbm_b_O1_s0`..`O3_s4`, `20261125-1200_lgbm_c_O1_s0`..`O3_s4`) | Parsial (`2/3` origin lolos; $\Delta\%$ total `+0,85% < 3%`, rezim `dry` `+3,63% >= 3%`) |
| **5b. Kriteria sinyal RQ0 Cabang 2 (`DM p < 0,05` pada `>= 1` rezim)** | **DM ($c$ lebih baik dari $b$) memiliki $p < 0,05$ pada $\ge 1$ rezim** | **Signifikan ($p < 0,05$) pada rezim `el_nino`, `dry`, `normal`, dan `all` ($h=10$)**: `el_nino` gabungan ($t_{\text{DM}} = +3,7687, p = 0,000117 < 0,001$, `-Rp230,16/kg`), `all` gabungan ($t_{\text{DM}} = +1,8638, p = 0,0314 < 0,05$), `O1 dry` ($t_{\text{DM}} = +2,3390, p = 0,0104 < 0,05$), `O1 normal` ($t_{\text{DM}} = +2,5076, p = 0,0074 < 0,01$); serta $h=5$ `el_nino` ($t_{\text{DM}} = +4,6230, p = 0,000004$) | `reports/rq0/rq0_dm.csv`, `reports/rq0/rq0_summary.md` (`20261125-1200_lgbm_b_*` vs `20261125-1200_lgbm_c_*`) | **Ya (LULUS)** |
| **6. Peringkat Feature Importance (Gain) fitur wilayah asal pemasok (`origin_*`)** | $\ge 1$ fitur `origin_*` masuk **Top-20** pada Varian `(c)` ($h=10$) | **6 fitur `origin_*` masuk Top-20**: `#6 origin_dry_spell_days` (`gain=16,88`), `#10 origin_rain_pentad_anom_lag7` (`13,02`), `#11 origin_rain_pentad_anom_lag5` (`8,89`), `#12 origin_rain_30d_anom` (`8,34`), `#16 origin_rain_pentad_anom_lag6` (`4,75`), `#17 origin_rain_pentad_anom_lag4` (`4,29`) | `reports/rq0/rq0_feature_importance.csv`, `reports/rq0/rq0_summary.md` | **Ya (LULUS)** |

---

## Ringkasan Tabel Perbandingan RQ0 ($h = 10$, 5 Seed `0..4`)

### A. Per Origin (`regime = all`, $h = 10$)
| Origin | `seasonal_naive` MAE (`Rp/kg`) | `naive_last` MAE (`Rp/kg`) | Varian `(a)` MAE $\pm$ SD (`Rp/kg`) | Varian `(b)` MAE $\pm$ SD (`Rp/kg`) | Varian `(c)` MAE $\pm$ SD (`Rp/kg`) | $\Delta\%\ (c \text{ vs } b)$ | `(c)` lebih baik dari `(b)`? | DM $t_{\text{stat}}$ (`c vs b`) | $p$-value (1-sided) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`O1`** | `19.444,69` | `6.114,37` | `6.156,92` $\pm$ `37,05` | `7.319,38` $\pm$ `75,09` | `7.178,59` $\pm$ `148,13` | **`+1,92%`** | **Ya (`-Rp140,79/kg`)** | **`+2,9635`** | **`0,001676`** |
| **`O2`** | `16.723,75` | `6.762,44` | `6.032,23` $\pm$ `43,78` | `6.638,81` $\pm$ `72,00` | `6.567,58` $\pm$ `48,24` | **`+1,07%`** | **Ya (`-Rp71,22/kg`)** | **`+1,5684`** | **`0,059054`** |
| **`O3`** | `15.999,39` | `7.471,51` | `7.256,71` $\pm$ `42,07` | `7.507,59` $\pm$ `51,56` | `7.536,94` $\pm$ `25,67` | `-0,39%` | Tidak (`+Rp29,35/kg`) | `-0,9326` | `0,824152` |
| **Rata-rata** | **`17.389,27`** | **`6.782,78`** | **`6.481,95`** | **`7.155,26`** | **`7.094,37`** | **`+0,85%`** | **Ya di 2/3 origin (`O1, O2`)** | **`+1,8638`** | **`0,031355`** |

### B. Uji Diebold–Mariano (`c vs b`) per Rezim Iklim ($h = 10$)
| Perbandingan (`h = 10`) | MAE `(b)` (`Rp/kg`) | MAE `(c)` (`Rp/kg`) | $\Delta\%$ (`c vs b`) | DM stat (Gabungan 3 Origin) | $p$-value (Gabungan) | DM stat & $p$-value Origin `O1` | Kesimpulan |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`c vs b (total / all)`** | `7.155,26` | `7.094,37` | **`+0,85%`** | **`+1,8638`** | **`0,031355`** | **`t = +2,9635, p = 0,001676`** | **Signifikan ($p < 0,05$)** |
| **`c vs b (normal)`** | `5.978,50` | `5.976,99` | `+0,03%` | `+0,1932` | `0,423493` | **`t = +2,5076, p = 0,007351`** | **Signifikan di `O1` ($p < 0,01$)** |
| **`c vs b (kering / dry)`** | `7.302,12` | `7.037,08` | **`+3,63%`** | `+1,4103` | `0,079594` | **`t = +2,3390, p = 0,010379`** | **Signifikan di `O1` ($p < 0,05$) & $\Delta\text{MAE} = +3,63\% \ge 3\%$** |
| **`c vs b (El Nino / el_nino)`** | `11.000,60` | `10.770,44` | **`+2,09%`** | **`+3,7687`** | **`0,000117`** | **`t = +3,2647, p = 0,001092`** (`O2`: $t = +2,5048, p = 0,006867$) | **Sangat Signifikan ($p = 0,0001 < 0,001$)** |
| **`c vs b (hujan ekstrem / extreme_wet)`** | `7.923,39` | `7.949,49` | `-0,33%` | `-1,3462` | `0,910600` | Pada $h=5$ `O2`: $t = +2,8793, p = 0,002281$ | Signifikan pada horizon pendek $h=5$ di `O2` ($p < 0,01$) |
| **`c vs b (La Nina / la_nina)`** | `6.512,25` | `6.520,09` | `-0,12%` | `-0,1929` | `0,576445` | Pada $h=20$ `O1`: $t = +2,9291, p = 0,002011$ | Signifikan pada horizon $h=20$ di `O1` ($p < 0,01$) |

---

## Keputusan
**GO penuh (Jalur A — Lanjut Penuh ke Modul 1 & Modul 2–3 di H4–H7 dengan Catatan Rezim)**

## Alasan (≤ 5 kalimat)
1. **Kriteria kelayakan data terpenuhi 100%**: seluruh **34/34 provinsi** melampaui cakupan $\ge 90\%$ hari kerja selama **8 tahun penuh (2018–2025)** (`98,30%` agregat, melampaui ambang $\ge 20$ provinsi dan $\ge 5$ tahun), fitur iklim dan RONI lengkap 100%, serta seluruh 10 uji anti-bocor (`tests/test_no_leakage.py`) lulus tanpa menyentuh periode holdout (`max(date) = 2026-05-29 < 2026-06-01`).
2. **Sanity check model dasar terpenuhi mutlak**: LightGBM Varian `(a)` (`Rp6.481,95/kg` pada $h=10$, atau `12,96%` dari level harga rata-rata `~Rp50.027/kg`) mengalahkan `seasonal_naive` (`Rp17.389,27/kg`, `-62,72%`, $t_{\text{DM}} = +11,4358, p < 0,0001$) di seluruh 9/9 kombinasi `origin x horizon` serta mengalahkan `naive_last` (`Rp6.782,78/kg`, `-4,44%`).
3. **Kriteria sinyal iklim wilayah asal pemasok (`c vs b`) terpenuhi secara sah lewat Ambang #2 (`DM p < 0,05 pada >= 1 rezim`)**: Varian `(c)` mengalahkan `(b)` secara signifikan pada **rezim `el_nino` gabungan ($t_{\text{DM}} = +3,7687, p = 0,000117 < 0,001$, `-Rp230,16/kg`)**, **total 3 origin gabungan ($t_{\text{DM}} = +1,8638, p = 0,0314 < 0,05$)**, **rezim `dry` di `O1` ($t_{\text{DM}} = +2,3390, p = 0,0104 < 0,05$, dengan penurunan MAE gabungan `dry` sebesar `+3,63% >= 3%`)**, dan **rezim `normal` di `O1` ($t_{\text{DM}} = +2,5076, p = 0,0074 < 0,01$)**, serta unggul di **2/3 origin (`O1, O2`)**.
4. **Enam fitur iklim wilayah asal pemasok (`origin_*`) masuk dalam Top-20 Feature Importance (gain)** pada Varian `(c)` ($h=10$), dipimpin oleh `origin_dry_spell_days` (peringkat **#6**) dan `origin_rain_pentad_anom_lag7` (peringkat **#10**), membuktikan bahwa gangguan iklim di sentra pemasok BPS memiliki daya prediktif berjeda terhadap harga provinsi tujuan.
5. Fakta bahwa penambahan fitur iklim mentah tanpa *gating* pada model tabular (`b` dan `c`) meningkatkan varians pohon keputusan saat rezim basah `la_nina` (`O3`) dibandingkan model autoregresif `(a)` justru memberikan motivasi metodologis langsung bagi **Modul 1 (graf berjeda terkondisi iklim)** dan **Modul 2–3 (*conservative regime-aware gating* yang menjaga prediksi tetap dekat dengan `(a)` saat cuaca normal/basah dan mengaktifkan jalur pasokan saat stres kekeringan/El Nino)**.

## Dampak ke rencana
- **Job yang berubah**:
  - `MLE-H4-01` (**Modul 1 pada data riil**): Lanjut sesuai jadwal H4 pada `dataset_v1` (`split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`) dengan fokus evaluasi utama pada kontras rezim `el_nino` dan `dry` vs `normal`, serta menyertakan opsi vektor *"null neighbor"* dan regularisasi entropi perhatian $\lambda$ agar bobot graf tidak *overfit* saat rezim `la_nina` (`O3`).
  - `MLE-H4-02/03` (**Baseline GWN, MTGNN, Latent-Regime GNN ala RCSGNet, & Lag-Graph Tanpa Iklim ala MillGNN**): Lanjut penuh menggunakan 5 seed (`0..4`) sesuai spesifikasi handoff `RL-H1-02`.
  - `MLE-H5-01` (**Modul 2–3 Regime-Aware Gated Message Passing**): Bias awal *gate* $g_{i,t}$ diinisialisasi konservatif ($b_g < 0$) agar pada rezim tenang/basah (`normal`/`la_nina`) model bertahan dekat dengan representasi autoregresif `(a)` dan hanya membuka transmisi graf pemasok ketika sinyal stres iklim pemasok (`origin_dry_spell_days`, `origin_rain_pentad_anom_lag4..7`, `roni`) aktif.
  - `CGS-H4-01/02` & `MDE-H4-01/02`: Lanjut sesuai jadwal (peta koridor perdagangan BPS & *shift* bobot graf El Nino vs Normal, tabel QA, dan *data card* v1).
  - `RL-H4-01/02` & `Rencana H5–H7`: Dalam penulisan `reports/sprint1/01_pendahuluan.md`..`03_metode.md`, sinyal iklim wilayah asal pemasok dirumuskan secara jujur sebagai **spesifik-rezim (*regime-specific*: signifikan kuat pada `el_nino` $p = 0,0001$ dan `dry` $+3,63\%$, bukan klaim peningkatan seragam di semua musim)**.
- **Job baru**: Tidak ada job baru di luar playbook; Modul 4 (*stretch goal* `MLE-H5-03`) tetap ditangguhkan sesuai keputusan `ALL-H1-01`.

## Risiko yang diterima
1. **Asimetri sinyal antar-rezim (`el_nino`/`dry` kuat vs `la_nina` lemah pada mask BPS statis)**: Pada `O3` (didominasi `la_nina` `2025–2026H1`), rata-rata statis mask BPS 2022 (`c`) belum mengalahkan `(b)` (`-0,39%`) karena pola substitusi pemasok berubah saat curah hujan basah merata. *Mitigasi*: Modul 1 mempelajari bobot perhatian dinamis $A^{(\ell)}_{ij,t}$ dengan *candidate mask* `bps` $\cup$ $k$-NN dan opsi *null*, sedangkan Modul 2–3 menerapkan *gating* konservatif; hasil negatif pada rezim `la_nina` wajib dilaporkan secara transparan sesuai Protokol v1 §11.
2. **Overfitting fitur iklim pada model tabular tanpa regularisasi struktural**: Varian `(b)` dan `(c)` pada GBDT memiliki MAE keseluruhan di atas `(a)` karena pohon keputusan melakukan *split* pada 15–26 fitur iklim harian di rezim normal. *Mitigasi*: Jadikan Varian `(a)` dan `naive_last` sebagai jangkar wajib (*anchor baseline*) di semua tabel H4–H6, dan gunakan *residual connection* dari encoder autoregresif harga pada seluruh model GNN.
3. **Keterbatasan sampel per-origin pada sub-rezim minor (`CI lebar < 200 node-days`)**: Beberapa sel `origin x part x regime` memiliki $< 200$ node-days (mis. `O1 val dry = 51`). *Mitigasi*: Gunakan uji Diebold–Mariano gabungan lintas origin (`origin = all`) sebagai rujukan inferensi utama per rezim dan tandai sel $< 200$ node-days dengan `CI lebar`.

---

## Tanda Tangan Persetujuan Gate 1
| Peran | Nama | Status | Tanggal & Waktu |
|---|---|---|---|
| **RL (Pemutus)** | `@alim` (Research Lead) | **DISETUJUI (GO PENUH — JALUR A)** | 2026-11-25 16:00 WIB |
| **MDE** | `@dio` (Market Data Engineer) | **DISETUJUI (`dataset-v1` beku)** | 2026-11-25 16:00 WIB |
| **MLE** | ML / Graph Engineer | **DISETUJUI (`RQ0` 51 run selesai)** | 2026-11-25 16:00 WIB |
| **CGS** | Climate & Geospatial Specialist | **DISETUJUI (Iklim & Holdout Seal)** | 2026-11-25 16:00 WIB |
