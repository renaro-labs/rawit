# 04 · MLE: ML/Graph Modeling Engineer

> **Tanggung jawab (brief §9):** Modul 1–4, semua baseline, run benchmark dan ablation.
> **Kepemilikan kunci:** kode model; checkpoint.
> **Prinsip:** semua model neural memakai **backbone yang sama** (encoder temporal + head prediksi). Yang berbeda hanya **cara graph dibentuk**: statis, adaptif, laten-regime, lag tanpa iklim, atau lag terkondisi iklim. Dengan begitu perbandingan *head-to-head* (RQ1) mengisolasi efek pengondisian iklim.
> **Batas hardware:** RTX 2050 **4 GB**. Pakai AMP (`torch.autocast("cuda", dtype=torch.float16)`), batch 16–32, hidden ≤ 64. LightGBM di CPU.

## Ringkasan job

| ID | Hari | Job | Mode | Output utama |
|---|---|---|---|---|
| MLE-H0-01 | H0/H1 pagi | `check_env.py` + lockfile env | PARALEL | `scripts/check_env.py`, `environment.lock.yml` |
| MLE-H1-01 | H1 | Loader sesuai skema (data dummy) | PARALEL | `src/renaro/data/io.py`, `datasets.py` |
| MLE-H1-02 | H1 | Generator data sintetis | PARALEL | `src/renaro/synth/` |
| MLE-H1-03 | H1 | Harness rolling-origin + seasonal naive + LightGBM | PARALEL | `src/renaro/eval/`, `baselines/naive.py`, `lgbm.py` |
| MLE-H2-01 | H2 | Baseline Graph WaveNet / MTGNN | PARALEL | `src/renaro/baselines/{gwn,mtgnn}.py` |
| MLE-H2-02 | H2 | Prototipe Modul 1 (sintetis) | PARALEL | `src/renaro/models/module1.py` |
| MLE-H3-01 | H3 pagi | Uji recovery jeda Modul 1 | PARALEL | `reports/synth/` |
| MLE-H3-02 | H3 siang | **Uji sinyal RQ0** (bersama RL) | SEKUENSIAL (dataset v1 + protokol) | `reports/rq0/` |
| MLE-H4-01 | H4 | Modul 1 pada data riil | PARALEL | runs + checkpoint |
| MLE-H4-02 | H4 | Baseline regime laten ala RCSGNet | PARALEL | `baselines/latent_regime.py` |
| MLE-H4-03 | H4 | Baseline lag ala MillGNN (disederhanakan) | PARALEL | `baselines/lag_graph.py` |
| MLE-H5-01 | H5 | Modul 2–3 (stabil/adaptif + gate) | PARALEL | `models/module23.py` |
| MLE-H5-02 | H5 | Ablation | PARALEL | `reports/ablation/` |
| MLE-H5-03 | H5 | Refit konfigurasi holdout + `predict.py` + manifest beku | PARALEL → Gate 2 | `frozen/manifest.yaml` |
| MLE-H5-04 | H5 | Modul 4 *(stretch)* | PARALEL | `models/module4.py` |
| MLE-H6-01 | H6 | **Analisis holdout** (lead; bersama CGS, RL) | SEKUENSIAL (prediksi holdout) | `reports/holdout/` |
| MLE-H7-01 | H7 | Paket kode reproducible | PARALEL | `release/code/` |

### Anggaran komputasi (perkiraan, untuk perencanaan)
| Model | Run | Estimasi/run (RTX 2050) | Total |
|---|---|---|---|
| LightGBM RQ0 (3 varian × 3 origin × 3 horizon × 5 seed) | 135 | < 1 menit (CPU) | ~1–2 jam |
| GWN, MTGNN (3 origin × 5 seed) | 30 | 3–8 menit | ~2–4 jam |
| Modul 1, ala RCSGNet, ala MillGNN (3 origin × 5 seed × 3) | 45 | 3–8 menit | ~3–6 jam |
| Ablation (4 varian × 3 origin × 5 seed) | 60 | 3–8 menit | ~3–8 jam |
| Refit holdout (semua model × 5 seed) | ~40 | 3–8 menit | ~2–5 jam |

