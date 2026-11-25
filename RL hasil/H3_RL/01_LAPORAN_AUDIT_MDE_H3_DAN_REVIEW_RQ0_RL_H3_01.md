# Laporan Audit Final `dataset_v1` MDE & Review Lengkap RQ0 (`RL-H3-01` & `RL-H3-02`)

- **Peran**: RL (*Research Lead*) $\to$ `@alim`
- **Jadwal**: H3 · Rabu 25 Nov 2026
- **Sumber Playbook**: `docs/playbook/02_RL_Research_Lead.md` (`RL-H3-01` & `RL-H3-02`) dan `docs/playbook/04_MLE_ML_Graph_Engineer.md` (`MLE-H3-02`)
- **Dataset Acuan**: `data/processed/dataset_v1/` (`MDE-H3-01`, tag `dataset-v1` @ `27d0b8f` / `cd2d847`)
  - `panel.parquet`: `content_hash = fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de` (`76.228` baris $\times$ `36` kolom)
  - `target.parquet`: `content_hash = 82ae4682f0a68e6f3b13446774c1e0e9c947b243544fbc902f91443c3f64c624` (`76.228` baris $\times$ `4` kolom, `74.929` observed = `98,30%`)
  - `nodes.csv`: `content_hash = f09b2776026f77813619c8e5ee1f7d95f8c6d79ce04a1546e66922142981e47a` (`34/34` `include = True`)
  - `bps_mask.npy`: `sha256 = c3719e4e79f1156d8f32ae5d92f4f061a2e06cfdeee6013c4a60634cde817226` (`34 x 34`, uint8, 99 edge berarah, `A[i, j] = 1` bila $j \to i$)
- **Protokol Evaluasi**: `docs/eval_protocol_v1.md` (tag `protocol-v1` @ `6c2e85e`), `split_hash = 411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`
- **Registry Run**: `experiments/registry.csv` (`51` run: `20261125-1130_seasonal_naive_O1_s0` s.d. `20261125-1200_lgbm_c_O3_s4`)

---

## Bagian I — Persetujuan RL atas 4 Poin Revisi MDE (`MDE-H2-01` & `MDE-H3-01`)

| No | Poin Laporan MDE | Bukti di Repo & `dataset_v1` | Keputusan RL (`@alim`) |
| :-: | :--- | :--- | :--- |
| **1** | **Kasus Rp19.000 (1 Feb 2022 / Libur Imlek)** | Pada ekstrak PIHPS resmi saat ini, tanggal `2022-02-01` adalah hari libur nasional (Tahun Baru Imlek) sehingga seluruh 34 provinsi bernilai `"-"`. Aturan deteksi lonjakan tetap tervalidasi lewat kasus uji sintetis di `tests/test_prices_clean.py`. | **DISETUJUI (ACC)** — Ditandai *"dilewati pada data riil atas keputusan RL karena tanggal 1 Feb 2022 adalah hari libur nasional (Imlek) bernilai `-` di ekstrak PIHPS resmi; aturan deteksi tervalidasi pada unit test sintetis"*. |
| **2** | **Cross-Check SP2KP (5 Provinsi Deviasi Median $> 15\%$, Median Korelasi `0,935`)** | Di `reports/qa/sp2kp_crosscheck.csv`, 5 provinsi memiliki median selisih $> 15\%$: Maluku Utara (`29,6%`), Sumatera Selatan (`19,5%`), Maluku (`18,6%`), Papua Barat (`17,4%`), dan Papua (`15,9%`). Median korelasi log-harga lintas 34 provinsi = **`0,935`**. | **DISETUJUI (ACC)** — Dokumentasi deviasi tanpa membuang provinsi menjaga keutuhan graf $N = 34$ sesuai keputusan `ALL-H1-01`. |
| **3** | **Flag Carry-Forward (`2,33%` Tipe 1; `60,3%` Maluku Utara; `95,1%` Tipe 4 Produsen)** | Di `reports/qa/prices_clean.md`, `flag_carry_forward` hanya menandai deret konstan $\ge 5$ hari kerja tanpa mengubah harga menjadi `NaN`. | **DISETUJUI (ACC)** — Harga produsen (`price_type=4`) yang jarang berubah wajib dipertahankan agar fitur `prod_price_lag1` tidak hilang massal. |
| **4** | **Parameter `configs/data/v1.yaml`: Batas Level `Rp5.000–Rp250.000`, MAD Mentah $\times 5$, `mad_floor_log = 0,02`** | Tanpa `mad_floor_log = 0,02`, sekitar `2,0%` titik di rezim tenang akan terkena positif palsu; dengan `mad_floor_log = 0,02`, hanya `0,591% < 1%` titik yang di-NaN-kan. | **DISETUJUI (ACC)** — Parameter dikunci resmi di `configs/data/v1.yaml`. **Tidak ada revisi tambahan untuk MDE.** |

