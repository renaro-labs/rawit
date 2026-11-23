# Laporan 3 â€” Kajian Literatur Pembeda (`RL-H1-02`) & Spesifikasi Baseline untuk MLE
**Disusun oleh:** RL (*Research Lead*)  
**Tanggal:** 23 November 2026  
**File CSV Terkait:** [06_matriks_positioning_5_paper_RL_H1_02.csv](./csv_laporan/06_matriks_positioning_5_paper_RL_H1_02.csv)  
**File LaTeX Terkait:** [RL-H1-02__lit_rcsgnet.tex](./RL-H1-02__lit_rcsgnet.tex), [RL-H1-02__lit_millgnn.tex](./RL-H1-02__lit_millgnn.tex), [RL-H1-02__lit_marketdna.tex](./RL-H1-02__lit_marketdna.tex), [RL-H1-02__lit_sdgf.tex](./RL-H1-02__lit_sdgf.tex), [RL-H1-02__lit_steve.tex](./RL-H1-02__lit_steve.tex)

---

## 1. Matriks Posisi Studi Kita vs 5 Kelompok Paper Terdekat

| Paper | Tahun | Domain / Data | Graph Berarah | Graph Dinamis | Distribusi Jeda / Edge ($\ell$) | Kondisi Pembentuk Graph | Iklim Eksogen Wilayah Asal | Uji OOD Rezim Iklim | Uji Graph Prior Keliru |
| :--- | :---: | :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: |
| **RCSGNet** [8] | 2026 | Kentang, 25 prov Tiongkok, mingguan | Ya | Ya | **Tidak** | **State pasar LATEN dari harga** | **Tidak** | **Tidak** | **Tidak** |
| **MarketDNA** [9] | 2026 | Kentang multi-hub | Ya | Ya | **Tidak** | **Token state pasar LATEN diskret** | **Tidak** | **Tidak** | **Tidak** |
| **MillGNN** [10] | 2025 | Multi-scale lead-lag umum | Ya | Ya | **Ya** (*decay-aware*) | **Jendela input + bias $-\lambda\ell$ (tanpa iklim)** | **Tidak** | **Tidak** | **Tidak** |
| **SDGF / DRAN** [13,14] | 2025 | Spatio-temporal umum | Ya | Ya | **Tidak** | **Gate statis + dinamis** | **Tidak** | **Tidak** | **Tidak** |
| **STEVE / DynaSTar** [4,15] | 2025/26 | Lalu lintas (*traffic OOD*) | Ya | Ya | **Tidak** | **Confounder / invarian laten** | **Tidak** | OOD trafik | **Tidak** |
| **STUDI INI (Renaro)** | **2026** | **Cabai Merah, 34 prov Indonesia, harian kerja** | **Ya** | **Ya** | **Ya ($0..8$ pentad + slot `null`)** | **Iklim teramati di wilayah asal ($c_j$)** | **Ya (*as-of*)** | **Ya (ENSO, Kering, Ekstrem)** | **Ya (10â€“50% + `none`)** |

---

## 2. Verifikasi Wajib Klaim RCSGNet (2026) & MarketDNA (2026) â€” Hasil Ekstraksi Akademik

### A. RCSGNet (Prioritas #1 â€” `bai2026rcsgnet`)
* **Judul Resmi**: *Regime-Aware Causal Spectral Graph Learning for Regional Potato Price Forecasting*
* **Penulis**: **Changqian Bai & Youpeng Wang**
* **Jurnal**: *Potato Research* (Springer Nature, ISSN 0014-3065), **Vol. 69, Issue 5, Juni 2026**
* **Dataset & Horizon**: Harga kentang mingguan di **25 provinsi Tiongkok (2012â€“2018)**; dievaluasi pada **1-step horizon** dan **4-step horizon** (MAE, RMSE, MAPE).
* **Baseline Pembanding di Paper**: CNN, LSTM, N-BEATS, Autoformer, dan Informer.
* **4 Komponen Arsitektur RCSGNet**:
  1. **Market State / Regime Encoder**: Menginspeksi konteks harga terkini untuk mengenali state pasar laten ($\pi_t$).
  2. **Directed Causal Graph Learner**: Mengestimasi pola pengaruh prediktif berarah antarprovinsi yang bergantung pada state laten aktif.
  3. **Spectral Graph Filtering & Temporal Decomposition**: Mendekomposisi fitur temporal ke komponen frekuensi dan menerapkan konvolusi graph spektral untuk menyaring *noise* jangka pendek dari tren musiman.
  4. **State-Gated Decoder**: Menggabungkan representasi lokal, hasil propagasi graph, dan *horizon embeddings*.

| Pertanyaan Verifikasi | Jawaban | Bukti & Implikasi untuk Sprint 1 |
| :--- | :---: | :--- |
| Apakah RCSGNet memakai cuaca/iklim eksogen? | **TIDAK** | Rezim pasar diinferensi secara laten dari histori harga kentang regional. |
| Apakah RCSGNet memakai distribusi jeda per edge? | **TIDAK** | Menggunakan *causal spectral graph* berarah per rezim laten tanpa distribusi lag diskret per edge. |
| Apakah RCSGNet memakai graph berarah? | **YA** | Matriks adjacensi berarah dipelajari untuk masing-masing state laten $k \in \{1..K\}$. |
| Apakah RCSGNet menguji OOD rezim iklim fisik? | **TIDAK** | Evaluasi dilakukan secara agregat pada split kronologis tanpa stratifikasi episode ENSO/kekeringan. |

