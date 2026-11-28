# Laporan MLE-H5-04: Modul 4 (Tujuan Pelatihan Tahan-Perturbasi & Lintas-Regime)

- **Status Gate 2**: Modul 4 (`MLE-H5-04`) adalah *stretch goal* yang **TIDAK mengubah** paket beku `gate2-freeze` (`b0d0ff9`) maupun `frozen/manifest.yaml` (tetap tercatat di `excluded` untuk holdout Sprint 1). Seluruh evaluasi dilakukan **strictly pada `dataset_v1` (`O1–O3`, `< 2026-06-01`)**.
- **Tiga komponen tujuan pelatihan Modul 4 (`src/renaro/models/module4.py`)**:
  1. **Penalti sensitivitas perturbasi graf**: `lambda_perturb * ||f(X, A) - f(X, A_tilde)||_1` (`lambda_perturb = 0.15`), dengan `A_tilde` dibentuk dari perturbasi acak `candidate_mask` per batch (`p in [0.10, 0.50]`, campuran edge-dropout & perturbasi `drop/add/rewire` pada prior BPS).
  2. **Risiko lintas-regime (V-REx kausal)**: `lambda_group_var * Var_g(R_g)` (`lambda_group_var = 5.0`), dengan `3` kelompok kuantil dibentuk **murni dari fitur iklim as-of `<= t`** (agregat asal `rain_30d_anom` 5 hari kerja terakhir; **0 akses `regime_labels.csv`** saat pelatihan).
  3. **Regularisasi prior lunak**: `lambda_prior * ||A * (1 - M_bps)||_1` (`lambda_prior = 0.05`) di atas `candidate_mask` off-diagonal penuh (`prior: soft_bps`), sehingga model dapat memanfaatkan edge non-BPS saat prior meleset namun tetap tertarik lunak ke `M_bps`.
- **VRAM Puncak GPU**: `0.637 GB` (< batas protokol `3,00 GB`).
- **Fraksi Massa Perhatian Non-BPS (`off_bps_mass`) akhir rata-rata**: `0.000`.

## 1. Perbandingan Head-to-Head O1-O3 (Seragam 10 Epoch, 5 Seed `0..4`, `h=10 MAE` Rp/kg)

| Model | `Val O1` | `Val O2` | `Val O3` | `Val 3-Origin Avg` | `Val Max CV` | `Test O1` | `Test O2` | `Test O3` | `Test 3-Origin Avg` | `Test Max CV` |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `module1` (Gate 2, 10 ep) | 7,085.61 | 7,774.84 | 3,886.58 | 6,249.01 | 9.79% | 6,892.19 | 7,333.91 | 7,964.57 | 7,396.89 | 5.16% |
| `module23` (Gate 2, 10 ep) | 7,013.81 | 7,767.62 | 3,883.02 | 6,221.48 | 5.25% | 6,840.44 | 7,175.17 | 7,839.82 | 7,285.14 | 4.18% |
| **`module4` (`MLE-H5-04`, 10 ep)** | **6,996.45** | **7,737.12** | **3,931.72** | **6,221.76** | **6.52%** | **6,996.38** | **7,568.41** | **7,878.18** | **7,480.99** | **9.09%** |

## 2. Evaluasi Lintas-Regime Uji `O1-O3` (`h=10 MAE` Rp/kg; sumber: proxy evaluasi iklim `dataset_v1/panel.parquet` (`dry_spell_days>=15`, `extreme_5d>=1`, `|roni|>=0.5`) karena `eval_splits/` ter-gitignore; 0 akses saat pelatihan)

| Model | `dry` | `el_nino` | `extreme_wet` | `la_nina` | `normal` | **Worst-Regime MAE** | **Std Lintas-Regime** |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `module1_g2` | 5,519.48 | 11,002.66 | 8,312.28 | 5,815.42 | 6,440.94 | **11,002.66** | 2,279.08 |
| `module23_g2` | 5,289.20 | 11,079.55 | 7,997.10 | 5,749.74 | 6,173.78 | **11,079.55** | 2,370.50 |
| `module4` | 5,464.22 | 12,148.24 | 8,053.89 | 5,684.54 | 6,269.66 | **12,148.24** | 2,777.77 |

## 3. Uji Ketahanan Perturbasi Graf pada Uji `O3` (`h=10 MAE` Rp/kg, 5 Seed x 3 Perturbation Seed)

| Model | `clean` (`M_bps`) | `none` (0 edge) | `drop` `p=50%` (delta vs clean) | `add` `p=50%` (delta vs clean) | `rewire` `p=50%` (delta vs clean) | Rata-rata `|delta|` `p=10..50%` |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `module23_g2` | 7,839.82 | 7,791.60 (-48.23) | 7,864.47 (+24.65) | 7,888.98 (+49.16) | 8,006.94 (+167.11) | **101.08** |
| `module4` | 7,878.18 | 7,774.59 (-103.60) | 7,872.76 (-5.42) | 7,876.73 (-1.46) | 7,932.40 (+54.22) | **90.10** |

- Referensi `module4` dengan mask pelatihan `soft_full` (`~eye(34)`): `O3 Test h=10 MAE = 7,878.18 Rp/kg`.
- Figur kurva ketahanan perturbasi: `reports/module4/fig_module4_robustness.png`.
