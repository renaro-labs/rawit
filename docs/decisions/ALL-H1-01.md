<!--
=============================================================================
  ALL-H1-01 · Keputusan Kickoff + Kontrak Data
  Role    : SEMUA (fasilitator RL, notulen MDE, peserta MLE & CGS)
  Sprint  : H1 · SEKUENSIAL (prasyarat semua job)
  Status  : DONE · 2026-11-23
  Target  : docs/decisions/ALL-H1-01.md (+ docs/data_contract.md, configs/global.yaml)
=============================================================================
-->

# ALL-H1-01 — Keputusan Kickoff & Kontrak Data Sprint 1

- **Waktu**: H1 (`2026-11-23`)
- **Fasilitator**: RL (*Research Lead*) · **Notulen**: MDE (*Market Data Engineer*)
- **Peserta**: RL, MDE, MLE (*ML/Graph Modeling Engineer*), CGS (*Climate & Geospatial Scientist*)
- **Referensi**: `Renaro_Research_Brief_Climate_GNN_Sprint1.pdf`, `shared/ALL-H1-01__kickoff_checklist.md`, `src/renaro/contract.py`, `RL/RL-H1-01__eval_protocol_v0.tex`, `CGS/CGS-H2-03__availability_table.py`

---

## 1. Ringkasan 4 Keputusan yang Dikunci

```text
1. Horizon        : h = 5, 10, 20 hari kerja; metrik utama h = 10 (window input = 60 hari kerja)
2. Target         : log(price) pada level harga pasar tradisional (price_type=1); metrik dihitung dalam Rp/kg setelah inverse exp()
3. CHIRPS         : Opsi B sebagai aturan utama (akhir pentad + 2 hari, memakai nilai final sebagai proksi prelim); Opsi A (jeda rilis aktual / prelim_sim) sebagai uji sensitivitas
4. Origin         : O1 / O2 / O3 + HOLDOUT sesuai ORIGINS di src/renaro/contract.py dengan embargo 20 hari kerja (holdout_start = 2026-06-01)
Disetujui oleh    : RL / MDE / MLE / CGS
Tanggal/jam       : 2026-11-23T06:50:00+07:00
```

---

## 2. Rincian & Alasan 4 Keputusan Terbuka

### Keputusan 1 — Horizon Prediksi (`h`) & Jendela Input
- **Nilai Terkunci**: `HORIZONS = (5, 10, 20)` hari kerja PIHPS; **`PRIMARY_HORIZON = 10`**; `WINDOW = 60` hari kerja; `EMBARGO_WORKDAYS = 20`.
- **Alasan**:
  - Selaras dengan kebutuhan operasional peringatan dini harga pangan 1–4 minggu kerja ke depan (Brief Hal. 6 & Hal. 12).
  - $h = 10$ (2 minggu kerja) dipilih sebagai metrik utama keputusan Gate 1 dan Gate 2 karena cukup panjang untuk menangkap jeda transmisi iklim/pasokan antarprovinsi (1–6 pentad), namun tidak terlalu jauh sehingga sinyal tidak terdilusi.
  - Embargo ditetapkan 20 hari kerja ($\ge \max(h)$) di antara akhir latih dan awal uji pada setiap origin agar tidak ada target yang tumpang tindih (*zero target overlap*).

### Keputusan 2 — Target Pemodelan & Skala Evaluasi Metrik
- **Nilai Terkunci**:
  - **Target model**: $\log(p_{i, t+h})$ (log natural dari level harga Cabai Merah Keriting pasar tradisional `price_type=1` dalam Rp/kg).
  - **Evaluasi metrik**: Prediksi model ditransformasi balik dengan $\hat{p}_{i, t+h} = \exp(\hat{y}_{i, t+h})$ ke dalam satuan **Rp/kg** sebelum menghitung **MAE**, **RMSE**, **sMAPE**, **worst-regime error**, dan **$\Delta$ error OOD**.
  - **Aturan validitas target**: Hanya observasi dengan `is_observed == True` dan bebas flag outlier/carry-forward (`target_mask == 1`) yang dievaluasi. Target **tidak pernah diimputasi**.
- **Alasan**:
  - Distribusi harga cabai merah sangat miring ke kanan (*right-skewed*, rentang Rp10.000–Rp170.000/kg di PIHPS tradisional). Melatih model pada skala $\log(p)$ menstabilkan gradien dan varians lintas rezim, sedangkan pelaporan metrik dalam Rp/kg menjaga interpretabilitas kebijakan dan keadilan perbandingan dengan baseline non-neural.

### Keputusan 3 — Aturan Ketersediaan (`available_at`) CHIRPS Final vs Prelim (`CGS-H2-03`)
- **Nilai Terkunci**:
  - **Utama — Opsi B (`pentad_end_plus_lag`, `lag_days = 2`)**: Data CHIRPS v3 `final_sat` (baik harian terdisagregasi maupun akumulasi pentad) untuk pentad yang berakhir pada tanggal $d_{\text{pentad}}$ ditetapkan memiliki `available_at` $= d_{\text{pentad}} + 2\text{ hari kalender}$ (memakai nilai final sebagai proksi rilis *prelim*).
  - **Sensitivitas — Opsi A (`release_timestamp` / `prelim_sim`)**: Menggunakan jeda rilis aktual (`pentad_end + 5d` untuk prelim dan `month_end + 21d` untuk final, diverifikasi lewat HTTP `Last-Modified` di `reports/qa/chirps_release_lag.md`).
  - **Harga PIHPS (`next_workday`, `lag_days = 1`)**: Harga hari kerja $t$ baru tersedia pada hari kerja berikutnya ($t+1$).
  - **RONI (`vintage_or_conservative_3m`)**: Menggunakan `vintage_date` rilis tabel CPC NOAA bila tercatat, atau aturan konservatif awal bulan `center_month + 3` (atau tanggal 10 bulan $m+2$ pada `dataset_v1`).
