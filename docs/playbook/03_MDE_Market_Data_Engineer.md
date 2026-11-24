# 03 · MDE: Market Data Engineer

> **Tanggung jawab (brief §9):** panel PIHPS, cleaning, kalender, mask BPS, varian prior, pipeline reproducible.
> **Kepemilikan kunci:** Dataset v1; data card.
> **Posisi di jalur kritis:** MDE-H1-01 → MDE-H2-01 → MDE-H3-01 **ada di jalur kritis**. Keterlambatan 1 jam di sini menggeser Gate 1. Prioritaskan job ini di atas semua job lain.

## Ringkasan job

| ID | Hari | Job | Mode | Output utama |
|---|---|---|---|---|
| ALL-H1-01 | H1 pagi | Kickoff (notulen) + buat `provinces.csv` | SEKUENSIAL | `docs/data_contract.md`, `data/ref/provinces.csv` |
| MDE-H1-01 | H1 | Scrape PIHPS 2017–2026, tipe 1 & 4 | PARALEL ★kritis | `data/raw/pihps/` |
| MDE-H1-02 | H1 | Tarik SP2KP 2024+ (validasi) | PARALEL | `data/raw/sp2kp/` |
| MDE-H1-03 | H1 sore | Laporan cakupan per provinsi-tahun | PARALEL | `reports/qa/coverage_pihps.{csv,md}` |
| MDE-H2-01 | H2 | Cleaning harga | PARALEL ★kritis | `data/interim/prices_clean.parquet` |
| MDE-H2-02 | H2 | Kalender Lebaran/Ramadan/libur | PARALEL | `data/interim/calendar.csv` |
| MDE-H2-03 | H2 | Digitasi mask BPS 34 provinsi | PARALEL | `data/interim/bps_mask.{csv,npy}` |
| MDE-H3-01 | H3 pagi | **Merge → dataset v1**, cek bocor, bekukan (bersama CGS) | SEKUENSIAL ★kritis | `data/processed/dataset_v1/` |
| MDE-H3-02 | H3 siang | Draft data card | PARALEL | `docs/data_card_draft.md` |
| MDE-H4-01 | H4 | Varian graph prior | PARALEL | `data/processed/graph_priors/` |
| MDE-H4-02 | H4 | Set perturbasi edge | PARALEL | `data/processed/perturbations/` |
| MDE-H5-01 | H5 | Pipeline satu perintah | PARALEL | `scripts/make_dataset.py` |
| MDE-H5-02 | H5 | Data card final | PARALEL | `docs/data_card.md` |
| MDE-H6-01 | H6 | Bagian data laporan + QA angka hasil | PARALEL | `reports/sprint1/04_data.md`, `reports/qa/numbers_check.md` |
| MDE-H7-01 | H7 | Rilis pipeline + data turunan + dokumentasi | PARALEL | `release/data/` |

---

## MDE-H1-01 · Scrape PIHPS 2017–2026 (tipe 1 dan 4)

| | |
|---|---|
| Waktu | H1 11.00–16.00 |
| Mode | PARALEL, **jalur kritis** |
| Input | Endpoint JSON publik PIHPS `GetGridDataKomoditas` (brief §7.2): `comcat_id=com_14`, `price_type_id=1` (pasar tradisional) dan `4` (produsen), tanpa API key, semua provinsi dalam satu respons |
| Tools | Browser + DevTools (tab *Network*), Python `requests`, `pandas`, `pyarrow`; rujukan scraper terbuka `github.com/gnatnib/pangan.id` |
| Handoff | MDE-H1-03, MDE-H2-01, CGS (file `_sealed`) |

