# Data Card — dataset_v1

> **Status:** FINAL v1 (MDE-H5-02) · **Tanggal:** 2026-11-27 · **Penulis:** MDE (Dio) · **QA:** MDE ✅, CGS (Fariq) ✅ · **Gate 1:** GO penuh (`docs/decisions/GATE1.md`, 2026-11-25)
> **Dataset:** `data/processed/dataset_v1/` · **tag:** `dataset-v1` (`27d0b8f`) · **kode build:** `62557c9` · **split_hash (loader MLE):** `411aec1a05c90fd698b2aa5aee84a03353e69b1e1d08a088ae78311124bd90ea`
>
> **Hash final (content_hash, tidak bergantung byte parquet):**
> panel `fceeecbf5e9fc59be45274abd448402134b7121cade13c20b234529cd6a1e9de` ·
> target `82ae4682f0a68e6f3b13446774c1e0e9c947b243544fbc902f91443c3f64c624` ·
> nodes `f09b2776026f77813619c8e5ee1f7d95f8c6d79ce04a1546e66922142981e47a` ·
> bps_mask `c3719e4e79f1156d8f32ae5d92f4f061a2e06cfdeee6013c4a60634cde817226`
>
> Semua angka dapat direproduksi dari repo: `python scripts/make_dataset.py --config configs/data/v1.yaml --skip-download --skip-climate`
> (bagian 8). Laporan QA: `reports/qa/dataset_v1.md`. Kerangka: *Datasheets for Datasets* (Gebru dkk.).
> Menggantikan `docs/data_card_draft.md` (MDE-H3-02).

---

## 1. Motivasi