Jalankan run panjang **semalam** (H4→H5) lewat `scripts/run_grid.py` dengan antrean. Bila estimasi meleset > 2×, kurangi seed dulu untuk ablation (bukan untuk model utama) dan catat di audit RL.

---

## MLE-H0-01 · Smoke test environment + lockfile
1. Tulis `scripts/check_env.py` (spesifikasi di file setup §2.4).
2. Buat env dari `environment.yml`, pasang torch cu126 + PyG, jalankan smoke test, lalu ekspor `environment.lock.yml` dan `requirements.lock.txt` → commit.
**DoD:** [ ] `torch.cuda.is_available() == True` · [ ] lockfile di `main` sebelum kickoff selesai.

---

## MLE-H1-01 · Loader sesuai skema (dengan data dummy)

| | |
|---|---|
| Waktu | H1 11.00–13.30 |
| Mode | PARALEL |
| Input | `docs/data_contract.md` (§5.7 struktur `dataset_v1/`), `configs/global.yaml` |
| Tools | `pandas`, `pyarrow`, PyTorch `Dataset`/`DataLoader` |
| Handoff | Semua job MLE; MDE-H3-01 (verifikasi muat) |

**Langkah**
1. `src/renaro/data/dummy.py`: membuat folder `dataset_v1/` palsu dengan **skema persis kontrak** (34 node, 2017-07 … 2026-05 hari kerja, fitur acak, mask 14%). Semua kode MLE diuji dengan ini sampai dataset asli ada.
2. `src/renaro/data/io.py`:
   - `load_panel(path) -> (panel_df, target_df, nodes_df, mask)`, **selalu** memotong `date < holdout_start` kecuali mode unsealed (file setup §7).
   - Validasi skema (kolom wajib, tipe, urutan node = `provinces.csv`). Gagal → exception yang jelas.
   - Hitung `split_hash` = hash (`content_hash` dataset + definisi split dari `global.yaml`) dan simpan di setiap run.
3. `src/renaro/data/datasets.py`:
   - `WindowDataset(panel, target, origin, part, horizons, window)` menghasilkan
     `X: [T_in, N, F]`, `y: [H, N]`, `y_mask: [H, N]` (True bila target observasi), `t_index`, `C: [T_in, N, F_clim]` (fitur iklim terpisah untuk Modul 1).
   - Normalisasi fitur: statistik dihitung **hanya dari bagian latih** setiap origin.
   - Opsi `node_subset` (hanya node `include=True` yang masuk loss/metrik; node lain tetap jadi input graph).
4. `tests/test_loader.py`: bentuk tensor, tidak ada tanggal ≥ holdout, normalisasi tidak memakai data validasi/uji.

**Output:** `src/renaro/data/{io,datasets,dummy}.py`, `tests/test_loader.py`.
**DoD:** [ ] test hijau di data dummy · [ ] satu batch termuat di GPU < 50 MB.

---

## MLE-H1-02 · Generator data sintetis (jeda terkondisi iklim yang diketahui)

| | |
|---|---|
| Waktu | H1 13.30–17.00 |
| Mode | PARALEL |
| Tools | `numpy` |
| Handoff | MLE-H2-02, MLE-H3-01, RL-H5-01 |

**Tujuan:** data dengan ground-truth graph dan jeda per edge yang **bergeser saat iklim asal berubah**. Dipakai untuk menjawab RQ1 sintetis: apakah Modul 1 menemukan kembali pergeseran jeda yang ditanam.