**Langkah**
1. **Rekam request asli.** Buka halaman Tabel Harga PIHPS (`https://www.bi.go.id/hargapangan`) → pilih *Pasar Tradisional*, komoditas *Cabai Merah Keriting*, semua provinsi, laporan harian, rentang 1 tahun → tampilkan. Di DevTools → Network, filter `GetGridData`, klik kanan → *Copy as cURL*. Simpan di `docs/sources/pihps_request_example.txt` (hapus cookie pribadi).
2. **Identifikasi parameter** dari request tersebut: nama parameter tanggal awal/akhir, tipe laporan, provinsi, komoditas, tipe harga. Tulis di `docs/sources/pihps_endpoint.md`. Cocokkan dengan kode `pangan.id` bila ada perbedaan.
3. **Uji 1 request kecil** (1 bulan) dari Python; pastikan JSON berisi semua provinsi dan struktur kolom tanggal jelas.
4. **Tulis scraper** `src/renaro/data/pihps.py`:
   ```python
   # Kerangka. URL dan nama parameter WAJIB diisi dari hasil DevTools (langkah 1–2).
   import json, time, hashlib, datetime as dt, pathlib, requests

   BASE_URL = "<URL GetGridDataKomoditas dari DevTools>"
   OUT = pathlib.Path("data/raw/pihps")
   SEALED = OUT / "_sealed"          # periode >= holdout_start
   HOLDOUT_START = dt.date(2026, 6, 1)

   def fetch(start: dt.date, end: dt.date, price_type: int) -> dict:
       params = {
           # isi sesuai request asli, contoh nama dari brief:
           "comcat_id": "com_14",
           "price_type_id": price_type,
           # "<param_tanggal_awal>": start.strftime(...),
           # "<param_tanggal_akhir>": end.strftime(...),
           # "<param_tipe_laporan>": "<harian>",
           # "<param_provinsi>": "<semua>",
       }
       r = requests.get(BASE_URL, params=params, timeout=120,
                        headers={"User-Agent": "renaro-research-client"})
       r.raise_for_status()
       return r.json()

   def save(payload: dict, path: pathlib.Path) -> None:
       path.parent.mkdir(parents=True, exist_ok=True)
       raw = json.dumps(payload, ensure_ascii=False).encode()
       path.write_bytes(raw)
       # catat sha256 ke manifest
   ```
5. **Jadwal request** (± 1 request/tahun, jeda ≥ 5 detik):
   - Tipe 1: 2017-07-01 … 2017-12-31 (pemanasan lag), lalu per tahun 2018 … 2025, lalu 2026-01-01 … **2026-05-31**.
   - Tipe 1 periode **2026-06-01 … hari ini** → simpan ke `data/raw/pihps/_sealed/` (lihat §7 file setup). **Jangan dibuka**; cukup cek jumlah baris/ukuran.
   - Tipe 4 (produsen): 2019 … 2026-05-31 (cakupan 29 provinsi 2019, 32 provinsi 2020), plus `_sealed` untuk ≥ 2026-06-01.
6. **Simpan mentah apa adanya**: `data/raw/pihps/pt{1|4}_{YYYYMMDD}_{YYYYMMDD}.json` + `data/raw/pihps/manifest.csv` (`file, price_type, start, end, n_bytes, sha256, fetched_at, http_status`).
7. **Parser** `src/renaro/data/pihps_parse.py`: JSON → long table (`date, prov_name_raw, price_type, price_raw`). Ubah string angka (`"45.250"`/`"45,250"`) ke float; `"-"`/kosong → NaN. Simpan `data/interim/pihps_long.parquet` (tanpa `_sealed`).
8. **Serahkan file `_sealed`** ke CGS (salin ke `RENARO_SEALED_DIR` milik CGS), lalu hapus dari drive bersama. Catat checksum di `docs/holdout_seal.md` (CGS mengisi bagian penerimaan).

**Output**
| Path | Isi |
|---|---|
| `data/raw/pihps/*.json` + `manifest.csv` | Respons mentah per tahun per tipe |
| `data/interim/pihps_long.parquet` | Long table hasil parsing (< 2026-06-01) |
| `docs/sources/pihps_endpoint.md` | URL, parameter, contoh respons, tanggal akses |
| Serah-terima `_sealed` ke CGS | Checksum di `docs/holdout_seal.md` |

