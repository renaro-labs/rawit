# 01 · Setup Environment, Tools, Repo, dan Kontrak Data

> Dikerjakan **sebelum** kickoff H1 (idealnya H0 sore) oleh masing-masing anggota. §5 (kontrak data) disahkan di ALL-H1-01.

---

## 1. Kondisi saat ini (diaudit 23 Nov 2026)

| Item | Status | Implikasi |
|---|---|---|
| Folder proyek `D:\renaro\supplychain` | **Bukan** repo git | Wajib `git init` (§4); commit hash dipakai untuk mengunci protokol & Gate 2 |
| `data/raw/{pihps,chirps_v3,enso,boundaries}`, `data/interim`, `data/processed` | Folder ada, **kosong** | Semua data diakuisisi di H1 |
| `scripts/download_chirps_v3.py` | Siap; sudah diuji untuk 2022-01-01/02 (`scripts/_test_out/`) | Dipakai CGS-H1-01 |
| `enso_index (1).csv` | 1950–2026, nilai konsisten RONI | Dipindah ke `data/raw/enso/` sebagai rujukan; RONI resmi tetap diunduh ulang (CGS-H1-02) |
| `Tabel Harga Berdasarkan Daerah (6).xlsx` | 3 deret nasional 2022 | Hanya untuk *sanity check* skala harga, **bukan** data latih |
| `BPS0000-distribusi_..._2022.pdf` | 17 MB, banyak halaman raster | Sumber mask BPS (MDE-H2-03) |
| Python sistem | 3.15.0; torch 2.14.1+cu126; pandas 3.1; numpy 2.5; **belum ada** PyG, LightGBM, xarray, netCDF4, rasterio, geopandas | Buat env terpisah (§2) |
| GPU | NVIDIA GeForce RTX 2050, **4 GB VRAM** | Cukup untuk 34 node; pakai batch kecil + AMP (lihat MLE) |
| OS | Windows 11, PowerShell + Git Bash | Hindari `make`; pipeline memakai CLI Python |

## 2. Environment

### 2.1 Kenapa env terpisah
Python 3.15 sangat baru. Stack geospasial (rasterio, GDAL, netCDF4, geopandas) dan LightGBM paling stabil di Windows lewat **conda-forge** dengan Python **3.12**. Semua anggota memakai env yang **sama persis** (lockfile) supaya hasil reproducible.

### 2.2 Instalasi (sekali per mesin)
1. Pasang **Miniforge** (conda-forge default) dari `https://github.com/conda-forge/miniforge`.
2. Di root repo, buat `environment.yml`:

```yaml
name: renaro
channels: [conda-forge]
dependencies:
  - python=3.12
  # inti data
  - numpy
  - pandas
  - pyarrow            # parquet
  - scipy
  - scikit-learn
  - statsmodels
  - pyyaml
  - tqdm
  - requests
  # model tabular
  - lightgbm
  # iklim & geospasial (terutama CGS)
  - xarray
  - netcdf4
  - h5netcdf
  - rasterio
  - rioxarray
  - geopandas
  - shapely
  - pyproj
  - exactextract       # zonal statistics dengan bobot fraksi piksel
  - pillow
  # dokumen & PDF (MDE: mask BPS)
  - pymupdf
  - pdfplumber
  # kalender
  - holidays
  # visual & notebook
  - matplotlib
  - jupyterlab
  - ipykernel
  # kualitas kode
  - pytest
  - ruff
  - pre-commit
  - pip
  - pip:
      - mlflow          # opsional; pelacakan run lokal (file store)
```

3. Buat env lalu pasang PyTorch + PyG lewat pip (wheel CUDA resmi):

```powershell
conda env create -f environment.yml
conda activate renaro
pip install torch --index-url https://download.pytorch.org/whl/cu126
pip install torch_geometric
```

> PyG inti tidak butuh `torch_scatter`/`torch_sparse` untuk graph sekecil ini (34 node). Jangan pasang ekstensi tersebut kecuali ada error spesifik.

4. Kunci versi (dilakukan **sekali** oleh MLE saat H1, lalu di-commit):

```powershell
conda env export --no-builds > environment.lock.yml
pip freeze > requirements.lock.txt
```

Anggota lain lalu membuat env dari `environment.lock.yml`.

