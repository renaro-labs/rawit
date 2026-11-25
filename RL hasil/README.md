# Indeks Lengkap Hasil Kerja RL (*Research Lead*) — Sprint 1 (H1 – H3)

Folder **`RL hasil/`** ini berisi seluruh hasil kerja, laporan presentasi, dossier jurnal, tabel CSV, dokumen kontrak, dan deliverable LaTeX untuk peran **RL (*Research Lead*)** yang sudah dirapikan dan siap dipresentasikan maupun dibagikan kepada anggota tim lainnya (**MDE**, **CGS**, dan **MLE**).

- **Folder Khusus Hari ke-3 (H3 RL)**: Tersedia di subfolder **[H3_RL/](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/README.md)** (serta di root workspace **[RL hasil H3/](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil%20H3/README.md)**).

---

## Struktur Folder `RL hasil/`

### 1. Laporan Utama & Dossier Presentasi (di Root `RL hasil/`)
Buka file-file bernomor **`00` s.d. `10`** ini secara berurutan saat memimpin rapat atau membaca ringkasan kerja RL:

| No | Nama File | Isi & Kegunaan Utama |
| :-: | :--- | :--- |
| **00** | [00_LAPORAN_UTAMA_RL_H1_PRESENTASI.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/00_LAPORAN_UTAMA_RL_H1_PRESENTASI.md) | **Laporan Eksekutif Utama RL H1**: Cakupan Wajib vs Stretch, 4 Keputusan Terbuka yang dikunci (`ALL-H1-01`), Protokol Evaluasi v0.1 (`RL-H1-01`), Hasil Smoke Test Environment, dan Pembagian Tugas H1–H3. |
| **01** | [01_LAPORAN_AUDIT_DATASET_DAN_GATE1.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/01_LAPORAN_AUDIT_DATASET_DAN_GATE1.md) | **Laporan Audit Dataset & Gate 1**: Verifikasi SHA256 74 file dataset (193,57 MiB), bukti kelulusan Gate 1 PIHPS Pasar Tradisional (34/34 provinsi $\ge 97,68\%$), dan identifikasi 2 bloker H2/H3. |
| **02** | [02_LAPORAN_AUDIT_BPS_MASK_2022.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/02_LAPORAN_AUDIT_BPS_MASK_2022.md) | **Laporan Ekstraksi Graf Perdagangan BPS Poldis 2022**: Dokumentasi ekstraksi matriks berarah $34 \times 34$ (99 koridor perdagangan cabai merah antarprovinsi) dari PDF BPS Poldis 2022 Hal. 32–164. |
| **03** | [03_LAPORAN_LITERATUR_DAN_POSITIONING_RL_H1_02.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/03_LAPORAN_LITERATUR_DAN_POSITIONING_RL_H1_02.md) | **Laporan Kajian Literatur & Handoff Baseline (`RL-H1-02`)**: Matriks positioning 5 kelompok paper, lembar verifikasi wajib RCSGNet & MarketDNA, serta spesifikasi PyTorch untuk `MLE-H4-02` & `MLE-H4-03`. |
| **04** | [04_LAPORAN_PEMETAAN_FITUR_DAN_DATASET.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/04_LAPORAN_PEMETAAN_FITUR_DAN_DATASET.md) | **Laporan Pemetaan Fitur & Asal Dataset**: Rangkuman lengkap fitur **Wajib Inti** vs **Sekunder/Support** vs **Khusus Evaluasi/QA (Dilarang Masuk Fitur)** beserta asal file mentahnya di `data/raw/`. |
| **05** | [05_DOSSIER_LENGKAP_2_JURNAL_PREMIUM_RCSGNET_DAN_MARKETDNA.txt](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/05_DOSSIER_LENGKAP_2_JURNAL_PREMIUM_RCSGNET_DAN_MARKETDNA.txt) | **Dossier Lengkap 2 Jurnal Premium (`.txt`)**: Metadata penuh, abstrak verbatim Inggris + terjemahan Indonesia, persamaan matematis 4 modul RCSGNet & 3 modul MarketDNA, dataset, baseline, studi ablasi, dan kalimat siap kutip. |
| **06** | [06_LAPORAN_PROTOKOL_EVALUASI_V1_TERKUNCI_RL_H2_01.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/06_LAPORAN_PROTOKOL_EVALUASI_V1_TERKUNCI_RL_H2_01.md) | **Protokol Evaluasi v1.0 Terkunci (`RL-H2-01` / `protocol-v1`)**: Dokumen protokol evaluasi final yang mengintegrasikan definisi & jumlah sampel rezim `CGS-H2-04`, aturan `available_at` & bukti HTTP HEAD probe `CGS-H2-03`, batas holdout tersegel `CGS-H3-02`, dan cakupan 34 provinsi `MDE-H1-03`. |
| **07** | [07_LAPORAN_POSITIONING_DAN_STRATEGI_KLAIM_RL_H2_02.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/07_LAPORAN_POSITIONING_DAN_STRATEGI_KLAIM_RL_H2_02.md) | **Tabel Positioning 11 Paper Terdekat & Strategi Batas Klaim (`RL-H2-02`)**: Matriks 12 baris (11 paper pesaing + Studi ini), tabel sumber per baris, 3 kalimat posisi resmi, dan strategi pembukaan peluang temuan eksperimental H4–H6. |
| **08** | [08_LAPORAN_AUDIT_MDE_H3_DAN_REVIEW_RQ0_RL_H3_01.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/08_LAPORAN_AUDIT_MDE_H3_DAN_REVIEW_RQ0_RL_H3_01.md) | **Audit Final `dataset_v1` MDE & Review RQ0 (`RL-H3-01`)**: Persetujuan 4 poin revisi MDE (`MDE-H2-01` & `MDE-H3-01`), audit pra-run fitur `(a)/(b)/(c)` & `available_at <= t`, serta evaluasi penuh 45-run LightGBM RQ0 & uji Diebold–Mariano. |
| **09** | [09_TEMPLATE_KEPUTUSAN_GATE1_RL_H3_02.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/09_TEMPLATE_KEPUTUSAN_GATE1_RL_H3_02.md) | **Dokumen Keputusan Gate 1 (`RL-H3-02` / `ALL-H3-01` — `docs/decisions/GATE1.md`)**: Bukti cakupan data harga (`98,30%`), hasil RQ0 (`c vs b`), dan penetapan **Opsi A (Lanjut Penuh dengan Catatan Rezim)**. |
| **10** | [10_LAPORAN_HASIL_EKSEKUSI_RQ0_LENGKAP_RL_H3_01.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/10_LAPORAN_HASIL_EKSEKUSI_RQ0_LENGKAP_RL_H3_01.md) | **Ringkasan Eksekusi Benchmark RQ0 (`reports/rq0/rq0_summary.md`)**: Tabel MAE/RMSE/sMAPE `(a)`, `(b)`, `(c)` vs `Seasonal Naive` & `Naive Last`, uji DM per rezim, dan Top-15 Permutation Feature Importance. |