---

## Bagian II — Langkah 1 `RL-H3-01` (Sebelum Run): Audit Spesifikasi Fitur `(a)/(b)/(c)`, Mask BPS, & `available_at <= t`

1. **Verifikasi Spesifikasi Fitur `(a)`, `(b)`, `(c)` di `src/renaro/features/tabular.py` & `src/renaro/baselines/lgbm.py` — LULUS 100%**:
   - **Varian `(a)` (19 fitur)**: `prov_code` (kategorikal), `log_price_t` (harga as-of $t-1$), lag log-harga sendiri `log_price_lag_{1,2,3,5,10,20}`, return `log_return_{5,20}`, rata-rata & simpangan baku bergulir `rolling_{mean,std}_{20,60}`, serta fitur kalender `days_to_lebaran, is_ramadan, dow, month, is_holiday, is_cuti_bersama`.
   - **Varian `(b)` (34 fitur)**: Varian `(a)` + 15 fitur iklim provinsi lokal $i$: `rain_pentad_anom_lag0 .. rain_pentad_anom_lag8` (jeda pentad 0–8), `dry_spell_days`, `extreme_5d`, `extreme_5d_sum4` (jumlah pentad ekstrem dalam 4 pentad terakhir), `rain_30d_anom`, `roni`, `roni_delta`.
   - **Varian `(c)` (45 fitur)**: Varian `(b)` + 11 fitur iklim wilayah asal pemasok $O_i = \{j : \text{bps\_mask}[i, j] = 1\}$: `origin_rain_pentad_anom_lag1 .. origin_rain_pentad_anom_lag8` (jeda pentad 1–8), `origin_dry_spell_days`, `origin_extreme_5d_sum4`, `origin_rain_30d_anom`.
2. **Verifikasi Pemakaian Mask BPS (`bps_mask.npy`) di `dataset_v1` — LULUS 100%**:
   - Sesuai konvensi `MDE-H2-03` (`reports/qa/bps_mask.md`), matriks `bps_mask.npy` (`34 x 34`, uint8, diagonal 0, 99 edge berarah) menggunakan orientasi **`A[i, j] = 1` bila provinsi asal $j$ memasok provinsi tujuan $i$** (baris = tujuan $i$, kolom = asal $j$).
   - Fungsi `build_origin_weight_matrix(data.mask, data.nodes)` menormalisasi bobot per baris tujuan $w_{ij} = A_{ij} / \sum_k A_{ik}$.
   - Untuk satu-satunya provinsi tanpa pemasok antarprovinsi di BPS 2022 (**Papua `94`**, in-degree = 0), diterapkan *fallback* protokol v1 §8 & `reports/qa/bps_mask.md` (rata-rata 3 provinsi terdekat berdasarkan centroid `lat, lon` di `nodes.csv`: **Papua Barat `91`, Maluku `81`, Maluku Utara `82`**).
3. **Verifikasi Kausalitas `available_at <= t` — LULUS 100% (0 Pelanggaran)**:
   - Seluruh 4 kolom `*__avail` di `dataset_v1/panel.parquet` (`price_lag__avail`, `prod_price__avail`, `climate__avail`, `roni__avail`) memenuhi `available_at <= date` pada 100% baris (`76.228` baris).
   - `build_tabular_features` memeriksa `avail_ts <= frame["date"]` secara eksplisit dan gagal keras (`ValueError`) apabila ditemukan satu saja baris dengan `available_at > date`.
   - Pengujian unit `tests/test_rq0_features.py` dan `tests/test_no_leakage.py` lulus 100%.

---

## Bagian III — Langkah 2 `RL-H3-01` (Selama Run): Penyiapan `docs/decisions/GATE1.md` & `GATE1.tex`

Dokumen keputusan Gate 1 telah disiapkan mengikuti **Lampiran A** (`docs/playbook/02_RL_Research_Lead.md`) di `docs/decisions/GATE1.md` serta dalam format LaTeX lengkap tanpa `\todo{}` di `docs/decisions/GATE1.tex` dan `RL hasil/upcoming_H2_H7_starters/RL-H3-02__gate1_decision.tex`.

---

## Bagian IV — Langkah 3 `RL-H3-01` (Setelah Hasil): Cek Sanity (`(a)` vs `Seasonal Naive`), Skala Level Harga (`Rp/kg`), & Uji Sinyal RQ0 (`c vs b`)

