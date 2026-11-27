# GATE 2: 2026-11-27, 19.15 WIB (STATUS SEMENTARA — TUNDA PEMBEKUAN MENUNGGU `MLE-H5-03`)

- **Hadir**: RL (`@alim`), MDE (`@akashuten`), MLE (`@agusprasetya`), CGS (`@fariqfaqih`)
- **Commit yang dinilai**: `1bd96be` (`origin/main`; mencakup MLE `54791ba`, MDE `ba14722`, CGS `75363fd`, RL `2b18e78`/`527ca2a`/`c5d9b98`/`1bd96be`)
- **Dataset**: `dataset_v1` · `content_hash.panel = fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de` · `split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`
- **Protokol**: `protocol-v1` (`6c2e85e`) + Amandemen `A1–A3` (`docs/protocol_amendments.md`, commit `1bd96be`)
- **Status Tag `gate2-freeze`**: **BELUM DIBUAT** (menunggu `MLE-H5-03` agar tag menunjuk commit yang memuat `frozen/manifest.yaml` ber-checksum SHA-256 dan `scripts/predict.py`)
- **Status Segel Holdout (`>= 2026-06-01`)**: **TETAP TERSEGEL** (`docs/holdout_seal.md`)

---

## Kriteria dan bukti

| Kriteria | Ambang | Nilai (`1bd96be`) | Sumber (`path` / `run_id`) | Lolos? |
| :--- | :--- | :--- | :--- | :---: |
| **1. Konsistensi `split_hash` semua run** | 100% cocok `dataset_v1` (`411aec1a...`) | **243 / 243 run (100%)** identik; 0 duplikat `run_id`; 100% `completed` | `experiments/registry.csv`, `docs/protocol_audit.md` Butir 1 | **LULUS** |
| **2. Anti-kebocoran waktu, fitur regime, & segel holdout** | `test_no_leakage.py` 0 FAIL; 0 fitur regime; `max(date) < 2026-06-01`; holdout tersegel | `12 PASS / 0 FAIL` (3 SKIP `data/interim`); 0 fitur regime di 7 YAML; `dataset_v1` `max(date) = 2026-05-29`; holdout `TERSEGEL` | `tests/test_no_leakage.py`, `docs/protocol_audit.md` Butir 2–4, 6, 8, `docs/holdout_seal.md` | **LULUS** *(wajib assert `preds.*` lokal pra-freeze)* |
| **3. Amandemen protokol tercatat sebelum holdout dibuka** | Deviasi implementasi tercatat di `docs/protocol_amendments.md` | Amandemen **`A1`** (`n_lags = 6`), **`A2`** (subset `CGS-H5-01`), dan **`A3`** (1-epoch ablasi) tercatat pada 2026-11-27 saat holdout masih tersegel | `docs/protocol_amendments.md` (`1bd96be`) | **LULUS** *(pengesahan bersama MLE & CGS saat freeze final)* |
| **4. Kelengkapan 8 model wajib (5 seed `0..4`, `O1–O3`)** | 8/8 model wajib lengkap 5 seed pada `dataset_v1` | **6 / 8 lengkap** (`seasonal_naive` det. 3 run `20261125-1130_*`, `lgbm_c` [+`lgbm_a/b`] 15 run `20261125-1200_*`, `module1` 30 run `h4_module1_*`, `latent_regime` 15 run `h4_latent_regime_*`, `lag_graph` 15 run `h4_lag_graph_*`, `module23` 15 run `h5_module23_*`); **2 / 8 GAGAL** (`gwn` penuh = 0 run `O1`/`O2`, 21 baris hanya `robustness_gwn_*` `O3` 3 seed; `mtgnn` penuh = 0 run riil) | `experiments/registry.csv`, `experiments/review_log.md`, `docs/protocol_audit.md` Butir 5 | **GAGAL (2 model kandidat eksklusi)** |
| **5. Refit origin `HOLDOUT` + `scripts/predict.py` uji kering** | Refit `HOLDOUT` lengkap + uji kering `predict.py` identik dengan `O3` | `scripts/predict.py` **belum ada**; refit origin `HOLDOUT` (`<= 2025-12-31`, val `2026-01..05`) = **0 run** | `scripts/predict.py` (tidak ditemukan), `experiments/registry.csv` | **GAGAL (Bloker `MLE-H5-03`)** |
| **6. Paket beku `frozen/manifest.yaml` + SHA-256 `ckpt.pt` + `git_sha` bersih** | Setiap model di manifest punya `ckpt.pt` + checksum SHA-256 dari working tree bersih | `frozen/manifest.yaml` **belum ada**; `lag_graph`, `latent_regime`, & `module23` tanpa `ckpt.pt`; 0/8 runner non-`train.py` memanggil `git_sha_clean()` | `frozen/manifest.yaml` (tidak ditemukan), `docs/protocol_audit.md` Butir 9 | **GAGAL (Bloker `MLE-H5-03`)** |
| **7. Tag Git `gate2-freeze` di remote** | Tag annotated `gate2-freeze` di `origin` menunjuk commit beku | Belum dibuat (`git tag -l`: hanya `dataset-v1`, `protocol-v1`) | `git tag -l` | **BELUM (Menunggu `MLE-H5-03`)** |