**Spesifikasi `src/renaro/synth/generator.py`**
1. Parameter (`configs/synth/default.yaml`): `N=34`, `T=2400` langkah (≈ 10 tahun hari kerja), `L=8` bin jeda (1 bin = 5 langkah ≈ 1 pentad), `density=0.14`, `noise_sd`, `seed`.
2. **Graph benar** `G`: edge berarah acak dengan densitas 14% (atau pakai `bps_mask.npy` asli bila sudah ada).
3. **Iklim sintetis** per node `c_j(t)`: AR(1) + musiman + episode kering acak (durasi 10–40 langkah). `dry_j(t) = 1` saat episode.
4. **Jeda bergantung iklim**: untuk tiap edge `j → i`, `ℓ_normal ∈ {1..4}` acak, `ℓ_dry = min(ℓ_normal + Δ, L)` dengan `Δ = 2`. Intensitas `a_dry = κ · a_normal` (κ = 1,5).
5. **Dinamika harga (log)**:
   `x_i(t) = ρ·x_i(t−1) + Σ_{j→i} a_ij(t) · u_j(t − 5·ℓ_ij(t)) + musiman_i(t) + ε_i(t)`,
   dengan `u_j(t) = −β·c_j(t) + x_j(t) − x_j(t−1)` (guncangan pasokan dari iklim + perubahan harga asal), dan `ℓ_ij(t)`, `a_ij(t)` ditentukan oleh `dry_j(t − 5·ℓ)`.
6. **Varian kontrol**: `mode="unconditioned"` (jeda tidak bergeser) untuk memastikan Modul 1 tidak "menemukan" pergeseran palsu.
7. Ekspor dalam **format dataset_v1 yang sama** (`panel.parquet` dengan kolom fitur iklim sintetis), plus `truth.npz`: `G [N,N]`, `lag_normal [N,N]`, `lag_dry [N,N]`, `dry [T,N]`, `A_true [T,N,N,L]` (boleh disimpan jarang).

**Output:** `src/renaro/synth/generator.py`, `configs/synth/{default,unconditioned}.yaml`, `data/synth/{default,unconditioned}/`.
**DoD:** [ ] determinisme per seed · [ ] plot cek: korelasi silang `u_j` vs `x_i` memuncak di `5·ℓ_normal` saat normal dan `5·ℓ_dry` saat kering untuk 3 edge contoh (`reports/synth/sanity_xcorr.png`).

---

## MLE-H1-03 · Harness rolling-origin + seasonal naive + LightGBM

| | |
|---|---|
| Waktu | H1 (mulai setelah protokol v0 draf ±15.00; kerangka bisa sejak 11.00) |
| Mode | PARALEL |
| Input | `eval_protocol_v0.md`, `configs/global.yaml` |
| Tools | LightGBM, scikit-learn, `statsmodels`, `pandas` |
| Handoff | MLE-H3-02 (RQ0), semua model |

**Langkah**
1. `src/renaro/eval/splits.py`: membaca origin dari `global.yaml` → indeks latih/val/uji + embargo. Fungsi `assert_no_overlap()`.
2. `src/renaro/eval/metrics.py`: MAE, RMSE, sMAPE (pada Rp/kg, hanya `y_mask=True`), `per_regime(preds, regime_labels)`, `worst_regime_error`, `ood_delta`, `seed_stability`.
3. `src/renaro/eval/dm_test.py`: Diebold–Mariano dengan koreksi Harvey–Leybourne–Newbold, loss absolut, HAC lag `h−1`, pada deret rata-rata loss lintas provinsi per tanggal. Uji unit: dua prediksi identik → statistik 0; satu jelas lebih baik → p kecil.
4. `src/renaro/baselines/naive.py`:
   - `naive_last`: ŷ(t+h) = y(t).
   - `seasonal_naive`: ŷ(t+h) = y pada tanggal hari kerja terdekat dengan (t+h − 364 hari). **Baseline wajib brief.**
5. `src/renaro/baselines/lgbm.py`: model **global** lintas provinsi (`prov_code` kategorikal), satu model per horizon (*direct*), target = `log p(t+h) − log p(t)` lalu dikonversi ke level. Hiperparameter tetap **[usulan default: num_leaves=31, learning_rate=0.05, n_estimators=2000 + early stopping 100 di validasi, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, min_data_in_leaf=50]**; `seed` = seed run.
6. `scripts/train.py --model <nama> --origin <O1|O2|O3|HOLDOUT> --seed <s> --config configs/models/<nama>.yaml` → menulis folder run (file setup §6) dan menolak jalan bila working tree git kotor.
7. Jalankan end-to-end di data dummy.

