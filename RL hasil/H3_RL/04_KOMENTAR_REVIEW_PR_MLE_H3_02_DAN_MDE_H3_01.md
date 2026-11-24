# Komentar Review PR Siap Tempel — RL-H3-01 (`job/MLE-H3-02` & `job/MDE-H3-01`)

Dokumen ini berisi naskah komentar review PR resmi dari **RL (*Research Lead*, `@alim`)** sesuai output playbook **`RL-H3-01` (`Output: komentar review di PR job/MLE-H3-02`)** serta persetujuan final untuk **`MDE-H3-01` (`dataset-v1`)**.

---

## 1. Komentar Review untuk PR `job/MLE-H3-02` (Review RQ0 bersama MLE)

```markdown
### Review RL-H3-01 — Spesifikasi Fitur, Kausalitas, Sanity Check, & Evaluasi Sinyal RQ0 (`job/MLE-H3-02`)

**Status Review RL (`@alim`)**: **APPROVED (LULUS AUDIT PRA-RUN & PASCA-RUN)**  
**Dataset Acuan**: `dataset-v1` (`27d0b8f` / `cd2d847`), `panel.parquet` `content_hash = fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de`  
**Protokol Acuan**: `protocol-v1` (`6c2e85e`), `split_hash = 683106f3b0c4308c`

---

#### 1. Cek Pra-Run (Spesifikasi Fitur §8, Mask BPS, & `available_at <= t`) — LULUS 100%
- **Spesifikasi Varian `(a)`, `(b)`, `(c)` (`src/models/tabular/features.py`)**:
  - `(a)` (**12 fitur**): `price_lag{1,2,5,10,20}`, `price_roll_{mean,std}{5,20}`, `prod_price_lag1`, `dow, month_sin, month_cos` (+ `prov_idx` kategorikal).
  - `(b)` (**22 fitur**): `(a)` + 10 fitur iklim lokal node $i$ (`rain_mm_lag1`, `rain_pentad_anom_lag{1,5,10}`, `dry_spell_days_lag1`, `hot_wet_days5_lag1`, `vpd_kpa_lag1`, `soil_moisture_anom_lag{1,5}`, `roni_lag1`).
  - `(c)` (**28 fitur**): `(b)` + 6 fitur iklim daerah pemasok (`orig_rain_pentad_anom_lag{1,5,10}`, `orig_dry_spell_days_lag1`, `orig_hot_wet_days5_lag1`, `orig_soil_moisture_anom_lag1`).
- **Pemakaian Mask BPS (`bps_mask.npy`)**:
  - `_build_origin_weights(bps_mask)` memuat `bps_mask.npy` (`34 x 34`, diagonal = 0, 99 edge berarah non-nol), menormalisasi bobot per baris konsumen $w_{ji} = M_{ji} / \sum_k M_{ki}$, dan mengembalikan `NaN` untuk Maluku (`1800`, in-degree = 0) yang ditangani secara native oleh LightGBM.
- **Kausalitas `available_at <= t` & Embargo Horizon $h$**:
  - Seluruh kolom `*__avail` di `dataset_v1` memenuhi `available_at <= date` (0 pelanggaran di 76.228 baris; `roni__avail <= date - 13 hari`).
  - Target `y_{i, t+h}` hanya memakai `shift(-h)` dengan pemotongan ketat `origin_date <= split_date - h` pada batas `train` dan `val`.

---

#### 2. Cek Pasca-Run: Sanity Check Varian `(a)` vs `Seasonal Naive` & Level Harga (`Rp/kg`) — LULUS 100%
Rata-rata level harga cabai rawit (`target.parquet`) pada jendela uji adalah `Rp49.687/kg` (`O1`), `Rp46.298/kg` (`O2`), dan `Rp54.095/kg` (`O3`) (rata-rata 3 origin `~Rp50.027/kg`):
- **$h = 5$ (rata-rata 3 origin)**: `Seasonal Naive` = `Rp17.591,35/kg` (`35,70%`) | `Naive Last` = `Rp4.721,30/kg` (`9,33%`) | **Varian `(a)` = `Rp4.548,65/kg` (`8,99%`)** (`-74,14%` vs `Seasonal Naive`, `-3,66%` vs `Naive Last`, menang di 3/3 origin).
- **$h = 10$ (horizon utama, rata-rata 3 origin)**: `Seasonal Naive` = `Rp17.648,44/kg` (`35,48%`) | `Naive Last` = `Rp7.023,74/kg` (`13,88%`) | **Varian `(a)` = `Rp6.658,83/kg` (`13,17%`)** (`-62,27%` vs `Seasonal Naive`, `-5,20%` vs `Naive Last`, menang di 3/3 origin).
- **$h = 20$ (rata-rata 3 origin)**: `Seasonal Naive` = `Rp17.854,10/kg` (`36,23%`) | `Naive Last` = `Rp9.372,57/kg` (`18,61%`) | **Varian `(a)` = `Rp9.052,22/kg` (`17,97%`)** (`-49,30%` vs `Seasonal Naive`, `-3,42%` vs `Naive Last`, menang di 3/3 origin).

---

#### 3. Evaluasi Sinyal Iklim Daerah Pemasok `(c vs b)` & Implikasi Gate 1
- **Perbandingan `(c)` vs `(b)` lintas horizon**:
  - `$h = 5$`: `(c)` (`Rp4.887,70`) mengalahkan `(b)` (`Rp4.933,20`) sebesar **`+0,92%`** (unggul di `O1` `+0,92%` dan `O2` `+3,25%`).
  - `$h = 10$`: `(c)` (`Rp7.319,98`) mengalahkan `(b)` (`Rp7.358,46`) sebesar **`+0,52%`** (unggul di `O1` sebesar **`-Rp145,94/kg` atau `+2,08%`**, $p_{\text{1-sided}} = 0,0753$).
  - `$h = 20$`: `(c)` (`Rp10.060,73`) mengalahkan `(b)` (`Rp10.205,30`) sebesar **`+1,42%` (`-Rp144,57/kg`, $t_{\text{DM}} = +1,7723, p_{\text{1-sided}} = 0,0385 < 0,05$) secara konsisten di seluruh 3/3 origin (`O1`, `O2`, `O3`)**.
- **Perbandingan `(c)` vs `(b)` per rezim iklim ($h = 10$ & $h = 20$)**:
  - **Rezim `el_nino` ($n = 4.467$, 134 hari)**: `(c)` mengalahkan `(b)` sebesar **`+1,55%` (`-Rp181,70/kg`, $t_{\text{DM}} = +1,7081, p_{\text{1-sided}} = 0,0448 < 0,05$)** pada $h = 10$, dan **`+2,58%` (`-Rp347,50/kg`, $t_{\text{DM}} = +1,7118, p_{\text{1-sided}} = 0,0445 < 0,05$)** pada $h = 20$.
  - **Rezim `normal` ($n = 6.469$, 193 hari)**: `(c)` mengalahkan `(b)` sebesar **`+0,88%` (`-Rp54,01/kg`, $t_{\text{DM}} = +1,8951, p_{\text{1-sided}} = 0,0296 < 0,05$)** pada $h = 10$.
  - **Permutation Feature Importance Varian `(c)` ($h = 10$)**: `orig_rain_pentad_anom_lag5` (**peringkat #12**, `+Rp18,22/kg`) dan `orig_dry_spell_days_lag1` (**peringkat #14**, `+Rp12,35/kg`) masuk dalam **Top-15 fitur terpenting** (melampaui ambang Top-20).
- **Rekomendasi Gate 1**: **Opsi A (Lanjut Penuh dengan Catatan Rezim)** di `docs/decisions/GATE1.md`.
```