---

## Ringkasan Model Wajib, Daftar Eksklusi, dan Penetapan `best_baseline_on_validation`

| No | Model Wajib Gate 2 | Run `O1–O3` (`registry.csv`) | `Val h=10 MAE` 3-Origin (`Rp/kg`) | `Test h=10 MAE` 3-Origin (`Rp/kg`) | `epochs` (`1bd96be`) | Status Holdout (Apabila Tidak Ditambah Sebelum Freeze Final) |
| :-: | :--- | :---: | ---: | ---: | :---: | :--- |
| 1 | `seasonal_naive` *(+ `naive_last`)* | 3 (+3) det. | `22.033,23` (`6.169,33`) | `17.389,27` (`6.782,78`) | det. | **LULUS MASUK HOLDOUT** (setelah masuk `frozen/manifest.yaml`) |
| 2 | `lgbm_c` *(+ `lgbm_a`, `lgbm_b`)* | 15 (+30), 5 seed | `6.792,94` (`lgbm_a: 6.176,97`) | `7.094,37` (`lgbm_a: 6.481,95`) | tabular | **LULUS MASUK HOLDOUT** (wajib simpan model + SHA-256 di `manifest.yaml`) |
| 3 | `latent_regime` (ala RCSGNet) | 15, 5 seed | **`5.947,37`** | `7.020,22` | `10` | **LULUS MASUK HOLDOUT** (wajib refit HOLDOUT + `ckpt.pt` + SHA-256) |
| 4 | `lag_graph` (ala MillGNN) | 15, 5 seed | `6.150,97` | `7.128,30` | `5` | **LULUS MASUK HOLDOUT** (wajib samakan epoch + `ckpt.pt` + SHA-256) |
| 5 | `module1` (`bps` & `none`) | 30, 5 seed | `6.442,73` (`bps`) | `7.320,82` (`bps`) | `5` | **LULUS MASUK HOLDOUT** (wajib samakan epoch + refit HOLDOUT + SHA-256) |
| 6 | `module23` (Modul 1–3) | 15, 5 seed | `6.864,81` | `7.581,05` | `2` | **LULUS MASUK HOLDOUT** (wajib naikkan/samakan epoch + `ckpt.pt` + SHA-256) |
| 7 | **`gwn` (Graph WaveNet)** | **0 penuh `O1–O3`** *(hanya 21 `robustness_gwn_*` O3 3 seed)* | — | — | — | **dikeluarkan dari holdout** *(kecuali MLE selesaikan 5 seed penuh + refit sebelum freeze final)* |
| 8 | **`mtgnn`** | **0 riil** *(hanya 5 sintetis `8a551a68`)* | — | — | — | **dikeluarkan dari holdout** *(kecuali MLE selesaikan 5 seed penuh + refit sebelum freeze final)* |

- **Penetapan Pra-Registrasi `best_baseline_on_validation` untuk Uji Diebold–Mariano (`MLE-H6-01`, `docs/eval_protocol_v1.md` §5.4)**:
  1. **Baseline tabular/statis terbaik pada validasi `O1–O3`**: **`lgbm_a`** (`Val h=10 avg = Rp6.176,97/kg`, Test `Rp6.481,95/kg`; dengan `lgbm_c` `Rp6.792,94/kg` sebagai pembanding tabular beriklim dan `naive_last` `Rp6.169,33/kg` sebagai jangkar martingale).
  2. **Baseline rezim laten ala RCSGNet (`MLE-H4-02`)**: **`latent_regime`** (`Val h=10 avg = Rp5.947,37/kg` — terendah secara keseluruhan pada validasi `O1–O3` pada snapshot `1bd96be`; nilai final dikonfirmasi ulang setelah `MLE-H5-03` menyamakan anggaran `epochs` pada validasi sebelum holdout dibuka).

---

## Keputusan

**NO-GO (TUNDA PEMBEKUAN — STATUS SEMENTARA MENUNGGU `MLE-H5-03`)**

- Pembekuan Gate 2 **belum disahkan** untuk pembukaan holdout H6; **tag `gate2-freeze` belum dibuat**; dan **holdout (`>= 2026-06-01`) tetap `TERSEGEL`**.
- Catatan ini merupakan status resmi sementara per 27 November 2026 19.15 WIB dan akan diperbarui menjadi **GO (Final Freeze)** segera setelah `MLE-H5-03` masuk ke `origin/main`.

## Alasan (<= 5 kalimat)