**Output:** `src/renaro/eval/{splits,metrics,dm_test}.py`, `src/renaro/baselines/{naive,lgbm}.py`, `scripts/train.py`, `tests/test_eval.py`.
**DoD:** [ ] `python scripts/train.py --model lgbm --origin O1 --seed 0` menghasilkan folder run lengkap pada data dummy · [ ] test DM & metrik hijau.

---

## MLE-H2-01 · Baseline Graph WaveNet / MTGNN

| | |
|---|---|
| Waktu | H2 09.15–13.00 |
| Mode | PARALEL |
| Input | Loader (MLE-H1-01), data dummy/sintetis |
| Tools | PyTorch, PyG (opsional), implementasi rujukan resmi Graph WaveNet [1] dan MTGNN [2] (repo penulis di GitHub; **cek lisensi** sebelum menyalin; tulis ulang bila lisensinya tidak jelas) |

**Langkah**
1. Port ke `src/renaro/baselines/gwn.py` dan `mtgnn.py` dengan antarmuka seragam: `forward(X [B,T_in,N,F], A_prior [N,N] | None) -> ŷ [B,H,N]`.
2. GWN: *support* = prior (opsional) + adjacency adaptif. MTGNN: graph learner bawaan, tanpa prior.
3. Skala kecil untuk 34 node: hidden 32, 4–8 layer dilatasi, dropout 0,3.
4. Loop latih bersama `src/renaro/train_loop.py`: Adam (lr 1e-3), early stopping di validasi (patience 15), maks 200 epoch, AMP, *gradient clipping* 5, loss MAE pada `y_mask`.
5. Uji pada sintetis: keduanya harus mengalahkan `naive_last`.

**Output:** `baselines/gwn.py`, `baselines/mtgnn.py`, `src/renaro/train_loop.py`, `configs/models/{gwn,mtgnn}.yaml`.
**DoD:** [ ] berjalan pada dummy & sintetis · [ ] memori GPU puncak < 3 GB (catat di config).

---

## MLE-H2-02 · Prototipe Modul 1: climate-conditioned lag graph

| | |
|---|---|
| Waktu | H2 13.00–17.00 |
| Mode | PARALEL |
| Input | Generator sintetis (MLE-H1-02), backbone dari MLE-H2-01 |
| Tools | PyTorch |
| Handoff | MLE-H3-01, MLE-H4-01 |

**Rumus (brief §5):**
$A^{(\ell)}_{ij,t} = \operatorname{softmax}_{j,\ell}\big[\phi_\theta(h_{i,\le t}, h_{j,\le t}, c_{j,\le t}, s_{ij}, \ell)\big]$

**Arsitektur `src/renaro/models/module1.py`**
1. **Encoder temporal node** (dipakai semua model neural): GRU 1 lapis, hidden 64, atas `X_i` → `h_i` (state akhir) dan `z_i(τ)` (state per langkah).
2. **Encoder iklim asal**: fitur iklim `j` pada 8 pentad terakhir yang **tersedia pada t** (anomali hujan pentad, durasi kering, ekstrem 5-harian, RONI) → MLP → `e_j`.
3. **Representasi berjeda**: `z_j^{(ℓ)}` = rata-rata `z_j(τ)` pada jendela pentad ke-ℓ ke belakang (τ ∈ [t−5ℓ, t−5ℓ+4]), ℓ = 1..L, L = 8.
4. **Pemberi skor** `φ_θ`: MLP([h_i, h_j, e_j, s_ij, emb(ℓ)]) → skalar. `s_ij` = fitur edge statis: log jarak, flag BPS, pangsa BPS (0 bila kosong).
5. **Normalisasi**: softmax atas semua pasangan (j, ℓ) untuk tiap tujuan `i`, dengan:
   - kandidat `j` dibatasi `candidate_mask` (varian prior: `none` = semua; `bps` = mask BPS ∪ {k tetangga terdekat});
   - satu opsi "null" (vektor nol) agar `i` bisa tidak mengambil informasi dari tetangga.
