# 2. Tinjauan Pustaka (*Related Work*)

> **Status Dokumen**: Pembaruan H6 (`ALL-H6-01`, pasca-pembekuan `gate2-freeze`) · **Peran**: RL (*Research Lead*, `@alim`) · **Tanggal**: Sabtu, 28 November 2026 (`H6`)  
> **Sumber Ringkasan & Rujukan Keputusan**: `docs/positioning.md`, catatan literatur `docs/lit/{rcsgnet,marketdna,millgnn,sdgf,steve}.tex`, `docs/references.bib`, `docs/protocol_amendments.md` (`A1–A4`), `docs/decisions/GATE2.md` (tag `gate2-freeze`, commit `b0d0ff9`), dan Brief v2 §2 & §6

Penelitian ini berada pada persimpangan empat kelompok literatur utama sesuai pemetaan Brief v2 §2: (1) pembelajaran graf spatio-temporal dan graf harga pertanian, (2) pembelajaran graf berarah yang peka terhadap jeda waktu (*lag/delay-aware*), (3) ketahanan model spatio-temporal terhadap pergeseran distribusi/rezim (*OOD & static-dynamic robustness*), serta (4) pemodelan harga pangan, cuaca wilayah sumber, dan guncangan iklim/ENSO.

---

## 2.1 Kelompok 1: Pembelajaran Graf Spatio-Temporal dan Graf Harga Pertanian

Arsitektur *spatio-temporal graph neural network* (ST-GNN) modern seperti **Graph WaveNet** (Wu dkk., 2019) dan **MTGNN** (Wu dkk., 2020) memelopori pembelajaran matriks ketetanggaan (*adjacency*) secara adaptif dari data melalui perkalian *embedding* node, baik sebagai pelengkap prior geografis maupun sepenuhnya tanpa prior. Namun, matriks adaptif pada kedua arsitektur generik tersebut bersifat statis sepanjang periode pengujian sehingga tidak dapat menyesuaikan kekuatan hubungan antarwilayah ketika terjadi guncangan eksternal.

Dalam domain spesifik peramalan harga komoditas pertanian multiregional, dua studi paling mutakhir menjadi pembanding langsung bagi penelitian ini. **RCSGNet** (Bai & Wang, *Potato Research* Vol. 69 No. 5, Juni 2026) merancang arsitektur *Regime-Conditioned Directed Causal Spectral Graph Network* untuk meramalkan harga kentang mingguan di $25$ provinsi Tiongkok (2012–2018). RCSGNet menginferensi *state* pasar laten ($s_t$) secara endogen dari histori harga untuk memadukan graf berarah lintas rezim melalui penyaringan spektral dan *state-gated decoder*. **MarketDNA** (Zhu dkk., *Potato Research*, Agustus 2026) melangkah pada jalur representasi simbolik dengan menokenisasi fragmen harga kentang multikawasan menjadi kosakata *state* pasar diskret yang diproses oleh *Cross-Centre State Transformer*. Verifikasi teks penuh dan abstrak resmi pada `docs/lit/rcsgnet.tex` dan `docs/lit/marketdna.tex` mengonfirmasi bahwa baik RCSGNet maupun MarketDNA beroperasi murni pada histori harga (*price-only*), mengandalkan **rezim laten endogen**, dan **tidak memodelkan variabel iklim eksogen maupun distribusi jeda waktu per edge**.

Sementara itu, upaya menggabungkan informasi cuaca ke dalam GNN harga pertanian telah dirintis oleh **CGNN** (*arXiv:2304.09761*, 2023) untuk harga kentang dan tomat di India serta **Min et al.** (2025) yang membandingkan RNN (*Stacked LSTM*) dan GNN (*StemGNN*, *TGCN*) pada harga grosir komoditas pertanian Korea Selatan. Kedua studi tersebut membuktikan bahwa variabel cuaca/iklim dapat digunakan di dalam GNN harga pertanian, tetapi cuaca hanya dimasukkan sebagai **fitur lokal node** di atas graf lokasi statis (CGNN) atau matriks perhatian antarvariabel tanpa prior perdagangan dan tanpa distribusi jeda per edge yang dikondisikan pada iklim wilayah asal (Min et al., 2025).

---

## 2.2 Kelompok 2: Graf Berarah yang Peka Terhadap Jeda Waktu (*Lag/Delay-Aware Graph Learning*)

Pada jaringan ekonomi dan fisik nyata, perambatan guncangan antar-node jarang berlangsung serentak. **MillGNN** (*arXiv:2509.03852*, 2025) memperkenalkan *Multi-Scale Lead-Lag GNN* dengan *decay-aware attention* yang menambahkan bias peluruhan $-\lambda \ell$ untuk menangkap relasi *lead-lag* asimetris lintas skala waktu pada deret waktu multivariat umum. **SAMSGL** (*arXiv:2312.02646*, 2023) mengatasi *time delay* pada data spatio-temporal (trafik dan cuaca) melalui penyelarasan deret multi-skala berbasis transformasi Fourier (FFT) dan blok *Graph-FC*. Meskipun keduanya secara eksplisit memodelkan jeda antar-node, bobot jeda pada MillGNN dan SAMSGL diturunkan semata dari kemiripan atau penyelarasan sinyal pada jendela input deret waktu, **tanpa pengondisian terhadap variabel iklim fisik eksogen di node asal** dan tanpa evaluasi pada pergeseran rezim iklim OOD.

