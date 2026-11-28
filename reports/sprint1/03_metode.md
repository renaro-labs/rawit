# 3. Metode

> **Status Dokumen**: Pembaruan H6 (`ALL-H6-01`, pasca-pembekuan `gate2-freeze`) · **Peran**: RL (*Research Lead*, `@alim`) · **Tanggal**: Sabtu, 28 November 2026 (`H6`)  
> **Rujukan Teknis & Keputusan**: Brief v2 §5–§8, `docs/eval_protocol_v1.md` (tag `protocol-v1`), `docs/protocol_amendments.md` (`A1–A4`), `docs/decisions/GATE2.md` (tag `gate2-freeze`, commit `b0d0ff9`), `docs/protocol_audit.md` (`10/10` LULUS), `docs/data_contract.md`, `docs/playbook/04_MLE_ML_Graph_Engineer.md`, dan `configs/global.yaml`

---

## 3.1 Formulasi Masalah, Representasi Data, dan Aturan Ketersediaan (`available_at <= t`)

Jaringan pasar cabai merah keriting dimodelkan sebagai graf berarah multiregional dengan himpunan node $\mathcal{V} = \{1, \dots, N\}$ yang merepresentasikan **$N = 34$ provinsi** struktur lama Indonesia (`prov_code` BPS 2-digit terurut sesuai `src/renaro/contract.py`). Pada setiap tanggal keputusan hari kerja PIHPS $t \in \mathcal{T}$ (Senin–Jumat), setiap node $i \in \mathcal{V}$ mengamati histori jendela input sepanjang $W = 60$ hari kerja, $X_{i,t-W+1:t} \in \mathbb{R}^{W \times F}$, yang memuat fitur harga historis *as-of*, kalender hari raya/libur nasional, fitur iklim provinsi lokal, dan indeks ENSO makro RONI. Tugas peramalan multi-horizon adalah memprediksi harga pasar tradisional cabai merah keriting (`price_type = 1`) pada horizon $h \in \{5, 10, 20\}$ hari kerja ke depan (dengan **horizon utama $h = 10$**). Model dilatih pada skala logaritmik ($y_{i,t+h} = \log P_{i,t+h}$ atau *log-return* $\Delta \log P_{i,t+h} = \log P_{i,t+h} - \log P_{i,t}$ yang dikonversi kembali ke level harga $\hat{P}_{i,t+h} = \exp(\hat{y}_{i,t+h})$), dan seluruh metrik galat dihitung dalam satuan **Rp/kg** hanya pada pasangan $(i, t+h)$ yang memiliki `is_observed == True` (tanpa imputasi target).

Seluruh fitur dalam panel `data/processed/dataset_v1/panel.parquet` dibangun mengikuti kontrak data (`docs/data_contract.md`) dan tabel ketersediaan resmi (`reports/qa/availability.csv`, 7 keluarga fitur) dengan aturan emas anti-kebocoran waktu **`available_at <= t`** yang diverifikasi melalui `pd.merge_asof(..., direction="backward")`, uji otomatis `tests/test_no_leakage.py` (termasuk uji *truncation* identik bit-for-bit), serta reproduksi independen dari *clone* bersih oleh CGS pada `MDE-H5-01` (commit `6874c0b`, `REPRODUCED OK`, 52 tes lulus):

- **Harga PIHPS (`price`)**: aturan `next_workday` (`lag_days = 1`), sehingga harga observasi hari $t$ baru dipakai sebagai fitur pada hari kerja berikutnya (`price_lag1`, `price_logret5`, `price_logret20`, `price_logmean20`, `price_logstd20`).
- **Curah hujan CHIRPS v3 (`rain_daily_final` / `rain_pentad_final`)**: bobot luas kabupaten/kota untuk `2017–2024` dan bobot produksi cabai 2024 untuk `2025–2026` (`year_plus_1`), dengan aturan ketersediaan utama **Opsi B** (`pentad_end + 2 hari kalender`, `final_sat` sebagai proksi operasional *prelim*) serta uji sensitivitas **Opsi A** (`prelim_sat`, `lag_days = 5`).
- **Indeks ENSO RONI (`roni`, `roni_delta`)**: aturan `vintage_or_conservative_3m` (tanggal rilis vintage CPC NOAA atau awal bulan `center_month + 3`).
- **Kalender (`calendar`)**: `known_in_advance` (SKB 3 Menteri: `days_to_lebaran`, `is_ramadan`, `is_holiday`, `is_cuti_bersama`, `dow`, `month`).
- **Label Rezim (`regime_labels.csv`, `CGS-H2-04`)**: berstatus **EVAL ONLY** dan dilarang keras masuk ke `panel.parquet`, fitur model, maupun input gerbang.