**DoD**
- [ ] Semua tahun 2017H2–2026-05 untuk tipe 1 ada dan `http_status=200`.
- [ ] Jumlah provinsi per file sesuai brief (27 pada Jul 2017; 34 sejak Jan 2018).
- [ ] Spot-check 3 tanggal acak × 3 provinsi cocok dengan tampilan situs.
- [ ] `max(date)` di `pihps_long.parquet` < 2026-06-01.

**Kalau macet:** endpoint menolak/berubah → (1) pakai kode `pangan.id` sebagai referensi; (2) MLE membantu (slack H1); (3) bila tetap gagal sampai H1 15.00, eskalasi ke RL; SP2KP (2024+) dipakai sementara untuk menguji pipeline, dan Gate 1 kemungkinan NO-GO data.

---

## MDE-H1-02 · Tarik SP2KP 2024+ untuk validasi silang

| | |
|---|---|
| Waktu | H1 14.00–16.30 (sambil menunggu jeda request PIHPS) |
| Mode | PARALEL |
| Input | Endpoint publik SP2KP Kemendag `average-price-public`, `variant_id=2`, sejak 1 Feb 2024; 38 provinsi + kab/kota + pasar |
| Tools | DevTools, `requests`, `pandas` |

**Langkah**
1. Rekam request dari situs SP2KP (sama seperti langkah 1–2 MDE-H1-01); dokumentasikan di `docs/sources/sp2kp_endpoint.md`.
2. Tarik level **provinsi**, Cabai Merah Keriting, 2024-02-01 … 2026-05-31; periode ≥ 2026-06-01 ke `_sealed` (sama aturannya).
3. Simpan mentah `data/raw/sp2kp/*.json` + manifest; parse ke `data/interim/sp2kp_long.parquet`.
4. Petakan 38 → 34 provinsi: provinsi pemekaran Papua digabung ke `91`/`94` dengan **rata-rata sederhana** (tandai `is_aggregated=True`). Hanya untuk validasi.

**Output:** `data/raw/sp2kp/`, `data/interim/sp2kp_long.parquet`, `docs/sources/sp2kp_endpoint.md`.
**DoD:** [ ] ≥ 30 provinsi ter-map ke kode BPS · [ ] tidak dipakai sebagai fitur/target (hanya validasi di MDE-H2-01).

---

## MDE-H1-03 · Laporan cakupan per provinsi-tahun

| | |
|---|---|
| Waktu | H1 16.00–17.00 |
| Mode | PARALEL (setelah MDE-H1-01) |
| Input | `data/interim/pihps_long.parquet` |
| Handoff | RL (kriteria data Gate 1), RL-H1-01 (node yang dievaluasi) |

**Langkah**
1. Definisikan **hari kerja PIHPS** = tanggal dengan laporan untuk ≥ 50% provinsi.
2. Untuk setiap (`prov_code`, `year`) tipe 1: `n_workdays`, `n_obs`, `coverage = n_obs / n_workdays`, `longest_gap_workdays`.
3. Hitung jumlah provinsi yang memenuhi **≥ 90% cakupan selama ≥ 5 tahun** dalam 2018–2025.
4. Buat heatmap cakupan (provinsi × tahun) `reports/qa/coverage_heatmap.png`.

**Output**
- `reports/qa/coverage_pihps.csv`: kolom `prov_code, prov_name, year, n_workdays, n_obs, coverage, longest_gap_workdays`.
- `reports/qa/coverage_pihps.md`: tabel ringkas + **kalimat kesimpulan**: "X dari 34 provinsi memenuhi kriteria data Gate 1 (ambang 20)".

**DoD:** [ ] angka X tertulis jelas · [ ] daftar provinsi yang gagal + alasannya (gap panjang, mulai terlambat).

---

## MDE-H2-01 · Cleaning harga

