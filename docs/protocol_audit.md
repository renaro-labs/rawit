# Audit Kepatuhan Protokol Evaluasi (`RL-H5-02` — Final Penutupan Gate 2)

- **Peran & Auditor**: RL (*Research Lead*) `@alim`
- **Tanggal Audit**: Audit awal 27 November 2026 (`2b18e78`/`1bd96be`) · **Audit Final Penutupan Gate 2: Sabtu, 28 November 2026 (`6f317be` + `MLE-H5-03`)**
- **Sumber Playbook**: `docs/playbook/02_RL_Research_Lead.md` (`RL-H5-02`) & `RL-H5-02__protocol_audit.tex`
- **Commit Repo yang Diaudit**: `6f317beb98e4d0e43bb093ecb8fa01a2662d3996` (`6f317be`, mencakup MDE `f6716aa`/`6874c0b` `REPRODUCED OK`, MLE `b9c73a3`/`21a2367`/`878803d`, CGS `75363fd`, RL `1bd96be`, dan eksekusi penuh `MLE-H5-03` 200 run `g2_*`)
- **Dataset Acuan**: `dataset_v1` (`data/processed/dataset_v1/VERSION`: `rows_panel = 76.228`, `2017-07-03..2026-05-29`, `content_hash.panel = fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de`, `split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`)
- **Protokol Acuan**: Tag Git `protocol-v1` (commit `6c2e85e50b319fc7215dbac6d46c847fbf27b2f5`; `docs/eval_protocol_v1.md` SHA-256 prefix `624758fcd6e825e8`) + Amandemen `A1–A4` (`docs/protocol_amendments.md`)
- **CSV Bukti Terstruktur**: `RL hasil H5/csv_laporan/02_checklist_audit_protokol_RL_H5_02.csv`

---

## 1. Checklist Wajib `RL-H5-02` (7 Butir Playbook)