Di luar domain pasar pangan, **CRAFormer** (Zhang dkk., *Entropy* Vol. 28 No. 1, 2025/2026) membangun *Dynamic-Lag Causal Graphs* (DAG waktu-terbuka per lag) dengan *role-aware gating* dan curah hujan lokal sebagai penggerak fisik untuk memprediksi pergeseran tanah longsor (*landslide displacement*). Kendati CRAFormer menggabungkan jeda waktu dan curah hujan, fokusnya adalah mekanika fisik satu situs geoteknik (bukan jaringan harga multiregional antarprovinsi) dengan peran kausal semi-statis dan tanpa uji pergeseran rezim makro ENSO maupun kesalahan spesifikasi prior perdagangan.

---

## 2.3 Kelompok 3: Ketahanan Pergeseran Distribusi, Rezim, dan Fusi Graf Statis-Dinamis (*OOD & Robustness*)

Untuk merespons ketidakstasioneran (*non-stationarity*) relasi antar-node, literatur peramalan spatio-temporal umum mengembangkan mekanisme adaptasi relasi dan gerbang fusi statis-dinamis. **DRAN** (*arXiv:2504.01531*, 2025) memadukan adaptasi distribusi dengan cabang relasi statis dan adaptif, sementara **SDGF** (*arXiv:2509.18135*, 2025) menggunakan *attention gate* untuk menggabungkan graf statis dan korelasi dinamis multi-skala. Pada jalur ketahanan OOD, **STEVE** (Ji dkk., *KDD* 2025) bersama **DynaSTar** (Hao dkk., *IJCAI* 2026) memodelkan *unseen confounder* secara laten melalui representasi basis untuk menjaga ketahanan prediksi trafik perkotaan pada pergeseran distribusi ruang-waktu.

Keempat studi tersebut menegaskan bahwa konsep graf adaptif, mekanisme *static-dynamic gating*, dan regularisasi invarian telah mapan di literatur umum—sehingga penelitian ini **tidak** mengklaim mekanisme *gating* atau adaptasi tersebut sebagai kebaruan arsitektur umum. Perbedaan mendasarnya adalah bahwa DRAN, SDGF, dan STEVE/DynaSTar dirancang untuk domain umum atau trafik perkotaan dengan gangguan/confounder yang diperlakukan sebagai **faktor laten**, belum mengondisikan distribusi jeda per edge pada variabel iklim fisik yang teramati, serta belum menguji ketahanan gabungan antara pergeseran rezim iklim fisik dan kesalahan spesifikasi prior jaringan perdagangan.

---

## 2.4 Kelompok 4: Harga Pangan, Jeda Cuaca Wilayah Sumber, dan Dinamika Iklim/ENSO

Dalam literatur ekonomi pertanian dan inflasi pangan tropis, anomali curah hujan, kekeringan berkepanjangan, dan siklus ENSO (El Nino–Southern Oscillation) diketahui memengaruhi pasokan dan volatilitas harga komoditas hortikultura secara tidak simetris antardaerah. Di Indonesia, data panel harian Pusat Informasi Harga Pangan Strategis (PIHPS Bank Indonesia) dan pemetaan koridor perdagangan antarprovinsi BPS (Poldis 2022) menunjukkan konsentrasi sentra pemasok cabai di sejumlah provinsi utama yang memasok wilayah defisit lintas pulau. Secara khusus, studi terbaru mengenai **harga teh Sri Lanka** (*arXiv:2608.24894*, 2026) memperlihatkan bahwa memasukkan fitur cuaca berjeda ($1$–$3$ minggu) yang berasal dari **wilayah perkebunan sumber** meningkatkan akurasi prediksi harga komoditas. Namun, pendekatan tersebut dibangun sebagai model deret waktu tanpa struktur graf spasial antarwilayah, tanpa pembelajaran bobot/jeda dinamis per pasangan wilayah, dan tanpa uji stratifikasi rezim iklim ekstrem maupun perturbasi prior perdagangan.

---

## 2.5 Ringkasan Matriks Positioning (11 Paper Terdekat vs Studi Ini)

Ringkasan perbandingan terhadap 11 studi terdekat di bawah ini diturunkan langsung dari matriks terverifikasi `docs/positioning.md` (seluruh klaim baris *Studi ini* berada dalam **Kategori AMAN** sesuai Brief v2 §6):