### 2.3 Variabel lingkungan

| Variabel | Siapa | Isi | Catatan |
|---|---|---|---|
| `RENARO_DATA_ROOT` | semua | path absolut ke `data/` (default `./data`) | Agar notebook/skrip konsisten |
| `BPS_API_KEY` | CGS (MDE opsional) | API key dari `https://webapi.bps.go.id` | **Jangan** di-commit; simpan di `.env` (sudah di `.gitignore`) |
| `RENARO_SEALED_DIR` | **hanya CGS** | path folder holdout di luar repo | Tidak diset di mesin anggota lain |
| `CUDA_VISIBLE_DEVICES` | MLE | `0` | – |

Gunakan file `.env` di root (dibaca dengan `python-dotenv` atau manual); berikan `.env.example` tanpa nilai rahasia.

### 2.4 Smoke test environment
`scripts/check_env.py` (dibuat MLE di H0/H1 pagi) mencetak versi paket dan menjalankan:
- `import torch; torch.cuda.is_available()` → harus `True` di mesin MLE.
- `import torch_geometric, lightgbm, xarray, netCDF4, rasterio, geopandas, exactextract`.
- Tulis/baca parquet kecil.
- Baca `scripts/_test_out/chirps_v3_final_sat_2022_idn.npz` dan cetak shape.

## 3. Struktur repo

```
supplychain/
├── configs/
│   ├── global.yaml            # train_start, holdout_start, horizon, origins, seeds
│   ├── data/                  # config pipeline data
│   └── models/                # satu yaml per model/baseline
├── data/                      # TIDAK di-commit (kecuali README & SHA256SUMS)
│   ├── raw/
│   │   ├── pihps/             # MDE
│   │   ├── sp2kp/             # MDE
│   │   ├── chirps_v3/         # CGS
│   │   ├── enso/              # CGS
│   │   ├── bps/               # CGS (produksi), MDE (PDF poldis)
│   │   └── boundaries/        # CGS
│   ├── interim/               # tabel bersih per sumber
│   └── processed/
│       ├── dataset_v1/        # BEKU di H3
│       ├── graph_priors/
│       ├── perturbations/
│       └── eval_splits/
├── docs/
│   ├── data_contract.md
│   ├── eval_protocol_v0.md / eval_protocol_v1.md
│   ├── data_card.md
│   ├── holdout_seal.md
│   ├── lit/                   # catatan paper (RL)
│   └── decisions/             # ALL-H1-01.md, GATE1.md, GATE2.md, GATE3.md
├── src/renaro/
│   ├── data/                  # scraper, cleaning, kalender, merge (MDE)
│   ├── climate/               # CHIRPS, zonal stats, indeks, RONI (CGS)
│   ├── graph/                 # prior, perturbasi (MDE)
│   ├── synth/                 # generator sintetis (MLE)
│   ├── models/                # Modul 1–4 (MLE)
│   ├── baselines/             # naive, LightGBM, GWN, MTGNN, ala RCSGNet, ala MillGNN (MLE)
│   └── eval/                  # split, metrik, DM test, stratifikasi regime (MLE + CGS)
├── scripts/                   # CLI: download_chirps_v3.py, make_dataset.py, train.py, predict.py
├── experiments/
│   ├── runs/<run_id>/         # config.yaml, metrics.json, preds.parquet, ckpt.pt, git_sha.txt
│   └── registry.csv
├── frozen/manifest.yaml       # dibuat di Gate 2
├── reports/                   # qa/, rq0/, ablation/, robustness/, holdout/, sprint1/
├── tests/
├── environment.yml / environment.lock.yml / requirements.lock.txt
├── .env.example
└── README.md
```

File lama di root (PDF brief, xlsx, csv ENSO, txt CHIRPS) dipindah ke `docs/source/` atau `data/raw/...` yang sesuai pada H1 pagi.

## 4. Git

```powershell
cd D:\renaro\supplychain
git init -b main
git add .gitignore environment.yml README.md docs/ configs/ src/ scripts/ tests/
git commit -m "[ALL-H1-01] init repo"
git remote add origin <url-repo-privat>
git push -u origin main
```

`.gitignore` minimum:

