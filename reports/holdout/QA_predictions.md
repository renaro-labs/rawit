# QA prediksi holdout — CGS-H6-01

- **Tanggal**: 2026-11-28 (WIB)
- **Pelaksana**: CGS (`@fariq`)
- **Repo/commit**: `b0d0ff98e36fdb10d9a9ef05bcf4ab3225cdf439` (tag `gate2-freeze`)
- **Manifest**: `frozen/manifest.yaml`, SHA-256 `3693ab39a37043e5e9304d2e967c630acaa604e3c3c757db4f24d8094187be0d`
- **Arsip checkpoint**: `dist/frozen_holdout_checkpoints_50runs.zip` (19.612.823 byte; SHA-256 `7b4179571ee0d238fb70274336ce2c80967a88aa448257ce57716df0e9b69312`)
- **Holdout**: `D:\renaro_sealed\holdout_v1\panel_v1` (panel gabungan 79.832 baris; 2026-06-02 .. 2026-10-30)
- **Waktu buka**: `2026-11-28T21:13:19+07:00` (file `HOLDOUT_UNSEALED` dibuat sekali)
- **Run**: `2026-11-28T21:13:58+07:00` .. `2026-11-28T21:19:33+07:00`
- **Output**: `reports/holdout/predictions/` (50 parquet + `predict_log.json`)

## 1. Verifikasi pra-inferensi

| Pemeriksaan | Hasil |
|---|---|
| SHA-256 50 checkpoint vs manifest | **50/50 cocok** |
| `frozen/manifest.yaml` di arsip vs repo | identik (SHA sama) |
| Dataset `dataset_v1` `SHA256SUMS` | 6/6 |
| Panel holdout `SHA256SUMS` | 6/6 |
| File sealed `SHA256SUMS.txt` | 196/196 |
| `HOLDOUT_UNSEALED` sebelum run | belum ada |
| Output prediksi sebelum run | belum ada |
| Model di luar manifest | tidak ada |

## 2. Kelengkapan output

- **50 file** `preds_<model>_s<seed>.parquet` = 10 model × 5 seed (`0..4`).
- Setiap file: **8.772 baris**; total **438.600 baris**.
- `date` minimum **2026-06-02**, maksimum **2026-10-02** (decision date).
- `target_date` maksimum **2026-10-29**; tidak ada target di luar 2026-10-31.
- `part = holdout`, `fold = HOLDOUT`.
- `predict_log.json`: `reads_holdout = true`, `git_head = b0d0ff9...`, 50 entri output.

| Model | Seed | File | Baris | `y_pred` NaN |
|---|---:|---:|---:|---:|
| `seasonal_naive` | 0–4 | 5 | 8.772/file | **75/file** |
| `naive_last` | 0–4 | 5 | 8.772/file | 0 |
| `lgbm_a` | 0–4 | 5 | 8.772/file | 0 |
| `lgbm_c` | 0–4 | 5 | 8.772/file | 0 |
| `gwn` | 0–4 | 5 | 8.772/file | 0 |
| `mtgnn` | 0–4 | 5 | 8.772/file | 0 |
| `latent_regime` | 0–4 | 5 | 8.772/file | 0 |
| `lag_graph` | 0–4 | 5 | 8.772/file | 0 |
| `module1` | 0–4 | 5 | 8.772/file | 0 |
| `module23` | 0–4 | 5 | 8.772/file | 0 |

## 3. Catatan kualitas: `seasonal_naive`

`seasonal_naive` menghasilkan **75/8.772 (0,86%) `y_pred` NaN per seed** (total 375 baris
lintas 5 seed, file berbeda; bukan baris yang sama harus dijumlahkan). Penyebab: harga
pada lag 364 hari tidak tersedia untuk sebagian provinsi/tanggal. `y_true` dan
`y_mask` tetap terisi pada baris tersebut.

Tindakan: MLE-H6-01 harus **mengecualikan baris `y_pred` NaN** dari MAE/RMSE/sMAPE
(atau melaporkan coverage `seasonal_naive` terpisah). Jangan mengimputasi NaN.
Model lain tidak memiliki NaN.

## 4. Label regime holdout

