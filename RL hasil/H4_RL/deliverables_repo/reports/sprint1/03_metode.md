# 3. Metode

> **Status Dokumen**: Draf Sprint 1 (`RL-H4-01`) · **Peran**: RL (*Research Lead*, `@alim`) · **Tanggal**: Kamis, 26 November 2026 (`H4`)  
> **Rujukan Teknis**: Brief v2 §5–§8, `docs/eval_protocol_v1.md` (tag `protocol-v1`), `docs/data_contract.md`, `docs/playbook/04_MLE_ML_Graph_Engineer.md`, dan `configs/global.yaml`

---

## 3.1 Formulasi Masalah, Representasi Data, dan Aturan Ketersediaan (`available_at <= t`)

Jaringan pasar cabai merah keriting dimodelkan sebagai graf berarah multiregional dengan himpunan node $\mathcal{V} = \{1, \dots, N\}$ yang merepresentasikan **$N = 34$ provinsi** struktur lama Indonesia (`prov_code` BPS 2-digit terurut sesuai `src/renaro/contract.py`). Pada setiap tanggal keputusan hari kerja PIHPS $t \in \mathcal{T}$ (Senin–Jumat), setiap node $i \in \mathcal{V}$ mengamati histori jendela input sepanjang $W = 60$ hari kerja, $X_{i,t-W+1:t} \in \mathbb{R}^{W \times F}$, yang memuat fitur harga historis *as-of*, kalender hari raya/libur nasional, fitur iklim provinsi lokal, dan indeks ENSO makro RONI. Tugas peramalan multi-horizon adalah memprediksi harga pasar tradisional cabai merah keriting (`price_type = 1`) pada horizon $h \in \{5, 10, 20\}$ hari kerja ke depan (dengan **horizon utama $h = 10$**). Model dilatih pada skala logaritmik ($y_{i,t+h} = \log P_{i,t+h}$ atau *log-return* $\Delta \log P_{i,t+h} = \log P_{i,t+h} - \log P_{i,t}$ yang dikonversi kembali ke level harga $\hat{P}_{i,t+h} = \exp(\hat{y}_{i,t+h})$), dan seluruh metrik galat dihitung dalam satuan **Rp/kg** hanya pada pasangan $(i, t+h)$ yang memiliki `is_observed == True` (tanpa imputasi target).

Seluruh fitur dalam panel `data/processed/dataset_v1/panel.parquet` dibangun mengikuti kontrak data (`docs/data_contract.md`) dan tabel ketersediaan resmi (`reports/qa/availability.csv`, 7 keluarga fitur) dengan aturan emas anti-kebocoran waktu **`available_at <= t`** yang diverifikasi melalui `pd.merge_asof(..., direction="backward")` dan uji otomatis `tests/test_no_leakage.py` (termasuk 4 uji *truncation* identik bit-for-bit):

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
   Indikator iklim fisik di provinsi asal/pemasok $j$ pada $L = 8$ pentad terakhir yang sudah tersedia pada tanggal keputusan $t$ (`rain_pentad_anom`, `dry_spell_days`, `extreme_5d`, `rain_30d_anom`, serta `roni`) dikodekan melalui jaringan MLP menjadi vektor konteks iklim asal $e_{j,t} = \mathrm{MLP}_{\text{clim}}(c_{j,\le t}) \in \mathbb{R}^{d_c}$.
3. **Representasi Berjeda per Bin Pentad ($z_j^{(\ell)}$)**:  
   Karena data curah hujan harian CHIRPS v3 merupakan disagregasi dari pentad, dimensi jeda didiskretisasi pada resolusi pentad $\ell = 1, \dots, L$ dengan $L = 8$ bin ($1$ bin $\approx 5$ hari kerja $\approx 1$ pentad, mencakup jendela historis hingga $\approx 35$–$40$ hari kerja). Representasi state asal pada bin jeda ke-$\ell$ dihitung sebagai rata-rata state temporal pada jendela pentad ke-$\ell$ ke belakang:
   $$z_j^{(\ell)} = \frac{1}{|\mathcal{W}_\ell|} \sum_{\tau \in [t - 5\ell,\, t - 5\ell + 4]} z_j(\tau).$$
