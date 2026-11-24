# Renaro Lab â€” Sprint 1 (`rawit`)
**Climate-Conditioned Dynamic Graph Learning for Food Price Forecasting Under Extreme Weather and Climate Regime Shifts**

> **Status repo (2026-11-24):** `main` adalah **satu-satunya versi kanonik**.
> Branch `mde`, `mle`, `job/CGS-H1`, dan `job/CGS-H2` sudah di-merge ke `main`.
> Playbook Sprint 1, materi GIS CGS, dan spesifikasi API BPS sudah dipindahkan
> dari folder lama `supplychain`. Lihat **[`docs/consolidation.md`](./docs/consolidation.md)**
> untuk peta konsolidasi dan aturan branch.

Repositori ini berisi hasil kerja Sprint 1 lintas peran — **RL (*Research Lead*)**, **MDE**, **MLE**, dan **CGS** — mulai dari **Kickoff & Kontrak Data (`ALL-H1-01`)**, **Protokol Evaluasi v0.1 (`RL-H1-01`)** dan **v1 terkunci (`RL-H2-01`)**, **Kajian Literatur & Positioning (`RL-H1-02`, `RL-H2-02`)**, **Ekstraksi Matriks Distribusi Perdagangan BPS Poldis 2022 (`bps_mask_2022.csv` / `bps_mask.npy`)**, hingga pipeline data PIHPS/SP2KP, paket iklim CGS, dan harness evaluasi MLE.

---

## 1. Paket Lengkap Laporan & CSV Presentasi RL (`RL hasil/`)

Seluruh laporan ringkas (Markdown & TXT) serta 11 tabel CSV siap pakai tersedia di dalam folder **[`RL hasil/`](./RL%20hasil/)**:

### Laporan Utama & Dossier (Urutan Baca yang Disarankan)
1.  **[00_LAPORAN_UTAMA_RL_H1_PRESENTASI.md](./RL%20hasil/00_LAPORAN_UTAMA_RL_H1_PRESENTASI.md)** â€” Ringkasan Eksekutif Kickoff, Cakupan Wajib vs Stretch, 4 Keputusan Terbuka, Smoke Test, & Pembagian Tugas Tim.
2.  **[04_LAPORAN_PEMETAAN_FITUR_DAN_DATASET.md](./RL%20hasil/04_LAPORAN_PEMETAAN_FITUR_DAN_DATASET.md)** â€” Pemetaan Fitur Wajib Inti vs Sekunder/Support vs Evaluasi/QA beserta Asal Dataset Mentahnya.
3.  **[01_LAPORAN_AUDIT_DATASET_DAN_GATE1.md](./RL%20hasil/01_LAPORAN_AUDIT_DATASET_DAN_GATE1.md)** â€” Audit Presisi 74 File Dataset Bundle & Bukti Kelulusan Gate 1 Cakupan Harga PIHPS 34 Provinsi.
4.  **[02_LAPORAN_AUDIT_BPS_MASK_2022.md](./RL%20hasil/02_LAPORAN_AUDIT_BPS_MASK_2022.md)** â€” Dokumentasi Ekstraksi Matriks $34 \times 34$ (99 Koridor Perdagangan Cabai Merah Antarprovinsi) dari PDF BPS Poldis 2022.
5.  **[03_LAPORAN_LITERATUR_DAN_POSITIONING_RL_H1_02.md](./RL%20hasil/03_LAPORAN_LITERATUR_DAN_POSITIONING_RL_H1_02.md)** â€” Matriks Positioning 5 Paper Terdekat, Verifikasi Klaim RCSGNet, & Spesifikasi Baseline Handoff untuk MLE (`MLE-H4-02` & `MLE-H4-03`).
6.  **[05_DOSSIER_LENGKAP_2_JURNAL_PREMIUM_RCSGNET_DAN_MARKETDNA.txt](./RL%20hasil/05_DOSSIER_LENGKAP_2_JURNAL_PREMIUM_RCSGNET_DAN_MARKETDNA.txt)** â€” Dossier Lengkap 2 Jurnal *Potato Research* (Springer 2026): **RCSGNet** (Bai & Wang, 2026) dan **MarketDNA** (Zhu dkk., 2026).
7.  **[06_LAPORAN_PROTOKOL_EVALUASI_V1_TERKUNCI_RL_H2_01.md](./RL%20hasil/06_LAPORAN_PROTOKOL_EVALUASI_V1_TERKUNCI_RL_H2_01.md)** — Protokol Evaluasi v1.0 Terkunci (RL-H2-01, Tag protocol-v1).
8.  **[07_LAPORAN_POSITIONING_DAN_STRATEGI_KLAIM_RL_H2_02.md](./RL%20hasil/07_LAPORAN_POSITIONING_DAN_STRATEGI_KLAIM_RL_H2_02.md)** — Tabel Positioning 11 Paper Terdekat & Strategi Batas Klaim (RL-H2-02).

