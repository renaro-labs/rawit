# Folder Khusus H3 RL — Research Lead (@alim) · Rabu 25 Nov 2026 (H3)

Folder ini berisi seluruh hasil kerja, laporan audit, keputusan Gate 1, komentar review PR, dan tabel CSV lengkap untuk tugas **Research Lead (RL)** pada **Hari ke-3 (H3)**:
1. **`RL-H3-01` · Review RQ0 (bersama MLE) & Audit Final `dataset_v1` MDE (`MDE-H2-01` & `MDE-H3-01`)**
2. **`RL-H3-02` / `ALL-H3-01` · Dokumen Keputusan Gate 1 (`docs/decisions/GATE1.md`)**

---

## 1. Struktur Folder Khusus H3 RL

### A. Laporan Utama Markdown (`.md`)
1. **[01_LAPORAN_AUDIT_MDE_H3_DAN_REVIEW_RQ0_RL_H3_01.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/01_LAPORAN_AUDIT_MDE_H3_DAN_REVIEW_RQ0_RL_H3_01.md)**
   - Audit lengkap 4 poin revisi MDE (`MDE-H2-01`) dan `dataset_v1` beku (`MDE-H3-01`, tag `dataset-v1` @ `27d0b8f`).
   - **Langkah 1 (Sebelum Run)**: Verifikasi spesifikasi fitur `(a)`, `(b)`, `(c)` sesuai Protokol Evaluasi v1 §8, verifikasi penggunaan `bps_mask.npy` pada fitur daerah asal pemasok, dan audit kausalitas `available_at <= t` (0 pelanggaran di 76.228 baris).
   - **Langkah 2 (Selama Run)**: Penyiapan struktur dan kriteria keputusan `GATE1.md`.
   - **Langkah 3 (Setelah Hasil)**: Cek sanity Varian `(a)` terhadap `Seasonal Naive` (`y_{t-260}`) dan `Naive Last` (`y_t`), perbandingan skala MAE terhadap level harga cabai rawit (`~Rp50.000/kg`), hasil uji Diebold–Mariano (Newey–West HAC) `(c vs b)` per origin dan per rezim iklim (`el_nino`, `la_nina`, `normal`), serta Permutation Feature Importance.
2. **[02_KEPUTUSAN_GATE1_RL_H3_02.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/02_KEPUTUSAN_GATE1_RL_H3_02.md)**
   - Dokumen resmi keputusan **Gate 1 (`docs/decisions/GATE1.md`)** yang merangkum bukti bagian (1) Cakupan Data Harga, (2) Sinyal Iklim di RQ0, keputusan cabang A/B/C (**Opsi A — Lanjut Penuh dengan Catatan Rezim**), dan daftar tindakan H4–H7.
3. **[03_LAPORAN_HASIL_EKSEKUSI_RQ0_LENGKAP_RL_H3_01.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/03_LAPORAN_HASIL_EKSEKUSI_RQ0_LENGKAP_RL_H3_01.md)**
   - Ringkasan eksekusi benchmark 45-run LightGBM RQ0 (`reports/rq0/rq0_summary.md`).
4. **[04_KOMENTAR_REVIEW_PR_MLE_H3_02_DAN_MDE_H3_01.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/04_KOMENTAR_REVIEW_PR_MLE_H3_02_DAN_MDE_H3_01.md)**
   - Naskah komentar review PR siap tempel (*copy-paste*) untuk **PR `job/MLE-H3-02`** (sesuai deliverable playbook `Output: komentar review di PR job/MLE-H3-02`) dan **PR `job/MDE-H3-01` (`dataset-v1`)**.

---

### B. Tabel Data & Audit Lengkap (`csv_laporan/`)
1. **[csv_laporan/01_audit_revisi_mde_dan_dataset_v1_beku_H3.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/csv_laporan/01_audit_revisi_mde_dan_dataset_v1_beku_H3.csv)**
   - Matriks audit 12 poin atas revisi MDE (`MDE-H2-01` & `MDE-H3-01`) beserta status keputusan RL (`ACC - TIDAK PERLU REVISI`).
2. **[csv_laporan/02_benchmark_sanity_acuan_rq0_RL_H3_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/csv_laporan/02_benchmark_sanity_acuan_rq0_RL_H3_01.csv)**
   - Tabel acuan sanity check `Seasonal Naive (lag 260)` dan `Naive Last (lag 0)` pada `dataset_v1_mde` untuk origin `O1, O2, O3` dan horizon $h \in \{5, 10, 20\}$.
3. **[csv_laporan/03_statistik_lengkap_36_kolom_panel_dataset_v1_mde.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/csv_laporan/03_statistik_lengkap_36_kolom_panel_dataset_v1_mde.csv)**
   - Statistik deskriptif lengkap ke-36 kolom `panel.parquet` (`76.228` baris), persentase missing, dan pemetaan ke varian fitur `(a)`, `(b)`, `(c)`.
4. **[csv_laporan/04_profil_34_provinsi_dataset_v1_sp2kp_dan_pemasok_bps.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/csv_laporan/04_profil_34_provinsi_dataset_v1_sp2kp_dan_pemasok_bps.csv)**
   - Profil lengkap 34 provinsi: jumlah observasi target, rata-rata/median harga (`Rp/kg`), rasio *carry-forward* tipe 1 & tipe 4, deviasi & korelasi SP2KP, serta pemasok utama BPS 2022.
5. **[csv_laporan/05_hasil_lengkap_rq0_a_b_c_vs_naive_RL_H3_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/csv_laporan/05_hasil_lengkap_rq0_a_b_c_vs_naive_RL_H3_01.csv)**
   - Hasil lengkap MAE, RMSE, sMAPE (`mean` dan `std` 5 seed) untuk `Seasonal Naive`, `Naive Last`, dan LightGBM Varian `(a)`, `(b)`, `(c)` di seluruh origin `O1..O3` dan horizon $h \in \{5, 10, 20\}$.
6. **[csv_laporan/06_hasil_uji_dm_dan_per_rezim_rq0_RL_H3_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/csv_laporan/06_hasil_uji_dm_dan_per_rezim_rq0_RL_H3_01.csv)**
   - Hasil uji statistik Diebold–Mariano (Newey–West HAC + koreksi HLN) antara `(c vs b)`, `(b vs a)`, `(c vs a)`, dan `(a vs snaive)` baik per origin, gabungan 3 origin, maupun per rezim iklim (`el_nino`, `la_nina`, `normal`).
7. **[csv_laporan/07_permutation_feature_importance_top15_varian_c_h10_RL_H3_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/H3_RL/csv_laporan/07_permutation_feature_importance_top15_varian_c_h10_RL_H3_01.csv)**
   - Peringkat Top-15 Permutation Feature Importance pada Varian `(c)` horizon utama $h=10$ (menunjukkan `orig_rain_pentad_anom_lag5` di peringkat #12 dan `orig_dry_spell_days_lag1` di peringkat #14).

---

### C. File Deliverable Standar Repo (`deliverables_repo/`)
Salinan file sesuai struktur path repositori `renaro-labs/rawit`:
- `deliverables_repo/docs/decisions/GATE1.md`
- `deliverables_repo/docs/rq0_review_RL_H3_01.md`
- `deliverables_repo/reports/rq0/rq0_results.csv`
- `deliverables_repo/reports/rq0/rq0_dm.csv`
- `deliverables_repo/reports/rq0/rq0_summary.md`