| | |
|---|---|
| Waktu | H2 09.15–15.00 |
| Mode | PARALEL, **jalur kritis** |
| Input | `pihps_long.parquet`, `sp2kp_long.parquet`, `data/ref/provinces.csv`, `calendar.csv` (draf dari MDE-H2-02 untuk flag pasca-Lebaran) |
| Tools | `pandas`, `numpy`, `matplotlib`, `pytest` |
| Handoff | MDE-H3-01 |

**Langkah**
1. **Pemetaan nama → kode** lewat kolom `pihps_name` di `provinces.csv`. Nama yang tidak ter-map → error, bukan diabaikan.
2. **Dedup**: kunci (`date, prov_code, price_type`). Jika duplikat berbeda nilai, ambil nilai terakhir di respons dan catat jumlahnya.
3. **Validasi dasar**: harga ≤ 0 → NaN. Harga di luar [Rp5.000, Rp250.000]/kg → `flag_outlier` (batas di `configs/data/v1.yaml`; cek dengan RL).
4. **Outlier berbasis deret** (per provinsi, pada log harga):
   - Hitung median bergulir 21 hari kerja dan MAD.
   - `flag_outlier = True` bila |log p − median| > 5·MAD **dan** pola *spike-and-revert* (lonjakan lalu kembali dalam ≤ 2 hari kerja).
   - Hanya titik spike-and-revert yang di-set `price = NaN`. Lonjakan yang bertahan (mis. pasca-Lebaran, 5–6 Mei 2022) **dipertahankan** dan diberi `flag_post_lebaran`.
   - Contoh uji: nilai nasional Rp19.000 pada 1 Feb 2022 (audit brief §7.1) harus tertandai bila juga muncul di level provinsi.
5. **Carry-forward**: nilai identik ≥ 10 hari kerja berturut-turut → `flag_carry_forward = True` (tidak dihapus; RL memutuskan perlakuan di protokol).
6. **Validasi silang SP2KP** (2024-02 … 2026-05): per provinsi hitung korelasi log-harga, median |selisih %|. Provinsi dengan median selisih > 15% dicatat.
7. **`available_at`** = hari kerja PIHPS berikutnya setelah `date`.
8. Tulis `tests/test_prices_clean.py`: kunci unik, tidak ada harga ≤ 0, `max(date) < holdout_start`, semua `prov_code` valid.
9. Laporan QA `reports/qa/prices_clean.md`: jumlah titik per flag per provinsi, 5 plot contoh (provinsi besar: 31, 32, 33, 35, 12) dengan titik flag diberi warna.

**Output**
| Path | Isi |
|---|---|
| `data/interim/prices_clean.parquet` | Skema §5.3 file setup |
| `reports/qa/prices_clean.md` + `figures/` | Ringkasan flag, plot, hasil validasi SP2KP |
| `tests/test_prices_clean.py` | Lulus |

**DoD**
- [ ] Skema persis §5.3 (nama kolom & tipe).
- [ ] `pytest tests/test_prices_clean.py` hijau.
- [ ] Proporsi titik yang di-NaN-kan < 1% (jika lebih, eskalasi ke RL; aturan mungkin terlalu agresif).

---

## MDE-H2-02 · Kalender Lebaran/Ramadan/libur

| | |
|---|---|
| Waktu | H2 (paralel dengan MDE-H2-01; ± 2 jam) |
| Mode | PARALEL |
| Input | Library `holidays` (negara `ID`), SKB 3 Menteri libur nasional & cuti bersama 2017–2026, pengumuman sidang isbat Kemenag (awal Ramadan, Idulfitri, Iduladha) |
| Tools | `pandas`, `holidays` |
| Handoff | MDE-H2-01 (flag pasca-Lebaran), MDE-H3-01 |