---

## 3.2 Modul 1 (*Metode Inti*): *Climate-Conditioned Directed Lag Graph*

Inti metodologis penelitian ini (`src/renaro/models/module1.py`, Brief v2 §5) adalah mempelajari bobot perhatian spasial-temporal berarah $A^{(\ell)}_{ij,t}$ yang secara simultan menentukan **dari provinsi asal $j$ mana** dan **pada bin jeda $\ell$ mana** informasi prediktif diambil oleh provinsi tujuan $i$ pada waktu $t$, dengan pengondisian langsung pada kondisi iklim fisik yang teramati di provinsi asal ($c_{j,\le t}$):

$$A^{(\ell)}_{ij,t} = \operatorname{softmax}_{j,\ell}\!\Big[\phi_\theta\!\big(h_{i,\le t},\, h_{j,\le t},\, c_{j,\le t},\, s_{ij},\, \ell\big)\Big], \qquad \ell \in \{1, \dots, L\}.$$

Arsitektur Modul 1 tersusun atas enam komponen terpadu yang dirancang efisien untuk $N = 34$ node:

1. **Encoder Temporal Node Bersama (*Shared Temporal Backbone*)**:  
   Untuk memastikan perbandingan *head-to-head* yang adil terhadap seluruh baseline neural, setiap node $i$ dikodekan menggunakan GRU 1 lapis berdimensi tersembunyi $d_h = 64$ (opsi tuning validasi O1: $\{32, 64\}$) atas jendela input $W = 60$ hari kerja, menghasilkan representasi state akhir $h_{i,\le t} \in \mathbb{R}^{d_h}$ dan deret state per langkah $z_i(\tau) \in \mathbb{R}^{d_h}$ untuk $\tau \in [t-W+1, t]$.
2. **Encoder Iklim Wilayah Asal ($c_{j,\le t} \to e_{j,t}$)**:  
   Indikator iklim fisik di provinsi asal/pemasok $j$ pada **8 pentad terakhir** yang sudah tersedia pada tanggal keputusan $t$ (`rain_pentad_anom`, `dry_spell_days`, `extreme_5d`, `rain_30d_anom`, serta `roni`) dikodekan melalui jaringan MLP menjadi vektor konteks iklim asal $e_{j,t} = \mathrm{MLP}_{\text{clim}}(c_{j,\le t}) \in \mathbb{R}^{d_c}$.
