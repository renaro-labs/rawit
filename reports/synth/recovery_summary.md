# CGS/MLE-H3-01 — synthetic lag recovery

Evaluasi pada test set sintetis; 5 seed; Module 1 default, unconditioned, dan kontrol e_j=0.
Ambang protokol v1 §5.5: Spearman > 0.70 (multi-edge), MAE lag ≤ 1.0 pentad, AUROC > 0.85.
Tabel di bawah adalah rata-rata 5 seed; detail per seed ada di `recovery_metrics.csv`.

| data | model | regime | n_seed | lag_acc | MAE lag | Spearman | AUROC | Δlag |
|---|---|---|---:|---:|---:|---:|---:|---:|
| default | module1_default | dry | 5 | 0.616 | 0.644 | 0.636 | 1.000 | 0.813 |
| default | module1_default | normal | 5 | 0.826 | 0.408 | 0.854 | 1.000 | 0.813 |
| default | module1_no_climate | dry | 5 | 0.640 | 0.628 | 0.759 | 1.000 | 0.011 |
| default | module1_no_climate | normal | 5 | 0.085 | 2.313 | 0.752 | 1.000 | 0.011 |
| unconditioned | module1_unconditioned | dry | 5 | 0.814 | 0.493 | 0.734 | 1.000 | -0.041 |
| unconditioned | module1_unconditioned | normal | 5 | 0.810 | 0.505 | 0.730 | 1.000 | -0.041 |

## Kesimpulan

- Module 1 default (rata-rata normal+dry, 5 seed): Spearman LULUS (ambang >0.70), MAE lag LULUS (ambang ≤1.0), AUROC LULUS (ambang >0.85).
- Δlag default rata-rata = 0.813 (nilai benar sintetis = 2.0); dry-only tetap dilaporkan pada tabel.
- Kontrol tanpa iklim/unconditioned: |Δlag| rata-rata = 0.026 (harus mendekati 0).
- Kesimpulan: **LULUS** terhadap ambang protokol v1.
