# Caption Figur Uji Recovery Sintetis (`RL-H5-01`)

- **Peran & Kurator**: RL (*Research Lead*) `@alim`
- **Tanggal**: Jumat, 27 November 2026 (H5)
- **Sumber Data (`MLE-H3-01` / `CGS-H3-01`)**:
  - `reports/synth/recovery_metrics.csv` (30 baris: 3 varian model × 2 rezim × 5 seed `0..4`)
  - `reports/synth/lag_true_vs_hat.parquet` (2.970 baris: 99 edge × 5 seed × 3 varian × 2 rezim)
  - `reports/synth/recovery_summary.md` & `src/renaro/synth/generator.py` (`SynthConfig(seed=0, mode="conditioned")`, `configs/synth/default.yaml`, `split_hash = 8a551a68b996326eef075e5c44eb22bcd3f4cb0662d82f4ba40447df68b26c6d`)
- **Skrip Generator Figur**: `scripts/plot_synth_recovery.py`
- **Ambang Protokol Evaluasi v1.0 (`docs/eval_protocol_v1.md` §5.5 & `reports/synth/recovery_summary.md`)**:
  - Korelasi peringkat Spearman multi-edge **$> 0{,}70$** (1-edge $> 0{,}80$)
  - MAE jeda **$\le 1{,}0$ pentad**
  - AUROC pemulihan edge **$> 0{,}85$**
  - Kontrol negatif (`module1_no_climate` dan `module1_unconditioned`): **$|\Delta\text{lag}| < 0{,}25$** (mendekati 0)

---

## Ringkasan Evaluasi Ambang Protokol v1 (`MLE-H3-01`, 5 Seed `0..4`)

| Metrik Evaluasi | Ambang Protokol v1 | Nilai Aktual (`mean ± sd`, 5 seed) | Status | Catatan Jujur / Nuansa |
| :--- | :---: | :---: | :---: | :--- |
| **Spearman agregat (`normal + dry`)** | $> 0{,}70$ | **`0,745 ± 0,119`** (`normal: 0,854 ± 0,012`; `dry: 0,636 ± 0,045`) | **LULUS (Agregat)** | Sub-rezim `dry-only` di bawah `0,70` pada 4/5 seed (hanya seed 3 $= 0{,}704$); wajib diungkap eksplisit. |
| **MAE jeda $\arg\max_\ell$ (`normal + dry`)** | $\le 1{,}0$ pentad | **`0,526 ± 0,131` pentad** (`normal: 0,408 ± 0,037`; `dry: 0,644 ± 0,046`) | **LULUS** | Lulus ambang $\le 1{,}0$ pentad baik secara agregat maupun pada masing-masing rezim. |
| **Akurasi $\arg\max_\ell$ tepat (99 edge)** | $\ge 0{,}80$ *(target starter)* | **`0,721 ± 0,113`** (`normal: 0,826 ± 0,019`; `dry: 0,616 ± 0,031`) | **LULUS di `normal`; Parsial di `dry`** | Rezim `normal` lulus $\ge 0{,}80$; penurunan di `dry` terkonsentrasi pada `lag_true = 3` (tertarik ke `4–5`) dan `lag_true = 6` (tertarik ke `4`). |
| **AUROC pemulihan edge** | $> 0{,}85$ | **`1,000 ± 0,000`** (`normal: 1,000`; `dry: 1,000`) | **LULUS** | Dievaluasi dalam kondisi *candidate prior mask* BPS 2022 aktif (`cand = G`); kekuatan bobot relatif antar-99 edge aktif mencapai Pearson $r = 0{,}980$ (`normal`) dan $0{,}960$ (`dry`). |
| **Pergeseran jeda $\Delta\text{lag}$ (`dry - normal`)** | Arah positif menuju $+2{,}0$ | **`+0,813 ± 0,053` pentad** | **ARAH BENAR (Teredam)** | Secara konsisten positif di 5/5 seed (`+0,725` s.d. `+0,866`), namun lebih kecil dari pergeseran DGP $+2{,}0$ akibat penyebaran massa perhatian pada beberapa bin lag. |
| **Kontrol tanpa iklim (`module1_no_climate`, $e_j = 0$)** | $|\Delta\text{lag}| < 0{,}25$ ($\approx 0$) | **`+0,011 ± 0,007` pentad** | **LULUS (Bersih)** | Tidak ada pergeseran jeda palsu ketika input iklim dinolkan saat inferensi. |
| **Kontrol `unconditioned` (DGP statis)** | $|\Delta\text{lag}| < 0{,}25$ ($\approx 0$) | **`-0,041 ± 0,013` pentad** | **LULUS (Bersih)** | Tidak ada pergeseran jeda palsu ketika DGP sintetis tidak memiliki pergeseran jeda. |
| **Rata-rata kontrol negatif $|\Delta\text{lag}_{\text{ctrl}}|$** | $< 0{,}25$ | **`0,026` pentad** | **LULUS** | Memenuhi syarat uji kontrol negatif protokol v1. |