| No | Item Kepatuhan (`RL-H5-02`) | Status | Bukti Terverifikasi (`path` / `run_id` / hasil eksekusi) | Tindakan / Justifikasi |
| :-: | :--- | :---: | :--- | :--- |
| **1** | **Semua run memakai `split_hash` dataset v1 yang sama** | **[LULUS]** | **443 / 443 run** di `experiments/registry.csv` (`243` historis H3–H5 + **`200` run Gate 2 `g2_*`**), seluruh tabel `reports/rq0/`, `reports/mle/`, `reports/h5/gate2_runs_all.csv`, serta `frozen/manifest.yaml` identik memakai `split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea` (0 duplikat `run_id`, 100% `completed`). Diperkuat oleh uji reproduksi clone bersih `MDE-H5-01` (`6874c0b`, `reports/qa/make_dataset_repro_cgs_20261128.txt`): **REPRODUCED OK** (4 hash file identik, 52 test PASS). | Kepatuhan penuh 100%. |
| **2** | **Tidak ada fitur dengan `available_at > t` (`tests/test_no_leakage.py` lulus di commit terakhir)** | **[LULUS]** | Eksekusi langsung `tests/test_no_leakage.py` di commit `6f317be` terhadap `data/processed/dataset_v1/` menghasilkan **12 PASS, 0 FAIL, 3 SKIP** (`data/interim/` ter-gitignore L12; ketiga tes truncation/rebuild telah lulus penuh di MDE `09340e9`/`ba14722` & CGS `6874c0b`). Seluruh uji `tests/test_frozen.py` lulus **5 / 5 PASS**. | Kepatuhan penuh pada artefak `dataset_v1` dan paket beku `MLE-H5-03`. |
| **3** | **Label regime tidak ada di daftar fitur model mana pun (`grep regime` di `configs/models/`)** | **[LULUS]** | Grep `regime\|label_primary\|is_dry\|is_extreme\|enso_phase\|holdout` di seluruh **17 berkas** `configs/models/*.yaml` (7 basis) dan `configs/models/gate2/*.yaml` (10 beku) menghasilkan **0 fitur regime** (kecocokan hanya pada nama model `latent_regime` dan komentar header `refit HOLDOUT`). `src/renaro/data/datasets.py` (`FEATURES` 10 kolom non-regime), `src/renaro/features/tabular.py`, dan `test_no_regime_or_label_columns` semuanya **PASS**. | Kepatuhan penuh. `regime_labels.csv` khusus evaluasi. |
| **4** | **Hiperparameter tidak dituning pada periode uji (hanya validasi)** | **[LULUS]** | `src/renaro/models/module1_training.py` (`fit(train, val)`), `scripts/run_h4_module1.py --mode tune` (hanya `O1 val`), `scripts/run_gate2.py` (konfigurasi beku seragam `configs/models/gate2/*.yaml` dipakai identik untuk `O1–O3` dan `HOLDOUT`), dan penetapan `best_baseline_on_validation = lgbm_c` (`Rp5.481,20/kg`) dihitung murni dari validasi `O1–O3` **sebelum** holdout dibuka (`reports/h5/gate2_validation_summary.csv`). Ketimpangan epoch `ANOM-02` telah ditutup oleh Amandemen `A4` (`epochs = 10, patience = 10` seragam). | Kepatuhan penuh (`ANOM-02` tertutup melalui `A4`). |
| **5** | **5 seed untuk tiap model wajib** | **[LULUS]** | **8 / 8 model wajib Gate 2** (`seasonal_naive`, `lgbm_c`, `gwn`, `mtgnn`, `latent_regime`, `lag_graph`, `module1` prior `bps`, `module23`) + **2 pendamping** (`naive_last`, `lgbm_a`) telah lengkap **5 / 5 seed (`0..4`) pada seluruh 4 origin (`O1, O2, O3, HOLDOUT`)** = **200 / 200 run `g2_*`** di `experiments/registry.csv` & `reports/h5/gate2_runs_all.csv` (0 error). Varian yang tidak dibekukan (`module1_none`, `module4`) dicatat resmi sebagai **"dikeluarkan dari holdout"** pada `frozen/manifest.yaml` dan `docs/decisions/GATE2.md`. | **PA-01 TERTUTUP PENUH** (8/8 model wajib lolos tanpa eksklusi). |
| **6** | **Tidak ada artefak yang menyentuh tanggal $\ge 2026-06-01$ (cek `max(date)` semua `preds.parquet`)** | **[LULUS]** | (a) `data/processed/dataset_v1/{panel,target}.parquet` `max(date) = 2026-05-29` (`test_no_holdout_dates` PASS, 0 baris `>= 2026-06-01`). (b) Audit langsung `PA-04` atas **200 / 200 berkas `experiments/runs/g2_*/preds.parquet`** (`reports/h5/pa04_maxdate_audit.csv`): `max(date) <= 2026-05-29` dan `max(target_date) <= 2026-05-29` (**0 baris `>= 2026-06-01`**). (c) Redaksi catatan RONI holdout di `RL hasil/csv_laporan/04_rolling_origin_splits_RL_H1_01.csv` L5 telah diverifikasi selesai pada `c5d9b98`. | **PA-04 TERTUTUP PENUH** dengan bukti terstruktur `reports/h5/pa04_maxdate_audit.csv`. |
| **7** | **Amandemen protokol (jika ada) tercatat sebelum Gate 2** | **[LULUS]** | Seluruh 4 deviasi dari `docs/eval_protocol_v1.md` telah dicatat formal dan disahkan sebagai **Amandemen `A1` (`n_lags = 6`), `A2` (subset `CGS-H5-01`), `A3` (1-epoch ablasi `MLE-H5-02` + fix `ANOM-07` `21a2367`), dan `A4` (`epochs = 10, patience = 10` seragam di `configs/models/gate2/*.yaml`)** pada `docs/protocol_amendments.md` **sebelum holdout dibuka** (tercantum pula di `frozen/manifest.yaml`). | **PA-03 TERTUTUP PENUH**. |

---

## 2. Checklist Tambahan Prasyarat Gate 2 (dari `RL-H5-02__protocol_audit.tex`)

| No | Item Prasyarat Gate 2 | Status | Bukti Terverifikasi | Tindakan / Justifikasi |
| :-: | :--- | :---: | :--- | :--- |
| **8** | **Holdout tidak dibuka sebelum H6** | **[LULUS]** | `docs/holdout_seal.md` L8, L36, L82–84: Status **TERSEGEL** di `D:\renaro_sealed\holdout_v1` & mirror VPS `/srv/audit/sealed/holdout_v1` (`SHA256SUMS` 196/196 & 6/6 OK); bagian `## Dibuka` masih kosong; tidak ada file `HOLDOUT_UNSEALED`. | Pertahankan segel hingga tag `gate2-freeze` ada di remote dan `CGS-H6-01` resmi dimulai. |
| **9** | **Checkpoint + config + commit dibekukan (`frozen/manifest.yaml`)** | **[LULUS]** | (a) `frozen/manifest.yaml` selesai dan memuat **10 model × 5 seed `HOLDOUT` = 50 / 50 `ckpt.pt`** dengan checksum SHA-256 terverifikasi 100%, `freeze_commit = 6f317beb98e4d0e43bb093ecb8fa01a2662d3996` (working tree bersih, diverifikasi pada `git_sha.txt` di seluruh 200 run `g2_*`), `best_baseline_on_validation = lgbm_c`, dan daftar `excluded`. (b) Uji kering resmi `scripts/predict.py` atas **50 / 50 run `O3`** (`35.496` baris/run) menghasilkan **50 / 50 IDENTIK (`max |delta y_pred| = 0,00e+00`)** (`reports/h5/gate2_dryrun_report.md`, `reports/h5/predict_dryrun_comparison.csv`). | **PA-02 TERTUTUP PENUH**; siap tag `gate2-freeze` dan handoff arsip 50 folder `HOLDOUT` ke CGS. |
| **10** | **Tidak ada data PIHPS mentah di artefak rilis (`release/`)** | **[LULUS]** | Direktori `release/` belum dibuat; pemindaian `*pihps*` di seluruh repo `6f317be` hanya menemukan parser, unit test, dokumentasi endpoint, dan tabel agregat cakupan (`reports/qa/coverage_pihps.csv`), **0 baris harga PIHPS mentah** (`data/raw/` diblok `.gitignore` L11). | Ulangi verifikasi ini saat paket `release/` disusun pada H7. |

