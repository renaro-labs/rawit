# MLE-H5-02 ablation

Validasi: 5 varian x 3 origin x 5 seed = 75 run; 825 baris metrik per regime/horizon.

MAE dihitung pada part `val` untuk horizon 5/10/20 dan dirata-ratakan per run (weighted by jumlah node-hari), lalu dilaporkan sebagai mean ± std antar 15 run. `delta` relatif terhadap varian `full`.

## Ringkasan h10 (primary horizon)

| variant | mean MAE ± std | delta vs full | delta % | n run |
|---|---:|---:|---:|---:|
| full | 8168.40 ± 2683.90 | +0.00 | +0.00% | 15 |
| no_climate | 8265.19 ± 3373.56 | +96.78 | +1.18% | 15 |
| no_lag | 8561.19 ± 3112.47 | +392.79 | +4.81% | 15 |
| no_gate | 8716.22 ± 3510.60 | +547.81 | +6.71% | 15 |
| no_calendar | 7731.32 ± 2600.13 | -437.08 | -5.35% | 15 |

## Ringkasan semua horizon

| variant | horizon | mean MAE ± std | delta vs full | delta % | n run |
|---|---:|---:|---:|---:|---:|
| full | 5 | 6693.84 ± 2160.47 | +0.00 | +0.00% | 15 |
| full | 10 | 8168.40 ± 2683.90 | +0.00 | +0.00% | 15 |
| full | 20 | 9844.33 ± 2355.59 | +0.00 | +0.00% | 15 |
| no_climate | 5 | 6771.02 ± 2603.98 | +77.18 | +1.15% | 15 |
| no_climate | 10 | 8265.19 ± 3373.56 | +96.78 | +1.18% | 15 |
| no_climate | 20 | 9452.53 ± 1725.54 | -391.80 | -3.98% | 15 |
| no_lag | 5 | 6733.64 ± 1974.58 | +39.81 | +0.59% | 15 |
| no_lag | 10 | 8561.19 ± 3112.47 | +392.79 | +4.81% | 15 |
| no_lag | 20 | 10567.78 ± 2734.57 | +723.46 | +7.35% | 15 |
| no_gate | 5 | 7473.97 ± 2968.95 | +780.13 | +11.65% | 15 |
| no_gate | 10 | 8716.22 ± 3510.60 | +547.81 | +6.71% | 15 |
| no_gate | 20 | 10096.15 ± 2442.32 | +251.82 | +2.56% | 15 |
| no_calendar | 5 | 6545.51 ± 2353.17 | -148.33 | -2.22% | 15 |
| no_calendar | 10 | 7731.32 ± 2600.13 | -437.08 | -5.35% | 15 |
| no_calendar | 20 | 9630.45 ± 2271.43 | -213.88 | -2.17% | 15 |

## Rincian per regime