3. **Representasi Berjeda per Bin Pentad ($z_j^{(\ell)}$) — Amandemen `A1` (`n_lags = 6` Data Riil vs 8 Bin Sintetis)**:  
   Karena data curah hujan harian CHIRPS v3 merupakan disagregasi dari pentad, dimensi jeda didiskretisasi pada resolusi pentad $\ell = 1, \dots, n_{\text{lags}}$ ($1$ bin $= 5$ hari kerja $\approx 1$ pentad). Untuk seluruh model graf berjeda pada data riil `dataset_v1` (`configs/models/{module1,lag_graph,module23,module4}.yaml` serta konfigurasi beku `configs/models/gate2/{module1,lag_graph,module23}.yaml`), jumlah bin jeda ditetapkan menjadi **`n_lags = 6`** (mencakup jendela historis hingga $30$ hari kerja) sesuai **Amandemen `A1`** (`docs/protocol_amendments.md`), berdasarkan hasil *tuning* validasi `O1` (`reports/mle/h4_module1_tuning.csv`) di mana `n_lags = 6` (`hidden=64, lr=0.001`) mengungguli 8 bin sekaligus menjaga konsumsi VRAM $< 3\text{ GB}$. Sebaliknya, pada generator dan uji pemulihan jeda data sintetis (`configs/synth/default.yaml`, §3.5), jumlah bin jeda dipertahankan sebanyak 8 bin agar selaras dengan DGP pergeseran jeda awal ($\ell_{\text{dry}} = \min(\ell_{\text{normal}} + 2, 8)$). Representasi state asal pada bin jeda ke-$\ell$ dihitung sebagai rata-rata state temporal pada jendela pentad ke-$\ell$ ke belakang:
   $$z_j^{(\ell)} = \frac{1}{|\mathcal{W}_\ell|} \sum_{\tau \in [t - 5\ell,\, t - 5\ell + 4]} z_j(\tau).$$
4. **Pemberi Skor Pasangan-Jeda ($\phi_\theta$) dan Fitur Edge Statis ($s_{ij}$)**:  
   Skor tak-ternormalisasi untuk pasangan berarah $(j \to i)$ pada jeda $\ell$ dihitung melalui:
   $$\phi_\theta\!\big(h_{i,\le t},\, h_{j,\le t},\, c_{j,\le t},\, s_{ij},\, \ell\big) = \mathrm{MLP}_\phi\!\Big(\big[h_{i,\le t} \,\|\, h_{j,\le t} \,\|\, e_{j,t} \,\|\, s_{ij} \,\|\, \mathrm{emb}(\ell)\big]\Big) \in \mathbb{R},$$
   di mana $s_{ij}$ memuat fitur edge statis (log jarak centroid antarprovinsi, bendera biner koridor perdagangan `bps_mask[i, j]`, dan pangsa BPS bila tersedia), sedangkan $\mathrm{emb}(\ell)$ adalah *embedding* bin jeda terpelajari.
5. **Pembatasan Kandidat (`candidate_mask`), Slot `null`, dan Normalisasi**:  
   Untuk setiap provinsi tujuan $i$, himpunan kandidat asal $j \in \mathcal{C}(i)$ dikendalikan oleh `candidate_mask` dengan dua varian utama pada eksperimen pengembangan: `bps` (mask koridor BPS Poldis 2022 `bps_mask.npy`) dan `none` (seluruh $N - 1$ provinsi lain tanpa prior perdagangan; pada pembekuan Gate 2, hanya `module1` prior `bps` yang dibekukan ke holdout, sedangkan `module1_none` dicatat sebagai `excluded` di `frozen/manifest.yaml` dan `docs/decisions/GATE2.md`). Selain itu, ditambahkan **satu opsi slot `null`** dengan skor terpelajari $\psi_{\text{null}}(h_{i,\le t})$ yang berpasangan dengan vektor pesan nol ($\mathbf{0}$), sehingga provinsi tujuan dapat secara adaptif memilih untuk tidak mengambil informasi spasial ketika sinyal dari provinsi lain sedang bising. Probabilitas perhatian $A^{(\ell)}_{ij,t}$ dan $A^{\text{null}}_{i,t}$ memenuhi $\sum_{j \in \mathcal{C}(i)} \sum_{\ell=1}^{n_{\text{lags}}} A^{(\ell)}_{ij,t} + A^{\text{null}}_{i,t} = 1$.