**Langkah**
1. Buat `data/ref/religious_dates.csv` secara **manual dari sumber resmi**: `year, ramadan_start, idulfitri, iduladha`, kolom `source_url`.
2. Buat `data/ref/cuti_bersama.csv` dari SKB 3 Menteri per tahun.
3. Generate `calendar.csv` (skema §5.4) dari `holidays.ID()` + dua file manual. Hasil `holidays` vs tabel manual dibandingkan; perbedaan dicatat dan yang dipakai adalah **sumber resmi**.
4. `is_workday_pihps` diisi dari data PIHPS (≥ 50% provinsi melapor).
5. Definisi jendela pasca-Lebaran untuk flag **[usulan default: Idulfitri s/d +10 hari kalender]**.

**Output:** `data/interim/calendar.csv`, `data/ref/religious_dates.csv`, `data/ref/cuti_bersama.csv`.
**DoD:** [ ] 2017-09-01 … 2026-12-31 lengkap tanpa celah · [ ] setiap tanggal Idulfitri punya `source_url`.

---

## MDE-H2-03 · Digitasi mask BPS 34 provinsi

| | |
|---|---|
| Waktu | H2 (± 4 jam; RL membantu verifikasi) |
| Mode | PARALEL |
| Input | `BPS0000-distribusi_perdagangan_komoditas_cabai_merah_di_indonesia_2022.pdf` (pindahkan ke `data/raw/bps/`) |
| Tools | `pymupdf` (ekstraksi teks), `pdfplumber` (tabel), spreadsheet untuk entri manual halaman raster |
| Handoff | MDE-H3-01, MDE-H4-01, MLE (RQ0 fitur asal, Modul 1 prior) |

**Konteks (brief §7.1):** PDF **tidak** punya matriks asal–tujuan. Per provinsi hanya ada daftar provinsi asal/tujuan + sebagian persentase; sekitar 14% pasangan berarah terisi; banyak halaman raster. Dipakai sebagai **mask biner**, bukan bobot edge.

**Langkah**
1. `pymupdf`: ekstrak teks per halaman → `data/interim/bps_pdf_text/page_XXX.txt`; tandai halaman tanpa teks (raster).
2. Petakan halaman → bab provinsi (daftar isi PDF).
3. Untuk setiap provinsi catat ke spreadsheet `data/interim/bps_mask_entry.csv`:
   `dest_code, origin_code, share_pct (boleh kosong), relation (asal|tujuan), page, method (text|manual), entered_by`.
   - "asal" = provinsi lain yang memasok provinsi ini → edge `origin → dest`.
   - "tujuan" = provinsi lain yang menerima dari provinsi ini → edge `ini → tujuan`.
4. Halaman raster: entri manual. **Verifikasi ganda**: RL memeriksa ulang sampel acak 20% halaman manual; selisih dicatat lalu diperbaiki.
5. Gabungkan kedua arah (union), buang diagonal, buang pasangan ke "luar negeri"/"lainnya".
6. Ekspor:
   - `bps_mask.csv` (long, satu baris per edge berarah unik, `share_pct` = maks bila ada lebih dari satu sumber).
   - `bps_mask.npy` (34×34 `uint8`, konvensi **`A[i, j] = 1` bila `j → i`**, urutan baris = `provinces.csv`).
7. Statistik: densitas (target ±14%), in-degree/out-degree per provinsi, provinsi tanpa asal (penting untuk RQ0 fitur (c)).

**Output**
| Path | Isi |
|---|---|
| `data/interim/bps_mask_entry.csv` | Entri mentah + halaman + metode |
| `data/interim/bps_mask.csv`, `bps_mask.npy` | Mask final |
| `reports/qa/bps_mask.md` | Densitas, derajat, daftar provinsi tanpa asal, hasil verifikasi ganda |

**DoD**
- [ ] 34 provinsi tercakup (ada baris untuk setiap provinsi sebagai asal atau tujuan, atau dicatat "tidak ada data").
- [ ] Kesalahan verifikasi ganda < 5% dari edge yang dicek.
- [ ] Konvensi indeks diuji: `tests/test_bps_mask.py` mengecek 3 edge yang diketahui dari PDF.

---

## MDE-H3-01 · Merge → dataset v1, cek kebocoran, bekukan (bersama CGS)

