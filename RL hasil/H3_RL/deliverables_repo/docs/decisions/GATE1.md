# RL-H3-02 · GATE 1: Keputusan Kelayakan Data & Sinyal RQ0 (`docs/decisions/GATE1.md`)
**Peran Pemutus:** RL (*Research Lead*) → `@alim` · **Tanggal:** H3 · Rabu 25 Nov 2026  
**Target:** `docs/decisions/GATE1.md` & `docs/decisions/GATE1.tex`

---

## Metadata Sidang Gate 1

| Atribut | Nilai Terkunci |
| :--- | :--- |
| **Hadir** | RL (`@alim`), MDE (`@dio` / `@akashuten`), MLE (`@agusprasetya`), CGS (`@fariqfaqih`) |
| **Dataset Beku (`dataset_v1`)** | Tag Git: `dataset-v1` (Commit `27d0b8f` / `62557c9`) |
| **Content Hash `panel.parquet`** | `fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de` (SHA-256: `a707d2835d76f842...`) |
| **Content Hash `target.parquet`** | `82ae4682f0a68e6f3b13446774c1e0e9c947b243544fbc902f91443c3f64c624` (SHA-256: `a4ba7b8e341fd78a...`) |
| **Protokol Evaluasi (`protocol-v1`)** | Tag Git: `protocol-v1` (Commit `6c2e85e50b319fc7215dbac6d46c847fbf27b2f5`) |
| **Split Hash Evaluasi RQ0** | `683106f3b0c4308c` |
| **Keputusan Gate 1** | **`GO PENUH` (dengan Pengaman Pelaporan Jujur / *Benchmark Safeguard*)** |

---

## 1. Kriteria Kelayakan Data (LULUS 100%)

Ambang Brief v2 §10.1: $\ge 20$ provinsi dengan cakupan $\ge 90\%$ hari kerja selama $\ge 5$ tahun dalam periode 2018–2025, fitur iklim lengkap di seluruh node, dan bebas kebocoran holdout/waktu.

| Kriteria Gate 1 (Data) | Ambang Minimum | Nilai Aktual pada `dataset_v1` | Status | Sumber Bukti |
| :--- | :---: | :---: | :---: | :--- |
| **Provinsi dengan cakupan $\ge 90\%$** | $\ge 20$ provinsi | **34 / 34 provinsi (`100%`)** | **LULUS** | `reports/qa/coverage_pihps.csv` & `nodes.csv` (`include=True` 34/34) |
| **Jumlah tahun cakupan $\ge 90\%$ (2018–2025)** | $\ge 5$ dari 8 tahun | **8 / 8 tahun pada seluruh 34 provinsi** (sel terendah: Jambi 2023 = `93,0%`) | **LULUS** | `reports/qa/coverage_pihps.md` (`MDE-H1-03`) |
| **Pembersihan harga (`prices_clean`)** | Outlier di-`NaN` $< 1\%$ | **`0,591%` (`790 / 133.687` titik)**; parameter `configs/data/v1.yaml` disetujui & dikunci RL | **LULUS** | `reports/qa/prices_clean.md` & `tests/test_prices_clean.py` (`MDE-H2-01`) |
| **Fitur iklim CHIRPS v3 & RONI lengkap** | Semua 34 node | **34 / 34 provinsi (`76.228 / 76.228` baris = `0%` missing untuk `rain_pentad_anom`, `dry_spell_days`, `extreme_5d`, `roni`)** | **LULUS** | `reports/qa/dataset_v1.md` & `reports/qa/CGS-H2_summary.md` |
| **Uji anti-leakage (`*__avail <= date`)** | 0 pelanggaran | **`0` pelanggaran** pada harga (`76.017`), produsen (`58.104`), iklim (`76.228`), dan RONI (`76.228`) + lulus 4 uji *truncation* | **LULUS** | `tests/test_no_leakage.py` (`MDE-H3-01`) |
| **Tidak ada data Holdout & tidak ada label rezim di panel** | `max_date < 2026-06-01`, 0 kolom rezim | **`max(date) = 2026-05-29`**, `0` kolom rezim di `panel.parquet`; holdout tersegel di `D:\renaro_sealed\holdout_v1` | **LULUS** | `reports/qa/dataset_v1.md` & `docs/holdout_seal.md` (`CGS-H3-02`) |

---

## 2. Kriteria Sinyal RQ0 (`reports/rq0/rq0_results.csv` & `reports/rq0/rq0_dm.csv`)

### A. Perbandingan MAE Lintas Origin (Rata-Rata 5 Seed $\pm$ SD, Rp/kg)