6. **Agregasi Pesan, Head Multi-Horizon, Regularisasi Entropi, dan Kompleksitas**:  
   Pesan spasial-temporal berjeda diagregasi menjadi:
   $$m_{i,t} = \sum_{j \in \mathcal{C}(i)} \sum_{\ell=1}^{n_{\text{lags}}} A^{(\ell)}_{ij,t}\, W_v\, z_j^{(\ell)},$$
   lalu digabungkan dengan state autoregresif lokal dan fitur kalender masa depan yang diketahui di muka ($\mathrm{cal}_{t+h}$) untuk menghasilkan prediksi seluruh horizon $h \in \{5, 10, 20\}$:
   $$\hat{y}_{i,t+h} = \mathrm{MLP}_{\text{head}}\!\big([h_{i,\le t} \,\|\, m_{i,t} \,\|\, \mathrm{cal}_{t+h}]\big).$$
   Fungsi objektif pelatihan adalah galat absolut (MAE) pada skala log-level atas observasi valid (`y_mask == True`) ditambah regularisasi entropi opsional $\lambda_H \cdot \frac{1}{N}\sum_{i=1}^N H(A_{i,\cdot,t})$. Pada skala $N = 34$ provinsi dan **`n_lags = 6`** bin jeda untuk data riil (`Amandemen A1`), ruang evaluasi skor $(i, j, \ell)$ berjumlah maksimal $34 \times 34 \times 6 = 6.936$ entri per langkah waktu (dibanding $9.248$ entri pada uji sintetis 8 bin), dengan kebutuhan memori GPU puncak $< 3\text{ GB}$ (terverifikasi aktual $\le 0{,}64\text{ GB}$ pada *batch* $64$).

---

## 3.3 Modul 2–3 (*Komponen Pendukung*): Jalur Stabil/Adaptif dan *Reliability Gate*

Hasil uji RQ0 pada Gate 1 menunjukkan bahwa sinyal iklim wilayah asal sangat signifikan pada rezim kekeringan dan El Nino (`el_nino` $p = 0{,}000117$; `O1 dry` $p = 0{,}0104$), tetapi penambahan fitur spasial tanpa penyaringan dapat menambah varians pada periode tenang atau rezim basah `la_nina` (`O3`). Untuk menjawab `RQ2` dan `RQ3`, Modul 2–3 (`src/renaro/models/module23.py`, Brief v2 §5 & `MLE-H5-01`) memadukan cabang adaptif terkondisi iklim ($H^{\mathrm{adapt}}_t$) dengan cabang stabil ($H^{\mathrm{stable}}_t$) melalui *reliability gate* $g_{t,i} \in (0, 1)^{d_h}$:

$$z_{t,i} = g_{t,i} \odot H^{\mathrm{adapt}}_{t,i} + (1 - g_{t,i}) \odot H^{\mathrm{stable}}_{t,i}, \qquad g_{t,i} = \sigma\!\Big(\mathrm{MLP}_g\!\big([\mathrm{shock}_{t,i} \,\|\, \mathrm{rel}_{t,i} \,\|\, \mathrm{shift}_{t,i}]\big)\Big),$$

dengan spesifikasi setiap komponen yang seluruhnya dijamin **tersedia pada tanggal keputusan $t$ (`available_at <= t`)**:

- **Jalur Adaptif ($H^{\mathrm{adapt}}_{t,i}$)**: keluaran agregasi pesan berjeda terkondisi iklim dari Modul 1 ($m_{i,t}$).
- **Jalur Stabil ($H^{\mathrm{stable}}_{t,i}$)**: agregasi spasial di atas graf statis terpelajari $A_{\mathrm{static}}$ (tanpa input iklim, berregularisasi $L_2$ lebih kuat) atau matriks prior perdagangan BPS ternormalisasi, yang berfungsi sebagai jangkar ketika sinyal iklim tidak aktif atau graf dinamis tidak stabil.
- **Sinyal Guncangan Iklim Asal ($\mathrm{shock}_{t,i}$)**: agregat fitur `extreme_5d` dan `dry_spell_days` di wilayah asal pemasok serta magnitudo indeks ENSO $|\mathrm{RONI}_t|$ yang tersedia pada $t$.
- **Sinyal Keandalan Graf Dinamis ($\mathrm{rel}_{t,i}$)**: entropi distribusi perhatian $H(A_t[i])$ (mengukur ketidakpastian pemilihan tetangga/jeda) dan jarak distribusi $A_t[i]$ terhadap rata-rata graf pada periode latih $\bar{A}_{\mathrm{train}}[i]$.
- **Sinyal Pergeseran Distribusi Input ($\mathrm{shift}_{t,i}$)**: skor-$z$ rata-rata dan simpangan baku jendela input harga $60$ hari kerja saat ini terhadap statistik distribusi pada data latih.

