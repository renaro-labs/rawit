# Tabel utama holdout — h = 10

MAE/RMSE dalam Rp/kg. `val 3-origin` = rata-rata validasi O1–O3 pada konfigurasi beku; `val refit` = validasi refit HOLDOUT (Jan–Mei 2026), bukan holdout test. `Δ dry−normal` dan `Δ extreme−normal` dihitung di dalam holdout; tidak ada label `el_nino` karena RONI resmi masih netral. `worst-regime` = max MAE antar regime holdout yang tersedia.

| Model | Peran | Val 3-origin | Val refit | Holdout MAE (mean ± sd) | RMSE | sMAPE | Coverage | Worst-regime | Worst n≥200 | Δ dry−normal | Δ extreme−normal | Δ vs val | DM median p | Sig. p<0.05 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `module1` | module | 6,249.0 | 6,431.1 | 7,452.6 ± 211.4 | 10,518.2 | 12.66 | 100.00% | 8,065.5 | 8,065.5 | 1,495.8 | 221.0 | 1,203.6 | 0.0744 | 0/5 |
| `module23` | module | 6,221.5 | 6,370.1 | 8,064.7 ± 467.2 | 11,703.2 | 13.43 | 100.00% | 9,505.9 | 8,843.0 | 1,924.5 | 2,587.4 | 1,843.2 | 0.1595 | 0/5 |
| `naive_last` | baseline | 6,169.3 | 7,050.6 | 8,198.4 ± 0.0 | 11,146.9 | 14.27 | 100.00% | 8,630.8 | 8,358.4 | 397.2 | 669.5 | 2,029.0 | 0.2215 | 0/5 |
| `lag_graph` | baseline | 5,995.0 | 6,240.3 | 8,592.5 ± 332.2 | 11,816.7 | 14.71 | 100.00% | 9,206.5 | 9,206.5 | 1,506.1 | 941.7 | 2,597.5 | 0.3737 | 0/5 |
| `lgbm_a` | baseline | 5,543.2 | 5,861.6 | 8,767.9 ± 39.0 | 12,487.9 | 14.76 | 100.00% | 10,387.3 | 9,871.5 | 2,724.1 | 3,239.9 | 3,224.8 | 0.4426 | 0/5 |
| `lgbm_c` | baseline | 5,481.2 | 6,042.1 | 8,800.5 ± 71.9 | 12,614.2 | 14.91 | 100.00% | 9,973.4 | 9,973.4 | 2,885.2 | 2,540.5 | 3,319.3 | – | –/5 |
| `gwn` | baseline | 6,532.2 | 5,965.7 | 8,870.0 ± 978.6 | 12,620.6 | 14.77 | 100.00% | 10,114.1 | 9,879.8 | 2,489.9 | 2,724.2 | 2,337.8 | 0.2272 | 0/5 |
| `latent_regime` | baseline | 5,947.8 | 6,353.2 | 9,142.8 ± 406.5 | 12,541.8 | 15.61 | 100.00% | 9,962.0 | 9,962.0 | 2,015.3 | 1,787.6 | 3,195.1 | 0.7523 | 0/5 |
| `mtgnn` | baseline | 6,433.2 | 5,878.8 | 9,512.2 ± 1,417.7 | 13,474.8 | 15.87 | 100.00% | 10,673.0 | 10,673.0 | 2,857.0 | 2,638.2 | 3,079.0 | 0.7092 | 0/5 |
| `seasonal_naive` | baseline | 22,033.2 | 15,289.3 | 13,957.2 ± 0.0 | 21,152.5 | 23.70 | 99.21% | 16,516.4 | 16,516.4 | 6,324.0 | 4,873.0 | -8,076.1 | 1.0000 | 0/5 |

Catatan: DM memakai `d = loss_model − loss_lgbm_c`; p satu sisi (`alternative='less'`), semakin kecil semakin kuat bukti model lebih baik dari baseline. Nilai p adalah median 5 seed. `seasonal_naive` memiliki 75 baris NaN/file; baris tersebut tidak masuk metrik (coverage < 100%).
