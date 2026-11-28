# GATE 2: 2026-11-28, 11.15 WIB (FINAL FREEZE — GO)

- **Hadir**: RL (`@alim`, penanggung jawab Gate 2 & eksekutor ambil-alih `MLE-H5-03`), MDE (`@akashuten`), MLE (`@agusprasetya`), CGS (`@fariqfaqih`)
- **Commit yang dinilai**: `6f317beb98e4d0e43bb093ecb8fa01a2662d3996` (`6f317be`, kode & eksekusi 200 run `g2_*` bersih; mencakup MDE `f6716aa`/`6874c0b` `REPRODUCED OK`, MLE `b9c73a3`/`21a2367`/`878803d`, CGS `75363fd`, dan RL `1bd96be`), ditutup oleh commit pembekuan ini yang memuat `frozen/manifest.yaml`, `docs/decisions/GATE2.md`, `docs/protocol_amendments.md` (`A1–A4`), `docs/protocol_audit.md`, serta laporan `reports/h5/` untuk dipasang tag **`gate2-freeze`**.
- **Dataset**: `dataset_v1` · `content_hash.panel = fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de` · `split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`
- **Protokol**: `protocol-v1` (`6c2e85e`) + Amandemen `A1–A4` (`docs/protocol_amendments.md`, dicatat seluruhnya sebelum holdout dibuka)
- **Status Segel Holdout (`>= 2026-06-01`)**: **MASIH TERSEGEL** hingga tag `gate2-freeze` terpasang di remote dan paket checkpoint `HOLDOUT` diserahkan kepada `CGS-H6-01` (`docs/holdout_seal.md`)

---

## Kriteria dan bukti