---

### 2. Subfolder `csv_laporan/` (22 Tabel CSV Siap Buka di Excel / Google Sheets)
Seluruh angka, keputusan, matriks, dan pembagian tugas dalam format tabel `.csv`:

| No | Nama File CSV | Keterangan Isi |
| :-: | :--- | :--- |
| **01** | [01_keputusan_kickoff_ALL_H1_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/01_keputusan_kickoff_ALL_H1_01.csv) | 4 Keputusan Terbuka (`ALL-H1-01`) + keputusan penanganan Harga Produsen yang dikunci RL. |
| **02** | [02_status_audit_dataset_bundle.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/02_status_audit_dataset_bundle.csv) | Status kesiapan 12 komponen dataset di workspace (OK vs Bloker H2/H3). |
| **03** | [03_cakupan_harga_pihps_34_provinsi_gate1.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/03_cakupan_harga_pihps_34_provinsi_gate1.csv) | Persentase cakupan observasi harga Pasar Tradisional vs Produsen per provinsi (34 provinsi). |
| **04** | [04_rolling_origin_splits_RL_H1_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/04_rolling_origin_splits_RL_H1_01.csv) | Tanggal batas Train, Embargo (20 hari kerja), Val, dan Test untuk `O1`, `O2`, `O3`, dan `HOLDOUT`. |
| **05** | [05_aturan_available_at_kontrak_v1.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/05_aturan_available_at_kontrak_v1.csv) | 9 aturan ketersediaan rilis (`available_at <= t`) untuk mencegah *data leakage*. |
| **06** | [06_matriks_positioning_5_paper_RL_H1_02.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/06_matriks_positioning_5_paper_RL_H1_02.csv) | Matriks perbandingan 5 paper utama (`RCSGNet`, `MarketDNA`, `MillGNN`, `SDGF`, `STEVE`) vs Studi Kita. |
| **07** | [07_bps_mask_2022_matriks_34x34.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/07_bps_mask_2022_matriks_34x34.csv) | Matriks biner $34 \times 34$ koridor perdagangan cabai merah antarprovinsi BPS Poldis 2022. |
| **08** | [08_bps_mask_2022_daftar_99_edges_audit.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/08_bps_mask_2022_daftar_99_edges_audit.csv) | Daftar 99 koridor perdagangan berarah (`src -> dst`) lengkap dengan nomor halaman PDF BPS sebagai bukti audit. |
| **09** | [09_smoke_test_env_status_H1.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/09_smoke_test_env_status_H1.csv) | Hasil 22 pemeriksaan `python scripts/check_env.py` (20 LULUS, 2 catatan tugas H2/H3). |
| **10** | [10_pembagian_tugas_dan_action_items_H1_H3.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/10_pembagian_tugas_dan_action_items_H1_H3.csv) | Daftar *action items* untuk RL, MDE, CGS, dan MLE menuju Gate 1 (H3). |
| **11** | [11_ringkasan_fitur_wajib_vs_sekunder.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/11_ringkasan_fitur_wajib_vs_sekunder.csv) | Tabel klasifikasi seluruh fitur (**Wajib Inti**, **Sekunder/Support**, **Dilarang Masuk Fitur**) beserta asal dataset-nya. |
| **12** | [12_audit_teliti_ketersediaan_56_fitur_dan_kolom.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/12_audit_teliti_ketersediaan_56_fitur_dan_kolom.csv) | Audit kolom-demi-kolom (56 fitur/kolom): jumlah baris terisi vs kosong dari 74.630 baris, % ketersediaan, cakupan provinsi, min/max/mean, aturan `available_at`, asal dataset mentah, dan PIC. |
| **13** | [13_audit_teliti_ketersediaan_34_dataset_dan_tabel.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/13_audit_teliti_ketersediaan_34_dataset_dan_tabel.csv) | Audit file-demi-file (34 dataset/tabel): status keberadaan (`ADA` vs `BELUM_ADA`), ukuran KB, dimensi baris $\times$ kolom, % kesiapan isi, fitur yang dihasilkan, dan tindak lanjut. |
| **14** | [14_distribusi_node_days_rezim_CGS_H2_04_RL_H2_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/14_distribusi_node_days_rezim_CGS_H2_04_RL_H2_01.csv) | Distribusi jumlah sampel (`node_days`) per origin (`O1`, `O2`, `O3`, `HOLDOUT`) dan per rezim (`dry`, `extreme_wet`, `el_nino`, `la_nina`, `normal`) beserta penanda `CI lebar` (`< 200` node-days) untuk `RL-H2-01`. |
| **15** | [15_matriks_lengkap_12_paper_positioning_RL_H2_02.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/15_matriks_lengkap_12_paper_positioning_RL_H2_02.csv) | Matriks lengkap 12 baris $\times$ 12 kolom (`RL-H2-02`): perbandingan 11 paper terdekat (`RCSGNet`, `MarketDNA`, `MillGNN`, `SAMSGL`, `CRAFormer`, `DRAN`, `SDGF`, `STEVE`, `CGNN`, `Min et al. 2025`, `Teh Sri Lanka`) vs `Studi ini`. |
| **16** | [16_audit_revisi_mde_dan_dataset_v1_beku_H3.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/16_audit_revisi_mde_dan_dataset_v1_beku_H3.csv) | Audit 12 item atas revisi MDE (`MDE-H2-01` & `MDE-H3-01`) dan status keputusan RL (`ACC - TIDAK PERLU REVISI`). |
| **17** | [17_benchmark_sanity_acuan_rq0_RL_H3_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/17_benchmark_sanity_acuan_rq0_RL_H3_01.csv) | Benchmark sanity acuan `Seasonal Naive (lag 260)` dan `Naive Last (lag 0)` per origin dan horizon. |
| **18** | [18_statistik_lengkap_36_kolom_panel_dataset_v1_mde.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/18_statistik_lengkap_36_kolom_panel_dataset_v1_mde.csv) | Statistik deskriptif lengkap ke-36 kolom `panel.parquet` (`dataset_v1_mde`). |
| **19** | [19_profil_34_provinsi_dataset_v1_sp2kp_dan_pemasok_bps.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/19_profil_34_provinsi_dataset_v1_sp2kp_dan_pemasok_bps.csv) | Profil 34 provinsi: harga PIHPS, *carry-forward* tipe 1 & tipe 4, deviasi & korelasi SP2KP, serta pemasok utama BPS 2022. |
| **20** | [20_hasil_lengkap_rq0_a_b_c_vs_naive_RL_H3_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/20_hasil_lengkap_rq0_a_b_c_vs_naive_RL_H3_01.csv) | Hasil lengkap MAE/RMSE/sMAPE untuk `Seasonal Naive`, `Naive Last`, dan Varian `(a)`, `(b)`, `(c)` (5 seed) pada seluruh origin `O1..O3` dan horizon $h \in \{5, 10, 20\}$. |
| **21** | [21_hasil_uji_dm_dan_per_rezim_rq0_RL_H3_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/21_hasil_uji_dm_dan_per_rezim_rq0_RL_H3_01.csv) | Hasil uji statistik Diebold–Mariano (Newey–West HAC) per origin, agregat 3 origin, dan per rezim iklim (`el_nino`, `la_nina`, `normal`). |
| **22** | [22_permutation_feature_importance_top15_varian_c_h10_RL_H3_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/22_permutation_feature_importance_top15_varian_c_h10_RL_H3_01.csv) | Peringkat Top-15 Permutation Feature Importance pada Varian `(c)` horizon utama $h=10$. |