```
data/raw/
data/interim/
data/processed/**/*.parquet
data/processed/**/*.npy
data/processed/**/*.npz
experiments/runs/**/ckpt*.pt
.env
mlruns/
*.ipynb_checkpoints
__pycache__/
```

- **Branch:** `job/<JOB-ID>` (mis. `job/MDE-H2-01`), merge ke `main` lewat PR. Review minimal 1 orang. RL mereview `docs/`, MLE mereview `src/renaro/models|baselines|eval`.
- **Tag wajib:** `protocol-v1` (RL-H2-01), `dataset-v1` (MDE-H3-01), `gate2-freeze` (ALL-H5-01), `sprint1-final` (ALL-H7-01).
- Data besar **tidak** di-commit. Integritas dijaga dengan `SHA256SUMS` (di-commit) dan data dibagi lewat drive bersama tim (folder `renaro_data/`, struktur sama dengan `data/`).

## 5. Kontrak data (disahkan di ALL-H1-01)

### 5.1 Konvensi umum
- **Kunci waktu:** `date` (tipe `date`, zona WIB, tanpa jam).
- **Kunci wilayah:** `prov_code` = **kode provinsi BPS 2 digit, struktur 34 provinsi lama** (PIHPS memakai struktur ini). Kab/kota di provinsi pemekaran Papua (Papua Selatan, Papua Tengah, Papua Pegunungan, Papua Barat Daya) dipetakan kembali ke `91` atau `94`.
- **Format file:** Parquet untuk tabel besar, CSV untuk tabel kecil/acuan. Encoding UTF-8.
- **Satuan:** harga Rp/kg; hujan mm (harian) atau mm/pentad.
- **Nilai hilang:** `NaN`/null, **tidak** pernah 0 atau -1.
- **`available_at`:** tanggal paling awal sebuah nilai boleh dipakai sebagai fitur. Aturan per sumber ada di `availability.csv` (CGS-H2-03) dan §5.6.

### 5.2 `provinces.csv` (acuan; dibuat MDE di H1)

| prov_code | prov_name |
|---|---|
| 11 | Aceh |
| 12 | Sumatera Utara |
| 13 | Sumatera Barat |
| 14 | Riau |
| 15 | Jambi |
| 16 | Sumatera Selatan |
| 17 | Bengkulu |
| 18 | Lampung |
| 19 | Kepulauan Bangka Belitung |
| 21 | Kepulauan Riau |
| 31 | DKI Jakarta |
| 32 | Jawa Barat |
| 33 | Jawa Tengah |
| 34 | DI Yogyakarta |
| 35 | Jawa Timur |
| 36 | Banten |
| 51 | Bali |
| 52 | Nusa Tenggara Barat |
| 53 | Nusa Tenggara Timur |
| 61 | Kalimantan Barat |
| 62 | Kalimantan Tengah |
| 63 | Kalimantan Selatan |
| 64 | Kalimantan Timur |
| 65 | Kalimantan Utara |
| 71 | Sulawesi Utara |
| 72 | Sulawesi Tengah |
| 73 | Sulawesi Selatan |
| 74 | Sulawesi Tenggara |
| 75 | Gorontalo |
| 76 | Sulawesi Barat |
| 81 | Maluku |
| 82 | Maluku Utara |
| 91 | Papua Barat |
| 94 | Papua |

Tambahkan kolom `pihps_name` (nama persis di respons PIHPS), `sp2kp_name`, `bps_poldis_name` untuk pemetaan nama → kode. Urutan baris ini = **urutan indeks node** di semua matriks (`node_idx` 0–33).

### 5.3 `prices_clean.parquet` (MDE)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `date` | date | Hari kerja PIHPS |
| `prov_code` | str(2) | §5.2 |
| `commodity` | str | `cabai_merah_keriting` |
| `price_type` | int | `1` pasar tradisional (target); `4` produsen (fitur Sprint 2) |
| `price_raw` | float | Nilai asli dari sumber (Rp/kg) |
| `price` | float | Setelah cleaning; `NaN` jika dibuang |
| `is_observed` | bool | `True` jika ada nilai asli pada `date` |
| `flag_outlier` | bool | Ditandai aturan outlier (MDE-H2-01) |
| `flag_post_lebaran` | bool | Dalam jendela pasca-Lebaran (bukan dibuang; hanya ditandai) |
| `flag_carry_forward` | bool | Nilai identik dengan hari sebelumnya ≥ N hari berturut-turut (indikasi tidak diperbarui) |
| `source` | str | `pihps` / `sp2kp` |
| `available_at` | date | Hari kerja berikutnya setelah `date` (aturan brief: harga hari *t* dipakai mulai *t*+1) |