---

## Figur 1 — `reports/figures/synth_lag_recovery.png` (dan `synth_lag_recovery.pdf`)

**Judul**: Pemulihan Jeda Terkondisi Iklim oleh Modul 1 pada Data Sintetis (`default` vs Kontrol Negatif, 5 Seed)

**Caption**:
> **Gambar 1.** Evaluasi pemulihan jeda transmisi terkondisi iklim oleh Modul 1 pada set uji sintetis `data/synth/default` (`module1_default`, $N = 34$ provinsi, $99$ edge berarah dari prior BPS 2022, rata-rata 5 random seed `0..4`, total $n = 495$ pasangan edge-seed per rezim), dibandingkan dengan dua kontrol negatif (`module1_no_climate` dengan fitur iklim $e_j = 0$ saat inferensi dan `module1_unconditioned` yang dilatih pada DGP sintetis tanpa pergeseran jeda). **(a–b)** Sumbu horizontal menunjukkan jeda benar yang ditanam pada DGP ($\ell_{\text{true}}$, dalam satuan pentad; `1–4` pada rezim `normal` dan bergeser $+2$ menjadi `3–6` pada rezim `dry`), sedangkan sumbu vertikal menunjukkan jeda terpelajari $\hat{\ell} = \arg\max_\ell \bar{A}_{ij}^{(\ell)}$; ukuran gelembung dan angka di dalamnya menyatakan jumlah pasangan edge-seed pada sel $(\ell_{\text{true}}, \hat{\ell})$, kurva hitam menunjukkan rata-rata jeda ekspektasi $\mathbb{E}[\ell] \pm \text{sd}$ per bin, garis putus-putus adalah identitas $y = x$, dan pita abu-abu adalah toleransi $\pm 1$ pentad. **(c)** Perbandingan pergeseran jeda rata-rata $\Delta\text{lag} = \mathbb{E}[\ell_{\text{dry}}] - \mathbb{E}[\ell_{\text{normal}}]$ lintas 5 seed (batang `mean ± sd` beserta titik 5 seed individual) terhadap target DGP $+2{,}0$ pentad (garis merah putus-putus) dan zona lulus kontrol negatif $|\Delta\text{lag}| < 0{,}25$ (pita abu-abu). **Evaluasi terhadap ambang protokol v1 §5.5** (Spearman multi-edge $> 0{,}70$, MAE lag $\le 1{,}0$ pentad, AUROC $> 0{,}85$, kontrol $|\Delta\text{lag}| < 0{,}25$): Modul 1 **LULUS secara agregat lintas 5 seed** dengan Spearman $= 0{,}745 \pm 0{,}119$, MAE lag $= 0{,}526 \pm 0{,}131$ pentad, AUROC $= 1{,}000$, dan rata-rata kontrol $|\Delta\text{lag}_{\text{ctrl}}| = 0{,}026$ (`no_climate`: $+0{,}011 \pm 0{,}007$; `unconditioned`: $-0{,}041 \pm 0{,}013$). Secara terpisah per rezim, performa sangat kuat pada rezim `normal` (akurasi $\arg\max = 0{,}826 \pm 0{,}019$, MAE $= 0{,}408 \pm 0{,}037$, Spearman $= 0{,}854 \pm 0{,}012$), namun secara transparan dicatat bahwa pada sub-rezim **`dry-only`** korelasi Spearman berada di bawah ambang (`0,636 ± 0,045`; hanya seed 3 $= 0{,}704$ yang melewati `0,70`, akurasi $= 0{,}616 \pm 0{,}031$, MAE $= 0{,}644 \pm 0{,}046$) dan magnitudo pergeseran terpelajari ($\Delta\text{lag} = +0{,}813 \pm 0{,}053$) teredam dibanding pergeseran DGP $+2{,}0$.

