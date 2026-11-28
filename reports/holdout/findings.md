# Findings holdout — MLE-H6-01

- **Sumber prediksi**: `reports/holdout/predictions/` (50 file, 10 model × 5 seed, 8.772 baris/file; commit `ba5cb65`).
- **Label regime**: `reports/holdout/regime_labels_holdout_panel.csv` (3.604 baris panel; `dry` 1.721, `normal` 1.185, `extreme_wet` 13 per horizon).
- **Baseline pembanding**: `best_baseline_on_validation = lgbm_c` dari `frozen/manifest.yaml` (dipilih sebelum holdout dibuka, bukan dipilih ulang).
- **Metrik utama**: MAE (Rp/kg) pada `y_mask=True` dan `y_pred` finite; `seasonal_naive` 75 NaN/file dikecualikan.
- **Tabel angka**: `reports/holdout/table_main.md`, `metrics_by_seed.csv`, `metrics_by_regime.csv`, `dm_tests.csv`.

## RQ0 — sinyal iklim wilayah asal (hasil H3, bukan holdout)

RQ0 sudah lulus Gate 1 pada `reports/rq0/rq0_summary.md`: varian `(c)` (harga + iklim lokal + iklim asal berbobot BPS) mengalahkan `(b)` pada `el_nino` gabungan ($t_{DM}=+3{,}77$, $p=0{,}000117$) dan `O1 dry` ($p=0{,}0104$), dengan penurunan MAE `dry` +3,63%. Sinyal melemah pada `la_nina` dan tidak universal. Holdout ini **tidak** mengulang RQ0; ia menguji konsekuensi RQ0 pada model beku.

## RQ1 — efektivitas Modul 1 pada holdout

Peringkat titik estimasi holdout (h=10, mean 5 seed):

| Model | Holdout MAE | vs `lgbm_c` | Val 3-origin | Δ holdout−val |
|---|---:|---:|---:|---:|
| `module1` | **7.452,6** ± 211,4 | **−1.348,0 (−15,3%)** | 6.249,0 | +1.203,6 |
| `module23` | 8.064,7 ± 467,2 | −735,9 (−8,4%) | 6.221,5 | +1.843,2 |
| `naive_last` | 8.198,4 ± 0,0 | −602,2 (−6,8%) | 6.169,3 | +2.029,0 |
| `lag_graph` | 8.592,5 ± 332,2 | −208,0 (−2,4%) | 5.995,0 | +2.597,5 |
| `lgbm_a` | 8.767,9 ± 39,0 | −32,6 (−0,4%) | 5.543,2 | +3.224,8 |
| `lgbm_c` (baseline) | 8.800,5 ± 71,9 | 0 | **5.481,2** | +3.319,3 |
| `gwn` | 8.870,0 ± 978,6 | +69,5 (+0,8%) | 6.532,2 | +2.337,8 |
| `latent_regime` | 9.142,8 ± 406,5 | +342,3 (+3,9%) | 5.947,8 | +3.195,1 |
| `mtgnn` | 9.512,2 ± 1.417,7 | +711,7 (+8,1%) | 6.433,2 | +3.079,0 |
| `seasonal_naive` | 13.957,2 ± 0,0 | +5.156,7 (+58,6%) | 22.033,2 | −8.076,1 |

**Hasil positif (titik estimasi).** `module1` adalah model dengan MAE holdout terendah, 15,3% lebih rendah dari `lgbm_c` dan 7,6% lebih rendah dari `module23`. Urutan validasi terbalik: `lgbm_c` terbaik di validasi (5.481) tetapi keempat terburuk di holdout (8.800). Degradasi holdout `module1` (+1.204) jauh lebih kecil dari `lgbm_c` (+3.319), `mtgnn` (+3.079), dan `latent_regime` (+3.195).

**Hasil negatif / kualifikasi (penting).** DM satu sisi vs `lgbm_c` pada h=10 menghasilkan **median p = 0,074** untuk `module1`; **0/5 seed** mencapai p < 0,05. Untuk `module23` median p = 0,160; `naive_last` 0,222. Tidak ada model yang secara statistik signifikan mengalahkan `lgbm_c` pada holdout ini. Jadi RQ1 hanya mendapat **dukungan arah**, bukan bukti signifikan. `seasonal_naive` tetap terburuk; `mtgnn` paling tidak stabil (sd 1.418).

Catatan: `lgbm_c` dipilih sebagai baseline dari validasi 3-origin; holdout memperlihatkan bahwa peringkat validasi tidak otomatis bertahan pada rezim kering. Ini temuan penting, bukan alasan memilih ulang baseline.

## RQ2 — worst-regime, OOD, dan stabilitas seed