| Kriteria | Ambang | Nilai (`6f317be` + `MLE-H5-03`) | Sumber (`path` / `run_id`) | Lolos? |
| :--- | :--- | :--- | :--- | :---: |
| **1. Konsistensi `split_hash` & reproduksibilitas data (`MDE-H5-01`)** | 100% run memakai `split_hash` identik (`411aec1a...`); reproduksi clone bersih `REPRODUCED OK` | **443 / 443 run** di `registry.csv` (`243` historis + `200` `g2_*`) identik `411aec1a...` (0 duplikat, 100% `completed`); uji reproduksi CGS `6874c0b` **REPRODUCED OK** (`52` test PASS) | `experiments/registry.csv`, `reports/qa/make_dataset_repro_cgs_20261128.txt`, `docs/protocol_audit.md` Butir 1 | **LULUS** |
| **2. Anti-kebocoran waktu, fitur regime, `PA-04`, & segel holdout** | `test_no_leakage.py` 0 FAIL; 0 fitur regime; semua `preds.parquet` `< 2026-06-01`; holdout tersegel | `test_no_leakage.py` **12 PASS / 0 FAIL**; 0 fitur regime pada 17 YAML (`configs/models/{,gate2/}*.yaml`); **200 / 200** `g2_*/preds.parquet` `max(date) <= 2026-05-29` dan `max(target_date) <= 2026-05-29` (`0` baris `>= 2026-06-01`); holdout `TERSEGEL` | `tests/test_no_leakage.py`, `reports/h5/pa04_maxdate_audit.csv`, `docs/protocol_audit.md` Butir 2–4, 6, 8, `docs/holdout_seal.md` | **LULUS** |
| **3. Amandemen protokol & penutupan temuan audit (`PA-01..PA-05`)** | Semua deviasi tercatat sebelum holdout dibuka; bug `ANOM-07` diperbaiki; checklist audit 10/10 | Amandemen **`A1`** (`n_lags=6`), **`A2`** (subset `CGS-H5-01`), **`A3`** (1-epoch ablasi), dan **`A4`** (kesetaraan `epochs=10, patience=10` `configs/models/gate2/*.yaml`) tercatat pra-holdout; `ANOM-07` diperbaiki di `21a2367` (`8.168,40`); audit protokol **10 / 10 LULUS** | `docs/protocol_amendments.md`, `docs/protocol_audit.md`, commit `21a2367` | **LULUS** |
| **4. Kelengkapan 8 model wajib pada split identik × 5 seed (`O1–O3` & `HOLDOUT`)** | 8/8 model wajib lengkap 5 seed `0..4` pada split identik dengan konfigurasi seragam | **8 / 8 model wajib LULUS** (`seasonal_naive`, `lgbm_c`, `gwn`, `mtgnn`, `latent_regime`, `lag_graph`, `module1`, `module23`) + **2 pendamping** (`naive_last`, `lgbm_a`) = **10 model × 4 origin (`O1, O2, O3, HOLDOUT`) × 5 seed = 200 / 200 run `g2_*`** (0 error, `epochs=10` seragam bagi 6 neural) | `experiments/registry.csv` (`g2_*`), `reports/h5/gate2_validation_summary.csv`, `reports/h5/gate2_runs_all.csv` | **LULUS** |
| **5. Refit `HOLDOUT` & uji kering `scripts/predict.py` pada periode uji `O3`** | Refit `HOLDOUT` (`train <= 2025-12-31`, `val 2026-01..05`) lengkap; uji kering `predict.py` identik dengan `O3` tanpa pelatihan | **50 / 50 run `HOLDOUT`** selesai (`g2_*_HOLDOUT_s0..4`); unit test `tests/test_frozen.py` **5 / 5 PASS**; uji kering `scripts/predict.py` atas **50 / 50 run `O3`** (`35.496` baris/run = `1.774.800` baris) menghasilkan **50 / 50 IDENTIK (`max |delta y_pred| = 0,00e+00`)** | `scripts/predict.py`, `tests/test_frozen.py`, `reports/h5/gate2_dryrun_report.md`, `reports/h5/predict_dryrun_comparison.csv`, `reports/h5/predict_dryrun_log.json` | **LULUS** |
| **6. Paket beku `frozen/manifest.yaml` + SHA-256 `ckpt.pt` + `git_sha` bersih** | Setiap model di manifest punya `config`, `seeds`, `checkpoints`, `sha256` terverifikasi dari commit bersih, `best_baseline_on_validation`, dan daftar `excluded` | `frozen/manifest.yaml` memuat **10 model × 5 seed = 50 / 50 checkpoint `ckpt.pt`** dengan checksum SHA-256 cocok 100%, `freeze_commit = 6f317beb...` bersih, `best_baseline_on_validation = lgbm_c` (`Rp5.481,20/kg`), dan `excluded = [module1_none, module4]` | `frozen/manifest.yaml`, `configs/models/gate2/*.yaml`, `scripts/build_gate2_manifest.py` | **LULUS** |
| **7. Tag Git `gate2-freeze` & handoff ke `CGS-H6-01`** | Tag annotated `gate2-freeze` terpasang di remote + paket checkpoint siap diserahkan ke CGS | Seluruh prasyarat teknis terpenuhi 100%; siap dibuat `git tag -a gate2-freeze -m "Gate 2 freeze"` dan `git push --tags` pada commit ini serta serah-terima arsip 50 folder `HOLDOUT` (`frozen_holdout_checkpoints_50runs.zip`) ke CGS | `frozen/manifest.yaml`, `docs/decisions/GATE2.md` | **LULUS (SIAP TAG)** |

---

## Ringkasan 10 Model Beku (`g2_*`, Commit `6f317be`, Seragam 10 Epoch Neural) & Daftar Eksklusi

