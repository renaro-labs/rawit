# Handout MLE-H5-03 · Refit HOLDOUT + `predict.py` + `frozen/manifest.yaml`

Disiapkan 2026-11-28 untuk MLE (RAWIT#56), sebagai prasyarat ALL-H5-01 (Gate 2, RAWIT#59)
dan CGS-H6-01. Training **belum** dijalankan penuh; dokumen ini menjelaskan alat yang sudah
ada, apa yang sudah diverifikasi, dan langkah yang tersisa.

## 1. Status singkat

| Item | Status |
|---|---|
| Runner Gate 2 `scripts/run_gate2.py` | ada (commit `b9c73a3`, impor eager di `21a2367`) |
| Inferensi `scripts/predict.py` + `src/renaro/frozen.py` | ada; smoke test identik (lihat §3) |
| Config beku `configs/models/gate2/*.yaml` | ada (10 model); keputusan anggaran epoch di §4 |
| Refit `HOLDOUT` lewat `rolling_origin(..., refit=True)` | ada; test HOLDOUT tetap SEALED |
| `tests/test_frozen.py` | 5 test lulus; suite penuh 161 lulus / 11 skip |
| Run O1–O3 + HOLDOUT (200 run) | **belum** — dibatalkan, diserahkan ke MLE |
| `frozen/manifest.yaml`, laporan uji kering, `best_baseline_on_validation` | **belum** |
| MLE-H5-02: bug sanity `aggregate_ablation.py` (ANOM-07) | **sudah** diperbaiki (`21a2367`): full = 8168.40 |

Kedua commit ada di branch lokal `mle` (di atas `origin/main` `753636f`) dan **belum di-push**.

## 2. Model yang dibekukan

| Model (manifest) | Wajib Gate 2 | Family | Config |
|---|:-:|---|---|
| `seasonal_naive` | ya | naive (deterministik) | `configs/models/gate2/seasonal_naive.yaml` |
| `naive_last` | pendamping | naive | `.../naive_last.yaml` |
| `lgbm_c` | ya | LightGBM, 1 model/horizon | `.../lgbm_c.yaml` |
| `lgbm_a` | pendamping (kandidat baseline DM) | LightGBM | `.../lgbm_a.yaml` |
| `gwn` | ya | Graph WaveNet lite | `.../gwn.yaml` |
| `mtgnn` | ya | MTGNN lite | `.../mtgnn.yaml` |
| `latent_regime` (ala RCSGNet) | ya | graph | `.../latent_regime.yaml` |
| `lag_graph` (ala MillGNN) | ya | graph | `.../lag_graph.yaml` |
| `module1` (prior `bps`) | ya | graph | `.../module1.yaml` |
| `module23` (Modul 1–3) | ya | graph | `.../module23.yaml` |

Config basis `configs/models/<model>.yaml` sengaja **tidak** diubah agar run H2–H5 lama tetap
reproducible. Config `gate2/` dipakai untuk O1–O3 **dan** refit HOLDOUT, sehingga
"konfigurasi holdout = konfigurasi validasi" (DoD #56).

## 3. Yang sudah diverifikasi (smoke test, 1 epoch, O3 seed 0)

`predict_frozen` membangun array input **independen** dari `WindowDataset` lalu dibandingkan
dengan prediksi uji O3 dari jalur latih (`--start 2025-01-01 --end 2026-05-31`, konteks =
holdout palsu = `dataset_v1`):

| Model | Baris uji | `y_pred` identik | maxdiff | y_true/mask/naive |
|---|---:|:-:|---:|:-:|
| seasonal_naive, naive_last | 35.496 | ya | 0.0 | ya |
| module1, lag_graph, latent_regime, module23 | 35.496 | ya | 0.0 | ya |
| gwn, mtgnn | 35.496 | ya | 0.0 | ya |
| lgbm_c | 35.496 | ya | 0.0 | ya |

Juga diverifikasi: refit HOLDOUT (naive_last, module1, gwn, lgbm_a) hanya membentuk part `val`,
decision 2026-01-01..2026-05-01, target ≤ 2026-05-28, train range `2018-01-02..2025-12-31`.
Ini **bukan** pengganti uji kering resmi (§5 langkah 3) karena memakai 1 epoch.

Catatan: `lgbm_c` O3 s0 via runner ini memberi val h10 MAE 3824.1, sedangkan registry RQ0
(`20261125-1200_lgbm_c_O3_s0`) 3928.2 walau kode `lgbm.py`/`tabular.py` tidak berubah sejak
RQ0. Kemungkinan beda versi LightGBM/lingkungan (mesin ini: lightgbm 4.7.0, pandas 3.1.0,
numpy 2.5.4, Python 3.15). Catat di laporan; angka Gate 2 pakai run `g2_*`.

## 4. Keputusan yang perlu MLE (dan RL) sahkan

1. **Anggaran latih neural seragam (ANOM-02).** `configs/models/gate2/` memakai
   `epochs: 10, patience: 10` untuk semua model neural (sebelumnya 2/5/10, dan best epoch
   hampir selalu = epoch terakhir, artinya masih under-trained). Karena config berubah,
   **validasi O1–O3 ikut diulang** dengan config yang sama; ini dicatat sebagai amandemen A4 di
   `docs/protocol_amendments.md` (milik RL) **sebelum** holdout dibuka. Bila MLE memilih
   anggaran lain, cukup ubah 6 file `gate2/*.yaml` (test `test_gate2_configs_cover_required_models`
   memaksa anggaran seragam).
2. **`best_baseline_on_validation`** ditetapkan dari rata-rata val h10 MAE 3 origin × 5 seed run
   `g2_*`, hanya di antara baseline (`seasonal_naive`, `naive_last`, `lgbm_a`, `lgbm_c`, `gwn`,
   `mtgnn`, `latent_regime`, `lag_graph`), sebelum holdout dibuka. RL di `docs/decisions/GATE2.md`
   menyebut kandidat `lgbm_a` / `latent_regime` (snapshot lama).
3. `module1` prior `none` dan Modul 4 (MLE-H5-04) tidak dibekukan → tulis di `excluded` /
   GATE2 sebagai "dikeluarkan dari holdout" bila tidak ikut.

## 5. Langkah menjalankan

Semua dari akar repo, working tree **bersih** (runner menolak tree kotor, kecuali
`experiments/registry.csv`).

```powershell
# 1) validasi O1-O3 + refit HOLDOUT, 5 seed (run yang sudah lengkap otomatis dilewati)
python scripts/run_gate2.py --models module1,module23,latent_regime,lag_graph,gwn,mtgnn `
    --origins O1,O2,O3,HOLDOUT --seeds 0,1,2,3,4
$env:CUDA_VISIBLE_DEVICES="-1"   # proses CPU terpisah untuk naive + LightGBM
python scripts/run_gate2.py --models seasonal_naive,naive_last,lgbm_a,lgbm_c `
    --origins O1,O2,O3,HOLDOUT --seeds 0,1,2,3,4 --threads 2
```

Output per run: `experiments/runs/g2_<model>_<origin>_s<seed>/` berisi `config.yaml`,
`git_sha.txt`, `ckpt.pt`, `ckpt.sha256`, `preds.parquet`, `summary.json`, `log.txt`, plus satu
baris di `experiments/registry.csv`.

**Perkiraan waktu (RTX 2050, satu proses GPU):** ±10 jam untuk 120 run neural (module1
±6 mnt/run, gwn/mtgnn ±6–7 mnt/run, lainnya ±3–4 mnt/run); CPU ±1 jam untuk 80 run naive/LightGBM.
**RAM:** tiap proses CUDA memakan ±3 GB commit; di laptop 8 GB jangan jalankan lebih dari
1 proses GPU + 1 proses CPU (percobaan 4 worker paralel gagal `ArrayMemoryError`/segfault).

```powershell
# 2) manifest: kumpulkan run g2_*_HOLDOUT_s{0..4} -> frozen/manifest.yaml (skrip perlu ditulis)
#    isi minimal per model: name, config, seeds, checkpoints, sha256 (+ run validasi O1-O3)
# 3) uji kering resmi pada periode uji O3 (bukan holdout asli): buat manifest sementara dari
#    run g2_*_O3_s*, lalu
python scripts/predict.py --manifest <manifest_O3.yaml> --context data/processed/dataset_v1 `
    --holdout data/processed/dataset_v1 --start 2025-01-01 --end 2026-05-31 --fold O3 `
    --out reports/h5/predict_dryrun
#    bandingkan preds_<model>_s<seed>.parquet dengan bagian test preds.parquet run O3 pada
#    (date, prov_code, h): y_pred harus identik (smoke test §3 = maxdiff 0.0).
# 4) cek PA-04: max(date/target_date) < 2026-06-01 untuk semua experiments/runs/*/preds.*
```

Format `frozen/manifest.yaml` yang dibaca `scripts/predict.py`:

```yaml
freeze_commit: <sha di git_sha.txt run>
dataset: {path: data/processed/dataset_v1, content_hash: {panel: fceeecbf..., target: 82ae4682..., nodes: f09b2776..., bps_mask: c3719e4e...}, split_hash: 411aec1a...}
protocol: protocol-v1
models:
  - name: module1
    config: configs/models/gate2/module1.yaml
    seeds: [0, 1, 2, 3, 4]
    checkpoints: [experiments/runs/g2_module1_HOLDOUT_s0/ckpt.pt, ...]
    sha256: [<isi ckpt.sha256>, ...]
  - ...
best_baseline_on_validation: <nama>
excluded: []
```

`predict.py` memverifikasi semua SHA-256 dulu (satu tidak cocok → berhenti), menolak menimpa
output, dan hanya mau membaca tanggal ≥ 2026-06-01 bila `HOLDOUT_UNSEALED` ada di
`RENARO_SEALED_DIR` (dibuat CGS pada CGS-H6-01). Prediksi holdout resmi dijalankan **CGS**,
bukan MLE.

## 6. Serah ke Gate 2 / CGS

1. Commit `configs/models/gate2/`, `frozen/manifest.yaml`, laporan uji kering, dan registry
   (checkpoint tetap gitignored; unggah `experiments/runs/g2_*` ke file Underleaf di path yang sama).
2. RL melengkapi `docs/decisions/GATE2.md` (GO/NO-GO + daftar "dikeluarkan dari holdout"),
   lalu `git tag -a gate2-freeze -m "Gate 2 freeze"` dan `git push origin gate2-freeze`.
3. CGS-H6-01 menjalankan perintah resmi di docstring `scripts/predict.py`.
