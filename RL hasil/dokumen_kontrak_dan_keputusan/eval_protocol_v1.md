# RL-H2-01 · Protokol Evaluasi v1.0 (TERKUNCI)
**Proyek:** Climate-Conditioned Dynamic Graph Learning for Food Price Forecasting Under Extreme Weather and Climate Regime Shifts (Sprint 1)

```text
Status: TERKUNCI · Tanggal: 2026-11-24 (H2) · Disetujui: RL, MDE, MLE, CGS
Tag Git: protocol-v1
Perubahan setelah ini hanya lewat docs/protocol_amendments.md, dengan alasan tertulis dan dicatat sebelum hasil holdout diketahui.
```

---

## 1. Ringkasan Perubahan dari v0 (`eval_protocol_v0`) ke v1 (`eval_protocol_v1`)

| Butir Protokol | Protokol v0 (Draf H1) | Protokol v1 (Final Terkunci H2) | Sumber / Bukti Verifikasi |
| :--- | :--- | :--- | :--- |
| **Horizon prediksi** | `h = 5, 10, 20` hari kerja; utama `h = 10` | **TETAP / DIKUNCI**: `h = [5, 10, 20]` hari kerja; horizon utama `h = 10` | `docs/decisions/ALL-H1-01.md` (#1) |
| **Transformasi target** | $\log(P_{i,t})$; metrik di Rp/kg setelah $\exp(\hat{y})$ | **TETAP / DIKUNCI**: `log_level` ($\log P_{i,t+h}$); seluruh metrik dihitung di Rp/kg setelah $\hat{P} = \exp(\hat{y})$ | `docs/decisions/ALL-H1-01.md` (#2) |
| **Panjang jendela input (`window`)** | `60` hari kerja (~12 minggu / ~18 pentad) | **TETAP / DIKUNCI**: `window = 60` hari kerja (`panel_start = 2017-07-01` untuk pemanasan lag awal 2018) | `configs/global.yaml` & `reports/qa/coverage_pihps.md` |
| **Aturan `available_at` CHIRPS** | Opsi B utama (`pentad_end + 2d`), Opsi A sensitivitas | **DIKUNCI DENGAN BUKTI PROBE HTTP**: Opsi B utama (`pentad_end + 2 hari`, `final_sat` sebagai proksi prelim); Opsi A sensitivitas (`prelim_sat = pentad_end + 5 hari`; `final_sat` aktual median lag `55,5` hari) | `reports/qa/chirps_release_lag.md` & `reports/qa/chirps_release_lag_probe.csv` (`CGS-H2-03`) |
| **Aturan `available_at` RONI** | Day-10 bulan $m+1$ / konservatif | **DIKUNCI**: `vintage_or_conservative_3m` (menggunakan tanggal rilis vintage CPC jika ada, atau awal bulan `center_month + 3`); *as-of join* `available_at <= date` | `reports/qa/roni.md` & `reports/qa/availability.csv` (`CGS-H1-02`, `CGS-H2-03`) |
| **Aturan bobot produksi CHIRPS** | Produksi kab/kota pra-cutoff (fallback uniform) | **DIKUNCI (`year_plus_1`)**: Bobot luas (`area weights`) untuk `2017–2024`; bobot produksi cabai 2024 (514 kab/kota, `1.469.325` ton) untuk `2025–2026` | `docs/cgs_h2_data.md` & `reports/qa/rain_prov.md` (`CGS-H2-01`) |
| **Definisi Regime: Kering (`dry`)** | `< P20` selama $\ge 3$ pentad berturut-turut | **DIKUNCI**: `rain_pentad_mm < p20_global` baseline pra-2018 provinsi selama $\ge 3$ pentad berturut-turut (`9.804` node-days pada `< 2026-06-01`) | `docs/regime_definitions.md` & `reports/qa/regime_counts.md` (`CGS-H2-04`) |
| **Definisi Regime: Ekstrem Basah (`extreme_wet`)** | `> P95` pentad (`extreme_5d == 1`) | **DIKUNCI**: `extreme_5d == 1` (akumulasi pentad $> P_{95}$ baseline provinsi; baseline rate `5,56%`, `7.100` node-days) | `docs/regime_definitions.md` & `reports/qa/climate_features.md` (`CGS-H2-02/04`) |
| **Urutan prioritas label utama (`label_primary`)** | `dry > extreme > ENSO > normal` | **DIKUNCI**: `dry > extreme_wet > el_nino > la_nina > normal` (bendera multi-label tetap disimpan; sel `< 200` node-days diberi flag `CI lebar`) | `docs/regime_definitions.md` & `reports/qa/regime_counts.md` (`CGS-H2-04`) |
| **Batas tanggal Holdout tersegel** | Mulai `2026-06-01` s.d. akhir data | **DIKUNCI**: `2026-06-01` s.d. `2026-10-31` (`tgl_akhir_holdout = min(PIHPS, CHIRPS final) = 2026-10-31`, 153 hari kalender CHIRPS final, disegel di `D:\renaro_sealed\holdout_v1`) | `docs/holdout_seal.md` (`CGS-H3-02`) |
| **Ambang verifikasi sintetis** | Korelasi peringkat $> 0{,}8$ (1-edge) / $> 0{,}7$ (multi-edge) | **TETAP / DIKUNCI**: Spearman $\rho > 0{,}80$ (graf 1-edge) dan $\rho > 0{,}70$ (graf 5-edge), MAE lag $\le 1{,}0$ pentad, AUROC edge $> 0{,}85$ | Brief v2 §8.3 & §5.10 protokol ini |
| **Origin rolling-origin & Embargo** | `O1`, `O2`, `O3` + `HOLDOUT`; embargo `20` hari kerja | **TETAP / DIKUNCI**: `O1` (Test 2023), `O2` (Test 2024), `O3` (Test 2025–Mei 2026), `HOLDOUT` (Mulai Juni 2026); embargo `20` hari kerja | `src/renaro/contract.py` & `configs/global.yaml` |

---

## 2. Nilai yang Dibekukan (Konsisten 100% dengan `configs/global.yaml`)

Seluruh script pemodelan dan evaluasi wajib membaca parameter berikut langsung dari `configs/global.yaml`:

| Field di `configs/global.yaml` | Nilai Terkunci | Rujukan Bukti / Dokumen |
| :--- | :--- | :--- |
| `train_start` | `"2018-01-02"` | Brief v2 §7.2; `panel_start: "2017-07-01"` dipakai khusus pemanasan lag 60 hari kerja |
| `holdout_start` | `"2026-06-01"` | Brief v2 §7.2 & `docs/holdout_seal.md` |
| `holdout_end` | `"2026-10-31"` | `docs/holdout_seal.md` (`min(PIHPS, CHIRPS final)`) |
| `horizons` | `[5, 10, 20]` (utama: `primary_horizon: 10`) | `docs/decisions/ALL-H1-01.md` (#1) |
| `embargo_workdays` | `20` | `docs/decisions/ALL-H1-01.md` (#4); $\ge \max(h) = 20$ hari kerja |
| `seeds` | `[0, 1, 2, 3, 4]` | Brief v2 §8 |
| `origins` | `O1`, `O2`, `O3`, `HOLDOUT` | `src/renaro/contract.py` (`ORIGINS`) |
| `window` / `window_workdays` | `60` | §1 protokol ini |
| `regime_definitions` | `priority_order: [dry, extreme_wet, el_nino, la_nina, normal]`, `drought_quantile: 0.20`, `drought_min_pentads: 3`, `extreme_quantile: 0.95`, `min_node_days_ci_flag: 200` | `docs/regime_definitions.md` & `reports/qa/regime_counts.md` (`CGS-H2-04`) |
| `chirps_availability` | `primary_option: "B"` (`pentad_end_plus_lag`, `lag_days: 2`), `sensitivity_option: "A"` (`release_timestamp`, `lag_days: 5`) | `reports/qa/availability.csv` & `reports/qa/chirps_release_lag.md` (`CGS-H2-03`) |

---

## 3. Definisi Regime Final (`CGS-H2-04` — Khusus Evaluasi, DILARANG Masuk Fitur Model)

Berdasarkan `docs/regime_definitions.md` dan `reports/qa/regime_counts.md` yang telah diverifikasi melalui 37 pemeriksaan otomatis (`verify_cgs_h2.py`):

1. **Larangan Keras Kebocoran Fitur**: Tabel `regime_labels.csv` adalah **EVAL ONLY**. Kolom-kolomnya (`enso_phase`, `episode_id`, `is_dry`, `is_extreme_rain`, `is_normal`, `label_primary`) **dilarang keras** di-join ke `panel.parquet` atau dipakai sebagai input fitur maupun gerbang model.
2. **Definisi Empat Kondisi Iklim & Normal**:
   - **ENSO (`el_nino` / `la_nina` / `neutral`)**: Diturunkan dari tabel episode resmi RONI (`data/raw/enso/roni.csv`) dengan aturan 5-musim berturut-turut NOAA ($\ge +0{,}5^\circ\text{C}$ untuk `el_nino`, $\le -0{,}5^\circ\text{C}$ untuk `la_nina`). Untuk setiap tanggal $t$, label menggunakan musim terbaru yang memiliki `available_at <= t` (*as-of join*).
   - **Kekeringan Lokal (`dry`)**: `rain_pentad_mm < p20_global` selama $\ge 3$ pentad berturut-turut pada provinsi tersebut (`p20_global` adalah persentil ke-20 dari pentad baseline pra-2018 provinsi tersebut). Label diterapkan ke seluruh hari kalender di dalam pentad yang memenuhi syarat.
   - **Hujan Ekstrem Lokal (`extreme_wet`)**: `extreme_5d == 1`, yakni akumulasi curah hujan pentad di atas persentil ke-95 ($P_{95}$) baseline provinsi (5% exceedance rate; pada data penuh `2017–2026-05` tercatat `5,56%`).
   - **Normal (`normal`)**: Hari-provinsi yang tidak termasuk `dry`, tidak termasuk `extreme_wet`, dan berada pada fase ENSO `neutral`.
3. **Urutan Prioritas Label Utama (`label_primary`)**:
   - Apabila satu observasi `(date, prov_code)` memenuhi lebih dari satu kondisi, urutan prioritas label utama adalah:
     $$\texttt{dry} > \texttt{extreme\_wet} > \texttt{el\_nino} > \texttt{la\_nina} > \texttt{normal}.$$
   - Seluruh bendera biner individu (`is_dry`, `is_extreme_rain`, `enso_phase`) tetap dipertahankan untuk analisis sensitivitas multi-label.
4. **Distribusi Jumlah Sampel (`node_days`) per Origin dan Penanda `CI lebar` (`< 200` node-days)**:

| Origin | Split Part | `dry` | `extreme_wet` | `el_nino` | `la_nina` | `normal` | Sel dengan Flag `CI lebar` (`< 200` node-days) |
| :---: | :---: | ---: | ---: | ---: | ---: | ---: | :--- |
| **O1** | `train` | 5.596 | 3.011 | 5.918 | 27.799 | 13.470 | — |
| **O1** | `val` | 51 | 596 | 0 | 5.609 | 0 | `dry (51)`, `el_nino (0)`, `normal (0)` |
| **O1** | `test` (2023) | **1.990** | **402** | **2.341** | **5.669** | **2.008** | **Tidak ada (semua rezim di O1 test $\ge 402$ node-days)** |
| **O2** | `train` | 5.838 | 3.901 | 5.918 | 39.077 | 13.470 | — |
| **O2** | `val` | 1.799 | 108 | 2.341 | 0 | 2.008 | `extreme_wet (108)`, `la_nina (0)` |
| **O2** | `test` (2024) | **1.066** | **797** | **4.463** | **1.880** | **4.238** | **Tidak ada (semua rezim di O2 test $\ge 797$ node-days)** |
| **O3** | `train` | 7.897 | 4.514 | 12.722 | 39.077 | 16.438 | — |
| **O3** | `val` | 806 | 292 | 0 | 1.880 | 3.278 | `el_nino (0)` |
| **O3** | `test` (2025–Mei 2026) | **661** | **1.585** | **0** | **12.518** | **2.780** | `el_nino (0)` (tahun 2025–awal 2026 didominasi La Nina/Normal) |
| **HOLDOUT** | `train` | 9.109 | 5.974 | 12.722 | 49.013 | 22.496 | — |
| **HOLDOUT** | `val` | 255 | 417 | 0 | 4.462 | 0 | `el_nino (0)`, `normal (0)` |
| **HOLDOUT** | `test` (`2026-06..10`) | **SEALED** | **SEALED** | **SEALED** | **SEALED** | **SEALED** | Dibuka 1 kali oleh `CGS-H6-01` setelah Gate 2 |
| **TOTAL (`< 2026-06-01`)** | **Semua** | **9.804** | **7.100** | **12.722** | **58.311** | **28.955** | Total = `116.892` node-days kalender |

> **Catatan Metodologis Penting**: Pada jendela pengujian (`test`) gabungan lintas `O1`, `O2`, dan `O3`, setiap rezim memiliki ribuan observasi (`dry = 3.717`, `extreme_wet = 2.784`, `el_nino = 6.804`, `la_nina = 20.067`, `normal = 9.026` node-days), sehingga estimasi *Worst-Regime MAE* dan *Regime Gap* pada set pengujian memiliki daya statistik yang sangat kuat. Hanya `O3 test` untuk `el_nino` yang bernilai `0` (karena episode El Nino 2023/2024 telah berakhir sebelum 2025), sehingga metrik `el_nino` dihitung dari `O1 test` dan `O2 test`.

---

## 4. Aturan Ketersediaan Rilis Final (`available_at` — `CGS-H2-03`)

Seluruh 24 fitur dalam 7 keluarga fitur (`docs/feature_dict.csv`) wajib mematuhi tabel aturan `reports/qa/availability.csv` berikut saat dilakukan *as-of join* (`available_at <= t`):

| Keluarga Fitur (`feature_family`) | Sumber Data | Varian | Aturan (`rule`) | `lag_days` | Pemutus | Bukti Verifikasi |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `rain_daily_final` | CHIRPS v3.0 daily final/sat | `final_sat` | `pentad_end_plus_lag` | `2.0` | **RL** | `ALL-H1-01.md` (#3); `reports/qa/chirps_release_lag.md` (Opsi B utama) |
| `rain_pentad_final` | CHIRPS v3.0 daily final/sat | `final_sat` | `pentad_end_plus_lag` | `2.0` | **RL** | `ALL-H1-01.md` (#3); `reports/qa/chirps_release_lag.md` (Opsi B utama) |
| `rain_prelim` | CHIRPS v3.0 daily prelim/sat | `prelim_sat` | `release_timestamp` | `5.0` | **CGS** | `reports/qa/chirps_release_lag_probe.csv` (Opsi A sensitivitas) |
| `roni` | CPC NOAA RONI (ERSSTv6) | `all` | `vintage_or_conservative_3m` | `NaN` | **CGS** | `data/raw/enso/roni_vintage_log.csv`; `reports/qa/roni.md` (915 musim) |
| `production_weight` | Satudata Pertanian / BPS | `all` | `year_plus_1` | `NaN` | **protocol** | `reports/qa/produksi_kab.md` (produksi 2024 dipakai mulai 2025) |
| `calendar` | SKB 3 Menteri | `all` | `known_in_advance` | `NaN` | **protocol** | `docs/data_contract.md` §2.2 |
| `price` | PIHPS / SP2KP | `all` | `next_workday` | `1.0` | **protocol** | `docs/data_contract.md` §2.1 (harga hari $t$ dipakai untuk prediksi dari $t$ ke $t+h$) |

**Bukti Empiris HTTP HEAD Probe CHIRPS (`reports/qa/chirps_release_lag_probe.csv`)**:
- Dari 6 file CHIRPS `final` (`2026-08-01` s.d. `2026-10-31`), jeda publikasi `Last-Modified` berkisar antara `18` hingga `109` hari (median `55,5` hari).
- Dari 6 file CHIRPS `prelim` (`2026-10-01` s.d. `2026-11-20`), jeda publikasi berkisar antara `2` hingga `8` hari (median `4,0` hari; 3 file terbaru memiliki jeda tepat `2` hari).
- Oleh karena itu, **Opsi B (`pentad_end + 2 hari` dengan `final_sat` sebagai proksi operasional prelim)** dikunci sebagai protokol utama, dan **Opsi A (`prelim_sat` lag 5 hari / `final_sat` lag aktual)** dijalankan sebagai eksperimen sensitivitas.

---

## 5. Protokol Evaluasi Mengikat (Berlaku Penuh dari v0)

### 5.1 Unit Spasial, Frekuensi, Horizon, dan Transformasi Target
- **Unit Spasial**: $N = 34$ provinsi struktur lama (`prov_code` BPS 2 digit sesuai `PROVINCES` di `src/renaro/contract.py`). Berdasarkan audit `MDE-H1-03` (`reports/qa/coverage_pihps.md`), **34 dari 34 provinsi memiliki cakupan $\ge 90\%$ di seluruh 8 tahun (2018–2025)** sehingga ke-34 provinsi masuk ke dalam panel pemodelan dan evaluasi.
- **Frekuensi Waktu**: Hari kerja PIHPS (Senin–Jumat).
- **Horizon Prediksi**: $h \in \{5, 10, 20\}$ hari kerja ke depan, dengan **horizon utama $h = 10$**.
- **Target & Skala Metrik**: Model dilatih pada $y_{i,t+h} = \log(P_{i,t+h})$. Saat evaluasi, prediksi dikembalikan ke skala Rupiah melalui $\hat{P}_{i,t+h} = \exp(\hat{y}_{i,t+h})$ dan seluruh metrik wajib dihitung dalam **Rp/kg** hanya pada pasangan $(i, t+h)$ yang memiliki `is_observed == True`.

### 5.2 Skema Rolling-Origin dan Embargo 20 Hari Kerja
- Setiap batas antara `train` dan `val`, serta antara `val` dan `test`, dipisahkan oleh **embargo 20 hari kerja** (`embargo_workdays = 20` $\ge \max(h)$) agar target $t+20$ dari jendela sebelumnya tidak pernah bocor ke jendela berikutnya:
  - **O1**: Train `2018-01-02..2022-06-30` | Val `2022-07-01..2022-12-31` | Test `2023-01-01..2023-12-31`
  - **O2**: Train `2018-01-02..2023-06-30` | Val `2023-07-01..2023-12-31` | Test `2024-01-01..2024-12-31`
  - **O3**: Train `2018-01-02..2024-06-30` | Val `2024-07-01..2024-12-31` | Test `2025-01-01..2026-05-31`
  - **HOLDOUT**: Train `2018-01-02..2025-12-31` | Val `2026-01-01..2026-05-31` | Test `2026-06-01..2026-10-31` (**TERSEGEL** di `D:\renaro_sealed\holdout_v1`).

### 5.3 Metrik Evaluasi Wajib
Pada himpunan indeks observasi valid $\mathcal{I}_g = \{(i, t) \in g : \texttt{is\_observed}_{i,t+h} = \text{True}\}$:
1. $\text{MAE}_g = \frac{1}{|\mathcal{I}_g|} \sum_{(i,t) \in \mathcal{I}_g} |\hat{P}_{i,t+h} - P_{i,t+h}|$ (Rp/kg — **metrik utama**)
2. $\text{RMSE}_g = \sqrt{\frac{1}{|\mathcal{I}_g|} \sum_{(i,t) \in \mathcal{I}_g} (\hat{P}_{i,t+h} - P_{i,t+h})^2}$ (Rp/kg)
3. $\text{sMAPE}_g = \frac{100\%}{|\mathcal{I}_g|} \sum_{(i,t) \in \mathcal{I}_g} \frac{2|\hat{P}_{i,t+h} - P_{i,t+h}|}{|\hat{P}_{i,t+h}| + |P_{i,t+h}|}$ (%)
4. $\text{Worst-Regime MAE} = \max_{r \in \mathcal{R}} \text{MAE}_r$ dan $\text{Regime Gap} = \text{Worst-Regime MAE} - \text{MAE}_{\text{normal}}$.

### 5.4 Uji Signifikansi Statistik Diebold–Mariano & Koreksi Multi-Perbandingan
- Selisih loss harian rata-rata lintas provinsi $d_{t,h} = \frac{1}{|\mathcal{N}_t|} \sum_{i \in \mathcal{N}_t} (|\hat{e}^{(A)}_{i,t+h}| - |\hat{e}^{(B)}_{i,t+h}|)$ diuji menggunakan statistik **Diebold–Mariano** dengan estimator varians **Newey–West HAC** pada bandwidth $L = h - 1$.
- Koreksi multi-perbandingan menggunakan prosedur **Holm–Bonferroni** pada tingkat signifikansi keluarga $\alpha = 0{,}05$ di atas keluarga pengujian utama (horizon utama $h = 10$ terhadap 2 baseline pra-registrasi: baseline tabular/statis terbaik dan baseline rezim laten ala RCSGNet `MLE-H4-02`).

### 5.5 Protokol RQ0 (Gate 1), Verifikasi Sintetis, dan Robustness Perturbasi Prior
- **RQ0 (`MLE-H3-02`)**: Membandingkan LightGBM pada 3 paket fitur: **(a)** harga + kalender, **(b)** (a) + iklim provinsi sendiri + RONI, **(c)** (b) + iklim provinsi pemasok utama menurut `bps_mask.npy`. Syarat Gate 1: (b) atau (c) memperbaiki MAE terhadap (a) pada $\ge 1$ rezim non-normal atau horizon utama $h=10$.
- **Verifikasi Sintetis (`MLE-H3-01`)**: Pemulihan jeda harus mencapai korelasi peringkat Spearman $> 0{,}80$ (1-edge) dan $> 0{,}70$ (5-edge) sebelum mengklaim interpretasi jeda pada data riil.
- **Perturbasi Prior Graf (`MDE-H4-02` & `CGS-H5-01`)**: Menguji `bps_mask.npy` pada tingkat kesalahan $p \in \{10\%, 20\%, 30\%, 40\%, 50\%\}$ (`drop`, `add`, `rewire`, 3 seed struktural `0, 1, 2`) serta prior `distance`, `surplus_deficit`, dan `none`.
- **Reprodusibilitas**: Seluruh model neural wajib dijalankan pada **5 random seeds (`0, 1, 2, 3, 4`)** dan dilaporkan sebagai $\text{mean} \pm \text{sd}$ di atas $3 \text{ origin} \times 5 \text{ seed} = 15$ run.

---

## 6. Log Amandemen (`docs/protocol_amendments.md`)

| No | Tanggal | Alasan Perubahan | Disetujui Oleh |
| :-: | :---: | :--- | :---: |
| — | — | *Belum ada amandemen (Protokol v1.0 baru dikunci pada H2, 24 Nov 2026)* | — |

---

## 7. Pernyataan Penguncian & Persetujuan Empat Peran

Dengan menandatangani dan meng-commit dokumen ini bersama tag `protocol-v1`, seluruh tim menyatakan bahwa:
1. Protokol evaluasi ini dikunci sebelum model inti (Modul 1–3) dijalankan pada data riil;
2. Tidak ada pemilihan model atau *hyperparameter tuning* pada jendela `test` maupun `HOLDOUT`;
3. Data `HOLDOUT` (`2026-06-01..2026-10-31`) hanya dibuka satu kali oleh CGS pada H6 setelah lulus audit Gate 2;
4. Seluruh hasil negatif (termasuk apabila modul graf tidak mengalahkan baseline pada rezim tertentu) wajib dilaporkan apa adanya.

| Peran | Nama Anggota Tim | Status Persetujuan | Tanggal |
| :--- | :--- | :---: | :---: |
| **RL (*Research Lead*)** | Alim (`@alim`) | DISETUJUI & DIKUNCI | 2026-11-24 |
| **MDE (*Market Data Engineer*)** | Akashuten (`@akashuten`) | DISETUJUI (Data & Cakupan PIHPS H1) | 2026-11-24 |
| **MLE (*ML/Graph Modeling Engineer*)** | Agus Prasetya (`@agusprasetya`) | DISETUJUI (Env & Kontrak Loader H1) | 2026-11-24 |
| **CGS (*Climate & Geospatial Scientist*)** | Muhammad Fariq Faqih (`@fariqfaqih`) | DISETUJUI (CHIRPS, RONI, Regime, Holdout Seal) | 2026-11-24 |