| | |
|---|---|
| Waktu | **H3 09.15–11.00** (tenggat keras: MLE-H3-02 mulai 11.00) |
| Mode | **SEKUENSIAL**, menunggu MDE-H2-01/02/03 + CGS-H2-01/02/03 |
| Input | `prices_clean.parquet`, `calendar.csv`, `bps_mask.npy`, `climate_features.parquet`, `roni.parquet`, `availability.csv`, `provinces.csv`, `coverage_pihps.csv` |
| Tools | `pandas` (`merge_asof`), `pyarrow`, `pytest`, `hashlib` |
| Peran CGS | Pemilik bagian iklim: menjelaskan aturan `available_at`, memeriksa join fitur iklim, menandatangani QA |
| Handoff | MLE-H3-02 (RQ0), CGS-H3-02 (segel holdout memakai skrip yang sama) |

**Langkah**
1. Skrip `scripts/build_dataset.py --start 2017-07-01 --end 2026-05-31 --out data/processed/dataset_v1`. Sediakan juga argumen `--raw-root <dir>` (default `data/`) dan `--allow-holdout` (hanya aktif bila `RENARO_SEALED_DIR` diset dan berisi file kunci CGS). Keduanya dipakai CGS-H3-02 untuk membangun panel holdout dengan kode yang sama.
2. **Kerangka panel**: semua `date` dengan `is_workday_pihps=True` × 34 `prov_code`.
3. **Join target**: `price_type=1`, `price` dan `is_observed` → `target.parquet`.
4. **Join fitur dengan aturan as-of**: untuk tiap sumber fitur (harga lag, iklim, RONI), gabungkan memakai `merge_asof(left_on="date", right_on="available_at", by="prov_code", direction="backward")`. Hasilnya: nilai terbaru yang **sudah tersedia** pada `date`. Simpan juga kolom `<fitur>__avail` untuk diuji.
5. **Kalender** di-join langsung pada `date` (diketahui di muka).
6. **Node include**: `nodes.csv` dengan `include = True` bila lolos kriteria cakupan (MDE-H1-03).
7. **Uji kebocoran** `tests/test_no_leakage.py`:
   - untuk setiap kolom `*__avail`: `(panel[c] <= panel.date).all()`;
   - `panel.date.max() < holdout_start`;
   - tidak ada kolom yang namanya mengandung `regime`/`label`;
   - fitur iklim pada `date` tidak berubah bila data iklim setelah `date` dihapus (uji *truncation*: bangun ulang panel dengan input dipotong di tanggal acak T, bandingkan baris ≤ T → harus identik).
8. **Bekukan**:
   - Tulis `panel.parquet`, `target.parquet`, `nodes.csv`, `bps_mask.npy`, `feature_dict.csv`, `VERSION`.
   - `SHA256SUMS` (semua file) + `content_hash` per tabel (`pandas.util.hash_pandas_object` setelah sort) agar reproduksi tidak bergantung pada byte Parquet.
   - Commit `SHA256SUMS`, `VERSION`, `feature_dict.csv`; tag `dataset-v1`.
9. Laporan QA `reports/qa/dataset_v1.md`: jumlah baris, rentang tanggal, % missing per fitur per provinsi, daftar node include, hasil uji bocor, tanda tangan MDE + CGS.

**Output**
| Path | Isi |
|---|---|
| `data/processed/dataset_v1/` | Struktur §5.7 file setup |
| `tests/test_no_leakage.py` | Lulus |
| `reports/qa/dataset_v1.md` | QA + tanda tangan |
| Tag `dataset-v1` | – |

**DoD**
- [ ] Semua uji hijau; hash diumumkan di kanal sebelum 11.00.
- [ ] MLE berhasil memuat dataset lewat loader MLE-H1-01 tanpa error (MLE konfirmasi).
- [ ] Tidak ada tanggal ≥ 2026-06-01.

