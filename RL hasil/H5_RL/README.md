# Folder Khusus H5 RL — Research Lead (`@alim`) · Jumat 27 Nov 2026 (H5)

Folder ini berisi seluruh hasil kerja **Research Lead (RL)** pada **Hari ke-5 (H5)** untuk dua tugas paralel: **`RL-H5-01 · Figur uji sintetis`** (`reports/figures/`) dan **`RL-H5-02 · Audit kepatuhan protokol`** (`docs/protocol_audit.md`).

---

## A. Deliverable `RL-H5-01` (Figur Uji Sintetis)

1. **[reports/figures/synth_lag_recovery.png](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/reports/figures/synth_lag_recovery.png)** *(+ versi vektor `synth_lag_recovery.pdf`, salinan di folder ini)*
   - Figur 3 panel (300 DPI): (a) Rezim Normal (`Acc = 0,826`, `MAE = 0,408`, `Spearman = 0,854`), (b) Rezim Kering/`dry` (`Acc = 0,616`, `MAE = 0,644`, `Spearman = 0,636 < 0,70` — dilaporkan jujur), dan (c) perbandingan pergeseran jeda `Delta lag` Modul 1 (`+0,813 ± 0,053`) vs kontrol negatif `no_climate` (`+0,011 ± 0,007`) & `unconditioned` (`-0,041 ± 0,013`).
2. **[reports/figures/synth_edge_heatmap.png](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/reports/figures/synth_edge_heatmap.png)** *(+ versi vektor `synth_edge_heatmap.pdf`, salinan di folder ini)*
   - Heatmap 2×2 panel ($34 \times 34$ kode BPS, arah $A[i, j]: j \to i$, diagonal dikosongkan, skala warna seragam *PowerNorm* $\gamma = 0{,}5$ $[0{,}00; 0{,}70]$): $A_{\text{true}}$ DGP vs $A_{\text{learned}}$ Modul 1 (5 seed) pada rezim Normal (`AUROC = 1,000*`, $r = 0{,}980$, $\rho = 0{,}945$, $r_{\text{row}} = 0{,}990$) dan Kering (`AUROC = 1,000*`, $r = 0{,}960$, $\rho = 0{,}915$, $r_{\text{row}} = 0{,}986$).
3. **[reports/figures/captions.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/reports/figures/captions.md)** *(+ `captions.tex`, salinan di folder ini: `01_captions_figur_sintetis_RL_H5_01.md`)*
   - Tabel ambang protokol v1 §5.5 + caption publikasi lengkap yang menyebutkan status **LULUS agregat**, catatan jujur sub-rezim `dry-only`, serta batas klaim dependensi prediktif (bukan identifikasi kausal maupun arus pasokan fisik).
4. **[RL-H5-01__synth_figures.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/upcoming_H2_H7_starters/RL-H5-01__synth_figures.tex)** *(salinan di folder ini)*
   - Dokumen LaTeX terisi penuh tanpa placeholder yang menautkan kedua figur `.pdf`.
5. **[scripts/plot_synth_recovery.py](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/scripts/plot_synth_recovery.py)** *(salinan di `deliverables_repo/scripts/`)*
   - Skrip `matplotlib` reproduksibel penuh (deterministik, membaca langsung `reports/synth/recovery_metrics.csv`, `lag_true_vs_hat.parquet`, dan `src/renaro/synth/generator.py`).
6. **[csv_laporan/01_rekap_recovery_sintetis_RL_H5_01.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil%20H5/csv_laporan/01_rekap_recovery_sintetis_RL_H5_01.csv)**
   - Tabel rekap evaluasi ambang protokol v1 §5.5 & korelasi matriks $A$ ($34 \times 34$) per varian/rezim.

---

## B. Deliverable `RL-H5-02` (Audit Kepatuhan Protokol — Prasyarat Gate 2)

7. **[docs/protocol_audit.md](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/docs/protocol_audit.md)** *(salinan di folder ini: `02_audit_kepatuhan_protokol_RL_H5_02.md`)*
   - Audit forensik 7 butir wajib playbook + 3 butir prasyarat Gate 2 pada commit `2b18e78`: **6 LULUS penuh** (Butir 1, 2, 3, 4, 8, 10), **1 LULUS dengan catatan** (Butir 6: `max(date) = 2026-05-29`, redaksi RONI holdout di `04_rolling_origin_splits_RL_H1_01.csv`, dan assert `preds.*` lokal), serta **3 GAGAL / Bloker Gate 2** (Butir 5: `gwn` & `mtgnn` penuh belum 5 seed; Butir 7: 3 deviasi belum dicatat di `protocol_amendments.md`; Butir 9: `frozen/manifest.yaml`, `ckpt.pt`, & `git_sha_clean()` belum selesai).
8. **[docs/protocol_audit.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/docs/protocol_audit.tex)** & **[RL-H5-02__protocol_audit.tex](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/upcoming_H2_H7_starters/RL-H5-02__protocol_audit.tex)** *(salinan di folder ini)*
   - Versi LaTeX terisi penuh tanpa placeholder.
9. **[csv_laporan/02_checklist_audit_protokol_RL_H5_02.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil%20H5/csv_laporan/02_checklist_audit_protokol_RL_H5_02.csv)**
   - Register checklist terstruktur 10 baris × 9 kolom dengan bukti eksak, status, PIC, dan tenggat penutupan.