| No | Model (`configs/models/gate2/`) | Peran Gate 2 | Run (`O1–O3` + `HOLDOUT`) | `Val O1` (`Rp/kg`) | `Val O2` (`Rp/kg`) | `Val O3` (`Rp/kg`) | `Val 3-Origin Avg` (`Rp/kg`) | `Val Max CV` | `Test 3-Origin Avg` (`Rp/kg`) | `HOLDOUT Val Avg ± SD` (`Rp/kg`) | Status Holdout |
| :-: | :--- | :--- | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | `seasonal_naive` | Wajib #1 (Naif musiman) | 15 + 5 = 20 | 24.422,56 | 23.880,92 | 17.796,22 | 22.033,23 | 0,00% | 17.389,27 | 15.289,29 ± 0,00 | **BEKU MASUK HOLDOUT** (5/5 SHA-256) |
| 2 | `naive_last` | Pendamping (Jangkar martingale) | 15 + 5 = 20 | 7.988,33 | 6.541,76 | 3.977,90 | 6.169,33 | 0,00% | 6.782,78 | 7.050,58 ± 0,00 | **BEKU MASUK HOLDOUT** (5/5 SHA-256) |
| 3 | `lgbm_a` | Pendamping (Tabular harga-only) | 15 + 5 = 20 | 6.279,71 | 6.543,17 | 3.806,59 | 5.543,16 | 0,63% | 6.667,56 | 5.861,57 ± 20,14 | **BEKU MASUK HOLDOUT** (5/5 SHA-256) |
| 4 | **`lgbm_c`** | **Wajib #2 (Tabular + iklim + kalender)** | 15 + 5 = 20 | 6.091,26 | 6.553,97 | 3.798,37 | **5.481,20** | 1,12% | 6.914,47 | 6.042,09 ± 49,54 | **BEKU MASUK HOLDOUT (`best_baseline_on_validation`)** |
| 5 | `gwn` | Wajib #3 (Graph WaveNet, 10 ep) | 15 + 5 = 20 | 7.393,35 | 8.095,18 | 4.108,22 | 6.532,25 | 13,33% | 7.622,41 | 5.965,67 ± 264,06 | **BEKU MASUK HOLDOUT** (5/5 SHA-256) |
| 6 | `mtgnn` | Wajib #4 (MTGNN, 10 ep) | 15 + 5 = 20 | 7.211,26 | 7.837,36 | 4.250,86 | 6.433,16 | 7,68% | 7.419,48 | 5.878,79 ± 222,87 | **BEKU MASUK HOLDOUT** (5/5 SHA-256) |
| 7 | `latent_regime` | Wajib #5 (ala RCSGNet, 10 ep) | 15 + 5 = 20 | 6.825,06 | 7.121,88 | 3.896,37 | 5.947,77 | 2,37% | 7.029,15 | 6.353,22 ± 93,03 | **BEKU MASUK HOLDOUT** (5/5 SHA-256) |
| 8 | `lag_graph` | Wajib #6 (ala MillGNN, 10 ep) | 15 + 5 = 20 | 6.869,25 | 7.235,84 | 3.879,87 | 5.994,99 | 4,01% | 7.100,21 | 6.240,28 ± 26,96 | **BEKU MASUK HOLDOUT** (5/5 SHA-256) |
| 9 | `module1` (`bps`) | Wajib #7 (Modul 1 prior BPS, 10 ep) | 15 + 5 = 20 | 7.085,61 | 7.774,84 | 3.886,58 | 6.249,01 | 9,79% | 7.396,89 | 6.431,12 ± 169,01 | **BEKU MASUK HOLDOUT** (5/5 SHA-256) |
| 10 | `module23` | Wajib #8 (Modul 1–3 penuh, 10 ep) | 15 + 5 = 20 | 7.013,81 | 7.767,62 | 3.883,02 | 6.221,48 | 5,25% | 7.285,14 | 6.370,09 ± 143,58 | **BEKU MASUK HOLDOUT** (5/5 SHA-256) |