**Kalau macet:** fitur iklim belum lengkap → bekukan **dataset v1-price** (harga + kalender + mask) agar MLE bisa memulai (a), lalu `v1.1` dengan iklim paling lambat 13.00 (RQ0 (b)/(c) mundur). Catat di `GATE1.md`.

---

## MDE-H3-02 · Draft data card

| | |
|---|---|
| Waktu | H3 11.00–16.00 |
| Mode | PARALEL |
| Output | `docs/data_card_draft.md` |

**Kerangka (ala Datasheets for Datasets)**
1. *Motivasi*: tujuan dataset, pembuat, pendanaan.
2. *Komposisi*: unit (provinsi × hari kerja), periode, jumlah node include, fitur (rujuk `feature_dict.csv`), missing.
3. *Proses pengumpulan*: PIHPS (endpoint, tanggal akses), SP2KP, CHIRPS v3 (varian), RONI (vintage), BPS Poldis 2022, BPS Hortikultura.
4. *Pra-pemrosesan*: aturan cleaning + flag, kalender, aturan `available_at`.
5. *Penggunaan*: untuk prediksi; **edge ≠ arus pasokan**; label regime hanya evaluasi.
6. *Distribusi & lisensi*: PIHPS "Hak Cipta – Semua Hak Dilindungi", **data mentah tidak diredistribusi**; atribusi BPS wajib; CHIRPS sitasi CHC.
7. *Pemeliharaan*: versi, hash, kontak.

---

## MDE-H4-01 · Varian graph prior

| | |
|---|---|
| Waktu | H4 09.15–13.00 |
| Mode | PARALEL |
| Input | `bps_mask.npy`, `provinces.csv`, batas wilayah + produksi per kab (dari CGS-H1-03), populasi per provinsi (BPS, Sensus Penduduk 2020 / proyeksi) |
| Tools | `geopandas`, `numpy` |
| Handoff | MLE-H4-01 (prior Modul 1), CGS-H5-01 (eksperimen misspesifikasi) |

**Langkah**
1. **`bps.npy`**: salinan `bps_mask.npy`.
2. **`distance.npy`**: jarak haversine antar *centroid berbobot produksi* provinsi (fallback: centroid geometri). Bobot `w = exp(-(d/σ)²)`, σ = median jarak; pertahankan k = 5 tetangga terdekat per tujuan `i`. Simpan juga `distance_km.npy` mentah.
3. **`surplus_deficit.npy`**: provinsi *surplus* bila pangsa produksi cabai > pangsa populasi; edge `j → i` bila `j` surplus, `i` defisit, dan `j` termasuk 5 surplus terdekat dari `i`.
4. **`none.npy`**: semua 1 kecuali diagonal (kandidat penuh; graph sepenuhnya dipelajari).
5. Simpan `graph_priors/meta.json`: untuk tiap varian, jumlah edge, densitas, parameter (σ, k), sumber data.
6. Gambar 4 peta/heatmap ke `reports/figures/graph_priors.png`.

**Output:** `data/processed/graph_priors/{bps,distance,distance_km,surplus_deficit,none}.npy`, `meta.json`, figur.
**DoD:** [ ] konvensi `A[i, j]` (j → i) dan urutan node sama dengan dataset v1 · [ ] diagonal 0 di semua varian.

## MDE-H4-02 · Set perturbasi edge

| | |
|---|---|
| Waktu | H4 13.00–17.00 |
| Mode | PARALEL |
| Input | `graph_priors/bps.npy` (dan opsional `distance.npy`) |
| Handoff | CGS-H5-01 |

**Langkah**
1. Implementasi `src/renaro/graph/perturb.py` dengan 3 operasi terhadap himpunan edge `E` (|E| = m):
   - **drop p%**: hapus `round(p·m)` edge acak.
   - **add p%**: tambah `round(p·m)` non-edge acak (bukan diagonal).
   - **rewire p%**: untuk `round(p·m)` edge `j → i`, ganti asal `j` dengan `j'` acak sehingga `j' → i` belum ada (in-degree `i` tetap).