Kunci unik: (`date`, `prov_code`, `commodity`, `price_type`).

### 5.4 `calendar.csv` (MDE)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `date` | date | Setiap hari kalender 2017-09-01 s/d 2026-12-31 |
| `is_workday_pihps` | bool | Ada laporan PIHPS untuk ≥ 50% provinsi |
| `is_holiday` | bool | Libur nasional (SKB 3 Menteri) |
| `is_cuti_bersama` | bool | Cuti bersama |
| `is_ramadan` | bool | Dalam bulan Ramadan (tanggal resmi Kemenag) |
| `days_to_lebaran` | int | Selisih hari ke Idulfitri terdekat (negatif = sebelum) |
| `days_to_iduladha` | int | idem Iduladha |
| `is_natal_tahunbaru` | bool | 20 Des – 5 Jan |
| `dow`, `month`, `doy` | int | Fitur kalender dasar |

Kalender bersifat deterministik dan diketahui di muka, jadi `available_at` = jauh sebelum `date` (fitur kalender masa depan **boleh** dipakai).

### 5.5 `climate_features.parquet` (CGS)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `date` | date | Hari kalender |
| `prov_code` | str(2) | – |
| `variant` | str | `final_sat` (latih/evaluasi) atau `prelim_sat` (simulasi real-time) |
| `rain_mm` | float | Hujan harian terbobot produksi/luas tanam cabai |
| `rain_pentad_mm` | float | Akumulasi pentad (pentad CHIRPS: hari 1–5, 6–10, …, 26–akhir bulan) yang memuat `date` |
| `rain_pentad_anom` | float | Anomali standar pentad terhadap klimatologi pentad yang sama |
| `rain_30d_anom` | float | Anomali akumulasi 30 hari (6 pentad) |
| `dry_spell_days` | int | Hari berturut-turut dengan hujan terbobot < 1 mm sampai `date` |
| `extreme_5d` | bool | Akumulasi 5-harian > persentil ke-95 klimatologi provinsi |
| `available_at` | date | Lihat §5.6 |

Catatan konvensi:
- Fitur berbasis pentad (`rain_pentad_*`, `rain_30d_anom`, `dry_spell_days`, `extreme_5d`) disimpan **satu baris per pentad** dengan `date` = **tanggal akhir pentad**. Penyelarasan ke panel harian dilakukan MDE-H3-01 lewat *as-of join* pada `available_at`.
- `dry_spell_days` dihitung pada resolusi pentad (5 × jumlah pentad kering berturut-turut), karena nilai harian CHIRPS adalah disagregasi pentad.

Plus `roni.parquet`: `season` (mis. `DJF`), `year`, `center_month`, `roni`, `vintage_date`, `available_at`.

### 5.6 Aturan `available_at` (draf; final di `availability.csv` dan protokol v1)

| Sumber | Aturan | Pemilik |
|---|---|---|
| Harga PIHPS tipe 1/4 | `date` + 1 hari kerja | MDE |
| CHIRPS final | **Keputusan RL di kickoff**. Opsi A: jeda rilis aktual final (realistis operasional, sinyal jeda pendek bisa hilang). Opsi B: asumsi "hujan tersedia setelah pentad selesai" (`akhir pentad + 2 hari`, setara jeda *prelim*), dengan data final sebagai proksi nilai prelim. **[usulan default: B untuk latih/evaluasi utama, A sebagai uji sensitivitas]** | CGS |
| CHIRPS prelim | Tanggal rilis prelim per pentad (dicatat dari `recentfiles.txt`/timestamp server) | CGS |
| RONI | Nilai musim berakhir bulan *m* tersedia setelah rilis CPC bulan *m*+1; karena dapat direvisi hingga 2 bulan, pakai **vintage**. Bila vintage historis tidak tersedia, pakai **lag konservatif +3 bulan** | CGS |
| Produksi BPS tahun *y* | 1 Jan *y*+1 | CGS |
| Kalender | selalu tersedia | MDE |
| Label regime | **tidak pernah** jadi fitur | CGS |