| Paper | Kelompok | Graph Berarah & Dinamis | Jeda per Edge ($\ell$) | Kondisi Pembentuk Graph | Iklim Eksogen | Uji OOD Rezim Iklim | Uji Prior Graf Keliru |
| :--- | :---: | :---: | :--- | :--- | :--- | :---: | :---: |
| **RCSGNet** (2026) | 1 | Ya / Ya | Tidak | Laten (state pasar dari harga) | Tidak (*price-only*) | Tidak | Tidak |
| **MarketDNA** (2026) | 1 | Ya / Ya | Tidak | Laten diskret (token harga) | Tidak (*price-only*) | Tidak | Tidak |
| **CGNN** (2023) | 1 | Tidak / Tidak | Tidak | Statis (lokasi) | Ya (fitur node saja) | Tidak | Tidak |
| **Min et al.** (2025) | 1 | Ya / Ya | Tidak | Laten (*self-attention* multivariat) | Ya (fitur node saja) | Tidak | Tidak |
| **MillGNN** (2025) | 2 | Ya / Ya | Ya (peluruhan $-\lambda\ell$) | Teramati dari jendela input | Tidak | Tidak | Tidak |
| **SAMSGL** (2023) | 2 | Ya / Ya | Ya (FFT *series-aligned*) | Teramati dari jendela input | Tidak (pada graf harga) | Tidak | Tidak |
| **CRAFormer** (2025/2026) | 2 | Ya / Semi-statis | Ya (DAG lokal longsor) | Peran kausal *d-separation* | Ya (hujan lokal longsor) | Tidak | Tidak |
| **DRAN** (2025) | 3 | Ya / Ya | Tidak | Laten / gate statis-dinamis | Tidak | Tidak | Tidak |
| **SDGF** (2025) | 3 | Ya / Ya | Tidak | *Attention gate* statis-dinamis | Tidak | Tidak | Tidak |
| **STEVE** (2025) / DynaSTar | 3 | Ya / Ya | Tidak | *Confounder* laten (trafik) | Tidak langsung | OOD trafik | Tidak |
| **Teh Sri Lanka** (2026) | 4 | Tidak ada graf | Jeda fitur 1–3 minggu | Tanpa graf | Ya (cuaca wilayah sumber) | Tidak | Tidak |
| **Studi ini (Renaro, 2026)** | **1–4** | **Ya / Ya ($j \to i$)** | **Ya (`n_lags = 6` riil [A1]; `L = 8` sintetis; + `null`)** | **Teramati: iklim fisik provinsi asal ($c_{j,\le t}$)** | **Ya (asal & lokal, `available_at <= t`)** | **Ya (5 rezim + *Worst-Regime MAE*)** | **Ya (perturbasi `bps_mask` 10–50% + `none`)** |

---

## 2.6 Posisi Penelitian (*Positioning Statements*)

Berdasarkan sintesis literatur di atas dan batas klaim Brief v2 §6, posisi studi ini dirumuskan dalam tiga kalimat resmi berikut:

1. **Kebaruan Formulasi Inti (Kategori AMAN)**:  
   *Sepengetahuan kami*, belum ada model *spatio-temporal graph neural network* (ST-GNN) antarprovinsi untuk peramalan harga komoditas pangan strategis di Indonesia yang secara eksplisit mengondisikan **distribusi probabilitas jeda transmisi per edge berarah** (`n_lags = 6` bin pentad pada data riil sesuai Amandemen `A1` di `docs/protocol_amendments.md` dan `L = 8` bin pada uji sintetis, beserta slot tidak-aktif/`null`) pada **indikator iklim fisik yang teramati di provinsi asal/pemasok** ($c_{j,\le t}$: anomali curah hujan pentad CHIRPS v3, durasi hari kering beruntun, kejadian hujan ekstrem, dan indeks ENSO RONI).
2. **Kontribusi Benchmark dan Uji Ketahanan (Kategori AMAN)**:  
   *Sepengetahuan kami*, studi ini merupakan kerangka benchmark harga cabai antarprovinsi Indonesia pertama yang menyatukan aturan bebas kebocoran waktu (*availability-safe* melalui `available_at <= t`), stratifikasi evaluasi lintas lima rezim iklim fisik (`dry`, `extreme_wet`, `el_nino`, `la_nina`, `normal`) dengan metrik `Worst-Regime MAE`, perbandingan *head-to-head* terhadap model rezim laten berbasis harga (ala RCSGNet) pada *backbone* identik dan anggaran pelatihan seragam (`epochs = 10`, Amandemen `A4`, dibekukan pada tag `gate2-freeze` sesuai `docs/decisions/GATE2.md` dengan `best_baseline_on_validation = lgbm_c`, sementara evaluasi holdout `>= 2026-06-01` menanti eksekusi tunggal `CGS-H6-01`), serta uji ketahanan terkontrol terhadap kesalahan spesifikasi prior graf perdagangan (`bps_mask` perturbasi $10\%$–$50\%$).
3. **Batas Klaim Jujur (Kategori JANGAN DIKLAIM)**:  
   Kami secara eksplisit **tidak** mengklaim konsep umum pembelajaran graf berarah/adaptif, mekanisme *static-dynamic gating*, regularisasi invarian, ataupun penyertaan variabel cuaca ke dalam GNN harga pertanian sebagai penemuan arsitektur umum yang baru; seluruh bobot edge dan distribusi jeda yang dipelajari diinterpretasikan secara ketat sebagai **dependensi prediktif berarah yang bergantung pada kondisi iklim**, bukan sebagai bukti kausalitas struktural ataupun estimasi arus pasokan fisik.
