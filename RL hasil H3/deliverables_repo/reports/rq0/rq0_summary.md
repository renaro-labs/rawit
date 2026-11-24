# Ringkasan Evaluasi Sinyal RQ0 (`reports/rq0/rq0_summary.md`)
**Job ID:** `MLE-H3-02` & `RL-H3-01`  
**Dataset:** `data/processed/dataset_v1/` (Tag `dataset-v1` @ `27d0b8f`, `panel: fceeecbf5e9f...`, `target: 82ae4682f0a6...`)  
**Protokol:** `docs/eval_protocol_v1.md` (Tag `protocol-v1` @ `6c2e85e`, `split_hash: 683106f3b0c4308c`)

---

## 1. Hasil Utama MAE (Rp/kg, Rata-Rata 5 Seed $\pm$ SD)

| Origin | Horizon $h$ | `Seasonal Naive` | `Naive Last` | Varian `(a)` (Harga + Kalender) | Varian `(b)` (+ Iklim Lokal) | Varian `(c)` (+ Iklim Asal BPS) | $\Delta\%$ `(c vs b)` |
| :---: | :---: | ---: | ---: | :---: | :---: | :---: | ---: |
| **O1** | `5` | Rp19.879,27 | Rp4.339,45 | Rp4.291,03 $\pm$ 36,92 | Rp4.909,45 $\pm$ 79,51 | Rp4.821,29 $\pm$ 57,74 | `+1,80%` |
| **O2** | `5` | Rp16.890,20 | Rp4.752,62 | Rp4.404,70 $\pm$ 17,65 | Rp4.781,75 $\pm$ 45,34 | Rp4.732,45 $\pm$ 27,20 | `+1,03%` |
| **O3** | `5` | Rp16.004,57 | Rp5.071,83 | Rp4.950,23 $\pm$ 14,19 | Rp5.108,41 $\pm$ 29,63 | Rp5.109,35 $\pm$ 40,21 | `-0,02%` |
| **Mean 3 Origin** | **`5`** | **Rp17.591,35** | **Rp4.721,30** | **Rp4.548,65** | **Rp4.933,20** | **Rp4.887,70** | **`+0,92%` (2/3 origin)** |
| **O1** | `10` | Rp19.972,13 | Rp6.546,44 | Rp6.434,04 $\pm$ 53,64 | Rp7.674,13 $\pm$ 89,96 | Rp7.528,19 $\pm$ 103,73 | `+1,90%` |
| **O2** | `10` | Rp16.884,91 | Rp6.992,76 | Rp6.238,96 $\pm$ 49,33 | Rp6.843,21 $\pm$ 59,25 | Rp6.849,71 $\pm$ 36,96 | `-0,09%` |
| **O3** | `10` | Rp16.088,29 | Rp7.532,01 | Rp7.303,48 $\pm$ 19,88 | Rp7.558,05 $\pm$ 30,27 | Rp7.582,03 $\pm$ 56,57 | `-0,32%` |
| **Mean 3 Origin** | **`10`** | **Rp17.648,44** | **Rp7.023,74** | **Rp6.658,83** | **Rp7.358,46** | **Rp7.319,98** | **`+0,52%`** |
| **O1** | `20` | Rp20.285,57 | Rp8.556,51 | Rp9.224,35 $\pm$ 125,84 | Rp10.856,17 $\pm$ 168,39 | Rp10.653,62 $\pm$ 268,94 | `+1,87%` |
| **O2** | `20` | Rp16.999,15 | Rp9.587,12 | Rp8.026,17 $\pm$ 45,48 | Rp9.100,79 $\pm$ 69,36 | Rp9.055,16 $\pm$ 138,76 | `+0,50%` |
| **O3** | `20` | Rp16.277,58 | Rp9.974,07 | Rp9.906,13 $\pm$ 49,21 | Rp10.658,93 $\pm$ 200,83 | Rp10.473,40 $\pm$ 146,19 | `+1,74%` |
| **Mean 3 Origin** | **`20`** | **Rp17.854,10** | **Rp9.372,57** | **Rp9.052,22** | **Rp10.205,30** | **Rp10.060,73** | **`+1,42%` (3/3 origin)** |

---

## 2. Evaluasi per Rezim Iklim & Uji Diebold–Mariano ($h = 10$, Gabungan 3 Origin)

- **`el_nino` ($n = 4.467$)**: MAE `(b)` = `Rp11.738,64` $\to$ MAE `(c)` = **`Rp11.556,94`** ($\Delta = +1{,}55\%$, `Rp181,70/kg` lebih rendah; $t_{\text{DM}} = +1{,}7081$, $p_{\text{1-sided}} = 0{,}0448 < 0{,}05$).
- **`normal` ($n = 6.469$)**: MAE `(b)` = `Rp6.113,96` $\to$ MAE `(c)` = **`Rp6.059,94`** ($\Delta = +0{,}88\%$; $t_{\text{DM}} = +1{,}8951$, $p_{\text{1-sided}} = 0{,}0296 < 0{,}05$).
- **`extreme_wet` ($n = 1.777$)**: MAE `(b)` = `Rp8.187,82` $\to$ MAE `(c)` = `Rp8.185,79` ($\Delta = +0{,}03\%$).
- **`dry` ($n = 2.450$)**: MAE `(b)` = `Rp6.133,00` $\to$ MAE `(c)` = `Rp6.133,76` ($\Delta = -0{,}01\%$).
- **`la_nina` ($n = 13.632$)**: MAE `(b)` = `Rp6.618,37` $\to$ MAE `(c)` = `Rp6.641,08` ($\Delta = -0{,}34\%$).
- **Top-15 Feature Importance Varian `(c)` ($h = 10$)**: `orig_rain_pentad_anom_lag5` menempati peringkat **#12** dan `orig_dry_spell_days_lag1` menempati peringkat **#14**.
