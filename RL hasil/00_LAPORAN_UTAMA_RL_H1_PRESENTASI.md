# Laporan Utama & Deck Presentasi RL (Research Lead) â€” Hari 1 (H1)
**Proyek:** *Climate-Conditioned Dynamic Graph Learning for Food Price Forecasting Under Extreme Weather and Climate Regime Shifts* (Sprint 1 Â· Renaro Lab)  
**Penyaji:** RL (*Research Lead*)  
**Audiens:** MDE (*Market Data Engineer*), CGS (*Climate & Geospatial Scientist*), MLE (*ML/Graph Modeling Engineer*)  
**Tanggal:** 23 November 2026  

---

## Daftar Isi Folder `RL hasil/` (Siap Dipresentasikan & Dibagikan ke Tim)

### A. Laporan Presentasi (Markdown)
1. **[00_LAPORAN_UTAMA_RL_H1_PRESENTASI.md](./00_LAPORAN_UTAMA_RL_H1_PRESENTASI.md)** *(Dokumen ini â€” Naskah Presentasi Kickoff & Laporan H1 RL)*
2. **[01_LAPORAN_AUDIT_DATASET_DAN_GATE1.md](./01_LAPORAN_AUDIT_DATASET_DAN_GATE1.md)** *(Laporan Audit Presisi 74 File Dataset, Cakupan 34 Provinsi, & Gap Menuju Gate 1)*
3. **[02_LAPORAN_AUDIT_BPS_MASK_2022.md](./02_LAPORAN_AUDIT_BPS_MASK_2022.md)** *(Laporan Ekstraksi & Verifikasi Bilateral 99 Directed Edges Poldis BPS 2022)*
4. **[03_LAPORAN_LITERATUR_DAN_POSITIONING_RL_H1_02.md](./03_LAPORAN_LITERATUR_DAN_POSITIONING_RL_H1_02.md)** *(Ringkasan 5 Paper Pembeda `RL-H1-02` & Spesifikasi Baseline untuk MLE)*
5. **[ALL-H1-01.md](./ALL-H1-01.md)** & **[data_contract.md](./data_contract.md)** *(Keputusan Resmi Kickoff & Kontrak Data v1.0)*

### B. Tabel CSV Siap Pakai & Presentasi (`RL hasil/csv_laporan/`)
1. **[01_keputusan_kickoff_ALL_H1_01.csv](./csv_laporan/01_keputusan_kickoff_ALL_H1_01.csv)** â€” 5 keputusan kunci yang dikunci RL beserta alasan ilmiah & dampak per role.
2. **[02_status_audit_dataset_bundle.csv](./csv_laporan/02_status_audit_dataset_bundle.csv)** â€” Status OK vs Kurang/Missing dari seluruh 12 komponen data Sprint 1.
3. **[03_cakupan_harga_pihps_34_provinsi_gate1.csv](./csv_laporan/03_cakupan_harga_pihps_34_provinsi_gate1.csv)** â€” Statistik presisi 34 provinsi (kode BPS, kode ISO, cakupan harga tradisional & produsen, in/out-degree BPS).
4. **[04_rolling_origin_splits_RL_H1_01.csv](./csv_laporan/04_rolling_origin_splits_RL_H1_01.csv)** â€” Batas tanggal `O1`, `O2`, `O3`, dan `HOLDOUT` beserta embargo 20 hari kerja.
5. **[05_aturan_available_at_kontrak_v1.csv](./csv_laporan/05_aturan_available_at_kontrak_v1.csv)** â€” Aturan anti-bocor waktu (`available_at`) untuk 9 keluarga fitur.
6. **[06_matriks_positioning_5_paper_RL_H1_02.csv](./csv_laporan/06_matriks_positioning_5_paper_RL_H1_02.csv)** â€” Matriks *head-to-head* studi kita vs RCSGNet, MarketDNA, MillGNN, SAMSGL, SDGF/DRAN, STEVE/DynaSTar.
7. **[07_bps_mask_2022_matriks_34x34.csv](./csv_laporan/07_bps_mask_2022_matriks_34x34.csv)** â€” Matriks biner terarah $34 \times 34$ hasil ekstraksi Poldis BPS 2022.
8. **[08_bps_mask_2022_daftar_99_edges_audit.csv](./csv_laporan/08_bps_mask_2022_daftar_99_edges_audit.csv)** â€” Daftar lengkap 99 directed edges dengan kode BPS, jarak (km), nomor halaman PDF/cetak, dan status verifikasi bilateral.
9. **[09_smoke_test_env_status_H1.csv](./csv_laporan/09_smoke_test_env_status_H1.csv)** â€” Hasil 22 titik pemeriksaan `check_env.py` (20 PASS, 2 Action Items untuk H2/H3).
10. **[10_pembagian_tugas_dan_action_items_H1_H3.csv](./csv_laporan/10_pembagian_tugas_dan_action_items_H1_H3.csv)** â€” Instruksi kerja RL kepada MDE, CGS, dan MLE menuju Gate 1 (H3).