- **Alasan**:
  - Arsip historis CHIRPS `prelim_sat` untuk 2018–2025 tidak selalu tersimpan terpisah per vintage di server UCSB, sedangkan rilis operasional prelim muncul ~2 hari setelah akhir pentad. Mengunci Opsi B sebagai jalur utama memungkinkan pelatihan dan evaluasi konsisten sepanjang 2018–2026, sementara Opsi A menjaga kejujuran ilmiah melalui audit sensitivitas jeda rilis di `reports/qa/chirps_release_lag.md`.

### Keputusan 4 — Daftar Origin *Rolling-Origin* (`RL-H1-01`)
- **Nilai Terkunci** (sesuai `ORIGINS` di `src/renaro/contract.py` & `RL/RL-H1-01__eval_protocol_v0.tex` §3):

| Origin | Periode Latih (`train`) | Periode Validasi (`val`) | Periode Uji (`test`) | Embargo |
| :--- | :--- | :--- | :--- | :---: |
| **`O1`** | `2018-01-02 .. 2022-06-30` | `2022-07-01 .. 2022-12-31` | **`2023-01-01 .. 2023-12-31`** | 20 hari kerja |
| **`O2`** | `2018-01-02 .. 2023-06-30` | `2023-07-01 .. 2023-12-31` | **`2024-01-01 .. 2024-12-31`** | 20 hari kerja |
| **`O3`** | `2018-01-02 .. 2024-06-30` | `2024-07-01 .. 2024-12-31` | **`2025-01-01 .. 2026-05-31`** | 20 hari kerja |
| **`HOLDOUT`** | `2018-01-02 .. 2025-12-31` | `2026-01-01 .. 2026-05-31` | **`SEALED` ($\ge$ `2026-06-01`)** | 20 hari kerja |

- **Alasan**:
  - `O1` menguji tahun 2023 (onset El Niño kuat 2023), `O2` menguji tahun 2024 (puncak & peluruhan El Niño 2023/2024), dan `O3` menguji 2025 s/d Mei 2026 (fase netral/La Niña lemah menuju transisi 2026).
  - Ketiga origin memberi 3 lipatan evaluasi independen untuk syarat Gate 1 (*"(c) menurunkan MAE vs (b) $\ge 3\%$ rata-rata dan konsisten di $\ge 2/3$ origin, atau DM $p < 0{,}05$ di $\ge 1$ regime"*).

---

## 3. Kesepakatan Kontrak Data, Struktur Repo, & Pengaman Holdout

1. **Identitas Node & Matriks Graph**:
   - 34 provinsi struktur lama diidentifikasi menggunakan **`prov_code` BPS 2 digit (`"11"` Aceh s/d `"94"` Papua)** sesuai urutan `PROVINCES` di `src/renaro/contract.py` (dan didaftarkan di `data/ref/provinces.csv`).
   - Konvensi matriks adjacensi di paket `renaro`: **`A[i, j] = 1` bila ada aliran prediktif dari provinsi asal `j` $\to$ provinsi tujuan `i`** (baris = tujuan `i`, kolom = asal `j`), disimpan di `data/interim/bps_mask.npy` (`34x34 uint8`). Catatan: file tabel digitasi `data/interim/bps_mask_2022.csv` menyimpan `baris = src, kolom = dst` sesuai `bps_mask_TEMPLATE.csv`, sehingga `bps_mask.npy = bps_mask_2022_matrix.T`.
2. **Konvensi Branch, Commit, & Run Eksperimen**:
   - Branch utama: `main`; branch pekerjaan per job: `job/<JOB-ID>` (contoh: `job/MDE-H2-03`, `job/CGS-H2-01`).
   - Format pesan commit: `[<JOB-ID>] <ringkasan singkat>`.
   - Satu run eksperimen = satu folder `experiments/runs/<run_id>/` berisi `config.yaml`, `git_sha.txt`, `metrics.json`, `preds.parquet`, `ckpt.pt`, `A_by_regime.npz`, dan `log.txt`, serta dicatat di `experiments/registry.csv`.
   - Tag Git wajib: `protocol-v1` (akhir H2), `dataset-v1` (H3), `gate2-freeze` (H5), `sprint1-final` (H7).
3. **Pengaman Holdout ($\ge$ `2026-06-01`)**:
   - Fungsi `assert_before_holdout()` di `src/renaro/contract.py` wajib dipanggil pada seluruh loader dan builder dataset dev.
   - Baris data mentah PIHPS dan ENSO dengan `date >= 2026-06-01` wajib dipisahkan ke direktori tersegel (`RENARO_SEALED_DIR`) oleh `CGS-H3-02` (`scripts/seal_holdout.py`) sebelum latihan model Gate 2 dimulai.
