# RENARO RAWIT — MLE Sprint 1 reproducible code package

Paket ini adalah **snapshot kode, konfigurasi, manifest, dan instruksi reproduksi** untuk eksperimen MLE Sprint 1. Checkpoint biner **tidak** disertakan; daftar path + SHA-256 ada di `CHECKPOINTS.csv` (handoff internal, bukan rilis publik).

- **Tag kanonik**: `sprint1-final` di repo `renaro-labs/rawit`
- **Commit beku Gate 2**: `b0d0ff98e36fdb10d9a9ef05bcf4ab3225cdf439` (tag `gate2-freeze`)
- **Dataset**: `data/processed/dataset_v1` (`split_hash = 411aec1a...`; tag `dataset-v1`)
- **Baseline validasi**: `lgbm_c` (`best_baseline_on_validation` di `frozen/manifest.yaml`)
- **Seed**: `0..4` untuk semua model

## Isi paket

| Path | Isi |
|---|---|
| `configs/` | 22 YAML: `global.yaml`, `data/v1.yaml`, model dasar, dan `models/gate2/*.yaml` |
| `frozen/manifest.yaml` | 10 model × 5 seed = 50 checkpoint + SHA-256; model eksklusi |
| `CHECKPOINTS.csv` | Daftar 50 checkpoint: model, seed, path, SHA-256, config |
| `requirements.lock.txt`, `environment.lock.yml` | Lockfile Python/conda (termasuk torch, LightGBM, geopandas) |
| `reproduce_sprint1.ps1` | Orkestrator Windows |
| `reproduce_sprint1.sh` | Orkestrator Linux/macOS |
| `README.md` | Dokumen ini |

## Instalasi environment

**Conda (disarankan):**

```bash
conda env create -f environment.lock.yml
conda activate rawit-mle
```

**pip:**

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.lock.txt
```

Python 3.12.16; GPU CUDA opsional (torch 2.14.1+cu126). Tanpa GPU, training neural jauh lebih lambat; inference tetap bisa CPU.

## Prasyarat data

Letakkan data mentah di `data/raw/` (gitignored), lalu jalankan pipeline:

- `data/raw/{chirps_v3,bps,boundaries,enso,sp2kp,pihps}`
- `data/interim/{roni.parquet,bps_mask_entry.csv,calendar.csv,...}`
- `data/processed/dataset_v1/` (dataset beku v1)

Jika data mentah sudah tersedia, lewati unduhan:

```powershell
python scripts\make_dataset.py --config configs\data\v1.yaml --skip-download
```

Dataset beku dapat diverifikasi dengan `data/processed/dataset_v1/VERSION` dan `SHA256SUMS` (6/6).

## Reproduksi cepat (RQ0)

Ini adalah DoD utama MLE-H7-01: orang lain (MDE) dapat menjalankan RQ0 dari clone bersih dan memperoleh angka yang sama (toleransi seed).

```powershell
git clone --branch sprint1-final https://github.com/renaro-labs/rawit.git
cd rawit
$env:PYTHONPATH="$PWD\src"
python scripts\check_env.py
python scripts\make_dataset.py --config configs\data\v1.yaml --skip-download
python scripts\run_rq0.py
python -m pytest -q tests\test_no_leakage.py
```

Output RQ0: `reports/rq0/rq0_results.csv`, `rq0_dm.csv`, `rq0_summary.md`, `rq0_feature_importance.csv`.

> **Penting:** `run_rq0.py` menulis ulang `experiments/registry.csv` dengan 51 run RQ0. Script reproduksi otomatis mem-backup dan mengembalikan registry asli; jika menjalankan manual di repo kerja, backup dulu registry atau gunakan clone bersih.

## Reproduksi penuh

```powershell
.\release\code\reproduce_sprint1.ps1 -PlanOnly          # lihat urutan tanpa menjalankan
.\release\code\reproduce_sprint1.ps1 -SkipDataset       # jika dataset_v1 sudah ada
```

Urutan yang dijalankan:

1. `check_env.py`
2. `make_dataset.py` (atau dilewati)
3. `run_rq0.py`
4. `run_gate2.py --models <10 model> --origins O1,O2,O3 --seeds 0,1,2,3,4` (150 run)
5. `run_ablation.py` untuk 5 varian × 3 origin × 5 seed (75 run) + `aggregate_ablation.py`
6. `robustness.py --mode both` (opsional; 42 run retrain + inference)
7. `predict.py` **hanya jika** `RENARO_SEALED_DIR/HOLDOUT_UNSEALED` ada dan output belum ada
8. `pytest -q`

Perkiraan runtime pada laptop RTX 2050: RQ0 ~10–20 menit; Gate 2 150 run ~8–12 jam; ablation ~2–3 jam; robustness ~1–2 jam. Gunakan `-SkipModels`/`-SkipAblation`/`-SkipRobustness` untuk subset.

## Hasil yang harus cocok

- `reports/h5/gate2_validation_summary.csv`: `lgbm_c` val 3-origin h10 = **5.481,20**; `lgbm_a` 5.543,16; `latent_regime` 5.947,77.
- `reports/rq0/rq0_summary.md`: RQ0 `c vs b` pada `el_nino` h10 $t=+3,7687$, $p=0,000117$; `dry` O1 $p=0,0104$.
- `reports/ablation/ablation_summary.md`: `full` h10 8.168,40; `no_lag` +4,81%; `no_gate` +6,71%.
- `reports/synth/recovery_summary.md`: Module 1 default MAE lag 0,526; Δ lag 0,813; kontrol |Δ lag| 0,026.
- `reports/robustness/robustness_summary.md`: Module 1 rewire p50 +83,01; GWN drop p50 +196,17.
- `reports/holdout/table_main.md`: holdout h10 Module 1 7.452,6; `lgbm_c` 8.800,5; DM median p 0,0744 (tidak signifikan).

Perbedaan kecil akibat seed/GPU diperbolehkan; angka besar (ranking, split hash, label counts) harus sama. `content_hash` dataset harus identik.

## Checkpoint

Checkpoint biner berstatus internal (tidak dirilis publik) karena data PIHPS tidak boleh diredistribusi. Untuk memverifikasi:

```powershell
python scripts\cgs\verify_holdout_integrity.py --require-checkpoints
```

Harus **50/50 SHA-256** cocok `frozen/manifest.yaml`. Path checkpoints ada di `CHECKPOINTS.csv`.

## Holdout

Holdout sudah dibuka satu kali oleh CGS-H6-01 (2026-11-28). Prediksi, label, dan analisis ada di repo:

- `reports/holdout/predictions/` (50 file; commit `ba5cb65`)
- `reports/holdout/table_main.md`, `findings.md`, `QA_predictions.md`

**Jangan** menjalankan `predict.py` ulang tanpa keputusan RL; hasil awal adalah hasil yang dilaporkan. `reproduce_sprint1.ps1` sengaja melewati holdout jika output sudah ada.

## Lisensi

Kode proyek milik Renaro Labs; tidak ada lisensi publik yang dinyatakan di repo. Data mentah mengikuti lisensi masing-masing sumber (lihat `release/climate/SOURCES.md`).
