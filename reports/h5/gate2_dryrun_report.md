# Laporan Uji Kering `scripts/predict.py` (MLE-H5-03 · Periode Uji O3)

- **Freeze Commit**: `6f317beb98e4d0e43bb093ecb8fa01a2662d3996`
- **Dataset**: `data/processed/dataset_v1` (`split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`)
- **Periode Uji Kering**: `2025-01-01..2026-05-31` (`--fold O3`, bukan holdout asli)
- **Cakupan**: **50 / 50 run** (`10` model × `5` seed `0..4`), masing-masing `35.496` baris prediksi
- **Maksimum `|y_pred_predict - y_pred_O3|`**: `0.00e+00` (**50 / 50 IDENTIK, LULUS**)
- **Audit `PA-04`**: **200 / 200 run** `experiments/runs/g2_*/preds.parquet` memiliki `max(date) <= 2026-05-29` dan `max(target_date) <= 2026-05-29` (`0` baris `>= 2026-06-01`).

| Model | Seed | Baris Uji | Maks `|delta y_pred|` | `y_true/mask/naive` Identik | Status |
| :--- | :---: | ---: | ---: | :---: | :---: |
| `seasonal_naive` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
| `naive_last` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
| `lgbm_a` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
| `lgbm_c` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
| `gwn` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
| `mtgnn` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
| `latent_regime` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
| `lag_graph` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
| `module1` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
| `module23` | `0..4` (5/5) | 35,496 | `0.00e+00` | Ya (5/5) | **LULUS** |