6. **Agregasi**: `m_i = Σ_{j,ℓ} A^{(ℓ)}_{ij,t} · W_v z_j^{(ℓ)}`.
7. **Head**: MLP([h_i, m_i, kalender masa depan]) → ŷ untuk H horizon.
8. `forward()` mengembalikan `ŷ` **dan** `A` (`[B,N,N,L]`) untuk analisis.
9. Regularisasi opsional: entropi `A` (λ kecil) agar perhatian tidak tersebar merata.

**Langkah:** implementasi → latih pada `data/synth/default` → cek loss turun dan `A` tidak seragam.

**Output:** `src/renaro/models/module1.py`, `configs/models/module1.yaml`.
**DoD:** [ ] memori puncak < 3 GB pada batch 32 · [ ] MAE sintetis < GWN pada data `default`.

---

## MLE-H3-01 · Uji recovery jeda Modul 1 (sintetis)

| | |
|---|---|
| Waktu | H3 09.15–11.00 |
| Mode | PARALEL |
| Handoff | RL-H5-01 (figur), laporan |

**Langkah**
1. Latih Modul 1 pada `synth/default` dan `synth/unconditioned`, masing-masing 5 seed.
2. Pada set uji sintetis, untuk setiap edge benar `j → i` dan setiap regime (dry_j = 0/1):
   - `lag_hat = argmax_ℓ mean_t A^{(ℓ)}_{ij,t}`.
   - **Akurasi jeda** = proporsi `lag_hat == lag_true`.
   - **Spearman** antara massa-jeda terpelajari (ekspektasi ℓ) dan jeda benar.
   - **Δlag** = E[ℓ | dry] − E[ℓ | normal], dibandingkan dengan Δ benar (2).
   - **AUROC edge**: Σ_ℓ A vs G.
3. Kontrol: (i) Modul 1 dengan `e_j = 0` (tanpa iklim) pada `default` → Δlag harus ≈ 0 (tidak bisa mendeteksi pergeseran); (ii) Modul 1 pada `unconditioned` → Δlag ≈ 0.
4. Bandingkan dengan ambang lolos di protokol v1 §10.

**Output**
- `reports/synth/recovery_metrics.csv`: `seed, data_variant, model_variant, regime, lag_acc, spearman, delta_lag, auroc`.
- `reports/synth/recovery_summary.md`: lolos/tidak terhadap ambang protokol.
- Data mentah figur (`reports/synth/lag_true_vs_hat.parquet`) untuk RL-H5-01.

**DoD:** [ ] tabel 5 seed lengkap · [ ] kesimpulan lolos/tidak tertulis eksplisit · [ ] kontrol dilaporkan.

---

## MLE-H3-02 · Uji sinyal RQ0 (bersama RL)

| | |
|---|---|
| Waktu | H3 11.00–15.30 |
| Mode | **SEKUENSIAL**: menunggu `dataset_v1` (MDE-H3-01) + tag `protocol-v1` (RL-H2-01) |
| Input | `dataset_v1/`, `regime_labels.csv` (hanya evaluasi), protokol v1 §8 |
| Tools | LightGBM, harness MLE-H1-03 |
| Handoff | RL-H3-02 (Gate 1) |

**Langkah**
1. `src/renaro/features/tabular.py`: bangun fitur dari panel (semuanya sudah *as-of* di dataset v1):
   - **(a)** lag log-harga sendiri (1, 2, 3, 5, 10, 20 hari kerja), return 5/20 hari, rata-rata & std bergulir 20/60, kalender (`days_to_lebaran`, `is_ramadan`, `dow`, `month`, libur).
   - **(b)** (a) + iklim provinsi sendiri: `rain_pentad_anom` pada jeda pentad 0–8, `dry_spell_days`, `extreme_5d` (jumlah dalam 4 pentad terakhir), `rain_30d_anom`.
   - **(c)** (b) + iklim **wilayah asal**: untuk tujuan `i`, asal `O_i = {j : bps_mask[i, j] = 1}` (fallback sesuai protokol bila kosong); agregat `Σ_j w_ij · rain_pentad_anom_j(lag)` dengan `w_ij` = pangsa BPS dinormalisasi (atau 1/|O_i|), jeda pentad 1–8; plus agregat `dry_spell_days` asal.
