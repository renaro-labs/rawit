# CGS-H5-01 robustness

Graph-prior misspecification dan joint climate-graph shift, Module 1 O3/BPS dan baseline GWN.

Split hash: `411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`. Semua evaluasi memakai part `val`/`test` resmi; holdout tidak disentuh.

## Cakupan data

- Total CSV: 6,648 baris; test-mode 5,640, train-mode 1,008.
- Mask: 47 = 45 perturbasi (3 op x 5 fraksi x 3 perturbation seed) + clean + no-prior.
- Test-mode: 5,640 baris (2,820 per part) = 47 mask x 5 checkpoint seed x 3 horizon x 4 regime x 2 part.
- Langkah 2 / train-mode: 1,008 baris (504 per part) = subset p={10,50} x {drop,add,rewire} x perturbation seed 0 x model seed 0-2, ditambah baseline clean, untuk Module 1 dan GWN.
- Registry evidence: 42 entri `robustness_*` (75 run ablation terpisah di `reports/ablation/`).

| mode | model | part | rows |
|---|---|---|---:|
| test | module1 | test | 2820 |
| test | module1 | val | 2820 |
| train | gwn | test | 252 |
| train | gwn | val | 252 |
| train | module1 | test | 252 |
| train | module1 | val | 252 |

## Hasil inferensi (5 checkpoint, tanpa retrain)

- MAE clean test h10: 7819.27 (± 207.38 antar seed).
- MAE p=50 test h10: 7852.12 (Δ +32.85 vs clean).
- Kurva penuh per regime: `fig_mae_vs_p.png`; joint shift p=50: `fig_joint_shift.png`.

## Hasil retrain (h10, evaluasi graph clean)

Δ dihitung terhadap baseline retrain clean model yang sama. Mean ± std antar 3 model seed.

| model | op | p | MAE ± std | Δ vs clean | Δ % |
|---|---|---:|---:|---:|---:|
| module1 | clean | - | 7805.10 ± 33.82 | +0.00 | +0.00% |
| module1 | add | 0.10 | 7796.06 ± 69.47 | -9.04 | -0.12% |
| module1 | add | 0.50 | 7872.17 ± 105.50 | +67.07 | +0.86% |
| module1 | drop | 0.10 | 7820.00 ± 107.88 | +14.90 | +0.19% |
| module1 | drop | 0.50 | 7828.38 ± 29.41 | +23.28 | +0.30% |
| module1 | rewire | 0.10 | 7820.19 ± 54.59 | +15.09 | +0.19% |
| module1 | rewire | 0.50 | 7888.11 ± 30.18 | +83.01 | +1.06% |
| gwn | clean | - | 8552.62 ± 252.60 | +0.00 | +0.00% |
| gwn | add | 0.10 | 8625.37 ± 305.92 | +72.75 | +0.85% |
| gwn | add | 0.50 | 8642.16 ± 258.01 | +89.53 | +1.05% |
| gwn | drop | 0.10 | 8514.59 ± 308.27 | -38.03 | -0.44% |
| gwn | drop | 0.50 | 8748.79 ± 223.62 | +196.17 | +2.29% |
| gwn | rewire | 0.10 | 8572.60 ± 253.47 | +19.98 | +0.23% |
| gwn | rewire | 0.50 | 8658.89 ± 211.03 | +106.26 | +1.24% |

Tabel mesin: `reports/robustness/robustness_retrain_h10.csv`.

## Joint shift per regime (h10, p=50, graph clean)

Δ MAE relatif terhadap baseline clean model yang sama pada regime tersebut.

| model | regime | op | MAE ± std | Δ vs clean | Δ % |
|---|---|---|---:|---:|---:|
| gwn | dry | add | 7382.12 ± 550.59 | +176.90 | +2.46% |
| gwn | dry | drop | 7368.55 ± 555.06 | +163.33 | +2.27% |
| gwn | dry | rewire | 7384.02 ± 507.47 | +178.80 | +2.48% |
| gwn | extreme_wet | add | 8804.76 ± 384.91 | +124.90 | +1.44% |
| gwn | extreme_wet | drop | 8959.01 ± 393.56 | +279.15 | +3.22% |
| gwn | extreme_wet | rewire | 8821.46 ± 387.98 | +141.60 | +1.63% |
| gwn | la_nina | add | 8686.98 ± 278.88 | +51.26 | +0.59% |
| gwn | la_nina | drop | 8764.46 ± 214.07 | +128.73 | +1.49% |
| gwn | la_nina | rewire | 8684.33 ± 207.64 | +48.60 | +0.56% |
| gwn | normal | add | 8653.40 ± 371.05 | +210.37 | +2.49% |
| gwn | normal | drop | 8883.36 ± 396.33 | +440.33 | +5.22% |
| gwn | normal | rewire | 8754.41 ± 466.53 | +311.38 | +3.69% |
| module1 | dry | add | 6344.83 ± 170.12 | +40.61 | +0.64% |
| module1 | dry | drop | 6293.76 ± 183.07 | -10.47 | -0.17% |
| module1 | dry | rewire | 6397.56 ± 83.99 | +93.33 | +1.48% |
| module1 | extreme_wet | add | 7906.18 ± 89.33 | -89.47 | -1.12% |
| module1 | extreme_wet | drop | 8113.68 ± 58.24 | +118.03 | +1.48% |
| module1 | extreme_wet | rewire | 8051.09 ± 149.85 | +55.44 | +0.69% |
| module1 | la_nina | add | 7994.27 ± 21.55 | +65.27 | +0.82% |
| module1 | la_nina | drop | 7973.35 ± 54.98 | +44.35 | +0.56% |
| module1 | la_nina | rewire | 8013.32 ± 86.39 | +84.32 | +1.06% |
| module1 | normal | add | 7691.00 ± 557.38 | +165.09 | +2.19% |
| module1 | normal | drop | 7417.74 ± 298.39 | -108.18 | -1.44% |
| module1 | normal | rewire | 7616.00 ± 343.31 | +90.08 | +1.20% |

Tabel lengkap p=10/50: `reports/robustness/robustness_retrain_by_regime.csv`.

## Limitasi

- 45 mask dibuat lokal dari `bps_mask.npy` karena paket perturbasi MDE-H4-02 belum tersedia; ini tetap dicatat sebagai limitasi sumber mask.
- DoD mengizinkan subset minimal p={10,50} bila waktu kurang; p=30 tidak dijalankan dan dicatat sebagai batas waktu.
- Retrain memakai anggaran tetap 2 epoch dan batch 32 (Module 1) / arsitektur `configs/models/gwn.yaml` dengan 2 epoch (GWN) agar 42 run selesai pada GPU 4 GB. Angka ini bukan hasil tuning jangka panjang.
- Test-mode memakai checkpoint H4 Module 1 seed 0-4; train-mode memakai seed 0-2 sesuai batas minimum audit.

## Bukti run

- `experiments/runs/robustness_module1_<prior>_s<seed>/metrics.csv` dan `run.json`.
- `experiments/runs/robustness_gwn_<prior>_s<seed>/metrics.csv` dan `run.json`.
- `experiments/registry.csv` dengan `run_id` berprefix `robustness_`.