### C. File LaTeX Deliverable Resmi RL
* **[RL-H1-01__eval_protocol_v0.tex](./RL-H1-01__eval_protocol_v0.tex)** *(Protokol Evaluasi v0 lengkap 12 bagian)*
* **[RL-H1-02__lit_rcsgnet.tex](./RL-H1-02__lit_rcsgnet.tex)**, **[RL-H1-02__lit_millgnn.tex](./RL-H1-02__lit_millgnn.tex)**, **[RL-H1-02__lit_marketdna.tex](./RL-H1-02__lit_marketdna.tex)**, **[RL-H1-02__lit_sdgf.tex](./RL-H1-02__lit_sdgf.tex)**, **[RL-H1-02__lit_steve.tex](./RL-H1-02__lit_steve.tex)**

---

## Ringkasan Eksekutif untuk Dipresentasikan RL kepada Tim

### 1. Tujuan & Cakupan Sprint 1 (09.00â€“09.20)
* **Hipotesis Inti**: Mengondisikan **bobot edge berarah dan distribusi jeda ($\ell \in \{0..8\}$ pentad)** pada **iklim teramati di provinsi asal ($c_j$: hujan pentad CHIRPS, *dry spell*, RONI)** menghasilkan prediksi harga Cabai Merah Keriting yang lebih akurat dan lebih tahan pada rezim iklim jarang (El NiÃ±o/kekeringan/hujan ekstrem) dibanding model yang menginferensi rezim secara laten dari harga (**RCSGNet**) atau lag graph tanpa iklim (**MillGNN**).
* **Tiga Gate Keputusan**:
  * **Gate 1 (H3)**: Uji kelayakan data ($\ge 20$ provinsi cakupan $\ge 90\%$ selama $\ge 5$ tahun + iklim lengkap) dan sinyal RQ0 (LightGBM `(c)` dengan hujan asal berjeda menurunkan MAE vs `(b)` $\ge 3\%$ rata-rata pada $h=10$ di $\ge 2/3$ origin, atau DM $p < 0{,}05$ di $\ge 1$ rezim).
  * **Gate 2 (H5)**: Semua baseline wajib + Modul 1â€“3 selesai pada split identik, lolos uji pemulihan jeda sintetis (akurasi $\ge 0{,}80$, Spearman $\ge 0{,}70$), dan model dibekukan di `frozen/manifest.yaml`.
  * **Gate 3 (H7)**: Buka holdout ($\ge$ 1 Juni 2026) **satu kali**, evaluasi tanpa tuning, dan tentukan jalur Sprint 2 (Jalur A: metode penuh; Jalur B: benchmark + temuan empiris; Jalur C: pivot).