### 5.7 `dataset_v1/` (MDE, beku di H3)

```
dataset_v1/
├── panel.parquet          # baris = (date, prov_code); semua fitur siap pakai, sudah di-align dengan available_at
├── target.parquet         # (date, prov_code, price) hanya hari observasi tipe 1
├── nodes.csv              # = provinces.csv + flag include (lolos cakupan)
├── bps_mask.npy           # 34x34, uint8; A[i, j] = 1 jika ada edge j -> i (j asal, i tujuan)
├── feature_dict.csv       # nama fitur, sumber, unit, aturan available_at
├── SHA256SUMS
└── VERSION                # "v1", tanggal, commit git
```

Konvensi matriks graph di semua kode: **`A[i, j]` = pengaruh dari asal `j` ke tujuan `i`** (sama dengan notasi brief $A_{ij}$, edge $j \to i$).

## 6. Konvensi eksperimen

- **Satu run = satu folder** `experiments/runs/<YYYYMMDD-HHMM>_<model>_<origin>_s<seed>/` berisi:
  - `config.yaml` (lengkap, termasuk path dataset + hash)
  - `git_sha.txt` (hasil `git rev-parse HEAD`; run dari working tree kotor **ditolak** oleh `train.py`)
  - `metrics.json` (MAE, RMSE, sMAPE per horizon, per regime)
  - `preds.parquet` (`date`, `prov_code`, `horizon`, `y_true`, `y_pred`, `origin`, `seed`, `model`)
  - `ckpt.pt` (untuk model neural)
  - `log.txt`
- `experiments/registry.csv` ditambah 1 baris per run (`run_id, model, origin, seed, split_hash, val_mae, status`).
- **Seed:** `[0, 1, 2, 3, 4]` (5 seed sesuai brief).
- MLflow opsional (`mlflow ui --backend-store-uri ./mlruns`); folder run tetap wajib karena itu yang dibekukan di Gate 2.

## 7. Pengaman holdout (berlaku sejak H1)

1. `configs/global.yaml`:
   ```yaml
   train_start: 2018-01-02
   holdout_start: 2026-06-01
   ```
2. Fungsi `renaro.data.io.load_panel()` **selalu** memotong `date < holdout_start`. Membuka holdout hanya mungkin bila `RENARO_SEALED_DIR` diset **dan** file `HOLDOUT_UNSEALED` ada di folder tersebut (dibuat CGS di H6).
3. MDE men-scrape periode ≥ 2026-06-01 ke **file terpisah** (`data/raw/pihps/_sealed/…`) dan langsung menyerahkannya ke CGS tanpa membuka isinya selain cek ukuran/jumlah baris.
4. CGS menyimpan holdout di luar repo, mencatat checksum di `docs/holdout_seal.md`, dan menghapus salinan di folder bersama.
5. Plot EDA/notebook apa pun yang menampilkan tanggal ≥ 2026-06-01 sebelum H6 = **pelanggaran protokol**. Catat di audit RL-H5-02.

## 8. Ringkasan tools per peran

| Peran | Tools utama |
|---|---|
| RL | Git/GitHub (review PR), Zotero (referensi), Markdown/LaTeX (Overleaf atau lokal; brief v2 dibuat dengan LaTeX), JupyterLab (membaca hasil), akses perpustakaan kampus (full-text RCSGNet/MarketDNA) |
| MDE | Python `requests`, `pandas`, `pyarrow`, DevTools browser (inspeksi endpoint PIHPS/SP2KP), `pymupdf`/`pdfplumber` + entri manual untuk halaman raster, `holidays`, `pytest` |
| MLE | PyTorch (CUDA 12.6), PyTorch Geometric, LightGBM, scikit-learn, `statsmodels`, matplotlib, MLflow (opsional), `pytest` |
| CGS | `scripts/download_chirps_v3.py`, `xarray` + `netCDF4`, `rasterio`/`rioxarray`, `geopandas`, `exactextract`, BPS WebAPI, QGIS (cek visual opsional), matplotlib |