---

## 3. Status Penutupan Seluruh Temuan Audit (`PA-01` s.d. `PA-05`)

| ID Temuan | Item Terkait | Status Awal (27 Nov) | Status Final (28 Nov) | Bukti Penutupan (`commit` / `path`) |
| :---: | :---: | :---: | :---: | :--- |
| **PA-01** | Butir 5 (`5 seed` 8 model wajib) | GAGAL (`6/8`) | **TERTUTUP (LULUS)** | `experiments/registry.csv` (`200` run `g2_*`, 8/8 model wajib + 2 pendamping × 4 origin × 5 seed), `reports/h5/gate2_runs_all.csv` |
| **PA-02** | Butir 9 (`frozen/manifest.yaml`, `ckpt.pt`, `git_sha`, `predict.py`) | GAGAL | **TERTUTUP (LULUS)** | `frozen/manifest.yaml` (50/50 SHA-256), `freeze_commit = 6f317be`, `scripts/predict.py` uji kering 50/50 `maxdiff = 0,00e+00` (`reports/h5/gate2_dryrun_report.md`), `tests/test_frozen.py` 5/5 PASS |
| **PA-03** | Butir 7 (`docs/protocol_amendments.md`) | LULUS (Tercatat `A1–A3`) | **TERTUTUP (LULUS `A1–A4`)** | `docs/protocol_amendments.md` (`A1–A4` tercatat & disahkan pra-holdout, tercantum di `frozen/manifest.yaml`) |
| **PA-04** | Butir 6 (`max(date)` `preds.parquet` lokal) | CATATAN LOKAL | **TERTUTUP (LULUS)** | `reports/h5/pa04_maxdate_audit.csv`: **200 / 200** `g2_*/preds.parquet` `max(date) <= 2026-05-29` (`0` baris `>= 2026-06-01`) |
| **PA-05** | Bug laporan `ANOM-07` (`aggregate_ablation.py`) | TERBUKA | **TERTUTUP (LULUS)** | Commit `21a2367` (di-merge pada `6f317be`): `scripts/aggregate_ablation.py` & `reports/ablation/ablation_summary.md` (`8.168,40`) diperbaiki |

---

## 4. Pernyataan Audit Resmi (Final Gate 2)

> **Status Kepatuhan Final**: Berdasarkan seluruh bukti terverifikasi pada commit `6f317be` (`dataset_v1` `content_hash = fceeecbf5e9f...`, `split_hash = 411aec1a...`, `protocol-v1` `6c2e85e` + Amandemen `A1–A4`) dan selesainya paket beku `MLE-H5-03`, protokol evaluasi dinyatakan **PATUH PENUH (10 / 10 BUTIR LULUS; 0 BLOKER TERSISA; `PA-01` s.d. `PA-05` TERTUTUP)**.
>
> **Keputusan Prasyarat Gate 2**: Seluruh syarat pembekuan Gate 2 (`ALL-H5-01`) terpenuhi. **Rekomendasi Audit RL: GO** untuk pemasangan tag **`gate2-freeze`**, penyerahan `frozen/manifest.yaml` beserta arsip 50 checkpoint `HOLDOUT` ke CGS, dan pembukaan segel holdout 1× oleh **`CGS-H6-01`**.

| Peran | Nama / Handle | Status Tanda Tangan | Tanggal |
| :--- | :--- | :---: | :---: |
| **RL (Auditor & Eksekutor Ambil-Alih `MLE-H5-03`)** | Alim (`@alim`) | **DIAUDIT & DISAHKAN (10/10 LULUS)** | 2026-11-28 |
| **MLE (Perancang Perkakas `MLE-H5-03` & Perbaikan `ANOM-07`)** | Agus Prasetya (`@agusprasetya`) | **TERVERIFIKASI (`b9c73a3`, `21a2367`, `878803d`)** | 2026-11-28 |
| **CGS (Segel Holdout & Uji Reproduksi `MDE-H5-01`)** | Muhammad Fariq Faqih (`@fariqfaqih`) | **REPRODUCED OK (`6874c0b`) — SIAP `CGS-H6-01`** | 2026-11-28 |