Head prediksi kemudian menerima $[h_{i,\le t} \,\|\, z_{t,i} \,\|\, \mathrm{cal}_{t+h}]$. Berdasarkan temuan Gate 1, bias awal lapisan akhir *gate* dapat diinisialisasi secara konservatif ($b_g < 0$) agar pada rezim tenang model tetap dekat dengan jalur stabil/autoregresif dan membuka jalur adaptif secara proporsional saat guncangan iklim asal aktif. Sesuai batas klaim Brief v2 §6, mekanisme *gating* ini diposisikan sebagai komponen pendukung (bukan klaim penemuan arsitektur *gating* baru).

---

## 3.4 Modul 4 (Ekstensi *Robustness Objective* — Dieksekusi di `O1–O3`, Dikeluarkan dari Holdout Sprint 1)

Modul 4 (`MLE-H5-04`, commit `886f635`, `src/renaro/models/module4.py`, `configs/models/module4.yaml`) telah diimplementasikan dan dieksekusi sebagai studi ekstensi di atas *backbone* Modul 2–3 (`n_lags = 6`, `epochs = 10`, `prior: soft_bps`) sebanyak **15 run (`O1–O3 × 5 seed`)** beserta **evaluasi ketahanan perturbasi graf pada 47 mask uji `O3`** melawan `module23` Gate 2 (`reports/module4/module4_summary.md`, `reports/module4/fig_module4_robustness.png`, VRAM puncak `0,637 GB`, uji unit `tests/test_module4.py` 6/6 lulus). Sesuai keputusan `docs/decisions/GATE2.md` dan `frozen/manifest.yaml` (tag `gate2-freeze`, `b0d0ff9`), **`module4` tetap ditetapkan sebagai dikeluarkan dari holdout Sprint 1 (`excluded`)** dan tidak mengubah paket beku holdout; penyempurnaan *warmup schedule*-nya dipindahkan ke Sprint 2. Tiga suku regularisasi yang diimplementasikan adalah:

1. **Penalti Sensitivitas Perturbasi Graf**: $\mathcal{L}_{\mathrm{pert}} = \lambda_{\mathrm{pert}} \|f(X, A) - f(X, \tilde{A})\|_1$ ($\lambda_{\mathrm{pert}} = 0{,}15$), di mana $\tilde{A}$ dibentuk dari perturbasi acak `candidate_mask` per *batch* pelatihan ($p \in [0{,}10; 0{,}50]$, campuran *edge dropout* dan perturbasi `drop/add/rewire` atas prior BPS) menggunakan *encode* bersama untuk efisiensi memori.
2. **Penalti Varians Risiko Lintas-Kelompok Kausal (V-REx)**: $\mathcal{L}_{\mathrm{vrex}} = \lambda_{\mathrm{vrex}} \operatorname{Var}_g(\mathcal{R}_g)$ ($\lambda_{\mathrm{vrex}} = 5{,}0$), di mana 3 kelompok kuantil dibentuk murni dari **fitur iklim yang tersedia pada $\le t$** (agregat anomali hujan 30-harian asal `rain_30d_anom` 5 hari kerja terakhir), **tanpa pernah mengakses** `regime_labels.csv` yang khusus untuk evaluasi.
3. **Regularisasi Prior Lunak**: $\mathcal{L}_{\mathrm{prior}} = \lambda_{\mathrm{prior}} \|A \odot (1 - M_{\mathrm{bps}})\|_1$ ($\lambda_{\mathrm{prior}} = 0{,}05$) di atas `candidate_mask` *off-diagonal* penuh (`soft_bps`), yang memberi penalti lunak apabila bobot perhatian keluar dari koridor BPS 2022 namun tetap memungkinkan aktivasi edge alternatif saat koridor utama terganggu.