2. Jalankan grid: varian {a, b, c} × origin {O1, O2, O3} × horizon {5, 10, 20} × seed {0..4} dengan **hiperparameter identik**.
3. Evaluasi: MAE/RMSE/sMAPE total dan per regime (label CGS, hanya evaluasi). Δ% MAE (c vs b) per origin. DM (c vs b) per regime dan total.
4. **Isi otomatis cek Gate 1** di ringkasan:
   - `mean_delta_pct ≥ 3%`? · `n_origin_c_better ≥ 2/3`? · `any_regime_DM_p < 0.05`?
5. Feature importance (gain) untuk (c): apakah fitur asal termasuk 20 teratas?
6. Sanity: (a) harus mengalahkan seasonal naive. Jika tidak, hentikan dan debug bersama RL.

**Output**
| Path | Isi |
|---|---|
| `reports/rq0/rq0_results.csv` | `variant, origin, horizon, seed, regime, mae, rmse, smape, n` |
| `reports/rq0/rq0_dm.csv` | `comparison, origin, horizon, regime, dm_stat, p_value` |
| `reports/rq0/rq0_summary.md` | Tabel ringkas (rata-rata 5 seed ± std), cek kriteria Gate 1 (✅/❌ per kriteria), feature importance |

**DoD:** [ ] semua run tercatat di `registry.csv` dengan `split_hash` sama · [ ] ringkasan diserahkan ke RL ≤ 15.30.

---

## MLE-H4-01 · Modul 1 pada data riil

| | |
|---|---|
| Waktu | H4 09.15–17.00 (+ antrean semalam) |
| Mode | PARALEL (setelah Gate 1) |
| Input | `dataset_v1`, `graph_priors/` (MDE-H4-01, tersedia siang; mulai dengan `bps_mask.npy` dari dataset) |
| Handoff | CGS-H5-01 (butuh checkpoint), MLE-H5-01 |

**Langkah**
1. *Tuning ringan* **hanya di validasi O1**: hidden {32, 64} × lr {1e-3, 3e-4} × L {6, 8} = 8 konfigurasi, seed 0. Pilih terbaik → dibekukan untuk semua origin.
2. Run penuh: origin {O1, O2, O3} × seed {0..4} × prior {`bps`, `none`}.
3. Simpan `A` rata-rata per regime (validasi) untuk analisis: `experiments/runs/<id>/A_by_regime.npz`.
4. Daftarkan checkpoint O3 seed 0–4 sebagai input CGS-H5-01: `experiments/handoff/module1_for_robustness.yaml`.

**Output:** 30 run + `configs/models/module1.yaml` (final) + file handoff.
**DoD:** [ ] semua run lulus · [ ] checkpoint untuk CGS tersedia ≤ H4 17.00.

## MLE-H4-02 · Baseline regime laten ala RCSGNet (disederhanakan)

| | |
|---|---|
| Input | Spesifikasi `docs/lit/rcsgnet.md` (RL-H1-02) |
| Tujuan | Pesaing *head-to-head* RQ1: graph berarah dikondisikan **state laten dari harga**, tanpa iklim |

**Spesifikasi `src/renaro/baselines/latent_regime.py`**
1. Backbone = sama dengan Modul 1 (encoder GRU + head).
2. **Encoder konteks pasar**: GRU atas return harga semua node pada 20 hari terakhir → pooling → `π_t = softmax(K)` (K **[usulan default: 3]**, sesuaikan dengan full-text RCSGNet).
3. Per state `k`: logit adjacency berarah `Θ_k [N,N]` (+ `candidate_mask`) → `A_k = softmax_j(Θ_k)`.
4. `A_t = Σ_k π_{k,t} A_k` → agregasi seperti Modul 1 (tanpa dimensi jeda, atau L = 1).
5. Regularisasi entropi `π` agar state tidak runtuh ke satu.
6. Run: 3 origin × 5 seed. Catat di laporan: "ala RCSGNet, disederhanakan, bukan reproduksi".