### 11 Tabel CSV Laporan (`RL hasil/csv_laporan/`)
- [`01_keputusan_kickoff_ALL_H1_01.csv`](./RL%20hasil/csv_laporan/01_keputusan_kickoff_ALL_H1_01.csv)
- [`02_status_audit_dataset_bundle.csv`](./RL%20hasil/csv_laporan/02_status_audit_dataset_bundle.csv)
- [`03_cakupan_harga_pihps_34_provinsi_gate1.csv`](./RL%20hasil/csv_laporan/03_cakupan_harga_pihps_34_provinsi_gate1.csv)
- [`04_rolling_origin_splits_RL_H1_01.csv`](./RL%20hasil/csv_laporan/04_rolling_origin_splits_RL_H1_01.csv)
- [`05_aturan_available_at_kontrak_v1.csv`](./RL%20hasil/csv_laporan/05_aturan_available_at_kontrak_v1.csv)
- [`06_matriks_positioning_5_paper_RL_H1_02.csv`](./RL%20hasil/csv_laporan/06_matriks_positioning_5_paper_RL_H1_02.csv)
- [`07_bps_mask_2022_matriks_34x34.csv`](./RL%20hasil/csv_laporan/07_bps_mask_2022_matriks_34x34.csv)
- [`08_bps_mask_2022_daftar_99_edges_audit.csv`](./RL%20hasil/csv_laporan/08_bps_mask_2022_daftar_99_edges_audit.csv)
- [`09_smoke_test_env_status_H1.csv`](./RL%20hasil/csv_laporan/09_smoke_test_env_status_H1.csv)
- [`10_pembagian_tugas_dan_action_items_H1_H3.csv`](./RL%20hasil/csv_laporan/10_pembagian_tugas_dan_action_items_H1_H3.csv)
- [`11_ringkasan_fitur_wajib_vs_sekunder.csv`](./RL%20hasil/csv_laporan/11_ringkasan_fitur_wajib_vs_sekunder.csv)
- [`12_audit_teliti_ketersediaan_56_fitur_dan_kolom.csv`](./RL%20hasil/csv_laporan/12_audit_teliti_ketersediaan_56_fitur_dan_kolom.csv)
- [`13_audit_teliti_ketersediaan_34_dataset_dan_tabel.csv`](./RL%20hasil/csv_laporan/13_audit_teliti_ketersediaan_34_dataset_dan_tabel.csv)
- [14_distribusi_node_days_rezim_CGS_H2_04_RL_H2_01.csv](./RL%20hasil/csv_laporan/14_distribusi_node_days_rezim_CGS_H2_04_RL_H2_01.csv)

---

## 2. File Kontrak & Deliverable Resmi di Path Proyek Utama

Seluruh file kontrak yang dibutuhkan oleh script **MDE, CGS, dan MLE** juga sudah ditempatkan langsung pada path standar kontrak:

| Job ID | Path Resmi di Repo | Deskripsi |
| :--- | :--- | :--- |
| **`ALL-H1-01`** | [`docs/decisions/ALL-H1-01.md`](./docs/decisions/ALL-H1-01.md) | Risalah 4 keputusan terbuka yang dikunci RL saat kickoff. |
| **`ALL-H1-01`** | [`docs/data_contract.md`](./docs/data_contract.md) | Kontrak Data v1.0 (9 tabel, skema kolom, tipe, kunci, aturan `available_at`). |
| **`ALL-H1-01`** | [`configs/global.yaml`](./configs/global.yaml) | Konfigurasi global (`train_start: 2018-01-02`, `holdout_start: 2026-06-01`, `horizons: [5, 10, 20]`, `origins`, `seeds`). |
| **`ALL-H1-01`** | [`src/renaro/contract.py`](./src/renaro/contract.py) | Konstanta & validator kontrak Python (`PROVINCES`, `ORIGINS`, `PANEL_REQUIRED_COLS`). |
| **`ALL-H1-01`** | [`data/ref/provinces.csv`](./data/ref/provinces.csv) | Tabel referensi 34 provinsi (`prov_code` BPS 2 digit, `iso_code`, `panel_dev_node_id`). |
| **`MLE-H0-01`** | [`scripts/check_env.py`](./scripts/check_env.py) | Script smoke test environment & pemeriksaan kebocoran holdout. |
| **`RL-H1-01`** | [`docs/eval_protocol_v0.tex`](./docs/eval_protocol_v0.tex) | Draf Protokol Evaluasi v0.1 (12 bagian, lengkap dengan [`docs/00_preamble.tex`](./docs/00_preamble.tex) & [`docs/references.bib`](./docs/references.bib)). |
| **`RL-H1-02`** | [`docs/lit/rcsgnet.tex`](./docs/lit/rcsgnet.tex) | Catatan literatur Prioritas #1: **RCSGNet** (Bai & Wang, *Potato Research* 2026). |
| **`RL-H1-02`** | [`docs/lit/marketdna.tex`](./docs/lit/marketdna.tex) | Catatan literatur: **MarketDNA** (Zhu dkk., *Potato Research* 2026). |
| **`RL-H1-02`** | [`docs/lit/millgnn.tex`](./docs/lit/millgnn.tex) | Catatan literatur Prioritas #2: **MillGNN** (2025) & **SAMSGL** (2023). |
| **`RL-H1-02`** | [`docs/lit/sdgf.tex`](./docs/lit/sdgf.tex) | Catatan literatur: **SDGF** (2025) & **DRAN** (2025). |
| **`RL-H1-02`** | [`docs/lit/steve.tex`](./docs/lit/steve.tex) | Catatan literatur: **STEVE** (KDD 2025) & **DynaSTar** (IJCAI 2026). |
| **`MDE-H2-03`** | [`reports/qa/bps_mask.md`](./reports/qa/bps_mask.md) | Laporan QA ekstraksi 99 koridor perdagangan BPS Poldis 2022 (data CSV/NPY di [`RL hasil/supporting_data/`](./RL%20hasil/supporting_data/)). |

| **RL-H2-01** | [docs/eval_protocol_v1.md](./docs/eval_protocol_v1.md) & [docs/eval_protocol_v1.tex](./docs/eval_protocol_v1.tex) | Protokol Evaluasi v1.0 Terkunci (protocol-v1) & [docs/protocol_amendments.md](./docs/protocol_amendments.md). |

| **RL-H2-02** | [docs/positioning.md](./docs/positioning.md) & [docs/positioning.tex](./docs/positioning.tex) | Tabel Positioning 11 Paper Terdekat vs Studi Ini & 3 Kalimat Posisi Resmi. |

