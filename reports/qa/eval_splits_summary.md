# CGS-H4-01 — eval splits per regime

Sumber: `data/processed/dataset_v1/panel.parquet` + `data/interim/regime_labels.csv`.
Rentang val/test mengikuti `configs/global.yaml`; tidak ada tanggal holdout.

| origin | part | regime | node-hari | target observed | CI lebar |
|---|---|---|---:|---:|---|
| O1 | test | dry | 1,414 | 1,392 | tidak |
| O1 | test | el_nino | 1,605 | 1,577 | tidak |
| O1 | test | extreme_wet | 275 | 269 | tidak |
| O1 | test | la_nina | 4,071 | 3,971 | tidak |
| O1 | test | normal | 1,407 | 1,379 | tidak |
| O1 | val | dry | 43 | 43 | ya |
| O1 | val | extreme_wet | 423 | 421 | tidak |
| O1 | val | la_nina | 3,954 | 3,913 | tidak |
| O2 | test | dry | 768 | 759 | tidak |
| O2 | test | el_nino | 3,239 | 3,177 | tidak |
| O2 | test | extreme_wet | 553 | 544 | tidak |
| O2 | test | la_nina | 1,338 | 1,296 | tidak |
| O2 | test | normal | 3,010 | 2,967 | tidak |
| O2 | val | dry | 1,276 | 1,258 | tidak |
| O2 | val | el_nino | 1,605 | 1,577 | tidak |
| O2 | val | extreme_wet | 64 | 62 | ya |
| O2 | val | normal | 1,407 | 1,379 | tidak |
| O3 | test | dry | 465 | 458 | tidak |
| O3 | test | extreme_wet | 1,115 | 1,105 | tidak |
| O3 | test | la_nina | 8,938 | 8,852 | tidak |
| O3 | test | normal | 1,994 | 1,975 | tidak |
| O3 | val | dry | 580 | 573 | tidak |
| O3 | val | extreme_wet | 200 | 197 | ya |
| O3 | val | la_nina | 1,338 | 1,296 | tidak |
| O3 | val | normal | 2,370 | 2,342 | tidak |

## DoD

- O1: 5 regime dengan ≥200 target observed (memenuhi)
- O2: 5 regime dengan ≥200 target observed (memenuhi)
- O3: 4 regime dengan ≥200 target observed (memenuhi)

`ci_wide` memakai target observed < 200 sebagai penanda CI lebar.
Subset identik untuk semua model: gunakan `renaro.eval.regimes.filter(preds, origin, part, regime)`.