- **Tujuan.** Panel harian *availability-safe* untuk memprediksi harga eceran cabai merah keriting di 34 provinsi Indonesia pada horizon 5/10/20 hari kerja, dengan fitur iklim (CHIRPS, RONI) dan prior graph antarprovinsi (mask BPS Poldis 2022). Dipakai untuk RQ0 dan model graph dinamis Sprint 1 *Climate-Conditioned Dynamic Graph Learning for Food Price Forecasting Under Extreme Weather and Climate Regime Shifts*.
- **Pembuat.** Tim Renaro Lab Sprint 1 (`renaro-labs/rawit`): MDE (harga, kalender, mask BPS, merge), CGS (iklim, RONI, bobot produksi, segel holdout), MLE (loader), RL (protokol, keputusan).
- **Pendanaan.** Belum diisi RL (lihat Pertanyaan terbuka #1).
- **Bukan untuk.** Identifikasi kausal (mis. "hujan menyebabkan kenaikan harga"), estimasi volume/arus pasokan antarprovinsi, atau keputusan harga tingkat pasar/kabupaten.

## 2. Komposisi

| Item | Nilai |
|---|---|
| Unit observasi | provinsi (`prov_code` BPS 2 digit, struktur lama 34 provinsi) × hari kerja PIHPS |
| Hari kerja PIHPS | tanggal dengan harga valid dari ≥ 50% provinsi (≥ 17), dari data (`calendar.is_workday_pihps`) |
| Periode panel | 2017-07-03 .. 2026-05-29 (diminta 2017-07-01 .. 2026-05-31); 2.242 hari kerja |
| Holdout | ≥ 2026-06-01 **TERSEGEL** (CGS-H3-02, `docs/holdout_seal.md`); tidak ada di dataset ini |
| Baris | `panel.parquet` 76.228 = 2.242 × 34, 36 kolom · `target.parquet` 76.228 (grid penuh) |
| Target | harga eceran pasar tradisional (PIHPS tipe 1), Rp/kg; teramati 74.929 (98,3%), sisanya NaN, **tidak diimputasi** |
| Node | 34/34 `include=True` (cakupan ≥ 90% pada ≥ 5 tahun 2018–2025; semua provinsi 8/8 tahun) — `nodes.csv` |
| Graph prior | `bps_mask.npy` 34×34 uint8, `A[i,j]=1` bila j → i; 99 edge, densitas 8,82%. Varian lain + perturbasi: bagian 5 |
| Fitur | 36 kolom panel, semuanya terdaftar di `dataset_v1/feature_dict.csv` (tabel 2.1) |

### 2.1 Fitur (rujukan baris `dataset_v1/feature_dict.csv`)

Baris = nomor baris file (header = baris 1). Peran: `feature` boleh jadi input model; `meta`/`avail` untuk audit; `target_*` hanya target.

| Baris | Kolom | Peran | Sumber | Aturan tersedia | % missing |
|---:|---|---|---|---|---:|
| 2 | `price` | target_same_day | PIHPS t1 | observasi hari itu (loader MLE menggeser H+1) | 1,70 |
| 3 | `is_observed` | target_mask | PIHPS t1 | observasi hari itu | 0 |
| 4 | `price_lag__avail` | avail | – | – | 0,28 |
| 5 | `price_lag1` | feature | PIHPS t1 | as-of next_workday | 0,28 |
| 6 | `price_obs_date` | meta | PIHPS t1 | as-of next_workday | 0,28 |
| 7 | `price_logret5` | feature | PIHPS t1 | as-of next_workday | 0,52 |
| 8 | `price_logret20` | feature | PIHPS t1 | as-of next_workday | 1,24 |
| 9 | `price_logmean20` | feature | PIHPS t1 | as-of next_workday | 0,73 |
| 10 | `price_logstd20` | feature | PIHPS t1 | as-of next_workday | 0,73 |
| 11 | `prod_price__avail` | avail | – | – | 23,78 |
| 12 | `prod_price_lag1` | feature | PIHPS t4 (produsen) | as-of next_workday | 23,78 |
| 13 | `prod_price_obs_date` | meta | PIHPS t4 | as-of next_workday | 23,78 |
| 14 | `climate__avail` | avail | – | – | 0 |
| 15 | `rain_mm` | feature | CHIRPS v3 final_sat | akhir pentad + 2 hari | 0 |
| 16 | `rain_pentad_mm` | feature | CHIRPS v3 final_sat | akhir pentad + 2 hari | 0 |
| 17 | `rain_pentad_anom` | feature | CHIRPS v3 final_sat | akhir pentad + 2 hari | 0 |
| 18 | `rain_30d_anom` | feature | CHIRPS v3 final_sat | akhir pentad + 2 hari | 4,28 |
| 19 | `dry_spell_days` | feature | CHIRPS v3 final_sat | akhir pentad + 2 hari | 0 |
| 20 | `extreme_5d` | feature | CHIRPS v3 final_sat | akhir pentad + 2 hari | 0 |
| 21 | `climate_pentad_date` | meta | CHIRPS v3 final_sat | akhir pentad + 2 hari | 0 |
| 22 | `roni__avail` | avail | – | – | 0 |
| 23 | `roni` | feature | NOAA CPC RONI | vintage / konservatif +3 bulan | 0 |
| 24 | `roni_delta` | feature | NOAA CPC RONI | vintage / konservatif +3 bulan | 0 |
| 25 | `roni_season_month` | meta | NOAA CPC RONI | vintage / konservatif +3 bulan | 0 |
| 26–35 | `is_holiday`, `is_cuti_bersama`, `is_ramadan`, `days_to_lebaran`, `days_to_iduladha`, `is_natal_tahunbaru`, `is_post_lebaran`, `dow`, `month`, `doy` | feature | `calendar.csv` (SKB 3 Menteri, isbat Kemenag) | diketahui di muka | 0 |

Kunci `date`, `prov_code` tidak didaftarkan sebagai fitur. Peta famili fitur CGS (24 fitur, 7 famili availability) ada di `docs/feature_dict.csv`.

### 2.2 Missing (pola yang diketahui)

Matriks lengkap fitur × provinsi: `reports/qa/dataset_v1_missing.csv`.

- `price` 1,70%: hari tanpa laporan PIHPS untuk provinsi itu, atau titik spike-and-revert yang dibuang cleaning. Terburuk Maluku Utara 4,2%, DI Yogyakarta 3,9%, NTT 3,6%.
- Fitur harga as-of (0,3–1,2%): awal panel Jul 2017 (hanya 27 provinsi melapor) dan 20 observasi pertama untuk `logret20`.
- `prod_price_lag1` 23,78%: harga produsen (tipe 4) baru ada sejak 2019; DKI Jakarta dan Bali tidak punya harga produsen (100% missing), Maluku Utara 82,3%.
- `rain_30d_anom` 4,28%, **seragam 4,3% di semua provinsi**. Dicek di `climate_features.parquet` (1.088 baris NaN): setiap tahun **pentad 2–4 Januari** (±1–20 Jan) kosong di semua provinsi, ditambah pentad 1 & 5 tahun 2017. Penyebab: baseline klimatologi hanya 2017, dan akumulasi 30 hari (6 pentad) untuk awal Januari 2017 tidak punya pentad Desember 2016 sebelumnya, sehingga klimatologi pentad-of-year 2–4 tidak terdefinisi dan jendela ±2 pentad tidak melingkar ke Desember. Akibat praktis: ±15 hari kerja per tahun tanpa `rain_30d_anom` (fitur lain lengkap). Perbaikan (milik CGS): perpanjang baseline ke 2008–2017 atau jendela melingkar.
- Fitur iklim lain, RONI, dan kalender: 0%.

## 3. Proses pengumpulan

| Sumber | Versi / edisi | Tanggal akses | Cara | Catatan |
|---|---|---|---|---|
| **PIHPS** (Bank Indonesia), cabai merah keriting `com_14` | tipe 1 (pasar tradisional), tipe 4 (produsen); laporan harian, tingkat provinsi | 2026-11-24 (18 file, HTTP 200; `data/raw/pihps/manifest.csv`) | `GET .../hargapangan/WebSite/TabelHarga/GetGridDataKomoditas`, satu request per tahun kalender, jeda ≥ 5 detik; parameter di `docs/sources/pihps_endpoint.md` | Tipe 1: 2017-07..2026-05; tipe 4: 2019..2026-05. Jul 2017 hanya 27 provinsi. Respons mentah + sha256 di manifest. |
| **SP2KP** (Kemendag) | `variant_ids=2`, level provinsi | 2026-11-24 (114 file; `data/raw/sp2kp/manifest.csv`) | `POST api-sp2kp.kemendag.go.id/report/api/average-price/export-area-daily-json`; `docs/sources/sp2kp_endpoint.md` | **Validasi saja**, tidak masuk panel. 2024-02..2026-05. Kode Kemendagri (Papua pemekaran) dipetakan ke 34 provinsi lama dengan agregasi. |
| **CHIRPS v3.0** (Climate Hazards Center, UCSB) | daily `final/sat` (utama); `prelim/sat` hanya untuk simulasi rilis | ±2026-11-23 (CGS-H1-01; final terakhir di CHC 2026-10-31) | subset Indonesia 0,05°, 2017-01..2026-05; `reports/qa/chirps_download.md` | Rata-rata provinsi berbobot produksi (2017–2024 bobot luas; 2025–26 bobot produksi kab 2024). CHIRPS harian adalah disagregasi pentad. |
| **NOAA CPC RONI** (ERSSTv6, base 1991–2020) | `RONI.ascii.txt`, vintage 2026-11-22 | 2026-11-22 | `data/raw/enso/roni_vintage_log.csv`; `reports/qa/roni.md` | Tidak ada arsip vintage historis → `available_at` konservatif awal bulan (center + 3). Shared 915 musim s/d FMA 2026; 6 musim berikutnya tersegel. Nilai dapat direvisi ~2 bulan. |
| **BPS** — *Distribusi Perdagangan Komoditas Cabai Merah di Indonesia 2022* (Poldis) | rilis 24 Okt 2022, katalog 8201019 | PDF di `data/raw/bps/` (2026-11-24) | digitasi RL+MDE, diverifikasi PyMuPDF (MDE-H2-03) | Mask biner, **bukan bobot**; tanpa persentase per provinsi. |
| **BPS / Satudata Pertanian** — produksi cabai | kab/kota 2024 (Satudata dataset 392); provinsi 2017–2023 (BPS WebAPI var 61) | CGS-H1-03 (2026-11-23) | `data/raw/bps/README.md` | Bobot produksi untuk agregasi hujan; aturan tahun y dipakai mulai y+1; data terakhir 2024. |
| Kalender | SKB 3 Menteri (libur & cuti bersama), sidang isbat Kemenag, library `holidays==0.109` | MDE-H2-02 | `data/ref/religious_dates.csv` (setiap baris `source_url`), `data/ref/cuti_bersama.csv` | Sumber resmi menang bila berbeda dengan library. |

## 4. Pra-pemrosesan

**Harga (MDE-H2-01, `reports/qa/prices_clean.md`, parameter `configs/data/v1.yaml`).**
- Nama provinsi → `prov_code` lewat `data/ref/provinces.csv`; nama tak dikenal menghentikan proses. 261 baris rusak (`Dum`) dibuang.
- Outlier deret: median bergulir 21 hari kerja (terpusat) pada log harga per (provinsi, tipe); deviasi bila |log p − median| > 5·MAD (lantai 0,02).
- **Yang dibuang** (`price` = NaN): hanya spike-and-revert (≤ 2 hari kerja searah, diapit titik normal) di luar jendela Idulfitri..+10 hari: 790 titik (0,591%).
- **Yang hanya di-flag** (tidak dibuang): batas level [5.000, 250.000] Rp/kg, `flag_post_lebaran` (4.435), `flag_carry_forward` ≥ 10 nilai identik (tipe 1: 2,3%; tipe 4: 95,1% — sifat sumber).
- Flag **tidak** masuk `target.parquet`; perlakuannya keputusan terbuka RL (Gate 1/2).
- Validasi silang SP2KP 2024–2026: `reports/qa/sp2kp_crosscheck.csv`.

**Kalender (MDE-H2-02).** 2017-01-01..2026-12-31 tanpa celah; Ramadan, Idulfitri, Iduladha dari isbat; cuti bersama dari SKB; `is_workday_pihps` dari data PIHPS di dalam rentang data, dari aturan di luar.

**Aturan `available_at` (dikunci di `reports/qa/availability.csv`, ALL-H1-01).**

| Famili | Aturan | Lag |
|---|---|---|
| Harga PIHPS (t1, t4) | `next_workday`: harga hari t dipakai mulai hari kerja PIHPS berikutnya | 1 hari kerja |
| CHIRPS final_sat | `pentad_end_plus_lag`: akhir pentad + 2 hari (Opsi B, keputusan RL) | 2 hari |
| CHIRPS prelim_sat | `release_timestamp` (sensitivitas) | 5 hari |
| RONI | `vintage_or_conservative_3m`: awal bulan (center_month + 3) | ±3 bulan |
| Bobot produksi | `year_plus_1` | 1 tahun |
| Kalender | `known_in_advance` | – |

**Merge (MDE-H3-01, `src/renaro/data/dataset_v1.py`).** Kerangka hari kerja PIHPS × 34; harga lag, iklim, RONI digabung dengan `merge_asof(date ← available_at, backward)` per provinsi (RONI nasional); kalender join langsung pada `date`. Kolom `<sumber>__avail` disimpan untuk audit. Uji kebocoran (`tests/test_no_leakage.py`): `*__avail ≤ date`, tanpa tanggal ≥ 2026-06-01, tanpa kolom regime/label, dan uji truncation di 4 tanggal T (input dipotong di T → baris ≤ T identik) — semua lulus.

**QA dataset (MDE-H3-01, `reports/qa/dataset_v1.md`, ditandatangani MDE + CGS 2026-11-25).**
- 10/10 uji kebocoran lulus: 4 kolom `*__avail ≤ date`, `max(date) = 2026-05-29 < 2026-06-01`, 0 kolom regime/label, uji truncation di 4 tanggal T identik bit-for-bit.
- CGS: 6 fitur iklim identik dengan baris `final_sat` yang dipilih `climate__avail` (0 mismatch dari 76.228 baris); RONI identik dengan tabel vintage (0 mismatch); lag maksimum iklim 5 hari, RONI 30 hari.
- Loader MLE (`validate_dataset` + `load_panel`): OK; `tests/test_loader.py` lulus di mesin MDE.
- Gate 1 (RL, 2026-11-25): cakupan 34/34 provinsi × 8/8 tahun (98,30%), iklim & RONI lengkap di 34 node, uji bocor lulus → **GO penuh**.

**Mask BPS (MDE-H2-03, `reports/qa/bps_mask.md`).** Union kotak "pembelian dari" dan "penjualan ke" luar provinsi per bab provinsi; diagonal 0; luar negeri dibuang. 99 edge berarah, densitas 8,82% (ekspektasi tim ±14%; tidak ada edge yang diinferensikan). Verifikasi ganda: bilateral 96/99 simetris (3,03% satu kotak; 2 salah cetak BPS terkonfirmasi narasi) dan teks PyMuPDF vs entri 195/195 cocok. Papua (94) tanpa asal/tujuan antarprovinsi.

## 5. Graph prior & perturbasi (MDE-H4-01, MDE-H4-02)

Semua matriks 34×34, urutan node = `nodes.csv` = `PROV_CODES`, konvensi `A[i, j]` = asal j → tujuan i, diagonal 0. Array `.npy` di `data/processed/graph_priors/` dan `data/processed/perturbations/` (tidak di git; disinkron lewat Underleaf/zip); `meta.json` dan `index.csv` ter-track.

| Varian | Edge | Densitas | Aturan / parameter |
|---|---:|---:|---|
| `bps` | 99 | 8,8% | salinan `dataset_v1/bps_mask.npy` (BPS Poldis 2022) |
| `distance` | 170 | 15,2% | w = exp(−(d/σ)²), σ = 1.337,8 km (median jarak), k = 5 asal terdekat per tujuan; jarak haversine antar centroid berbobot produksi kab 2024 (`distance_km.npy` mentah, 56–4.577 km) |
| `surplus_deficit` | 115 | 10,2% | j → i bila j surplus (pangsa produksi cabai besar 2017 > pangsa penduduk SP2020), i defisit, j di 5 surplus terdekat i; 11 provinsi surplus |
| `none` | 1.122 | 100% | kandidat penuh (graph dipelajari) |

Catatan prior: dengan aturan surplus–defisit, **Jawa Timur dan Sulawesi Selatan berstatus defisit** walaupun di Poldis 2022 keduanya pemasok terbesar (16 dan 9 tujuan); hanya 16 dari 115 edge `surplus_deficit` juga ada di `bps`. Status 4 provinsi (16, 18, 52, 65) berubah bila memakai rata-rata produksi 2017–2024 (`meta.json`). Tahun 2017 dipakai karena satu-satunya yang tersedia sebelum train (aturan y+1).

**Perturbasi** (`renaro.graph.perturb`, dasar `bps`, 3 operasi × p ∈ {10,…,50}% × seed {0,1,2} = 45 matriks, `perturbations/index.csv`): `drop` menghapus round(p·m) edge, `add` menambah round(p·m) non-edge, `rewire` memindah asal round(p·m) edge ke asal baru yang bukan edge asli (in-degree tetap). Jaccard vs base (rata-rata seed) turun monoton:

| op | 10% | 20% | 30% | 40% | 50% |
|---|---:|---:|---:|---:|---:|
| drop | 0,899 | 0,798 | 0,697 | 0,596 | 0,495 |
| add | 0,908 | 0,832 | 0,767 | 0,712 | 0,664 |
| rewire | 0,817 | 0,664 | 0,535 | 0,424 | 0,329 |

drop/add identik dengan `masks.npz` stopgap MLE (dipakai `scripts/robustness.py`); rewire stopgap memindah 1–2 edge lebih sedikit pada p ≥ 20%.

## 6. Penggunaan

- **Untuk prediksi**, dibaca lewat loader MLE (`renaro.data.io.load_panel`, `renaro.data.datasets.WindowDataset`); tidak ada CSV pribadi. Split resmi: `renaro.contract.ORIGINS` (O1–O3; holdout SEALED).
- **`panel.price` adalah harga hari itu** (sama dengan target), sesuai kontrak §2.7; loader MLE menggesernya 1 hari kerja. Model di luar loader harus memakai fitur as-of (`price_lag1`, `price_logret*`, …), bukan `price`.
- **Edge ≠ arus pasokan.** Mask BPS hanya menandai pasangan provinsi yang tercetak di Poldis 2022 (satu tahun survei); edge yang dipelajari model adalah dependensi prediktif, bukan volume atau arah perdagangan.
- **Label regime hanya untuk evaluasi.** `regime_labels` (CGS-H2-04) dan fase/episode ENSO tidak ada di panel dan dilarang menjadi fitur.
- **Jangan dipakai untuk klaim kausal** atau untuk menyimpulkan harga di tingkat kabupaten/pasar.
- **Batasan:** baseline klimatologi hanya 2017; produksi terakhir 2024; mask dari satu tahun (2022); harga produsen tidak tersedia di beberapa provinsi; RONI tanpa vintage historis asli.

## 7. Distribusi & lisensi

- **PIHPS (Bank Indonesia):** situs mencantumkan "Hak Cipta – Semua Hak Dilindungi". **Data mentah dan panel harga tidak diredistribusi** di GitHub; `data/raw`, `data/interim`, `data/processed` di-gitignore. Di repo hanya metadata: `dataset_v1/{SHA256SUMS,VERSION,feature_dict.csv}`, `graph_priors/{meta.json,centroids.csv,surplus_deficit_shares.csv}`, `perturbations/index.csv` (mask BPS turunan publikasi BPS, bukan data harga). Pertukaran data antaranggota tim lewat zip internal (`scripts/mde/make_handoff_zip.py`, menolak file holdout).
- **SP2KP (Kemendag):** hanya validasi; tidak diredistribusi.
- **BPS:** atribusi wajib ("Sumber: Badan Pusat Statistik") untuk Poldis 2022 dan data produksi.
- **CHIRPS:** sitasi Climate Hazards Center (UCSB) sesuai halaman produk CHIRPS v3; teks sitasi resmi v3 menunggu CGS (Pertanyaan terbuka #3).
- **NOAA CPC RONI:** sebutkan NOAA Climate Prediction Center sebagai sumber.
- **Rilis publik:** kode + data turunan/agregat saja; keputusan akhir RL (MDE-H7-01).

## 8. Keterbatasan & hasil uji reproduksi

**Keterbatasan utama**
1. **Struktur 34 provinsi lama.** Node = kode BPS 2 digit sebelum pemekaran 2022; Papua Barat (91) dan Papua (94) mencakup provinsi baru (Papua Barat Daya, Papua Tengah, Papua Pegunungan, Papua Selatan). Sumber berkode baru (SP2KP) diagregasi ke 34 node (`is_aggregated`).
2. **Hari kerja saja.** Panel hanya berisi hari kerja PIHPS (≥ 50% provinsi melapor; 2.242 hari). Akhir pekan, libur nasional tanpa laporan, dan sebagian cuti bersama tidak ada; horizon 5/10/20 = hari kerja, bukan hari kalender.
3. **CHIRPS harian adalah disagregasi pentad.** Variasi di dalam pentad bukan observasi; fitur dipakai di level pentad/30 hari. Baseline klimatologi hanya 2017 (pola missing `rain_30d_anom` awal Januari, bagian 2.2). Iklim dirata-rata berbobot produksi (2017–2024 bobot luas, 2025–2026 produksi kab 2024).
4. **Mask BPS biner, satu tahun (Poldis 2022).** Tidak ada bobot/volume, tidak ada persentase per provinsi; pola 2022 dianggap berlaku 2017–2026. Dua salah cetak diagram BPS tetap dimuat (aturan "put 1 for every printed link"); filter `n_confirmations == 2` untuk 97 edge bersih. Papua (94) tanpa edge.
5. **Lain:** harga produsen (t4) tidak ada untuk DKI dan Bali; RONI tanpa arsip vintage historis (lag konservatif +3 bulan); produksi terakhir 2024; flag cleaning tidak masuk target (perlakuan menunggu RL).

**Uji reproduksi (MDE-H5-01, `scripts/make_dataset.py`, README bagian 3)** — dari JSON PIHPS/SP2KP mentah, PDF BPS, dan iklim CGS:

| Mesin | Perintah | Hasil |
|---|---|---|
| MDE · Windows, Python 3.14, pandas 3.1 | `--skip-download --skip-climate` | **REPRODUCED OK** (4/4 content_hash identik; 67 test; 27 s; run kedua semua tahap dilewati) |
| MDE · Linux, Python 3.10, pandas 2.3 | `--skip-download --skip-climate` | **REPRODUCED OK** |
| MDE · Linux, Python 3.10, pandas 2.3 | `--skip-download` (iklim CGS dihitung ulang dari CHIRPS) | **REPRODUCED OK (numerik)**: 4 kolom iklim beda ≤ 4·10⁻¹⁰ (pembulatan floating-point), kolom lain identik |
| CGS · clone bersih | `--skip-download --skip-climate` | menunggu |

## 9. Pemeliharaan

| Item | Nilai |
|---|---|
| Versi | `v1` (beku) — tag `dataset-v1` @ `27d0b8f` |
| Hash isi | panel `fceeecbf5e9f…`, target `82ae4682f0a6…`, nodes `f09b2776026f…`, mask `c3719e4e79f1…` (lengkap di `VERSION`) |
| Hash file | `data/processed/dataset_v1/SHA256SUMS` (LF; valid di Windows/Linux) |
| Reproduksi | `python scripts/make_dataset.py --config configs/data/v1.yaml --skip-download --skip-climate` → `REPRODUCED OK` (bagian 8); `content_hash` sama di pandas 2.3 / 3.0 / 3.1 |
| Uji | `pytest tests/test_no_leakage.py tests/test_build_dataset.py tests/test_graph_priors.py tests/test_perturb.py` |
| Artefak turunan | `data/processed/graph_priors/meta.json` (sha256 tiap array), `data/processed/perturbations/index.csv` (sha256 tiap matriks) |
| Kontak | MDE: @dio · iklim: CGS · keputusan: RL |
| Perubahan | Setelah beku hanya lewat versi baru (`v1.1`, …) + catatan di `docs/data_card.md`; holdout hanya dibuka CGS-H6-01 dengan skrip yang sama (`--allow-holdout`). |

### Pertanyaan terbuka

1. Pendanaan (RL).
2. Perlakuan flag carry-forward / post-Lebaran pada target dan evaluasi (RL; saat ini tidak dipakai loader).
3. Teks sitasi resmi CHIRPS v3 dan lisensi rilis data turunan (CGS, RL; MDE-H7-01).
4. Perpanjangan baseline klimatologi untuk menutup `rain_30d_anom` awal Januari (CGS; butuh dataset v1.1).
5. Uji reproduksi mesin kedua oleh CGS (bagian 8).

### Riwayat

| Versi | Tanggal | Perubahan |
|---|---|---|
| draft | 2026-11-25 | MDE-H3-02, 7 bagian |
| v1 | 2026-11-27 | MDE-H5-02: hash final + split_hash, QA & tanda tangan CGS, Gate 1, graph prior + perturbasi, keterbatasan, hasil uji reproduksi, penjelasan missing `rain_30d_anom` |