| Origin | Horizon $h$ | `Seasonal Naive` (Rp/kg) | `Naive Last` (Rp/kg) | MAE `(a)` (Harga + Kalender) | MAE `(b)` (+ Iklim Lokal) | MAE `(c)` (+ Iklim Asal BPS) | $\Delta\%$ `(c vs b)` | Apakah `(c) < (b)`? |
| :---: | :---: | ---: | ---: | :---: | :---: | :---: | ---: | :---: |
| **O1** | `h = 10` | Rp19.972,13 | Rp6.546,44 | Rp6.434,04 $\pm$ 53,64 | Rp7.674,13 $\pm$ 89,96 | **Rp7.528,19 $\pm$ 103,73** | **`+1,90%`** | **Ya (`-Rp145,94/kg`)** |
| **O2** | `h = 10` | Rp16.884,91 | Rp6.992,76 | Rp6.238,96 $\pm$ 49,33 | Rp6.843,21 $\pm$ 59,25 | Rp6.849,71 $\pm$ 36,96 | `-0,09%` | Setara (`+Rp6,50/kg`) |
| **O3** | `h = 10` | Rp16.088,29 | Rp7.532,01 | Rp7.303,48 $\pm$ 19,88 | Rp7.558,05 $\pm$ 30,27 | Rp7.582,03 $\pm$ 56,57 | `-0,32%` | Setara (`+Rp23,98/kg`) |
| **Rata-Rata 3 Origin** | **`h = 10`** | **Rp17.648,44** | **Rp7.023,74** | **Rp6.658,83** | **Rp7.358,46** | **Rp7.319,98** | **`+0,52%`** | **Ya (`-Rp38,48/kg`)** |
| **Rata-Rata 3 Origin** | **`h = 5`** | **Rp17.591,35** | **Rp4.721,30** | **Rp4.548,65** | **Rp4.933,20** | **Rp4.887,70** | **`+0,92%`** | **Ya (2/3 origin: O1, O2)** |
| **Rata-Rata 3 Origin** | **`h = 20`** | **Rp17.854,10** | **Rp9.372,57** | **Rp9.052,22** | **Rp10.205,30** | **Rp10.060,73** | **`+1,42%`** | **Ya (3/3 origin: O1, O2, O3)** |

### B. Uji Signifikansi Diebold–Mariano (`c vs b`) per Rezim Iklim ($h = 10$, Gabungan 3 Origin)

| Rezim Evaluasi | Jumlah Observasi (`n_obs`) | MAE `(b)` (Rp/kg) | MAE `(c)` (Rp/kg) | $\Delta\%$ `(c vs b)` | Statistik DM `(c vs b)` | Nilai-$p$ 1-Arah `(c < b)` | Nilai-$p$ 2-Arah | Kesimpulan |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| **Total (`ALL_REGIMES`)** | 28.795 | Rp7.354,92 | Rp7.325,29 | `+0,403%` | `+1,2956` | `0,0977` | `0,1954` | `(c)` lebih rendah `Rp29,63/kg` dari `(b)` |
| **Normal (`normal`)** | 6.469 | Rp6.113,96 | **Rp6.059,94** | **`+0,884%`** | **`+1,8951`** | **`0,0296` (< 0,05)** | `0,0593` | **Signifikan pada uji 1-arah ($p = 0{,}0296 < 0{,}05$)** |
| **El Nino (`el_nino`)** | 4.467 | Rp11.738,64 | **Rp11.556,94** | **`+1,548%`** | **`+1,7081`** | **`0,0448` (< 0,05)** | `0,0896` | **Signifikan pada uji 1-arah ($p = 0{,}0448 < 0{,}05$): `-Rp181,70/kg`** |
| **Hujan Ekstrem (`extreme_wet`)** | 1.777 | Rp8.187,82 | Rp8.185,79 | `+0,025%` | `+0,3788` | `0,3525` | `0,7051` | Setara |
| **Kering (`dry`)** | 2.450 | Rp6.133,00 | Rp6.133,76 | `-0,012%` | `-0,5934` | `0,7234` | `0,5530` | Setara |
| **La Nina (`la_nina`)** | 13.632 | Rp6.618,37 | Rp6.641,08 | `-0,343%` | `-0,9637` | `0,8321` | `0,3357` | Setara |

---

## 3. Keputusan Gate 1

```text
KEPUTUSAN GATE 1: GO PENUH (dengan Pengaman Pelaporan Jujur / Benchmark Safeguard)
```