- **Penetapan Resmi Pra-Holdout `best_baseline_on_validation` (`frozen/manifest.yaml`, untuk Uji Diebold–Mariano `MLE-H6-01`)**:
  - **`lgbm_c`** (`Val h=10 MAE 3-origin = Rp5.481,20/kg`, `Val Max CV = 1,12%`), dipilih secara deterministik sebagai baseline wajib dengan rata-rata MAE validasi `O1–O3` terendah pada konfigurasi beku `g2_*` **sebelum** data holdout dibuka.
  - Sebagai pembanding diagnostik tambahan (bukan pengganti pembanding utama uji DM), baseline graf/rezim terbaik pada validasi adalah **`latent_regime`** (`Rp5.947,77/kg`) dan tabular harga-saja terbaik adalah **`lgbm_a`** (`Rp5.543,16/kg`).
  - Catatan ilmiah penting: setelah anggaran pelatihan disetarakan pada 10 epoch (`A4`), **`module23`** (`Val = Rp6.221,48`, `Test = Rp7.285,14`, `Test Max CV = 4,18%`) mengungguli **`module1`** (`Rp6.249,01` / `Rp7.396,89`), **`mtgnn`** (`Rp6.433,16` / `Rp7.419,48`), dan **`gwn`** (`Rp6.532,25` / `Rp7.622,41`), sekaligus seluruh 8 model non-naif mengungguli `naive_last` (`Rp7.050,58`) pada validasi `HOLDOUT` (`2026-01..05`).
- **Daftar Model Tidak Lolos / Eksklusi Resmi (Sesuai DoD Gate 2)**:
  - **`module1_none`** — **dikeluarkan dari holdout** (varian ablasi tanpa prior BPS; hanya `module1` ber-prior `bps` yang dibekukan ke holdout).
  - **`module4`** — **dikeluarkan dari holdout** (target *stretch goal* `MLE-H5-04` yang tidak masuk pembekuan Sprint 1 dan dipindahkan ke Sprint 2).
  - Seluruh **8 / 8 model wajib Gate 2** (`seasonal_naive`, `lgbm_c`, `gwn`, `mtgnn`, `latent_regime`, `lag_graph`, `module1`, `module23`) **lolos penuh** tanpa eksklusi.

---

## Keputusan

**GO — PEMBEKUAN GATE 2 DISAHKAN (`gate2-freeze`)**

- Seluruh 7 kriteria Gate 2 dan 10/10 butir audit protokol (`docs/protocol_audit.md`) **LULUS**.
- Amandemen **`A1–A4`** (`docs/protocol_amendments.md`) disahkan secara resmi sebelum data holdout dibuka.
- Setelah commit ini di-push beserta tag annotated **`gate2-freeze`** ke `origin` dan paket 50 folder checkpoint `HOLDOUT` diserahkan kepada CGS, **`CGS-H6-01` resmi mendapat lampu hijau** untuk membuka segel `HOLDOUT` (`>= 2026-06-01`) **tepat satu kali** melalui `scripts/predict.py --manifest frozen/manifest.yaml`.

## Alasan (<= 5 kalimat)