## MLE-H4-03 · Baseline lag ala MillGNN (disederhanakan)

**Spesifikasi `src/renaro/baselines/lag_graph.py`**
- = Modul 1 **tanpa** input iklim `e_j` (bobot hanya bergantung pada `h_i, h_j, s_ij, ℓ`, artinya berubah per jendela input, bukan per kondisi eksogen) + bias *decay* `−λ·ℓ` pada skor (λ dipelajari).
- Run: 3 origin × 5 seed. Selisih Modul 1 vs baseline ini = efek **pengondisian iklim** pada lag graph.

**DoD H4-02/03:** [ ] split identik dengan Modul 1 · [ ] hasil validasi masuk `registry.csv`.

---

## MLE-H5-01 · Modul 2–3: jalur stabil/adaptif + reliability gate

**Rumus (brief §5):** $z_t = g_t \odot H^{\text{adapt}}_t + (1-g_t)\odot H^{\text{stable}}_t$

**Spesifikasi `src/renaro/models/module23.py`**
1. `H_adapt` = keluaran agregasi Modul 1 (`m_i`).
2. `H_stable` = agregasi atas graph **statis** yang dipelajari (satu `A_static` per node tujuan, tanpa iklim, regularisasi L2 lebih kuat) atau prior BPS ternormalisasi.
3. Gate `g_t,i = σ(MLP([shock_i, rel_i, shift_i]))` dengan input yang **tersedia pada t**:
   - `shock_i`: `extreme_5d` dan `dry_spell_days` di asal (agregat), |RONI|;
   - `rel_i`: entropi `A_t[i]` dan jarak `A_t[i]` dari rata-rata latihnya;
   - `shift_i`: z-score mean/std jendela input vs statistik latih.
4. Head menerima `[h_i, z_i, kalender]`.
5. Run: 3 origin × 5 seed.

## MLE-H5-02 · Ablation (validasi)

| Varian | Perubahan |
|---|---|
| `full` | Modul 1–3 |
| `no_climate` | `e_j = 0` dan fitur shock iklim gate = 0 |
| `no_lag` | L = 1 (tanpa distribusi jeda) |
| `no_gate` | `g = 1` (hanya adaptif) |
| `no_calendar` | fitur kalender dibuang di semua bagian |

Run: 5 varian × 3 origin × 5 seed. **Output:** `reports/ablation/ablation_val.csv` (`variant, origin, horizon, seed, regime, mae, rmse, smape`) + `ablation_summary.md` (rata-rata ± std, Δ vs `full`, per regime).

**DoD:** [ ] semua varian memakai konfigurasi `full` selain komponen yang dibuang.

## MLE-H5-03 · Refit konfigurasi holdout + `predict.py` + manifest beku

| | |
|---|---|
| Waktu | H5 (antrean refit dimulai paling lambat 12.00) |
| Mode | PARALEL → prasyarat ALL-H5-01 (Gate 2) |
| Handoff | CGS-H6-01 |

**Langkah**
1. Untuk setiap model wajib (seasonal naive, LightGBM (c), GWN, MTGNN, ala RCSGNet, ala MillGNN, Modul 1, Modul 1–3) × 5 seed: latih dengan origin `HOLDOUT` (latih ≤ 2025-12-31, val 2026-01-01 … 2026-05-31), konfigurasi **sama** dengan validasi.
2. `scripts/predict.py --manifest frozen/manifest.yaml --context data/processed/dataset_v1 --holdout <path_panel_holdout> --out <dir>`:
   - menyambung jendela input dari akhir dataset v1 ke periode holdout;
   - menulis `preds_<model>_s<seed>.parquet` per model;
   - tidak melakukan pelatihan apa pun.