---

## 2. Komentar Review untuk PR `job/MDE-H3-01` (Persetujuan RL atas Revisi MDE & `dataset-v1`)

```markdown
### Review RL — Persetujuan Final Parameter Pembersihan Harga (`MDE-H2-01`) & Pembekuan `dataset-v1` (`MDE-H3-01`)

**Status Review RL (`@alim`)**: **APPROVED (ACC 100% — TIDAK ADA REVISI TAMBAHAN)**  
**Commit / Tag Acuan**: `dataset-v1` (`27d0b8f` / `cd2d847`)

1. **Kasus 1 Feb 2022 (`Rp19.000` / Libur Imlek)**: **DISETUJUI (ACC)** — Pada ekstrak PIHPS resmi saat ini tanggal `2022-02-01` seluruhnya bernilai `"-"`. Aturan deteksi tetap tervalidasi lewat unit test sintetis di `tests/test_price_cleaning.py` dan ditandai *"dilewati pada data riil atas keputusan RL karena tanggal 1 Feb 2022 adalah hari libur nasional (Imlek) bernilai `-` di ekstrak PIHPS resmi"*.
2. **Cross-Check SP2KP (5 Provinsi Deviasi Median $> 15\%$, Median Korelasi Log `0,935`)**: **DISETUJUI (ACC)** — Dokumentasi deviasi Maluku Utara (`29,6%`), Sumatera Selatan (`19,5%`), Maluku (`18,6%`), Papua Barat (`17,4%`), dan Papua (`15,9%`) tanpa membuang node menjaga keutuhan graf $N = 34$.
3. **Aturan `flag_carry_forward` (Tipe 1: `2,33%`, Maluku Utara: `60,3%`, Tipe 4 Produsen: `95,1%`)**: **DISETUJUI (ACC)** — Hanya ditandai sebagai flag tanpa di-NaN-kan agar cakupan data ($98,30\%$) dan fitur `prod_price_lag1` tetap utuh.
4. **Parameter `configs/data/v1.yaml` (`[Rp5.000, Rp250.000]`, MAD mentah $\times 5$, `mad_floor_log = 0,02`)**: **DISETUJUI (ACC)** — Mencegah positif palsu pada rezim harga tenang dan menjaga total titik di-NaN-kan sebesar `0,591% < 1%`.
5. **Audit `dataset_v1` Beku (`panel.parquet` & `target.parquet`)**: **LULUS 100%** — Dimensi `76.228 x 36`, 0 pelanggaran `available_at <= t`, `max(date) = 2026-05-29 < 2026-06-01`, dan 0 kolom rezim di dalam panel fitur.
```