4. **Pemberi Skor Pasangan-Jeda ($\phi_\theta$) dan Fitur Edge Statis ($s_{ij}$)**:  
   Skor tak-ternormalisasi untuk pasangan berarah $(j \to i)$ pada jeda $\ell$ dihitung melalui:
   $$\phi_\theta\!\big(h_{i,\le t},\, h_{j,\le t},\, c_{j,\le t},\, s_{ij},\, \ell\big) = \mathrm{MLP}_\phi\!\Big(\big[h_{i,\le t} \,\|\, h_{j,\le t} \,\|\, e_{j,t} \,\|\, s_{ij} \,\|\, \mathrm{emb}(\ell)\big]\Big) \in \mathbb{R},$$
   di mana $s_{ij}$ memuat fitur edge statis (log jarak centroid antarprovinsi, bendera biner koridor perdagangan `bps_mask[i, j]`, dan pangsa BPS bila tersedia), sedangkan $\mathrm{emb}(\ell)$ adalah *embedding* bin jeda terpelajari.
5. **Pembatasan Kandidat (`candidate_mask`), Slot `null`, dan Normalisasi**:  
   Untuk setiap provinsi tujuan $i$, himpunan kandidat asal $j \in \mathcal{C}(i)$ dikendalikan oleh `candidate_mask` dengan dua varian utama: `bps` (gabungan mask BPS Poldis 2022 berarah `bps_mask.npy` dengan $k$ tetangga geografis terdekat agar provinsi berderajat masuk nol seperti Papua `94` tetap memiliki kandidat) dan `none` (seluruh $N - 1$ provinsi lain tanpa prior perdagangan). Selain itu, ditambahkan **satu opsi slot `null`** dengan skor terpelajari $\psi_{\text{null}}(h_{i,\le t}, c_{i,\le t})$ yang berpasangan dengan vektor pesan nol ($\mathbf{0}$), sehingga provinsi tujuan dapat secara adaptif memilih untuk tidak mengambil informasi spasial ketika sinyal dari provinsi lain sedang bising. Probabilitas perhatian $A^{(\ell)}_{ij,t}$ dan $A^{\text{null}}_{i,t}$ memenuhi $\sum_{j \in \mathcal{C}(i)} \sum_{\ell=1}^{L} A^{(\ell)}_{ij,t} + A^{\text{null}}_{i,t} = 1$.
6. **Agregasi Pesan, Head Multi-Horizon, Regularisasi Entropi, dan Kompleksitas**:  
   Pesan spasial-temporal berjeda diagregasi menjadi:
   $$m_{i,t} = \sum_{j \in \mathcal{C}(i)} \sum_{\ell=1}^{L} A^{(\ell)}_{ij,t}\, W_v\, z_j^{(\ell)},$$
   lalu digabungkan dengan state autoregresif lokal dan fitur kalender masa depan yang diketahui di muka ($\mathrm{cal}_{t+h}$) untuk menghasilkan prediksi seluruh horizon $h \in \{5, 10, 20\}$:
   $$\hat{y}_{i,t+h} = \mathrm{MLP}_{\text{head}}\!\big([h_{i,\le t} \,\|\, m_{i,t} \,\|\, \mathrm{cal}_{t+h}]\big).$$
   Fungsi objektif pelatihan adalah galat absolut (MAE) pada observasi valid (`y_mask == True`) ditambah regularisasi entropi opsional $\lambda_H \cdot \frac{1}{N}\sum_{i=1}^N H(A_{i,\cdot,t})$ dengan $\lambda_H$ kecil agar distribusi perhatian tetap tajam dan dapat diinterpretasikan. Pada skala $N = 34$ provinsi dan $L = 8$ bin jeda, ruang evaluasi skor $(i, j, \ell)$ hanya berjumlah maksimal $34 \times 34 \times 8 = 9.248$ entri per langkah waktu, dengan kebutuhan memori GPU puncak $< 3\text{ GB}$ pada ukuran *batch* $32$.

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