1. Seluruh prasyarat data, anti-kebocoran, robustness, figur sintetis, dan amandemen protokol (`A1–A3`) dari MDE (`ba14722`), CGS (`54791ba`), dan RL (`1bd96be`) telah selesai dengan 0 kebocoran dan holdout tetap tersegel.
2. Namun prasyarat wajib `MLE-H5-03` belum tersedia di repositori: `frozen/manifest.yaml`, checksum SHA-256 `ckpt.pt`, `scripts/predict.py` beserta uji keringnya, dan refit origin `HOLDOUT` masih kosong.
3. Selain itu, 2 dari 8 model wajib (`gwn` penuh dan `mtgnn` penuh) belum memiliki 5 seed pada `O1–O3` `dataset_v1`, anggaran `epochs` antar model neural masih timpang (`10` vs `5` vs `2` epoch, `ANOM-02`), dan bug `scripts/aggregate_ablation.py` L116–117 (`ANOM-07`) belum diperbaiki.
4. Sesuai aturan Gate 2 (`docs/playbook/00_README.md` §5–§6), pemasangan tag `gate2-freeze` tanpa `frozen/manifest.yaml` ber-checksum akan melanggar DoD dan memblokir eksekusi `CGS-H6-01`.
5. Gate 2 akan langsung diperbarui ke **GO** dan di-tag `gate2-freeze` segera setelah `MLE-H5-03` di-merge ke `main`, dengan mencatat secara resmi setiap model yang belum selesai sebagai **"dikeluarkan dari holdout"**.

## Dampak ke rencana

- **Job yang berubah / tertahan sementara**:
  - `CGS-H6-01` (buka holdout 1×) **ditahan sementara** sampai `MLE-H5-03` selesai, `docs/decisions/GATE2.md` diperbarui ke final GO, dan tag `gate2-freeze` ada di remote.
  - `ALL-H5-01` (Gate 2) tetap terbuka pada fase penutupan `MLE-H5-03`.
- **Job / aksi wajib sebelum finalisasi Gate 2**:
  - **MLE (`@agusprasetya`) — `MLE-H5-03` & perbaikan audit**:
    1. Jalankan refit origin `HOLDOUT` (`train <= 2025-12-31`, `val 2026-01-01..2026-05-31`) dengan anggaran `epochs` setara ($\ge 10$–$30$) dari commit bersih (`git_sha_clean()`), simpan `ckpt.pt` + SHA-256 untuk seluruh model yang lulus, dan tulis **`frozen/manifest.yaml`** (termasuk `best_baseline_on_validation` dan `excluded: [gwn, mtgnn]` bila GWN/MTGNN penuh tidak sempat selesai).
    2. Tulis **`scripts/predict.py`** dan jalankan uji kering pada periode uji `O3` hingga identik.
    3. Perbaiki bug `scripts/aggregate_ablation.py` L116–117 (`ANOM-07`: `9.490,31` -> `8.168,40`) dan jalankan assert lokal `max(date) < 2026-06-01` atas seluruh `experiments/runs/*/preds.*` (`PA-04`).
  - **MDE (`@akashuten`)**: Merge commit `baeea86` (`origin/mde`, perbaikan `--dry-run`) ke `main` sebelum tag `gate2-freeze`.
  - **RL (`@alim`) + CGS (`@fariqfaqih`)**: Setelah `MLE-H5-03` masuk ke `main`, verifikasi checksum `frozen/manifest.yaml`, sahkan Amandemen `A1–A3`, perbarui `docs/decisions/GATE2.md` ke **GO**, buat dan push `git tag -a gate2-freeze -m "Gate 2 freeze"`, lalu buka lampu hijau `CGS-H6-01`.

## Risiko yang diterima

- **Eksklusi `gwn` dan `mtgnn` dari holdout (jika tidak selesai di `MLE-H5-03`)**: Keduanya akan dicatat eksplisit sebagai **"dikeluarkan dari holdout"** pada `frozen/manifest.yaml` dan versi final `docs/decisions/GATE2.md`, sehingga evaluasi holdout H6 membandingkan 6 keluarga model beku (`seasonal_naive`/`naive_last`, `lgbm_{a,c}`, `latent_regime`, `lag_graph`, `module1`, `module23`).
- **Keterbatasan komputasi GPU 4 GB Sprint 1**: Subset retrain `CGS-H5-01` (`A2`) dan anggaran 1-epoch ablasi (`A3`) telah didokumentasikan secara transparan di `docs/protocol_amendments.md` dan akan dilaporkan jujur pada bagian keterbatasan `RL-H7-01`.
- **Pergeseran jadwal kecil H5 -> H6**: Penundaan sementara tag `gate2-freeze` lebih baik daripada membekukan commit tanpa `frozen/manifest.yaml` atau membuka segel holdout sebelum paket inferensi teruji.