2. Grid: p ∈ {10, 20, 30, 40, 50} × operasi {drop, add, rewire} × seed {0, 1, 2} = **45 matriks** per prior.
3. Simpan `perturbations/bps_{op}_p{pp}_s{seed}.npy` + `perturbations/index.csv` (`file, base, op, p, seed, n_edges, jaccard_vs_base`).
4. Unit test: jumlah edge sesuai operasi, tidak ada diagonal, determinisme per seed.

**Output:** `data/processed/perturbations/` (45 file + index).
**DoD:** [ ] `jaccard_vs_base` menurun monoton terhadap p · [ ] test hijau.

---

## MDE-H5-01 · Pipeline satu perintah (raw → dataset v1)

| | |
|---|---|
| Waktu | H5 |
| Mode | PARALEL |
| Tools | Python CLI (`argparse`), tanpa `make` (Windows) |

**Langkah**
1. `scripts/make_dataset.py --config configs/data/v1.yaml [--skip-download]` menjalankan berurutan: parse PIHPS → SP2KP → cleaning → kalender → mask → (memanggil langkah iklim milik CGS) → build_dataset → uji.
2. Setiap tahap idempoten: lewati bila output ada dan hash input tidak berubah (simpan `data/interim/.stamps/*.json`).
3. Akhir pipeline: bandingkan `content_hash` hasil dengan `dataset_v1/SHA256SUMS`/`content_hash` → cetak `REPRODUCED OK` atau diff.
4. **Uji reproduksi oleh orang lain**: CGS menjalankan dari clone bersih di mesinnya (dengan `--skip-download` + drive bersama) dan harus mendapat `REPRODUCED OK`.

**Output:** `scripts/make_dataset.py`, `configs/data/v1.yaml`, bagian "Reproduksi dataset" di `README.md`.
**DoD:** [ ] `REPRODUCED OK` di 2 mesin berbeda.

## MDE-H5-02 · Data card final
Perbarui `docs/data_card_draft.md` → `docs/data_card.md` dengan: hash final dataset v1, statistik QA, graph prior + perturbasi, hasil uji reproduksi, keterbatasan (struktur 34 provinsi lama, hari kerja saja, CHIRPS disagregasi pentad, mask BPS biner 2022 saja).

---

## MDE-H6-01 · Bagian data laporan + QA angka hasil

| | |
|---|---|
| Waktu | H6 (paralel dengan analisis holdout) |
| Output | `reports/sprint1/04_data.md`, `reports/qa/numbers_check.md` |

**Langkah**
1. Tulis bagian data: sumber, cakupan (heatmap), cleaning, kalender, mask BPS, graph prior, aturan ketersediaan (ringkasan; detail di data card).
2. **QA angka**: skrip `scripts/recompute_metrics.py` menghitung ulang MAE/RMSE/sMAPE **langsung dari `preds.parquet`** untuk setiap angka di tabel hasil (validasi, ablation, robustness, holdout) lalu bandingkan dengan `metrics.json`. Toleransi 1e-6.
3. Laporkan selisih di `numbers_check.md` (angka, sumber, nilai ulang, status).

**DoD:** [ ] 100% angka di tabel laporan dicek · [ ] tidak ada selisih yang belum dijelaskan.

## MDE-H7-01 · Rilis pipeline + data turunan

**Langkah**
1. `release/data/README.md`: cara mengunduh ulang PIHPS sendiri (skrip + parameter), hash yang diharapkan.
2. Sertakan **data turunan** yang boleh dirilis (keputusan akhir RL): mask BPS (dengan atribusi BPS), graph prior, perturbasi, kalender, `feature_dict.csv`, statistik cakupan. **Tidak** menyertakan harga PIHPS mentah atau panel harga harian.
3. Lisensi & sitasi per sumber di `release/data/SOURCES.md`.

**DoD:** [ ] `release/data/` tidak memuat file harga PIHPS (cek `grep -r price`) · [ ] RL menyetujui daftar file.