## 3.4 Modul 4 (*Stretch Goal* — Opsional)

Modul 4 (`MLE-H5-04`) merupakan ekstensi *robustness objective* bersifat *stretch* yang hanya dijalankan apabila Modul 1–3 dan paket beku selesai sebelum tenggat Gate 2 (`H5`); jika tidak, Modul 4 dialihkan ke Sprint 2. Tiga suku regularisasi opsional yang dikaji adalah:

1. **Penalti Sensitivitas Perturbasi Graf**: $\mathcal{L}_{\mathrm{pert}} = \|f(X, A) - f(X, \tilde{A})\|_1$, di mana $\tilde{A}$ dibentuk dari perturbasi acak `candidate_mask` per *batch* pelatihan untuk melatih ketahanan terhadap prior graf yang meleset.
2. **Penalti Varians Risiko Lintas-Kelompok Berbasis Fitur**: varians fungsi kerugian antar kelompok sampel yang dibentuk murni dari **fitur yang tersedia pada $t$** (misalnya kuantil anomali hujan wilayah asal dalam *batch*), **tanpa pernah menyentuh** `regime_labels.csv` yang khusus untuk evaluasi.
3. **Regularisasi Prior Lunak**: $\mathcal{L}_{\mathrm{prior}} = \lambda_{\mathrm{prior}} \|A \odot (1 - M_{\mathrm{bps}})\|_1$, yang memberi penalti lunak apabila bobot perhatian keluar dari koridor BPS 2022 namun tetap memungkinkan aktivasi edge alternatif saat koridor utama terganggu.

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

- **Uji Pemulihan Jeda Sintetis (`MLE-H1-02` & `MLE-H3-01`)**: Sebelum mengklaim interpretabilitas jeda pada data riil, Modul 1 diuji pada generator harga sintetis berjeda terkondisi iklim (`N = 34, T = 2400, L = 8`, di mana $\ell_{\text{dry}} = \min(\ell_{\text{normal}} + 2, 8)$ saat episode kering) serta dua kontrol negatif: (i) Modul 1 dengan $e_j = 0$ pada data `default`, dan (ii) Modul 1 penuh pada data `unconditioned` (jeda tidak bergeser, sehingga $\Delta\ell$ harus $\approx 0$). Ambang lulus protokol: korelasi peringkat Spearman $> 0{,}80$ (1-edge) / $> 0{,}70$ (5-edge), MAE lag $\le 1{,}0$ pentad, dan AUROC edge $> 0{,}85$.
- **Studi Ablasi (`MLE-H5-02`)**: Membandingkan lima varian konfigurasi identik pada validasi: `full` (Modul 1–3), `no_climate` ($e_j = 0$ dan sinyal shock iklim gate $= 0$), `no_lag` ($L = 1$), `no_gate` ($g = 1$), dan `no_calendar`.

---

## 3.6 Ringkasan Protokol Evaluasi v1.0 (`protocol-v1`)

Seluruh eksperimen mematuhi protokol terkunci `docs/eval_protocol_v1.md` (`configs/global.yaml`, tag `protocol-v1`):

1. **Rolling-Origin, Embargo, dan Holdout Tersegel**:
   - `O1`: Train `2018-01-02..2022-06-30` | Val `2022-07-01..2022-12-31` | Test `2023-01-01..2023-12-31`.
   - `O2`: Train `2018-01-02..2023-06-30` | Val `2023-07-01..2023-12-31` | Test `2024-01-01..2024-12-31`.
   - `O3`: Train `2018-01-02..2024-06-30` | Val `2024-07-01..2024-12-31` | Test `2025-01-01..2026-05-31`.
   - `HOLDOUT`: Train `2018-01-02..2025-12-31` | Val `2026-01-01..2026-05-31` | Test `2026-06-01..2026-10-31` (**TERSEGEL** oleh CGS di luar repositori; hanya dibuka satu kali pada H6 untuk model yang beku di `frozen/manifest.yaml` pasca-Gate 2).
   - Setiap batas `train`/`val` dan `val`/`test` dipisahkan oleh **embargo $20$ hari kerja** ($\ge \max(h)$), dan *hyperparameter tuning* ringan hanya dilakukan pada validasi `O1` lalu dibekukan untuk semua origin.