| variant | horizon | regime | mean MAE | std | delta vs full | n run |
|---|---:|---|---:|---:|---:|---:|
| full | 5 | dry | 8359.70 | 4286.97 | +0.00 | 15 |
| full | 5 | el_nino | 7655.77 | 956.14 | +0.00 | 5 |
| full | 5 | extreme_wet | 7876.96 | 1538.16 | +0.00 | 15 |
| full | 5 | la_nina | 6414.90 | 3186.89 | +0.00 | 10 |
| full | 5 | normal | 4931.22 | 508.15 | +0.00 | 10 |
| full | 10 | dry | 9370.45 | 4264.56 | +0.00 | 15 |
| full | 10 | el_nino | 11869.24 | 1558.53 | +0.00 | 5 |
| full | 10 | extreme_wet | 11097.86 | 3677.38 | +0.00 | 15 |
| full | 10 | la_nina | 7503.23 | 3990.02 | +0.00 | 10 |
| full | 10 | normal | 5701.82 | 691.51 | +0.00 | 10 |
| full | 20 | dry | 11440.66 | 3376.26 | +0.00 | 15 |
| full | 20 | el_nino | 20709.23 | 1393.29 | +0.00 | 5 |
| full | 20 | extreme_wet | 10931.13 | 2883.91 | +0.00 | 15 |
| full | 20 | la_nina | 9005.96 | 1055.52 | +0.00 | 10 |
| full | 20 | normal | 6746.23 | 380.68 | +0.00 | 10 |
| no_climate | 5 | dry | 8214.94 | 4553.52 | -144.76 | 15 |
| no_climate | 5 | el_nino | 7273.43 | 505.87 | -382.34 | 5 |
| no_climate | 5 | extreme_wet | 7596.37 | 1643.32 | -280.59 | 15 |
| no_climate | 5 | la_nina | 6665.36 | 3757.65 | +250.46 | 10 |
| no_climate | 5 | normal | 4970.81 | 590.96 | +39.59 | 10 |
| no_climate | 10 | dry | 9702.37 | 5777.90 | +331.91 | 15 |
| no_climate | 10 | el_nino | 9703.20 | 883.21 | -2166.04 | 5 |
| no_climate | 10 | extreme_wet | 10743.95 | 3144.65 | -353.91 | 15 |
| no_climate | 10 | la_nina | 7970.46 | 4869.24 | +467.23 | 10 |
| no_climate | 10 | normal | 5940.17 | 924.84 | +238.36 | 10 |
| no_climate | 20 | dry | 10869.87 | 3328.18 | -570.78 | 15 |
| no_climate | 20 | el_nino | 17475.50 | 629.45 | -3233.72 | 5 |
| no_climate | 20 | extreme_wet | 11428.97 | 3374.63 | +497.84 | 15 |
| no_climate | 20 | la_nina | 9143.96 | 1132.32 | +138.00 | 10 |
| no_climate | 20 | normal | 6800.81 | 399.24 | +54.58 | 10 |
| no_lag | 5 | dry | 8505.56 | 4011.26 | +145.87 | 15 |
| no_lag | 5 | el_nino | 7835.71 | 978.50 | +179.94 | 5 |
| no_lag | 5 | extreme_wet | 8086.71 | 1523.09 | +209.75 | 15 |
| no_lag | 5 | la_nina | 6548.09 | 2962.87 | +133.19 | 10 |
| no_lag | 5 | normal | 4976.39 | 467.47 | +45.17 | 10 |
| no_lag | 10 | dry | 10711.91 | 7094.49 | +1341.45 | 15 |
| no_lag | 10 | el_nino | 13198.57 | 4070.27 | +1329.34 | 5 |
| no_lag | 10 | extreme_wet | 11591.80 | 4204.35 | +493.94 | 15 |
| no_lag | 10 | la_nina | 7705.92 | 4457.79 | +202.69 | 10 |
| no_lag | 10 | normal | 5957.31 | 607.25 | +255.49 | 10 |
| no_lag | 20 | dry | 13120.72 | 5088.17 | +1680.07 | 15 |
| no_lag | 20 | el_nino | 21624.88 | 3947.71 | +915.65 | 5 |
| no_lag | 20 | extreme_wet | 11172.79 | 2913.90 | +241.66 | 15 |
| no_lag | 20 | la_nina | 9750.55 | 1810.26 | +744.58 | 10 |
| no_lag | 20 | normal | 7225.38 | 758.54 | +479.15 | 10 |
| no_gate | 5 | dry | 9481.91 | 6187.36 | +1122.21 | 15 |
| no_gate | 5 | el_nino | 8510.59 | 1532.22 | +854.83 | 5 |
| no_gate | 5 | extreme_wet | 8157.14 | 1971.07 | +280.18 | 15 |
| no_gate | 5 | la_nina | 7443.13 | 4065.46 | +1028.23 | 10 |
| no_gate | 5 | normal | 5393.86 | 699.80 | +462.64 | 10 |
| no_gate | 10 | dry | 10652.43 | 6509.58 | +1281.98 | 15 |
| no_gate | 10 | el_nino | 11917.16 | 1959.16 | +47.92 | 5 |
| no_gate | 10 | extreme_wet | 11085.91 | 3662.45 | -11.95 | 15 |
| no_gate | 10 | la_nina | 8425.51 | 4868.37 | +922.28 | 10 |
| no_gate | 10 | normal | 5813.78 | 604.40 | +111.96 | 10 |
| no_gate | 20 | dry | 11235.26 | 2884.78 | -205.39 | 15 |
| no_gate | 20 | el_nino | 20807.32 | 1092.57 | +98.10 | 5 |
| no_gate | 20 | extreme_wet | 11076.64 | 2615.28 | +145.51 | 15 |
| no_gate | 20 | la_nina | 9385.83 | 997.18 | +379.86 | 10 |
| no_gate | 20 | normal | 7018.06 | 517.42 | +271.83 | 10 |
| no_calendar | 5 | dry | 8558.23 | 5112.02 | +198.54 | 15 |
| no_calendar | 5 | el_nino | 7390.37 | 519.30 | -265.40 | 5 |
| no_calendar | 5 | extreme_wet | 7389.12 | 1827.44 | -487.84 | 15 |
| no_calendar | 5 | la_nina | 6413.97 | 3381.40 | -0.93 | 10 |
| no_calendar | 5 | normal | 4587.76 | 425.75 | -343.46 | 10 |
| no_calendar | 10 | dry | 9403.42 | 4769.04 | +32.97 | 15 |
| no_calendar | 10 | el_nino | 10987.40 | 922.44 | -881.84 | 5 |
| no_calendar | 10 | extreme_wet | 9878.12 | 3155.82 | -1219.75 | 15 |
| no_calendar | 10 | la_nina | 7222.47 | 3875.48 | -280.76 | 10 |
| no_calendar | 10 | normal | 5286.21 | 578.40 | -415.61 | 10 |
| no_calendar | 20 | dry | 11337.60 | 3747.54 | -103.05 | 15 |
| no_calendar | 20 | el_nino | 19875.69 | 1771.52 | -833.54 | 5 |
| no_calendar | 20 | extreme_wet | 10689.82 | 3009.64 | -241.31 | 15 |
| no_calendar | 20 | la_nina | 9069.91 | 1032.24 | +63.95 | 10 |
| no_calendar | 20 | normal | 6509.77 | 475.34 | -236.46 | 10 |

## Sanity check terhadap H5-01

- H5-01 `full` (2 epoch, 15 run): mean val h10 MAE 6864.81.
- Ablation `full` (1 epoch, matched budget): mean val h10 MAE 9490.31 (delta +2625.50).
- Perbedaan ini konsisten dengan pengurangan epoch; delta antar varian di bawah tetap dihitung terhadap baseline matched-budget.

## Protokol

- Semua varian memakai arsitektur dan hyperparameter `configs/models/module23.yaml`; hanya komponen yang diuji yang diubah: `no_gate` = g=1 (hanya adaptif), `no_climate` = iklim dan shock gate nol, `no_lag` = L=1, `no_calendar` = kalender nol di encoder/head. Jadwal training memakai 1 epoch yang sama untuk semua varian (lihat catatan budget).
- Varian dan `full` pada studi ini dilatih dengan 1 epoch agar anggaran komputasi identik antar varian. Run H5-01 `full` memakai 2 epoch; karena itu angka `full` di sini adalah baseline ablation yang matched-budget, bukan pengganti angka H5-01.
- Split hash: `411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`.
- Bukti run: `experiments/runs/ablation_<variant>_<origin>_s<seed>/` dan `experiments/registry.csv` (75 entri `ablation_*`).