Sesuai batas klaim Brief v2 §6, Modul 4 bukan kontribusi kebaruan utama dan tidak diklaim sebagai penemuan metode *invariance* umum.

---

## 3.5 Baseline Wajib, Uji Mekanisme Sintetis, dan Studi Ablasi

Seluruh pembanding dijalankan pada **split, 5 seed (`0..4`), praproses, dan fungsi evaluasi yang identik**:

| Kelompok | Model Baseline | Peran Ilmiah dalam Evaluasi |
| :--- | :--- | :--- |
| **Naif** | `naive_last` ($\hat{P}_{t+h} = P_t$) & `seasonal_naive` ($\hat{P}_{t+h} = P_{t+h-364\text{d}}$) | Jangkar batas bawah (*sanity check* wajib: semua model harus mengalahkan `seasonal_naive`). |
| **Tabular (RQ0)** | `LightGBM` varian `(a)` (19 fitur: harga+kalender), `(b)` (34 fitur: `(a)`+iklim lokal), `(c)` (45 fitur: `(b)`+iklim asal BPS) | Mengukur sinyal iklim wilayah asal tanpa arsitektur GNN dan menjadi pembanding tabular kuat. |
| **ST-GNN Generik** | `Graph WaveNet (GWN)` (prior BPS + adjacency adaptif) & `MTGNN` (graph learner tanpa prior) | Pembanding ST-GNN standar dengan graf adaptif statis lintas waktu. |
| **Pembanding Head-to-Head RQ1 (Rezim Laten)** | `Latent-Regime GNN` (baseline disederhanakan ala **RCSGNet**, $K=3$ state laten dari return harga 20 hari terakhir, *backbone* GRU identik, tanpa iklim) | Memisahkan nilai informasi iklim eksogen teramati (Modul 1) vs rezim pasar laten dari histori harga (*dicatat eksplisit sebagai versi disederhanakan ala RCSGNet, bukan reproduksi penuh*). |
| **Pembanding Head-to-Head RQ1 (Lag Tanpa Iklim)** | `Lag-Graph Tanpa Iklim` (baseline disederhanakan ala **MillGNN**, Modul 1 dengan $e_j = 0$ + bias peluruhan $-\lambda \ell$) | Mengisolasi efek pengondisian iklim pada distribusi jeda per edge. |

- **Uji Pemulihan Jeda Sintetis (`MLE-H1-02`, `MLE-H3-01`, & `RL-H5-01`)**: Sebelum mengklaim interpretabilitas jeda pada data riil, Modul 1 diuji pada generator harga sintetis berjeda terkondisi iklim (`configs/synth/default.yaml`: `N = 34, T = 2400`, `L = 8` bin khusus data sintetis — berbeda dari `n_lags = 6` data riil sesuai Amandemen `A1` — dengan $\ell_{\text{dry}} = \min(\ell_{\text{normal}} + 2, 8)$ saat episode kering) serta dua kontrol negatif: (i) Modul 1 dengan $e_j = 0$ pada data `default`, dan (ii) Modul 1 penuh pada data `unconditioned` (jeda tidak bergeser, sehingga $\Delta\ell$ harus $\approx 0$). Ambang lulus protokol: korelasi peringkat Spearman $> 0{,}80$ (1-edge) / $> 0{,}70$ (5-edge), MAE lag $\le 1{,}0$ pentad, dan AUROC edge $> 0{,}85$ (figur publikasi di `reports/figures/synth_{lag_recovery,edge_heatmap}.png`).
- **Studi Ablasi (`MLE-H5-02`, Amandemen `A3`)**: Membandingkan lima varian konfigurasi identik pada validasi (`75` run `val`-only dengan anggaran seragam 1 epoch *matched-budget* sesuai Amandemen `A3`, bug agregasi `ANOM-07` telah diperbaiki di commit `21a2367`): `full` (Modul 1–3), `no_climate` ($e_j = 0$ dan sinyal shock iklim gate $= 0$), `no_lag` ($L = 1$), `no_gate` ($g = 1$), dan `no_calendar`.