2. **Stratifikasi Rezim Iklim (*Eval Only*)**:  
   Evaluasi distratifikasi pada lima rezim dengan urutan prioritas $\texttt{dry} > \texttt{extreme\_wet} > \texttt{el\_nino} > \texttt{la\_nina} > \texttt{normal}$ (`CGS-H2-04`), dengan penanda `CI lebar` pada sel $< 200$ *node-days*.
3. **Metrik dan Uji Statistik**:  
   Metrik utama adalah **MAE (Rp/kg)**, didampingi RMSE (Rp/kg), sMAPE (%), `Worst-Regime MAE` ($\max_r \text{MAE}_r$), `Regime Gap` ($\text{Worst-Regime MAE} - \text{MAE}_{\text{normal}}$), dan stabilitas $5$ seed ($\text{mean} \pm \text{sd}$). Uji signifikansi perbedaan akurasi menggunakan **uji Diebold–Mariano** dengan koreksi **Harvey–Leybourne–Newbold (HLN)** atas selisih loss absolut harian rata-rata lintas provinsi, varians **Newey–West HAC** dengan *bandwidth* $L = h - 1$, serta koreksi multi-perbandingan **Holm–Bonferroni** ($\alpha = 0{,}05$) terhadap baseline terbaik pra-registrasi.
4. **Protokol Uji Ketahanan Prior Graf (`RQ3`)**:  
   Matriks `bps_mask.npy` diuji pada tingkat perturbasi $p \in \{10\%, 20\%, 30\%, 40\%, 50\%\}$ untuk tiga operator (`drop`, `add`, `rewire`, 3 seed struktural `0, 1, 2`) serta varian prior `distance`, `surplus_deficit`, dan `none`, dan dilaporkan melalui kurva degradasi MAE pada periode normal vs rezim ekstrem.

---

## 3.7 Ringkasan Batas Klaim Penelitian (Brief v2 §6)

| Kategori | Rumusan yang Diberlakukan pada Seluruh Laporan Sprint 1 |
| :--- | :--- |
| **AMAN** | *"Sepengetahuan kami"*, pengondisian distribusi jeda per edge ($\ell \in \{1,\dots,8\}$ pentad + slot `null`) pada iklim fisik teramati di wilayah asal ($c_{j,\le t}$) untuk ST-GNN harga cabai $34$ provinsi Indonesia; benchmark *availability-safe* (`available_at <= t`) terstratifikasi 5 rezim iklim dengan *Worst-Regime MAE* dan uji kesalahan prior graf $10\%$–$50\%$; perbandingan *head-to-head* terkontrol antara pengondisian iklim asal vs rezim pasar laten dari harga (ala RCSGNet) vs lag tanpa iklim (ala MillGNN). |
| **BERISIKO** *(Hanya sebagai temuan eksperimental terkualifikasi)* | Efektivitas *reliability gate* (Modul 2–3) dalam menahan degradasi pada rezim jarang atau perturbasi prior $30\%$–$50\%$, serta efektivitas penalti *robustness* (Modul 4, jika dijalankan) dalam memperkecil *Regime Gap* — hanya boleh dilaporkan sebagai hasil ablasi empiris, bukan klaim penemuan metode umum baru. |
| **JANGAN DIKLAIM** *(Dilarang Mutlak)* | (1) Mengklaim graf adaptif, *static-dynamic gating*, atau *invariance regularization* sebagai kebaruan arsitektur umum; (2) mengklaim sebagai studi pertama yang memasukkan variabel iklim/cuaca ke dalam GNN harga pertanian atau pertama yang memodelkan rezim pada GNN harga pangan; (3) mengklaim bobot edge $A^{(\ell)}_{ij,t}$ sebagai bukti kausalitas struktural atau arus pasokan fisik cabai antarprovinsi. |
