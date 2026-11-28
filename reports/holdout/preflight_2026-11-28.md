# Preflight CGS-H6-01 — verifikasi sebelum buka holdout

- **Tanggal**: 2026-11-28 (WIB)
- **Pelaksana**: CGS (`@fariq`)
- **Repo**: `D:\renaro\rawit` · branch `job/CGS-H6`
- **Commit evaluasi**: `b0d0ff9` (tag annotated `gate2-freeze` = objek `783506f`)
- **Hasil**: **BERHENTI (BLOCKED)** — paket checkpoint `HOLDOUT` tidak ada; holdout **tidak dibuka**.
- **Keputusan**: sesuai langkah 2 CGS-H6-01, "Ada yang tidak cocok → hentikan, lapor RL."

Dokumen ini hanya memuat metadata dan checksum. **Tidak ada nilai holdout** yang dibaca,
ditampilkan, atau dianalisis.

---

## 1. Prasyarat Gate 2

| # | Prasyarat | Bukti | Status |
|---|---|---|---|
| 1 | Tag `gate2-freeze` ada di remote | `git ls-remote --tags origin gate2-freeze` → `783506f... refs/tags/gate2-freeze`; peeled commit `b0d0ff9` | **OK** |
| 2 | `frozen/manifest.yaml` ada di tag | 10 model × 5 seed = 50 entri; 50 SHA-256; `best_baseline_on_validation: lgbm_c`; `excluded: module1_none, module4` | **OK** |
| 3 | Manifest SHA-256 (file) | `3693ab39a37043e5e9304d2e967c630acaa604e3c3c757db4f24d8094187be0d` | **Tercatat** |
| 4 | Dataset `dataset_v1` cocok manifest | `VERSION` v1: panel `fceeecbf5e9f...`, target `82ae4682f0a6...`, nodes `f09b2776026f...`, bps_mask `c3719e4e79f1...`; `SHA256SUMS` 6/6 OK | **OK** |
| 5 | Panel holdout utuh | `panel_v1/SHA256SUMS` **6/6 OK**; `holdout_v1/SHA256SUMS.txt` **196/196 OK** | **OK** |
| 6 | `predict.py` siap dan pernah diuji kering | `reports/h5/gate2_dryrun_report.md`: 50/50 run O3, `max |Δ y_pred| = 0`, tanpa pelatihan | **OK** |
| 7 | Paket 50 checkpoint `HOLDOUT` diterima | 50/50 path di manifest **tidak ditemukan** di `experiments/runs/` | **GAGAL** |
| 8 | `HOLDOUT_UNSEALED` | Tidak ada di `D:\renaro_sealed` | Belum dibuat (benar) |
| 9 | Output prediksi holdout | `reports/holdout/predictions/` tidak ada | Belum dibuat (benar) |

---

## 2. Audit checkpoint (bukti kegagalan)

Manifest menunjuk 50 file `experiments/runs/g2_<model>_HOLDOUT_s<seed>/ckpt.pt`.
Pemeriksaan pada mesin CGS:

| Model | Checkpoint ditemukan | SHA cocok manifest |
|---|---:|---:|
| `seasonal_naive` | 0/5 | 0/5 |
| `naive_last` | 0/5 | 0/5 |
| `lgbm_a` | 0/5 | 0/5 |
| `lgbm_c` | 0/5 | 0/5 |
| `gwn` | 0/5 | 0/5 |
| `mtgnn` | 0/5 | 0/5 |
| `latent_regime` | 0/5 | 0/5 |
| `lag_graph` | 0/5 | 0/5 |
| `module1` | 0/5 | 0/5 |
| `module23` | 0/5 | 0/5 |
| **Total** | **0/50** | **0/50** |

`experiments/runs/` (208 direktori) berisi run H4/H5, ablasi, robustness, serta
beberapa run `module1`/`gwn`; tidak ada direktori `g2_*_HOLDOUT_s*`.

Satu-satunya `ckpt.pt` di `D:\renaro` berjumlah **43 file**, semuanya di
`_rawit_untracked_backup_20261128\g2_runs_cancelled` (hasil re-run yang dibatalkan):