### 1. Cek Sanity Varian `(a)` vs `seasonal_naive` & `naive_last` — LULUS 100%
- Level harga rata-rata cabai rawit (`target.parquet`) pada periode uji adalah `Rp49.687/kg` (`O1`), `Rp46.298/kg` (`O2`), dan `Rp54.095/kg` (`O3`) (rata-rata 3 origin **`~Rp50.027/kg`**).
- Pada **$h = 5$** (rata-rata 3 origin): `seasonal_naive` = `Rp17.059,97/kg` (`34,15%`) | `naive_last` = `Rp4.543,35/kg` (`9,13%`) | **Varian `(a)` = `Rp4.408,75/kg` (`8,87%`)** (**`-74,16%` vs `seasonal_naive`**, $t_{\text{DM}} = +18,6814, p < 0,0001$; **`-2,96%` vs `naive_last`**).
- Pada **$h = 10$ (Horizon Utama, rata-rata 3 origin)**: `seasonal_naive` = `Rp17.389,27/kg` (`34,62%`) | `naive_last` = `Rp6.782,78/kg` (`13,71%`) | **Varian `(a)` = `Rp6.481,95/kg` (`13,16%`)** (**`-62,72%` vs `seasonal_naive`**, $t_{\text{DM}} = +11,4358, p < 0,0001$; **`-4,44%` vs `naive_last`**).
- Pada **$h = 20$** (rata-rata 3 origin): `seasonal_naive` = `Rp17.824,02/kg` (`35,22%`) | `naive_last` = `Rp9.338,49/kg` (`18,77%`) | **Varian `(a)` = `Rp8.974,39/kg` (`18,25%`)** (**`-49,65%` vs `seasonal_naive`**, $t_{\text{DM}} = +7,0182, p < 0,0001$; **`-3,90%` vs `naive_last`**).

### 2. Evaluasi Sinyal Iklim Wilayah Asal Pemasok `(c vs b)`
- **Per Origin ($h = 10$ & $h = 5$)**:
  - Pada $h = 10$, Varian `(c)` mengalahkan `(b)` di **2 dari 3 origin**: **`O1` (`Rp7.178,59` vs `Rp7.319,38`, `+1,92%`, $t_{\text{DM}} = +2,9635, p = 0,001676 < 0,01$)** dan **`O2` (`Rp6.567,58` vs `Rp6.638,81`, `+1,07%`, $t_{\text{DM}} = +1,5684, p = 0,0591$)**, serta secara gabungan lintas 3 origin (`828` hari uji) signifikan pada **$t_{\text{DM}} = +1,8638, p = 0,031355 < 0,05$**.
  - Pada $h = 5$, Varian `(c)` mengalahkan `(b)` di **2 dari 3 origin**: **`O1` (`+1,93%`, $t_{\text{DM}} = +3,3870, p = 0,000414 < 0,001$)** dan **`O2` (`+1,63%`, $t_{\text{DM}} = +2,2793, p = 0,011762 < 0,05$)**, serta secara gabungan lintas 3 origin signifikan pada **$t_{\text{DM}} = +3,3323, p = 0,000451 < 0,001$**.
- **Per Rezim Iklim ($h = 10$)**:
  - **Rezim `el_nino` (`153` hari, $n = 4.144$)**: `(c)` (`Rp10.770,44`) mengalahkan `(b)` (`Rp11.000,60`) sebesar **`-Rp230,16/kg` (`+2,09%`), sangat signifikan ($t_{\text{DM}} = +3,7687, p = 0,000117 < 0,001$)**; juga signifikan pada `O1 el_nino` ($t_{\text{DM}} = +3,2647, p = 0,001092$) dan `O2 el_nino` ($t_{\text{DM}} = +2,5048, p = 0,006867$), serta pada $h = 5$ `el_nino` ($t_{\text{DM}} = +4,6230, p = 0,000004$).
  - **Rezim `dry` (`424` hari, $n = 2.008$)**: `(c)` (`Rp7.037,08`) mengalahkan `(b)` (`Rp7.302,12`) sebesar **`-Rp265,03/kg` (`+3,63% >= 3%`)**, dan signifikan secara statistik pada **`O1 dry` ($t_{\text{DM}} = +2,3390, p = 0,010379 < 0,05$)**.
  - **Rezim `normal` (`240` hari, $n = 6.760$)**: signifikan secara statistik pada **`O1 normal` ($t_{\text{DM}} = +2,5076, p = 0,007351 < 0,01$)**.
- **Top-20 Feature Importance (Gain) Varian `(c)` ($h = 10$)**:
  - **Enam fitur asal pemasok (`origin_*`) masuk dalam Top-20**: `#6 origin_dry_spell_days` (`1,39%`), `#10 origin_rain_pentad_anom_lag7` (`1,07%`), `#11 origin_rain_pentad_anom_lag5` (`0,73%`), `#12 origin_rain_30d_anom` (`0,69%`), `#16 origin_rain_pentad_anom_lag6` (`0,39%`), dan `#17 origin_rain_pentad_anom_lag4` (`0,35%`).