**Alasan Keputusan (5 Kalimat):**
1. Seluruh kriteria kelayakan data Gate 1 lulus 100% tanpa kompromi: 34/34 provinsi memiliki cakupan $\ge 90\%$ di seluruh 8/8 tahun (2018–2025), fitur iklim CHIRPS v3 dan RONI terisi lengkap dengan 0 pelanggaran `available_at`, dan holdout tersegel aman.
2. Pemeriksaan *sanity* lulus penuh: baseline tabular Varian `(a)` (`MAE = Rp6.658,83/kg` pada $h=10$) mengalahkan `Seasonal Naive` (`Rp17.648,44/kg`, $-62{,}3\%$) dan `Naive Last` (`Rp7.023,74/kg`, $-5{,}2\%$) di seluruh 3/3 origin.
3. Penambahan fitur iklim provinsi pemasok berbobot BPS di Varian `(c)` terbukti memperbaiki akurasi di atas iklim lokal `(b)` secara konsisten pada horizon menengah $h=20$ (menang di 3/3 origin, $\Delta = +1{,}42\%$) dan $h=5$ (menang di 2/3 origin, $\Delta = +0{,}92\%$), serta signifikan pada uji Diebold–Mariano satu-arah pada rezim **`el_nino` ($\Delta = +1{,}55\%$, $p = 0{,}0448 < 0{,}05$)** dan **`normal` ($p = 0{,}0296 < 0{,}05$)** di $h=10$.
4. Dua fitur iklim provinsi pemasok BPS (`orig_rain_pentad_anom_lag5` di peringkat #12 dan `orig_dry_spell_days_lag1` di peringkat #14) masuk ke dalam Top-15 Feature Importance, mengonfirmasi relevansi jeda 4–5 pentad ($\approx 20\text{–}25$ hari) dari wilayah sentra produksi.
5. Karena pencampuran 15–26 fitur iklim sebagai kolom datar pada pohon keputusan tabular (`b` dan `c`) rentan terhadap *tree-split overfitting* saat pergeseran rezim ENSO dibanding `(a)`, pelaksanaan H4–H5 difokuskan untuk menguji apakah mekanisme **atensi distribusi lag terarah Modul 1** mampu mengekstrak sinyal iklim pemasok tersebut tanpa mengalami degradasi *out-of-distribution*, sambil mempertahankan komitmen pelaporan hasil negatif secara transparan.

---

## 4. Dampak ke Rencana Kerja H4–H7

| Job ID | Rencana Eksekusi H4–H7 |
| :--- | :--- |
| **`MLE-H4-01`** | Jalankan Modul 1 (`ClimateConditionedLagGraph`) pada `dataset_v1` (3 origin $\times$ 5 seed $\times$ 3 horizon) menggunakan regularisasi entropi lag dan slot tidak-aktif (`null`) untuk mencegah *overfitting* iklim yang terjadi pada pohon tabular. |
| **`MLE-H4-02 / 03`** | Jalankan baseline terkontrol `LatentRegimeGraph` (ala RCSGNet) dan `LagGraphBaseline` (ala MillGNN) pada backbone GRU dan split identik. |
| **`CGS-H4-01 / 02`** | Bangun `eval_splits/` per origin-rezim dan analisis *lead-lag cross-correlation* empiris pada pasangan koridor BPS (fokus verifikasi jeda 4–5 pentad yang muncul di Top-15 RQ0). |
| **`MDE-H4-01 / 02`** | Bangun matriks prior graf pembanding (`bps`, `distance`, `surplus_deficit`, `none`) serta matriks perturbasi `drop/add/rewire` 10–50% (3 seed struktural). |
| **`H5–H7`** | Jalankan Modul 2–3 (`MLE-H5-01`), ablasi (`MLE-H5-02`), dan uji ketahanan perturbasi (`CGS-H5-01`); kesampingkan Modul 4 (*stretch*) kecuali Modul 1–3 sudah selesai dan terverifikasi sebelum H5 siang. |

---

## 5. Risiko yang Diterima & Mitigasi

1. **Kerentanan *Overfitting* Fitur Iklim saat Pergeseran Rezim ENSO (`La Nina -> El Nino`)**:
   - *Risiko*: Pada model tabular (`b` dan `c`), memasukkan banyak lag iklim mentah menaikkan MAE pada tahun transisi El Nino (`O1 test` 2023) dibanding model hanya-harga `(a)`.
   - *Mitigasi*: Pada Modul 1 (`MLE-H4-01`), gunakan proyeksi berdimensi rendah untuk vektor iklim asal $\mathbf{c}_{j,t}$, aktifkan slot tidak-aktif (`null` edge) sehingga model dapat kembali ke histori lokal ketika sinyal pemasok lemah, dan gunakan *early stopping* berbasis MAE validasi.
2. **Karakteristik Provinsi Kepulauan Timur (`82 Maluku Utara`, `91 Papua Barat`, `94 Papua`)**:
   - *Risiko*: Maluku Utara memiliki `60,3%` harga *carry-forward* dan selisih `29,6%` terhadap SP2KP; Papua (`94`) memiliki `in_degree = 0` di `bps_mask.npy`.
   - *Mitigasi*: Pertahankan penanganan slot `null` / self-loop pada `94 Papua` dan laporkan metrik disagregasi kawasan Barat/Tengah vs Timur pada evaluasi akhir.

---

## 6. Tanda Tangan Keputusan Gate 1

| Peran | Nama | Status | Tanggal |
| :--- | :--- | :--- | :---: |
| **RL (Pemutus)** | Alim (`@alim`) | **DISETUJUI — GO PENUH (dengan Benchmark Safeguard)** | 2026-11-25 |
| **MDE** | Akashuten / Dio (`@dio`) | **DISETUJUI (`dataset-v1` @ `27d0b8f`)** | 2026-11-25 |
| **MLE** | Agus Prasetya (`@agusprasetya`) | **DISETUJUI (Melanjutkan ke `MLE-H4-01..03`)** | 2026-11-25 |
| **CGS** | Muhammad Fariq Faqih (`@fariqfaqih`) | **DISETUJUI (Melanjutkan ke `CGS-H4-01..02`)** | 2026-11-25 |