---

## 3.6 Protokol Evaluasi v1.0 (`protocol-v1`), Amandemen `A1–A4`, dan Pembekuan Gate 2 (`gate2-freeze`)

Seluruh eksperimen mematuhi protokol terkunci `docs/eval_protocol_v1.md` (`configs/global.yaml`, tag `protocol-v1`), empat amandemen pra-holdout pada `docs/protocol_amendments.md`, dan keputusan pembekuan Gate 2 (`docs/decisions/GATE2.md`, tag `gate2-freeze`, commit `b0d0ff9`):

1. **Rolling-Origin, Embargo, dan Holdout Tersegel**:
   - `O1`: Train `2018-01-02..2022-06-30` | Val `2022-07-01..2022-12-31` | Test `2023-01-01..2023-12-31`.
   - `O2`: Train `2018-01-02..2023-06-30` | Val `2023-07-01..2023-12-31` | Test `2024-01-01..2024-12-31`.
   - `O3`: Train `2018-01-02..2024-06-30` | Val `2024-07-01..2024-12-31` | Test `2025-01-01..2026-05-31`.
   - `HOLDOUT`: Train `2018-01-02..2025-12-31` | Val `2026-01-01..2026-05-31` | Test `2026-06-01..2026-10-31` (**TERSEGEL** oleh CGS di luar repositori; hanya dibuka satu kali oleh `CGS-H6-01` melalui `scripts/predict.py --manifest frozen/manifest.yaml`). Pada saat dokumen metode ini diperbarui (H6 pra-eksekusi `CGS-H6-01`), **holdout belum dibuka sehingga belum ada hasil maupun klaim kinerja holdout**.
   - Setiap batas `train`/`val` dan `val`/`test` dipisahkan oleh **embargo $20$ hari kerja** ($\ge \max(h)$), dan *hyperparameter tuning* ringan hanya dilakukan pada validasi `O1` lalu dibekukan untuk semua origin.
2. **Stratifikasi Rezim Iklim (*Eval Only*)**:  
   Evaluasi distratifikasi pada lima rezim dengan urutan prioritas $\texttt{dry} > \texttt{extreme\_wet} > \texttt{el\_nino} > \texttt{la\_nina} > \texttt{normal}$ (`CGS-H2-04`), dengan penanda `CI lebar` pada sel $< 200$ *node-days*.
3. **Metrik, Uji Statistik, & Penetapan Pra-Holdout `best_baseline_on_validation`**:  
   Metrik utama adalah **MAE (Rp/kg)**, didampingi RMSE (Rp/kg), sMAPE (%), `Worst-Regime MAE` ($\max_r \text{MAE}_r$), `Regime Gap` ($\text{Worst-Regime MAE} - \text{MAE}_{\text{normal}}$), dan stabilitas $5$ seed ($\text{mean} \pm \text{sd}$). Uji signifikansi perbedaan akurasi menggunakan **uji Diebold–Mariano** dengan koreksi **Harvey–Leybourne–Newbold (HLN)** atas selisih loss absolut harian rata-rata lintas provinsi, varians **Newey–West HAC** dengan *bandwidth* $L = h - 1$, serta koreksi multi-perbandingan **Holm–Bonferroni** ($\alpha = 0{,}05$). Sesuai `frozen/manifest.yaml` dan `docs/decisions/GATE2.md`, pembanding utama pra-holdout yang ditetapkan sebelum holdout dibuka adalah **`best_baseline_on_validation = lgbm_c`** (`Val h=10 MAE` 3-origin `= Rp5.481,20/kg`).
4. **Protokol Uji Ketahanan Prior Graf (`RQ3` & Amandemen `A2`)**:  
   Matriks `bps_mask.npy` diuji pada tingkat perturbasi $p \in \{10\%, 20\%, 30\%, 40\%, 50\%\}$ untuk tiga operator (`drop`, `add`, `rewire`, 3 seed struktural `0, 1, 2`) serta varian `clean` dan `none` (`test-mode` penuh 47 mask × 5 seed; *retrain* `train-mode` pada subset $p \in \{10\%, 50\%\}$ × 3 seed sesuai Amandemen `A2`), dan dilaporkan melalui kurva degradasi MAE pada periode normal vs rezim ekstrem.