- **0/43** cocok dengan SHA-256 di `frozen/manifest.yaml`.
- Contoh: `g2_seasonal_naive_HOLDOUT_s0` = `84126daf...` (backup) vs `437ff854...` (manifest).
- Checkpoint backup memakai `git_sha` lama `21a2367`, bukan freeze `6f317be`.

Arsip yang disebut `docs/decisions/GATE2.md` (`frozen_holdout_checkpoints_50runs.zip`,
±31,3 MB) tidak ditemukan di:

- `dist/`
- pencarian drive lokal yang tersedia (`D:\`, profil pengguna)
- file Underleaf proyek RAWIT (`data/`, `processed/`, root proyek)

---

## 3. Keputusan

**Holdout tidak dibuka.** Membuka holdout tanpa 50 checkpoint yang SHA-256-nya cocok
akan melanggar prosedur buka-sekali dan tidak dapat dipulihkan; hasil prediksi juga
tidak akan dapat diverifikasi terhadap manifest.

Tidak ada yang dijalankan dari:

```text
HOLDOUT_UNSEALED
reports/holdout/predictions/preds_*.parquet
reports/holdout/regime_labels_holdout.csv
```

---

## 4. Langkah membuka blokir

1. **MLE/RL** menyerahkan arsip 50 folder `experiments/runs/g2_*_HOLDOUT_s*/`
   (isi minimal `ckpt.pt`, `config.yaml`, `git_sha.txt`) ke CGS melalui drive
   bersama atau file Underleaf. Sertakan checksum arsip.
2. **CGS** mengekstrak ke `experiments/runs/`, lalu memverifikasi 50/50 SHA-256
   terhadap `frozen/manifest.yaml`:

   ```powershell
   @'
   import hashlib, yaml
   from pathlib import Path
   root = Path(".")
   manifest = yaml.safe_load((root/"frozen/manifest.yaml").read_text(encoding="utf-8"))
   bad = []
   n = 0
   for entry in manifest["models"]:
       for seed, ckpt, want in zip(entry["seeds"], entry["checkpoints"], entry["sha256"]):
           p = root/ckpt; n += 1
           got = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"
           if got != want: bad.append((ckpt, got, want))
   print(f"{n-len(bad)}/{n} cocok")
   for row in bad: print("BAD", *row)
   @' | python -
   ```

3. Jika 50/50 cocok: tulis `D:\renaro_sealed\HOLDOUT_UNSEALED` berisi waktu dan
   commit `b0d0ff9` (sekali), lalu jalankan:

   ```powershell
   python scripts/predict.py --manifest frozen/manifest.yaml `
     --context data/processed/dataset_v1 `
     --holdout "$env:RENARO_SEALED_DIR\holdout_v1\panel_v1" `
     --out reports/holdout/predictions
   ```

   Perhatikan `panel_v1` — deskripsi task menulis `...\holdout_v1` (level satu di
   atasnya), yang akan ditolak `validate_dataset`.

4. Hitung label regime holdout (definisi CGS-H4-01) → `reports/holdout/regime_labels_holdout.csv`.
5. Isi bagian "Dibuka" di `docs/holdout_seal.md` dan commit prediksi + label.

---

## 5. Reproduksi pemeriksaan

```powershell
git fetch --all --prune
git ls-remote --tags origin gate2-freeze
git show gate2-freeze:frozen/manifest.yaml
Get-ChildItem experiments\runs -Directory | Where-Object Name -like 'g2_*_HOLDOUT_s*'
Get-ChildItem D:\renaro -Recurse -Filter ckpt.pt
python scripts\cgs\verify_holdout_integrity.py
python scripts\cgs\verify_holdout_integrity.py --require-checkpoints   # gagal selama 0/50
```

Output verifikasi 28 November 2026:

```text
[ok] dataset_v1: 6/6 checksum cocok
[ok] holdout panel_v1: 6/6 checksum cocok
[ok] holdout 196-file manifest: 196/196 checksum cocok
[GAP] checkpoint manifest: 0/50 SHA-256 cocok
      missing: 50 (contoh: experiments/runs/g2_seasonal_naive_HOLDOUT_s0/ckpt.pt)
[info] HOLDOUT_UNSEALED: tidak ada (tersegel)
[info] output prediksi: belum ada
HASIL: integritas data OK, tetapi checkpoint belum lengkap (0/50) — HOLD, jangan buka holdout.
```