1. Seluruh 8 model wajib Gate 2 beserta 2 model pendamping (10 model × 4 origin × 5 seed = 200 run `g2_*`) telah selesai dilatih pada `dataset_v1` dengan `split_hash` identik (`411aec1a...`), commit bersih `6f317be`, dan anggaran seragam 10 epoch untuk ke-6 model neural (`A4`).
2. Paket beku `frozen/manifest.yaml` telah memuat seluruh 50 checkpoint `HOLDOUT` lengkap dengan checksum SHA-256 terverifikasi 100%, penetapan pra-holdout `best_baseline_on_validation = lgbm_c` (`Rp5.481,20/kg`), serta daftar eksklusi resmi `module1_none` dan `module4` sebagai dikeluarkan dari holdout.
3. Uji kering `scripts/predict.py` pada seluruh 50 run periode uji `O3` (`1.774.800` baris prediksi) menghasilkan keluaran identik penuh (`max |delta y_pred| = 0,00e+00`) tanpa pelatihan ulang, dan seluruh 5/5 uji unit `tests/test_frozen.py` lulus.
4. Seluruh prasyarat anti-kebocoran dan integritas data lulus penuh: `tests/test_no_leakage.py` 0 FAIL, audit `PA-04` atas 200/200 `g2_*/preds.parquet` mengonfirmasi `max(date) <= 2026-05-29` (`0` baris `>= 2026-06-01`), bug `ANOM-07` telah diperbaiki di `21a2367`, dan uji reproduksi `MDE-H5-01` (`6874c0b`) lulus `REPRODUCED OK`.
5. Dengan 10/10 butir `docs/protocol_audit.md` berstatus `LULUS` dan Amandemen `A1–A4` tercatat sebelum holdout dibuka, tidak ada lagi bloker untuk memasang tag `gate2-freeze` dan membuka tahap inferensi holdout `CGS-H6-01`.

## Dampak ke rencana

- **Job yang berubah / resmi dibuka**:
  - `ALL-H5-01` (Gate 2) **SELESAI (GO)** setelah push commit & tag `gate2-freeze` ke remote `origin`.
  - `MLE-H5-03` **SELESAI** melalui ambil-alih eksekusi oleh RL di mesin lokal RTX 4050 pada commit `6f317be` menggunakan perkakas resmi MLE (`b9c73a3`, `878803d`).
  - `CGS-H6-01` (buka segel holdout 1× + jalankan `scripts/predict.py`) **RESMI DIBUKA** setelah CGS menerima arsip 50 folder `experiments/runs/g2_*_HOLDOUT_s*/` (`frozen_holdout_checkpoints_50runs.zip`, ~31,3 MB `ckpt.pt`, terverifikasi SHA-256 terhadap `frozen/manifest.yaml`) lewat drive bersama/Underleaf.
- **Job baru / tindak lanjut H6–H7**:
  - `CGS-H6-01` wajib memverifikasi kecocokan 50/50 SHA-256 `ckpt.pt` terhadap `frozen/manifest.yaml` pada tag `gate2-freeze` sebelum mengeksekusi inferensi holdout 1×.
  - `MLE-H6-01` & `RL-H6-01` menjalankan analisis pasca-holdout (uji Diebold–Mariano berpasangan terhadap `lgbm_c` + analisis per rezim) hanya di atas prediksi beku hasil `CGS-H6-01` tanpa modifikasi model.
  - `MLE-H5-04` (`module4`) resmi dipindahkan ke Sprint 2.

## Risiko yang diterima

- **Anggaran seragam 10 epoch pada model neural (`A4`)**: Pemilihan 10 epoch (`patience = 10`) menjaga kesetaraan antar 6 model neural dan kelayakan waktu Sprint 1, namun `gwn` (`val_max_cv = 13,33%`) dan `module1` (`val_max_cv = 9,79%`) masih menunjukkan sensitivitas seed sedang pada `O1–O2`; varians antar-seed dilaporkan penuh sebagai deviasi standar 5 seed pada `RL-H7-01`.
- **Transfer artefak checkpoint biner di luar Git**: Karena `experiments/runs/` masuk `.gitignore` L16, ke-50 file `ckpt.pt` (`31,3 MB`) diserahkan ke CGS melalui arsip terpisah dan integritasnya dijamin secara kriptografis melalui 50 checksum SHA-256 pada `frozen/manifest.yaml` (diverifikasi otomatis oleh `scripts/predict.py`).
- **Keterbatasan historis H5 (`A2`, `A3`)**: Subset retrain `CGS-H5-01` (`A2`) dan ablasi 1-epoch `MLE-H5-02` (`A3`) sudah tercatat transparan di `docs/protocol_amendments.md` dan tidak memengaruhi paket model beku `g2_*` untuk evaluasi holdout H6.