5. **Ringkasan Amandemen Protokol (`A1–A4`) dan Pembekuan Gate 2 (`gate2-freeze`)**:  
   Empat amandemen teknis dicatat sebelum holdout dibuka pada `docs/protocol_amendments.md`: **`A1`** (`n_lags = 6` untuk model graf data riil; data sintetis tetap 8 bin), **`A2`** (cakupan subset *retrain* `CGS-H5-01`), **`A3`** (anggaran 1-epoch ablasi `MLE-H5-02` + perbaikan `ANOM-07`), dan **`A4`** (kesetaraan anggaran pelatihan **`epochs = 10, patience = 10`** untuk seluruh 6 model neural pada `configs/models/gate2/*.yaml`). Pada **Gate 2** (`docs/decisions/GATE2.md`, Keputusan: **GO**, tag `gate2-freeze` di commit `b0d0ff9`, audit protokol `docs/protocol_audit.md` **10/10 LULUS**), sebanyak **200 run `g2_*`** (`10` model × `4` origin `O1, O2, O3, HOLDOUT` × `5` seed `0..4`, `split_hash = 411aec1a...`) telah diselesaikan dari commit bersih `6f317be`, dengan 50/50 checksum SHA-256 `ckpt.pt` terverifikasi di `frozen/manifest.yaml`, uji kering `scripts/predict.py` 50/50 `O3` identik (`max |delta y_pred| = 0,00e+00`), audit `PA-04` 200/200 `< 2026-06-01`, serta `module1_none` dan `module4` tercatat resmi sebagai `dikeluarkan dari holdout`.

---

## 3.7 Ringkasan Batas Klaim Penelitian (Brief v2 §6)

| Kategori | Rumusan yang Diberlakukan pada Seluruh Laporan Sprint 1 |
| :--- | :--- |
| **AMAN** | *"Sepengetahuan kami"*, pengondisian distribusi jeda per edge (`n_lags = 6` pentad pada data riil sesuai Amandemen `A1` dan 8 pentad pada uji sintetis, ditambah slot `null`) pada iklim fisik teramati di wilayah asal ($c_{j,\le t}$) untuk ST-GNN harga cabai $34$ provinsi Indonesia; benchmark *availability-safe* (`available_at <= t`) terstratifikasi 5 rezim iklim dengan *Worst-Regime MAE* dan uji kesalahan prior graf $10\%$–$50\%$; perbandingan *head-to-head* terkontrol antara pengondisian iklim asal vs rezim pasar laten dari harga (ala RCSGNet) vs lag tanpa iklim (ala MillGNN). |
| **BERISIKO** *(Hanya sebagai temuan eksperimental terkualifikasi)* | Efektivitas *reliability gate* (Modul 2–3) dalam menahan degradasi pada rezim jarang atau perturbasi prior $30\%$–$50\%$, serta efektivitas penalti *robustness* (Modul 4 yang dieksekusi pada `O1–O3` dan dikeluarkan dari holdout Sprint 1) dalam menahan degradasi perturbasi graf — hanya boleh dilaporkan sebagai hasil eksperimen/ablasi empiris, bukan klaim penemuan metode umum baru. |
| **JANGAN DIKLAIM** *(Dilarang Mutlak)* | (1) Mengklaim graf adaptif, *static-dynamic gating*, atau *invariance regularization* sebagai kebaruan arsitektur umum; (2) mengklaim sebagai studi pertama yang memasukkan variabel iklim/cuaca ke dalam GNN harga pertanian atau pertama yang memodelkan rezim pada GNN harga pangan; (3) mengklaim bobot edge $A^{(\ell)}_{ij,t}$ sebagai bukti kausalitas struktural atau arus pasokan fisik cabai antarprovinsi. |