3. **Uji kering** `predict.py` memakai panel "holdout palsu" = periode uji O3 (bukan holdout asli). Output harus identik dengan prediksi run O3 bila konteksnya sama.
4. Tulis `frozen/manifest.yaml`:
   ```yaml
   freeze_commit: <sha>
   dataset: {path: data/processed/dataset_v1, content_hash: <...>}
   protocol: protocol-v1
   models:
     - name: module1
       config: configs/models/module1.yaml
       seeds: [0,1,2,3,4]
       checkpoints: [experiments/runs/<id_s0>/ckpt.pt, ...]
       sha256: [...]
     - ...
   best_baseline_on_validation: <nama>   # ditetapkan SEBELUM holdout dibuka, dipakai untuk uji DM
   excluded: []                         # model yang tidak beku
   ```

**DoD:** [ ] uji kering lolos · [ ] manifest lengkap dengan checksum · [ ] `best_baseline_on_validation` terisi.

## MLE-H5-04 · Modul 4 *(stretch)*: robustness objective
Hanya bila MLE-H5-01..03 selesai sebelum 14.00.
- Penalti sensitivitas perturbasi graph: `‖f(X, A) − f(X, Ã)‖` dengan `Ã` = perturbasi acak `candidate_mask` per batch.
- Risiko lintas-regime: varians loss antar **kelompok yang dibentuk dari fitur yang tersedia pada t** (mis. kuantil anomali hujan asal). **Jangan** memakai `regime_labels.csv` (hanya evaluasi).
- Regularisasi prior lunak: `λ‖A ⊙ (1 − M_bps)‖₁`.
Bila tidak selesai: pindah ke Sprint 2, catat di laporan.

---

## MLE-H6-01 · Analisis holdout (lead; bersama CGS dan RL)

| | |
|---|---|
| Waktu | H6 11.00–15.00 |
| Mode | **SEKUENSIAL**: menunggu prediksi holdout dari CGS-H6-01 |
| Input | `reports/holdout/predictions/`, label regime holdout (CGS), hasil validasi |
| Handoff | RL-H7-01, ALL-H6-01 |

**Langkah**
1. Hitung metrik per model × seed × horizon × regime pada holdout.
2. **Worst-regime error**, **perubahan error OOD** (holdout El Niño vs normal validasi), **stabilitas 5 seed** (std).
3. **DM** setiap model vs `best_baseline_on_validation` (dari manifest, bukan dipilih ulang).
4. Tabel & figur:
   - `table_main.md`: model × {MAE, RMSE, sMAPE, worst-regime, Δ OOD, std seed, DM p} (validasi rata-rata 3 origin + holdout).
   - `fig_error_timeline.png`: error harian rata-rata lintas provinsi dengan arsir regime.
   - `fig_per_regime.png`: MAE per regime per model.
   - `fig_A_dry_vs_normal.png`: `A` Modul 1 rata-rata saat asal kering vs normal (validasi), dengan catatan "dependensi prediktif, bukan arus pasokan".
   - Gabungkan kurva robustness dari CGS-H5-01.
5. Tulis interpretasi singkat untuk setiap RQ di `reports/holdout/findings.md` (termasuk hasil negatif).

**DoD:** [ ] setiap angka bisa dilacak ke file prediksi · [ ] MDE menerima daftar angka untuk QA (MDE-H6-01).

## MLE-H7-01 · Paket kode reproducible

**Isi `release/code/`** (atau tag `sprint1-final` di repo):
1. `README.md`: instalasi env (lockfile), urutan perintah reproduksi.
2. `scripts/reproduce_sprint1.ps1` (dan `.sh`): `make_dataset` → RQ0 → semua model per origin → ablation → (holdout, hanya bila holdout tersedia).
3. Semua `configs/`, `frozen/manifest.yaml`, seed.
4. Checkpoint: internal (drive tim), dirujuk dengan checksum. Tidak dirilis publik bila memuat informasi dari data PIHPS yang tidak boleh diredistribusi (keputusan RL).
5. `pytest` hijau dari clone bersih.

**DoD:** [ ] orang lain (MDE) bisa menjalankan RQ0 dari clone bersih dan mendapat angka yang sama (toleransi seed).