### B. MarketDNA (`marketdna2026`)
* **Judul Resmi**: *MarketDNA: Discrete Market-State Tokenization for Multi-Centre Potato Price Forecasting*
* **Penulis**: **Yun Zhu, Shuyi Yang, Qihui Ling, Kexiang Wei, & Juchuan Dai**
* **Jurnal**: *Potato Research* (Springer Nature), **Agustus 2026 (Online First 13 Agustus 2026)**
* **Dataset & Horizon**: Harga kentang harian/periodik multi-centre/multi-provinsi; dievaluasi pada **1-step, 2-step, dan 4-step horizon**.
* **Baseline Pembanding di Paper**: ARIMA, LSTM, Bi-LSTM, AM-LSTM, N-BEATS, dan varian PatchTST.
* **3 Komponen Arsitektur MarketDNA**:
  1. **Latent Market-State Tokenization**: Memecah fragmen histori harga kontinu menjadi kosakata diskret token state pasar (*reusable market-state tokens*).
  2. **Cross-Centre State Transformer**: Memodelkan transisi state sepanjang waktu dan ko-pergerakan antar-pusat perdagangan regional.
  3. **Self-Supervised Pretraining**: Pra-pelatihan lewat *market-state reconstruction*, *masked state modeling*, dan *state transition prediction* **tanpa** membutuhkan data cuaca/logistik eksternal.

**Kesimpulan Eskalasi RL**: Klaim utama di Brief v2 Â§6 **100% AMAN** dan tidak perlu direvisi. Eksperimen kunci RQ1 adalah membandingkan **Modul 1** melawan **Baseline Regime Laten ala RCSGNet (`MLE-H4-02`)** pada backbone temporal, split, dan seed yang identik.

---

## 3. Spesifikasi Teknis Handoff RL kepada MLE (`MLE-H4-02` & `MLE-H4-03`)

### A. Spesifikasi Baseline 1: `LatentRegimeGraph` (*ala RCSGNet, disederhanakan* â€” `MLE-H4-02`)
* **File Target**: `src/renaro/baselines/latent_regime.py`
* **Arsitektur**:
  1. Gunakan encoder temporal GRU (`hidden_dim = 64`, `window = 60` hari kerja) dan head prediksi multi-horizon $h \in \{5, 10, 20\}$ yang **sama persis** dengan Modul 1.
  2. Dari representasi return harga 20 hari kerja terakhir, proyeksikan ke distribusi bobot rezim laten global/node:
     $$\pi_t = \operatorname{softmax}(\mathbf{W}_\pi \bar{h}_t) \in \Delta^{K-1}, \quad K = 3.$$
  3. Sediakan $K = 3$ matriks parameter graph berarah $\mathbf{\Theta}_k \in \mathbb{R}^{34 \times 34}$ yang dibatasi oleh `candidate_mask` (`bps_mask.npy`), normalkan per baris tujuan $\mathbf{A}_k = \operatorname{softmax}_j(\mathbf{\Theta}_k)$, lalu bentuk graph efektif $\mathbf{A}_t = \sum_{k=1}^K \pi_{t,k} \mathbf{A}_k$ (**tanpa** input iklim $c_j$ dan **tanpa** dimensi lag $\ell$).
  4. Tambahkan regularisasi entropi $\mathcal{L}_{\text{ent}} = -\lambda_{\text{ent}} H(\frac{1}{B}\sum_{b=1}^B \pi_{b,t})$ dengan $\lambda_{\text{ent}} = 0{,}01$ agar state laten tidak runtuh (*collapse*) ke satu matriks.

### B. Spesifikasi Baseline 2: `LagGraphBaseline` (*ala MillGNN, disederhanakan* â€” `MLE-H4-03`)
* **File Target**: `src/renaro/baselines/lag_graph.py`
* **Arsitektur**:
  1. Warisi langsung kelas `ClimateConditionedLagGraph` (Modul 1) agar jumlah parameter temporal dan head identik.
  2. Nolkan/abaikan input iklim wilayah asal ($c_j \equiv \mathbf{0}$) pada fungsi skor perhatian edge-lag.
  3. Tambahkan parameter peluruhan jeda yang dipelajari $\lambda = \operatorname{softplus}(\theta_{\text{decay}})$ sehingga logit perhatian untuk edge $j \to i$ pada lag pentad $\ell \in \{0..8\}$ menjadi:
     $$e^{(\ell)}_{ij,t} = \varphi_\theta(h_{i,\le t},\, h_{j,\le t-\ell},\, s_{ij},\, \ell) - \lambda \cdot \ell.$$
  4. Selisih metrik antara **Modul 1** dan **`LagGraphBaseline`** mengukur secara murni kontribusi pengondisian iklim wilayah asal ($c_j$) pada distribusi jeda graph.

