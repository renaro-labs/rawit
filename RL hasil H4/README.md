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
   - Audit forensik lengkap atas **111 run data riil** di `experiments/registry.csv` (`51` run H3 + `60` run neural H4, `split_hash = 411aec1a...`) serta **30 run sintetis/recovery** terbaru (`gwn`, `mtgnn`, `module1`, `recovery_metrics.csv`) pada commit `8b4aac4`.
6. **[experiments/anomaly_report_H4.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/experiments/anomaly_report_H4.md)** *(salinan di folder ini: `05_LAPORAN_ANOMALI_RUN_HARIAN_RL_H4_02.md`)*
   - Laporan anomali khusus `RL-H4-02` yang membedah 6 anomali terverifikasi (`ANOM-01` s/d `ANOM-06`), matriks 6 kriteria wajib, tabel 30 run individual ber-CV tinggi (`5,85%`–`12,11%`), ketidaksetaraan config `n_lags: 6 vs 8` & `epochs: 5 vs 10`, `checkpoint=False`, bloker 3/8 model Gate 2, serta draf eskalasi ke MLE.
7. **[experiments/anomaly_report_H4.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/experiments/anomaly_report_H4.csv)** *(salinan di folder ini: `csv_laporan/02_daftar_anomali_run_harian_RL_H4_02.csv`)*
   - Register anomali terstruktur (11 baris) siap olah untuk pelacakan penutupan temuan pada sesi H5 / Gate 2.
8. **[RL-H4-02__run_review_log.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/upcoming_H2_H7_starters/RL-H4-02__run_review_log.tex)** *(salinan di folder ini & di `experiments/review_log.tex`)*
   - Versi LaTeX terisi penuh (**0 `\todo{}`**).
9. **[csv_laporan/01_audit_run_harian_registry_dan_sintetis_RL_H4_02.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil%20H4/csv_laporan/01_audit_run_harian_registry_dan_sintetis_RL_H4_02.csv)**
   - Tabel rekap CSV lengkap 20 baris audit seluruh kelompok run di `experiments/registry.csv` dan artefak sintetis repo.