- `reports/holdout/regime_labels_holdout.csv`: **5.202 baris harian** (34 provinsi × 153 hari; 2026-06-01 .. 2026-10-31), skema sama dengan `data/interim/regime_labels.csv`.
- `reports/holdout/regime_labels_holdout_panel.csv`: **3.604 baris** untuk tanggal panel kerja; 0 label hilang saat di-join ke panel.
- Distribusi: `dry` **2.995** (57,6%), `normal` **2.176** (41,8%), `extreme_wet` **31** (0,6%), `el_nino` **0**, `la_nina` **0**.
- Validasi metode: dijalankan ulang pada periode shared 2017–Mei 2026 → **116.892 baris, 0 mismatch** untuk `enso_phase`, `episode_id`, `is_dry`, `is_extreme_rain`, `is_normal`, `label_primary`, dan `pentad_end` vs `data/interim/regime_labels.csv`.

### Cara label dihitung

1. Rebuild `rain_prov_daily` dari CHIRPS mentah `raw_merged/chirps_v3` + `w_kab_pixel.npz` (bobot 2024 untuk 2026), lalu `to_pentad` + `add_rolling_30d` + `add_features` dengan `data/interim/climatology.parquet` (baseline 2017).
2. Verifikasi overlap: 23.052 baris shared 2017–Mei 2026, **max |selisih| = 0** untuk semua kolom numerik; `extreme_5d`, `pentad_of_year`, `n_days`, `available_at` identik.
3. Gabungkan RONI shared (915 musim) + holdout (6 musim), lalu `enso_by_date` (as-of `available_at`), `mark_dry` (p20_global; ≥3 pentad), `primary_label` (prioritas `dry > extreme_wet > el_nino > la_nina > normal`), dan `expand_daily`.
4. Filter tanggal 2026-06-01..2026-10-31; join ke panel kerja untuk versi `_panel.csv`.
5. Uji regresi: ulangi langkah 3–4 pada 2017–Mei 2026 → 116.892 baris, **0 mismatch** vs `data/interim/regime_labels.csv`.

**Catatan ENSO:** seluruh label holdout memakai `enso_phase = neutral` karena
tabel RONI resmi (`phase`) belum menyatakan episode El Niño sampai ASO 2026
(aturan 5 musim berturut-turut). `raw_phase` sudah `elnino` untuk MJJ–ASO 2026,
tetapi `phase` resmi tetap `neutral`; jadi holdout **tidak** boleh disebut
"El Niño holdout" tanpa kualifikasi.

## 5. Reproduksi

```powershell
# pra-run (setelah arsip diekstrak ke experiments/runs)
python scripts\cgs\verify_holdout_integrity.py --require-checkpoints

# run satu kali (sudah dilakukan; JANGAN dijalankan ulang)
python scripts\predict.py --manifest frozen/manifest.yaml `
  --context data\processed\dataset_v1 `
  --holdout "$env:RENARO_SEALED_DIR\holdout_v1\panel_v1" `
  --out reports\holdout\predictions

# cek output
python - <<'PY'
import json, pandas as pd
from pathlib import Path
root=Path("reports/holdout/predictions")
log=json.loads((root/"predict_log.json").read_text())
print(len(log["outputs"]), log["reads_holdout"], log["git_head"])
print(len(list(root.glob("preds_*.parquet"))), sum(len(pd.read_parquet(p)) for p in root.glob("preds_*.parquet")))
PY
```

## 6. Batasan

1. Hasil ini adalah **hasil pertama** setelah holdout dibuka; tidak ada run ulang.
   Jika ditemukan bug setelah titik ini, hasil awal tetap dilaporkan dan run ulang
   wajib diberi label **post-hoc**.
2. `seasonal_naive` memiliki 75 NaN/file (lihat §3); metrik harus menghitung coverage.
3. Holdout didominasi `dry` (57,6%) dan hanya 31 hari `extreme_wet`; tidak ada
   `el_nino`/`la_nina` resmi. Klaim per regime harus disertai jumlah observasi/CI.
4. Label regime adalah **EVAL ONLY**; jangan di-join ke fitur atau panel.