---

### 3. Subfolder `dokumen_kontrak_dan_keputusan/` (Salinan File Kontrak & Konfigurasi yang Dikunci RL)
Salinan file kontrak resmi yang juga sudah terpasang di folder proyek utama (`docs/`, `configs/`, `src/renaro/`):
- [ALL-H1-01.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/dokumen_kontrak_dan_keputusan/ALL-H1-01.md) — Risalah 4 keputusan terbuka kickoff (`docs/decisions/ALL-H1-01.md`).
- [data_contract.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/dokumen_kontrak_dan_keputusan/data_contract.md) — Kontrak Data v1.0 (`docs/data_contract.md`).
- [global.yaml](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/dokumen_kontrak_dan_keputusan/global.yaml) — Konfigurasi global yang dikunci (`configs/global.yaml`).
- [contract.py](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/dokumen_kontrak_dan_keputusan/contract.py) — Konstanta & validator Python (`src/renaro/contract.py`).

---

### 4. Subfolder `latex_deliverables_H1/` (Deliverable Resmi LaTeX RL Hari ke-1)
Salinan seluruh dokumen `.tex` dan `.bib` tugas `RL-H1-01` dan `RL-H1-02` yang sudah selesai diisi (juga sudah terpasang di `docs/` dan `docs/lit/`):
- [00_preamble.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/latex_deliverables_H1/00_preamble.tex) — Preamble LaTeX bersama.
- [references.bib](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/latex_deliverables_H1/references.bib) — Bibliografi BibTeX (sudah diperbarui dengan penulis & volume resmi RCSGNet dan MarketDNA).
- [RL-H1-01__eval_protocol_v0.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/latex_deliverables_H1/RL-H1-01__eval_protocol_v0.tex) — Draf Protokol Evaluasi v0.1 lengkap 12 bagian (`docs/eval_protocol_v0.tex`).
- [RL-H1-02__lit_rcsgnet.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/latex_deliverables_H1/RL-H1-02__lit_rcsgnet.tex) — Catatan literatur Prioritas #1: **RCSGNet** (Bai & Wang, *Potato Research* Vol. 69 No. 5, Juni 2026).
- [RL-H1-02__lit_marketdna.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/latex_deliverables_H1/RL-H1-02__lit_marketdna.tex) — Catatan literatur: **MarketDNA** (Zhu, Yang, Ling, Wei, & Dai, *Potato Research*, Agustus 2026).
- [RL-H1-02__lit_millgnn.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/latex_deliverables_H1/RL-H1-02__lit_millgnn.tex) — Catatan literatur Prioritas #2: **MillGNN** (2025) & **SAMSGL** (2023).
- [RL-H1-02__lit_sdgf.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/latex_deliverables_H1/RL-H1-02__lit_sdgf.tex) — Catatan literatur: **SDGF** (2025) & **DRAN** (2025).
- [RL-H1-02__lit_steve.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/latex_deliverables_H1/RL-H1-02__lit_steve.tex) — Catatan literatur: **STEVE** (KDD 2025) & **DynaSTar** (IJCAI 2026).

---

### 5. Subfolder `supporting_data/` (Data Referensi & Matriks BPS Hasil Ekstraksi)
- [provinces.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/supporting_data/provinces.csv) — Tabel jembatan 34 provinsi (`contract_node_idx 0..33`, `prov_code` BPS 2 digit, `iso_code`, `panel_dev_node_id`).
- [availability.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/supporting_data/availability.csv) — Tabel aturan ketersediaan rilis (`available_at`).
- [bps_mask_2022.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/supporting_data/bps_mask_2022.csv), [bps_mask_2022_pages.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/supporting_data/bps_mask_2022_pages.csv), [bps_mask_entry.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/supporting_data/bps_mask_entry.csv), [bps_mask.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/supporting_data/bps_mask.csv), [bps_mask.npy](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/supporting_data/bps_mask.npy) — Hasil ekstraksi lengkap graf perdagangan BPS Poldis 2022.

---

### 6. Subfolder `upcoming_H2_H7_starters/` (Template Tugas RL Hari ke-2 s.d. Hari ke-7)
Berisi template LaTeX resmi untuk hari-hari berikutnya (`RL-H2-01` s.d. `RL-H7-01`) beserta `00_preamble.tex` dan `references.bib` terbaru agar siap dikerjakan mulai H2.