### 2. Empat Keputusan Terbuka yang Dikunci RL (`ALL-H1-01`)
1. **Horizon & Window**: $h \in \{5, 10, 20\}$ hari kerja; **utama $h = 10$**; window input $W = 60$ hari kerja.
2. **Target & Metrik**: Model dilatih pada **$\log(\text{price})$ level** pasar tradisional (`price_type=1`); semua metrik (**MAE**, **RMSE**, **sMAPE**, **worst-regime error**, **$\Delta$ error OOD**, uji **DM-HLN** lag HAC $= h-1$) dihitung pada skala **Rp/kg** setelah transformasi invers $\exp()$.
3. **Ketersediaan CHIRPS (`CGS-H2-03`)**: **Opsi B dikunci sebagai aturan utama** (`available_at = pentad_end + 2 hari`, memakai `final_sat` sebagai proksi prelim); **Opsi A** (jeda rilis aktual `pentad_end + 5 hari` / `month_end + 21 hari`) dijalankan sebagai uji sensitivitas di `reports/qa/chirps_release_lag.md`.
4. **Origin *Rolling-Origin* (`RL-H1-01`)**:
   * **`O1`**: Latih `2018-01-02..2022-06-30` | Val `2022H2` | Uji **`2023-01-01..2023-12-31`** (Onset El NiÃ±o 2023)
   * **`O2`**: Latih `2018-01-02..2023-06-30` | Val `2023H2` | Uji **`2024-01-01..2024-12-31`** (Puncak/Transisi El NiÃ±o 2024)
   * **`O3`**: Latih `2018-01-02..2024-06-30` | Val `2024H2` | Uji **`2025-01-01..2026-05-31`** (Netral/La NiÃ±a 2025 â€“ Mei 2026)
   * **`HOLDOUT`**: Latih `2018-01-02..2025-12-31` | Val `2026-01..05` | Uji **`SEALED` (`2026-06-01..2026-11-20`)**
   * Embargo antar-split = **20 hari kerja**.

### 3. Temuan Audit Dataset & Tugas Kritis Tim Menuju Gate 1 (H3)
* **Yang Sudah Beres (âœ…)**:
  1. **Harga PIHPS Tradisional**: **34/34 provinsi lolos syarat Gate 1** dengan cakupan valid `95,67%` (Maluku) s/d `97,63%` (Jawa Tengah) selama 2.195 hari kerja (`2018-01-01..2026-05-29`).
  2. **Mask Graph BPS Poldis 2022 (`MDE-H2-03`)**: Sudah diekstrak penuh oleh RL+MDE menjadi **99 directed edges** (`bps_mask_2022.csv` & `bps_mask.npy`), lengkap dengan audit 195 halaman PDF dan solusi fallback untuk **Papua (`94`)** yang ber-*in-degree* 0.
  3. **Batas Wilayah, Grid CHIRPS $0{,}05^\circ$, Kalender SKB, & RONI NOAA**: 100% lengkap dan lolos verifikasi SHA-256 (74/74 file).
* **Dua Tugas Kritis yang Harus Diselesaikan CGS & MDE Sebelum Gate 1 (âŒ $\to$ Target H2/H3)**:
  1. **[KRITIS â€” CGS] Selesaikan Unduhan CHIRPS v3 (`2019-05` s/d `2026-11`)**: Saat ini baru ada 16/107 bulan (`2018-01..2019-04` = 485 hari), sehingga 13 kolom iklim di `panel_dev.parquet` masih 100% `NaN`. CGS wajib melanjutkan unduhan 91 bulan tersisa dan menghitung fitur pentad (`CGS-H2-01` & `CGS-H2-02`).
  2. **[KRITIS â€” CGS & MDE] Segel Baris Holdout Mentah ($\ge$ `2026-06-01`)**: Pindahkan 8.442 baris harga PIHPS (`2026-06-01..2026-11-23`) di `data/raw/pihps/` dan 4 musim RONI (`MJJ..ASO 2026`) ke `RENARO_SEALED_DIR` (`CGS-H3-02`).

