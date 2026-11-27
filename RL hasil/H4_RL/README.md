# Folder Khusus H4 RL — Research Lead (`@alim`) · Kamis 26 Nov 2026 (H4)

Folder ini berisi seluruh hasil kerja **Research Lead (RL)** pada **Hari ke-4 (H4)** untuk tugas **`RL-H4-01 · Draft pendahuluan, related work, metode`** (siap diintegrasikan pada `RL-H7-01` dan di-*commit* ke `reports/sprint1/`).

---

## Daftar File Deliverable `RL-H4-01`

1. **[01_pendahuluan.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/reports/sprint1/01_pendahuluan.md)** *(salinan di folder ini: `01_pendahuluan.md`)*
   - Masalah keterkaitan harga cabai antarprovinsi & pergeseran dependensi mengikuti iklim, `RQ0`–`RQ3` (termasuk status lulus Gate 1 H3), kontribusi berurutan **benchmark $\to$ bukti empiris $\to$ metode** (seluruh klaim kebaruan memakai *"sepengetahuan kami"*), ruang lingkup **Scope A**, serta batas studi (**bukan identifikasi kausal**).
2. **[02_related_work.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/reports/sprint1/02_related_work.md)** *(salinan di folder ini: `02_related_work.md`)*
   - Ringkasan `docs/positioning.md` dalam **4 kelompok literatur sesuai Brief v2 §2**, matriks positioning 11 paper terdekat vs Studi ini, dan 3 kalimat posisi resmi (100% kategori AMAN).
3. **[03_metode.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/reports/sprint1/03_metode.md)** *(salinan di folder ini: `03_metode.md`)*
   - Representasi data & aturan ketersediaan `available_at <= t`, **Modul 1** (persamaan resmi $A^{(\ell)}_{ij,t}$ Brief §5 + 6 komponen arsitektur & kompleksitas 34 node), **Modul 2–3** (rumus *reliability gate* $g_{t,i}$ atas `shock`/`rel`/`shift`), **Modul 4 (*stretch*)**, daftar baseline wajib + uji sintetis + ablasi, ringkasan Protokol Evaluasi v1.0 (`protocol-v1`), dan tabel Batas Klaim.
4. **[RL-H4-01__report_sections.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/upcoming_H2_H7_starters/RL-H4-01__report_sections.tex)** *(salinan di folder ini & di `reports/sprint1/`)*
   - Versi LaTeX terisi penuh (**0 `\todo{}`**) yang sinkron 100% dengan ketiga berkas Markdown.

---

## Daftar File Deliverable `RL-H4-02` (Review Run Harian H4–H5 & Laporan Anomali)

5. **[experiments/review_log.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/experiments/review_log.md)** *(salinan di folder ini: `04_review_log_RL_H4_02.md`)*
   - Log review kronologis Sesi H4 (`8b4aac4`, 111 run) dan **Sesi H5 (`54791ba`, 243 run `experiments/registry.csv` + 30 run sintetis = 273 run)**: cek `split_hash`, 5 seed, `git_sha_clean()`, varians antar-seed, dan bloker Gate 2.
6. **[experiments/anomaly_report_H4.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/experiments/anomaly_report_H4.md)** & **[experiments/anomaly_report_H4.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/experiments/anomaly_report_H4.csv)** *(salinan: `05_LAPORAN_ANOMALI_RUN_HARIAN_RL_H4_02.md`, `csv_laporan/02_daftar_anomali_run_harian_RL_H4_02.csv`)*
   - Laporan & register anomali Sesi H4 (`ANOM-01` s/d `ANOM-06`).
7. **[experiments/anomaly_report_H5.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/experiments/anomaly_report_H5.md)** & **[experiments/anomaly_report_H5.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/experiments/anomaly_report_H5.csv)** *(salinan: `06_LAPORAN_ANOMALI_RUN_HARIAN_H5_RL_H4_02.md`, `csv_laporan/04_daftar_anomali_run_harian_H5_RL_H4_02.csv`)*
   - Laporan & register anomali Sesi H5 (`54791ba`): pelacakan `ANOM-01`..`ANOM-06` + temuan baru `ANOM-07` (bug `aggregate_ablation.py` L116–117), `ANOM-08` (polusi kolom `model` & unweighted `val_mae` di `robustness.py`), `ANOM-09` (`module23` 2-epoch & `no_calendar` ablasi 1-epoch), dan `ANOM-10` (duplikasi mask perturbasi).
8. **[RL-H4-02__run_review_log.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/upcoming_H2_H7_starters/RL-H4-02__run_review_log.tex)** *(salinan di folder ini & di `experiments/review_log.tex`)*
   - Versi LaTeX H4–H5 terisi penuh (**0 `\todo{}`**).
9. **CSV Rekap Audit Run Harian**:
   - Sesi H4 (`8b4aac4`): [csv_laporan/01_audit_run_harian_registry_dan_sintetis_RL_H4_02.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil%20H4/csv_laporan/01_audit_run_harian_registry_dan_sintetis_RL_H4_02.csv)
   - Sesi H5 (`54791ba`, 243 registry + 30 sintetis): [csv_laporan/03_audit_run_harian_H5_243_registry_dan_30_sintetis_RL_H4_02.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil%20H4/csv_laporan/03_audit_run_harian_H5_243_registry_dan_30_sintetis_RL_H4_02.csv)