---

## Figur 2 — `reports/figures/synth_edge_heatmap.png` (dan `synth_edge_heatmap.pdf`)

**Judul**: Heatmap Matriks Dependensi $34 \times 34$: $A$ Benar DGP vs $A$ Terpelajari Modul 1 pada Rezim Normal dan Kering

**Caption**:
> **Gambar 2.** Perbandingan matriks dependensi terarah $34 \times 34$ antara matriks bobot benar DGP sintetis ($A_{\text{true}}$, direkonstruksi deterministik dari `src/renaro/synth/generator.py`, `seed = 0`, `mode = conditioned`) dan total massa perhatian terpelajari Modul 1 ($A_{\text{learned}}[i,j] = \sum_{\ell=1}^{8} \bar{A}_{ij}^{(\ell)}$, rata-rata 5 seed `0..4` dari `reports/synth/lag_true_vs_hat.parquet`) untuk dua rezim iklim sintetis: **(a–b)** rezim `normal` dan **(c–d)** rezim `kering` (`dry`, penguatan bobot DGP $\kappa = 1{,}5\times$). Urutan 34 baris dan kolom mengikuti kode provinsi BPS resmi (`src/renaro/contract.py`, `11` Aceh hingga `94` Papua) dengan garis putus-putus memisahkan 6 gugus kepulauan (Sumatera, Jawa, Bali–Nusa Tenggara, Kalimantan, Sulawesi, Maluku–Papua). Konvensi arah adalah **$A[i, j]$ menyatakan pengaruh dari provinsi asal $j$ (kolom) ke provinsi tujuan $i$ (baris), $j \to i$**; entri diagonal $i = j$ (*self-loop*) sengaja dikosongkan (abu-abu), dan baris `94` (Papua) kosong karena memiliki `in_degree = 0` pada prior BPS 2022. Keempat panel menggunakan **skala warna seragam** (*PowerNorm* $\gamma = 0{,}5$, rentang $[0{,}00; 0{,}70]$) agar perbedaan skala absolut antara bobot DGP ($0{,}019$–$0{,}278$ pada `normal`; $0{,}028$–$0{,}416$ pada `dry`) dan massa perhatian softmax Modul 1 ($0{,}050$–$0{,}678$) tampak transparan. **Evaluasi terhadap ambang protokol v1 §5.5**: pemisahan edge aktif vs non-edge mencapai **AUROC $= 1{,}000 > 0{,}85$ (LULUS)** pada kedua rezim — dengan catatan jujur bahwa `AUROC = 1,000` dievaluasi dengan *candidate prior mask* BPS aktif (`cand = G`) — sementara kesesuaian pola bobot relatif pada $99$ edge aktif sangat tinggi: Pearson $r = 0{,}980$ (Spearman $\rho = 0{,}945$; ternormalisasi baris $r_{\text{row}} = 0{,}990$) pada rezim `normal` dan Pearson $r = 0{,}960$ (Spearman $\rho = 0{,}915$; $r_{\text{row}} = 0{,}986$) pada rezim `dry`. Sesuai batas klaim proyek, matriks $A$ ini merepresentasikan **dependensi prediktif harga antarprovinsi**, **bukan** identifikasi kausal maupun pengukuran volume arus pasokan fisik.