| Model | Worst-regime (semua) | Worst-regime (n≥200) | Δ dry−normal | Δ extreme−normal | sd seed |
|---|---:|---:|---:|---:|---:|
| `module1` | 8.065,5 | 8.065,5 | +1.495,8 | +221,0 | 211,4 |
| `module23` | 9.505,9 | 8.843,0 | +1.924,5 | +2.587,4 | 467,2 |
| `naive_last` | 8.630,8 | 8.358,4 | +397,2 | +669,5 | 0,0 |
| `lgbm_c` | 9.973,4 | 9.973,4 | +2.885,2 | +2.540,5 | 71,9 |
| `gwn` | 10.114,1 | 9.879,8 | +2.489,9 | +2.724,2 | 978,6 |

- **Worst-regime**: `module1` punya worst-regime terendah di antara model non-naif (8.066 vs `lgbm_c` 9.973; `module23` 8.843 jika `extreme_wet` n=13 dikecualikan). Ini konsisten dengan tujuan reliability gating, tetapi belum signifikan secara DM.
- **Δ dry−normal**: semua model lebih buruk saat `dry`; `module1` +1.496, `lgbm_c` +2.885. Artinya keunggulan `module1` justru muncul pada kondisi kering holdout.
- **Δ extreme−normal**: hanya 13 observasi `extreme_wet` per horizon; sel ini terlalu kecil untuk klaim. Nilai besar (`module23` +2.587) tidak boleh ditafsirkan sebagai efek regime yang stabil.
- **Stabilitas 5 seed**: `module1` sd 211 (CV ~2,8%); `lgbm_c` sd 72 (CV ~0,8%); `module23` 467; `gwn` 979; `mtgnn` 1.418. `module1` lebih baik rata-rata tetapi kurang stabil dibanding `lgbm_c`; varians ini harus dilaporkan.
- **OOD El Niño tidak tersedia.** RONI resmi tetap `neutral` sampai ASO 2026; label holdout `el_nino` = 0 hari. Rencana "holdout El Niño vs normal validasi" **tidak dapat dijalankan**; yang bisa dihitung adalah `dry` vs `normal` dan `extreme_wet` vs `normal` di dalam holdout. Ini keterbatasan data, bukan hasil negatif model.

## RQ3 — robustness prior graf (CGS-H5-01, validasi)

Kurva robustness CGS-H5-01 digabungkan di `reports/holdout/fig_robustness_combined.png`; angka lengkap di `reports/robustness/robustness_summary.md`.

- **Inferensi (tanpa retrain)**: MAE clean test h10 `module1` 7.819,27 ± 207,38; p=50 `module1` 7.852,12 (Δ +32,85). Kurva per regime ada di panel atas.
- **Retrain subset**: `module1` paling tahan terhadap rewire p50 (Δ +83,01; +1,06%) dan drop p50 (+23,28; +0,30%); `gwn` lebih sensitif (drop p50 +196,17; +2,29%; rewire p50 +106,26; +1,24%).
- **Joint shift p50**: `gwn` normal drop +440,33 (+5,22%) adalah degradasi terbesar; `module1` normal add +165,09 (+2,19%) dan dry add +40,61 (+0,64%). Secara umum `module1` lebih tahan daripada `gwn`, tetapi tetap ada degradasi; tidak ada klaim invariansi penuh.

## Kesimpulan dan batas klaim

1. **RQ1**: `module1` adalah kandidat terbaik pada holdout kering (MAE 7.453), tetapi DM vs `lgbm_c` tidak signifikan (median p 0,074; 0/5 seed < 0,05). Klaim yang benar: "arah positif, belum signifikan".
2. **RQ2**: worst-regime dan degradasi dry `module1` lebih rendah dari `lgbm_c`; `extreme_wet` (n=13) tidak cukup untuk klaim. Tidak ada bukti holdout El Niño karena label resmi netral.
3. **RQ3**: robustness `module1` lebih baik dari `gwn` pada perturbasi prior dan joint shift di validasi; holdout tidak menguji perturbasi graf (model beku dijalankan pada graf BPS).
4. **Hasil negatif yang wajib dilaporkan**: peringkat validasi tidak bertahan di holdout (`lgbm_c` turun); tidak ada signifikansi DM; `seasonal_naive` memiliki 75 NaN/file; `mtgnn` sangat tidak stabil; holdout didominasi `dry` (57,6%) dan tidak punya `el_nino`/`la_nina`.
5. **Batas**: label regime EVAL ONLY; `dry` bukan kausalitas; peta/angka holdout tidak boleh dipakai untuk memilih model atau mengubah manifest; perubahan apa pun setelah titik ini adalah post-hoc.

## Peta artefak

| Pertanyaan | Tabel/angka | Figur |
|---|---|---|
| RQ1 ranking, DM | `table_main.md`, `dm_tests.csv`, `dm_summary.csv` | `fig_error_timeline.png` |
| RQ2 per regime | `metrics_by_regime.csv`, `table_main.md` | `fig_per_regime.png` |
| RQ2 stabilitas seed | `metrics_overall.csv`, `metrics_by_seed.csv` | — |
| RQ2 attention asal dry vs normal | `attention_origin_dry_normal.csv`, `attention_origin_by_run.csv` | `fig_A_dry_vs_normal.png` |
| RQ3 robustness | `reports/robustness/robustness_summary.md` | `fig_robustness_combined.png` |
