# CGS-H5-01 robustness

Model: Module 1 O3 bps, 5 seeds; 47 masks including clean/no-prior.

## Hasil inferensi

- MAE clean test: 7607.62; MAE p=50 rata-rata: 7618.96 (delta +11.34).
- Kurva per regime: `fig_mae_vs_p.png`; joint shift: `fig_joint_shift.png`.

Catatan: `data/processed/perturbations/` dibuat dari `bps_mask.npy` karena paket perturbasi MDE belum tersedia; 45 mask = 3 op x 5 fraksi x 3 perturbation seed. Baseline GWN belum dijalankan pada subset ini.
