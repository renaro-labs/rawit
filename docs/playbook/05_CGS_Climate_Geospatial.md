# 05 · CGS: Climate & Geospatial Scientist

> **Tanggung jawab (brief §9):** CHIRPS v3, hujan terbobot produksi, RONI & vintage, definisi regime, set evaluasi per regime, uji robustness.
> **Kepemilikan kunci:** fitur iklim; **segel holdout** (satu-satunya orang yang memegang data ≥ 2026-06-01 sampai H6).
> **Posisi di jadwal:** cabang CHIRPS **hampir kritis (slack ≈ 0)**. Unduhan harus berjalan sebelum makan siang H1.
> **Catatan ilmiah wajib (brief §7.2):** nilai CHIRPS harian = **disagregasi dari pentad**, bukan observasi harian independen. Ekstrem dan durasi kering didefinisikan pada **akumulasi pentad/5-harian**, dan klaim presisi jeda dibuat pada **resolusi pentad**.

## Ringkasan job

| ID | Hari | Job | Mode | Output utama |
|---|---|---|---|---|
| CGS-H1-01 | H1 | Pasang env geospasial + unduh CHIRPS v3 | PARALEL (hampir kritis) | `data/raw/chirps_v3/` + manifest |
| CGS-H1-02 | H1 | RONI resmi + catat vintage | PARALEL | `data/raw/enso/roni.csv`, `roni_vintage_log.csv` |
| CGS-H1-03 | H1 | Produksi/luas cabai per kab/kota + batas wilayah | PARALEL | `data/raw/bps/produksi_kab.csv`, `data/raw/boundaries/` |
| CGS-H2-01 | H2 | Hujan harian terbobot produksi per provinsi | PARALEL | `data/interim/rain_prov_daily.parquet` |
| CGS-H2-02 | H2 | Indeks pentad: anomali, kering, ekstrem | PARALEL | `data/interim/climate_features.parquet` |
| CGS-H2-03 | H2 | Tabel ketersediaan (`available_at`) | PARALEL | `data/interim/availability.csv` |
| CGS-H2-04 | H2 | Label regime (evaluasi saja) | PARALEL | `data/interim/regime_labels.csv` |
| (MDE-H3-01) | H3 pagi | Merge dataset v1: pemilik bagian iklim | SEKUENSIAL | tanda tangan QA |
| CGS-H3-02 | H3 siang | **Segel holdout** | SEKUENSIAL (dataset v1) | holdout di luar repo + `docs/holdout_seal.md` |
| CGS-H4-01 | H4 | Set evaluasi per regime | PARALEL | `data/processed/eval_splits/` |
| CGS-H4-02 | H4 | Diagnostik lead-lag hujan asal → harga | PARALEL | `reports/leadlag/` |
| CGS-H5-01 | H5 | Misspesifikasi graph prior + joint shift | SEKUENSIAL (checkpoint Modul 1 H4) | `reports/robustness/` |
| CGS-H6-01 | H6 pagi | **Buka holdout satu kali**, jalankan model beku | SEKUENSIAL (Gate 2) | `reports/holdout/predictions/` |
| (MLE-H6-01) | H6 | Analisis bersama MLE/RL | SEKUENSIAL | – |
| CGS-H7-01 | H7 | Arsip paket iklim | PARALEL | `release/climate/` |

---

## CGS-H1-01 · Pasang env geospasial + unduh CHIRPS v3

| | |
|---|---|
| Waktu | H1 11.00 → berjalan di latar belakang sampai H2 pagi |
| Mode | PARALEL, **hampir kritis** |
| Input | `scripts/download_chirps_v3.py` (resume-safe, manifest SHA-256), katalog `https://data.chc.ucsb.edu/products/CHIRPS/v3.0/` |
| Tools | env `renaro` (xarray + netCDF4 → output `.nc`; tanpa itu output `.npz`), PowerShell |
| Handoff | CGS-H2-01 |

**Fakta skrip (sudah dicek):** argumen `--start --end --variant {final/sat|final/rnl|prelim/sat} --out --bbox --source {auto|tif|netcdf} --fmt {auto|npz|netcdf} --cache-dir --keep-global --overwrite --delay --retries --timeout`. Bbox default Indonesia (94,0 −11,5 141,5 6,5). Satu file output per tahun; `manifest.csv` di folder `--out`. File global (~12 MB/hari) dihapus setelah diklip (~0,35 MB/hari) kecuali `--keep-global`. Menjalankan ulang perintah yang sama = **melanjutkan** (resume).

**Langkah**
1. Aktifkan env dan cek `python -c "import xarray, netCDF4"`. Jalankan uji 2 hari:
   ```powershell
   python scripts/download_chirps_v3.py --start 2022-01-01 --end 2022-01-02 --variant final/sat --out data/raw/chirps_v3/_smoke --fmt netcdf
   ```
   Bandingkan nilainya dengan `scripts/_test_out/chirps_v3_final_sat_2022_idn.npz` (harus identik untuk tanggal yang sama).
2. **Prioritas 1: periode latih + pemanasan lag** (2017-09-01 … 2026-05-31). Satu proses per tahun, **folder `--out` berbeda per proses** (agar `manifest.csv` tidak bentrok), maksimal 3 proses paralel agar tetap sopan ke server:
   ```powershell
   # jalankan dari root repo dengan env renaro aktif
   $py   = (Get-Command python).Source      # python milik env renaro
   $root = (Get-Location).Path
   foreach ($y in 2022,2023,2024,2025,2021,2020,2019,2018,2017,2026) {   # tahun terpenting dulu
     while ((Get-Job -State Running).Count -ge 3) { Start-Sleep -Seconds 60 }
     $s = if ($y -eq 2017) { "2017-09-01" } else { "$y-01-01" }
     $e = if ($y -eq 2026) { "2026-05-31" } else { "$y-12-31" }
     Start-Job -Name "chirps$y" -ArgumentList $py,$root,$s,$e,$y -ScriptBlock {
       param($py,$root,$s,$e,$y)
       Set-Location $root
       & $py scripts/download_chirps_v3.py --start $s --end $e --variant final/sat `
            --out "data/raw/chirps_v3/final_sat/$y" --fmt netcdf *> "data/raw/chirps_v3/log_$y.txt"
     } | Out-Null
   }
   Get-Job | Format-Table Name, State     # pantau; log per tahun ada di data/raw/chirps_v3/log_<tahun>.txt
   ```
   Sesi PowerShell harus tetap terbuka selama job berjalan. Jika sesi tertutup, cukup jalankan ulang blok ini: skrip melanjutkan dari manifest.
   Estimasi transfer ±38 GB (±3.200 hari × ~12 MB) dan hasil klip ±1,1 GB. Urutkan tahun dari yang paling banyak dipakai (2022–2025) bila bandwidth terbatas.
3. **Periode holdout** (2026-06-01 … tanggal *final* terakhir yang tersedia): unduh langsung ke folder tersegel:
   ```powershell
   python scripts/download_chirps_v3.py --start 2026-06-01 --end <tgl_final_terakhir> --variant final/sat --out $env:RENARO_SEALED_DIR\chirps_v3\final_sat\2026H2 --fmt netcdf
   ```
   Cek tanggal *final* terakhir dari listing `daily/final/sat/2026/`. Sisa periode yang hanya ada di *prelim* diunduh dengan `--variant prelim/sat` ke folder tersegel terpisah dan **diberi tanda** (pemakaiannya diputuskan protokol).
4. **Prioritas 2: baseline klimatologi** untuk anomali (harus **sebelum 2018** agar tidak bocor ke periode uji):
   - Opsi A **[disarankan]**: produk `pentads/` CHIRPS v3 untuk 1998–2017 (± 72 file/tahun, ±5× lebih sedikit dari harian). Skrip saat ini hanya untuk harian; tambahkan opsi `--product pentads` (cek pola nama file di katalog `pentads/`) sebagai pekerjaan kecil H1 sore.
   - Opsi B: harian `final/sat` 2008–2017 (10 tahun) semalam H1→H2.
   Catat pilihan di `docs/decisions/ALL-H1-01.md` atau `availability.csv`.
5. **Prioritas 3 (opsional):** `prelim/sat` 2025–2026 untuk simulasi real-time; `final/rnl` hanya bila ada waktu (uji sensitivitas varian).
6. Pantau: setiap ±2 jam cek `manifest.csv` (`status` ≠ `ok` → jalankan ulang perintah yang sama).
7. Verifikasi akhir: setiap tahun punya jumlah hari benar, tidak ada `status` gagal, dimensi `time × lat × lon` konsisten, rentang lat 6,5…−11,5 dan lon 94…141,5.

**Output**
| Path | Isi |
|---|---|
| `data/raw/chirps_v3/final_sat/<YYYY>/chirps_v3_final_sat_<YYYY>_idn.nc` + `manifest.csv` | Hujan harian klip Indonesia, mm/hari |
| `data/raw/chirps_v3/clim/` | Baseline klimatologi (pentad 1998–2017 atau harian 2008–2017) |
| `$RENARO_SEALED_DIR/chirps_v3/...` | Periode holdout (tidak di folder bersama) |
| `reports/qa/chirps_download.md` | Ringkasan: hari per tahun, gagal, ukuran, tanggal final terakhir |

**DoD**
- [ ] 2017-09-01 … 2026-05-31 lengkap (0 gagal) paling lambat **H2 10.00**.
- [ ] Data holdout tidak ada di `data/raw/` bersama.
- [ ] Tanggal final terakhir dicatat (menentukan akhir evaluasi holdout).

**Kalau macet:** unduhan lambat → prioritaskan tahun 2020–2026; jalankan malam; bila 2018–2019 belum ada di H2 siang, RL memutuskan apakah origin O1 dipendekkan.

---

## CGS-H1-02 · RONI resmi + vintage

| | |
|---|---|
| Waktu | H1 11.00–13.00 |
| Mode | PARALEL |
| Input | NOAA CPC RONI (`https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni`), `enso_index (1).csv` di folder proyek (rujukan) |
| Tools | `requests`, `pandas` |
| Handoff | CGS-H2-03, CGS-H2-04, MDE-H3-01 |

**Langkah**
1. Unduh tabel RONI resmi (format teks CPC) → simpan mentah `data/raw/enso/roni_raw_<YYYYMMDD>.txt` (tanggal unduh = *vintage* hari ini).
2. Parse ke `roni.csv`: `year, season (DJF..NDJ), center_month, roni`.
3. Bandingkan dengan `enso_index (1).csv`: selisih maksimum dan musim yang berbeda (berguna untuk menunjukkan revisi).
4. **Vintage historis:** cek apakah CPC menyediakan arsip rilis lama (halaman arsip/ENSO diagnostic discussion). Jika ada, kumpulkan ke `roni_vintage_log.csv` (`vintage_date, year, season, roni`). Jika **tidak**, terapkan aturan konservatif (file setup §5.6): nilai musim berakhir bulan *m* dipakai mulai **awal bulan m+3**.
5. **Cek status El Niño 2018–19 menurut RONI** (brief §7.2 menugaskan CGS): apakah memenuhi ≥ 5 musim berturut-turut ≥ +0,5? Tulis hasilnya; ini menentukan apakah episode tersebut masuk evaluasi.
6. Catat status 2026: MJJ–ASO naik ke +1,97 menurut audit brief, tetapi label resmi butuh ≥ 5 musim. Label holdout berbasis **tanggal**, bukan label episode.

**Output:** `data/raw/enso/roni.csv`, `roni_raw_<tgl>.txt`, `roni_vintage_log.csv` (atau catatan "tidak ada arsip → lag konservatif"), `reports/qa/roni.md` (perbandingan + status 2018–19 + daftar episode 2018–2026).
**DoD:** [ ] daftar episode ENSO 2018–2026 menurut RONI tertulis · [ ] aturan `available_at` RONI ditetapkan.

---

## CGS-H1-03 · Produksi/luas cabai per kab/kota + batas wilayah

| | |
|---|---|
| Waktu | H1 13.00–17.00 |
| Mode | PARALEL |
| Input | Statistik Hortikultura BPS (katalog 5204003; edisi 2024 terverifikasi), BPS WebAPI (butuh `BPS_API_KEY`, ada rate limit, atribusi wajib); batas administrasi kab/kota |
| Tools | `requests`, `pandas`, `geopandas` |
| Handoff | CGS-H2-01 (bobot), MDE-H4-01 (centroid berbobot, surplus/defisit) |

**Langkah**
1. Daftar akun & API key di `webapi.bps.go.id`; simpan di `.env`.
2. Ambil produksi (ton) dan, bila ada, luas panen (ha) **cabai besar** per kab/kota untuk tahun sebanyak mungkin 2017–2025. Fallback: unduh tabel PDF/XLSX dari publikasi Statistik Hortikultura per edisi.
3. Batas wilayah kab/kota: sumber dengan lisensi terbuka (mis. geoBoundaries IDN ADM2) atau BIG/Ina-Geoportal. Simpan `data/raw/boundaries/idn_adm2.gpkg` + `SOURCE.md` (versi, lisensi, tanggal).
4. Kunci join: kode kab/kota BPS 4 digit. Kab/kota hasil pemekaran setelah tahun data → dipetakan ke induknya. Kab/kota di 4 provinsi Papua baru → `prov_code` 91/94 (struktur 34 provinsi).
5. **Aturan tahun:** produksi tahun *y* dipakai mulai *y*+1. Jika tahun awal (2017) tidak tersedia, pakai edisi terdekat yang tersedia dan **catat sebagai keterbatasan** (bobot statis).
6. Catatan istilah: brief menyebut "luas tanam" (§ ringkasan perubahan) dan "produksi" (§7.2). **[usulan default: bobot = produksi; luas panen sebagai uji sensitivitas]**. Konfirmasi ke RL.

**Output**
- `data/raw/bps/produksi_kab.csv`: `kab_code, kab_name, prov_code, year, produksi_ton, luas_panen_ha, source, edition`.
- `data/raw/boundaries/idn_adm2.gpkg` + `SOURCE.md`.
- `reports/qa/produksi_kab.md`: cakupan tahun, kab tanpa data, top-10 kab produsen (cek kewajaran: sentra Jawa Barat/Jawa Tengah/Jawa Timur/Sumatera Utara harus muncul).

**DoD:** [ ] ≥ 95% kab/kota ter-join ke poligon · [ ] setiap provinsi punya ≥ 1 kab dengan bobot > 0 (atau dicatat).

---

## CGS-H2-01 · Hujan harian terbobot produksi per provinsi

| | |
|---|---|
| Waktu | H2 10.00–13.00 |
| Mode | PARALEL |
| Input | CHIRPS klip (CGS-H1-01), `idn_adm2.gpkg`, `produksi_kab.csv` |
| Tools | `exactextract`, `scipy.sparse`, `xarray`, `numpy` |
| Handoff | CGS-H2-02 |

**Langkah**
1. **Matriks bobot piksel sekali saja:** dengan `exactextract` hitung fraksi cakupan setiap sel 0,05° oleh setiap poligon kab → matriks jarang `W_kab [n_kab × n_pixel]` (baris dinormalisasi = rata-rata terbobot luas). Simpan `data/interim/w_kab_pixel.npz`.
2. **Hujan kab per hari:** `rain_kab[t] = W_kab @ precip[t].ravel()` (NaN piksel: normalisasi ulang bobot baris tanpa NaN). Jauh lebih cepat daripada zonal stats per hari.
3. **Bobot produksi:** `w_k,prov,y = produksi_k,y−1 / Σ_k∈prov produksi_k,y−1` (aturan *y*+1).
4. **Hujan provinsi:** `rain_mm[t, prov] = Σ_k w_k · rain_kab[t, k]`. Provinsi tanpa data produksi → rata-rata terbobot luas, kolom `weight_method = "area"`.
5. Simpan juga varian terbobot luas (`rain_mm_area`) untuk uji sensitivitas.
6. Sanity: plot musiman rata-rata per provinsi (Jawa: kering Jun–Sep); bandingkan total tahunan dengan kisaran wajar (1.500–4.000 mm).

**Output:** `data/interim/rain_kab_daily.parquet` (opsional, untuk diagnostik), `data/interim/rain_prov_daily.parquet` (`date, prov_code, variant, rain_mm, rain_mm_area, weight_method`), `reports/qa/rain_prov.md`.
**DoD:** [ ] 34 provinsi × seluruh hari tanpa NaN tak terjelaskan · [ ] sanity plot di-commit.

---

## CGS-H2-02 · Indeks pentad: anomali, durasi kering, ekstrem

| | |
|---|---|
| Waktu | H2 13.00–15.30 |
| Mode | PARALEL |
| Input | `rain_prov_daily.parquet`, baseline klimatologi (CGS-H1-01 prioritas 2) |
| Handoff | MDE-H3-01 |

**Langkah**
1. **Pentad CHIRPS**: setiap bulan dibagi 6 pentad (hari 1–5, 6–10, 11–15, 16–20, 21–25, 26–akhir bulan) → 72 pentad/tahun. `rain_pentad_mm` = jumlah hujan harian terbobot dalam pentad.
2. **Klimatologi** per provinsi per pentad-of-year dari periode baseline (sebelum 2018, dengan pembobotan produksi yang sama): rata-rata dan std, memakai jendela ±2 pentad agar sampel cukup.
3. Fitur (satu baris per `prov_code` × pentad, `date` = **tanggal akhir pentad**):
   - `rain_pentad_anom` = (x − μ)/σ (pakai `log1p` bila distribusi sangat miring; catat pilihan).
   - `rain_30d_anom` = anomali jumlah 6 pentad terakhir.
   - `dry_spell_days` = 5 × jumlah pentad berturut-turut dengan `rain_pentad_mm` < **[usulan default: 5 mm/pentad]** (dihitung pada resolusi pentad, bukan harian).
   - `extreme_5d` = `rain_pentad_mm` > persentil ke-95 klimatologi provinsi (jendela ±2 pentad).
4. Fitur harian `rain_mm` tetap disertakan (untuk model yang memakai harian), tetapi dokumentasikan bahwa nilainya disagregasi.
5. Tambahkan `roni` (dari CGS-H1-02) sebagai tabel terpisah `roni.parquet` dengan `available_at`.
6. Gabungkan ke `climate_features.parquet` (skema file setup §5.5; untuk fitur pentad, `date` = akhir pentad dan `available_at` diisi CGS-H2-03).

**Output:** `data/interim/climate_features.parquet`, `data/interim/roni.parquet`, `data/interim/climatology.parquet`, `reports/qa/climate_features.md` (distribusi tiap fitur, % pentad ekstrem per provinsi ≈ 5%).
**DoD:** [ ] proporsi `extreme_5d` di periode baseline ≈ 5% (validasi definisi) · [ ] tidak ada pemakaian data ≥ 2018 di klimatologi.

---

## CGS-H2-03 · Tabel ketersediaan (`available_at`)

| | |
|---|---|
| Waktu | H2 15.30–16.30 |
| Mode | PARALEL |
| Handoff | MDE-H3-01 (merge as-of + uji bocor), RL-H2-01 (protokol) |

**Langkah**
1. **Bukti jeda rilis CHIRPS:** ambil `Last-Modified` (HTTP HEAD) beberapa file `daily/final/sat` dan `daily/prelim/sat` bulan-bulan terakhir serta `recentfiles.txt` → perkirakan jeda (hari) antara akhir pentad/bulan dan rilis. Simpan bukti di `reports/qa/chirps_release_lag.md`.
2. Isi `availability.csv`:

   | feature_family | source | variant | rule | lag_days | evidence | decided_by |
   |---|---|---|---|---|---|---|
   | price | PIHPS | pt1 | next_workday | 1 | brief §7.2 | protokol |
   | rain_daily | CHIRPS | final_sat | (opsi A/B, lihat file setup §5.6) | … | chirps_release_lag.md | RL |
   | rain_pentad_* | CHIRPS | final_sat | pentad_end + lag | … | … | RL |
   | rain_* | CHIRPS | prelim_sat | pentad_end + lag_prelim | … | … | CGS |
   | roni | CPC | – | vintage / +3 bulan | … | roni.md | CGS |
   | production_weight | BPS | – | year+1 | – | brief §7.2 | protokol |
   | calendar | – | – | known_in_advance | – | – | – |

3. Hitung kolom `available_at` di `climate_features.parquet` dan `roni.parquet` sesuai aturan yang dikunci RL.

**DoD:** [ ] setiap fitur di `feature_dict.csv` punya satu baris aturan · [ ] RL menyetujui (komentar di PR).

---

## CGS-H2-04 · Label regime (evaluasi saja)

| | |
|---|---|
| Waktu | H2 (draf definisi ke RL sebelum 12.00; tabel final 17.00) |
| Mode | PARALEL |
| Handoff | RL-H2-01 (definisi), MLE-H3-02 (evaluasi RQ0), CGS-H4-01 |

**Langkah**
1. Usulkan definisi ke RL (dikunci di protokol v1), default di protokol v0 §4:
   - ENSO: aturan NOAA (±0,5 RONI, ≥ 5 musim berturut-turut). **Boleh** memakai nilai RONI final karena hanya untuk evaluasi.
   - Kering per provinsi: `rain_pentad_mm` < persentil ke-20 klimatologi selama ≥ 3 pentad berturut-turut.
   - Hujan ekstrem: `extreme_5d = True`.
   - Normal: tidak satu pun di atas.
2. Tabel per (`date`, `prov_code`): `enso_phase` (elnino/lanina/neutral), `episode_id` (mis. `elnino_2023_24`), `is_dry`, `is_extreme_rain`, `is_normal`, `label_primary` (aturan prioritas protokol).
3. **Ringkasan kontras per origin:** jumlah node-hari per regime di setiap periode uji O1/O2/O3 → `reports/qa/regime_counts.md`. Regime dengan < 200 node-hari diberi tanda "CI lebar".
4. File diletakkan di `data/interim/` dan **tidak** masuk `panel.parquet` (MDE memastikan; diuji `test_no_leakage.py`).

**Output:** `data/interim/regime_labels.csv`, `docs/regime_definitions.md`, `reports/qa/regime_counts.md`.
**DoD:** [ ] tidak ada tanggal ≥ 2026-06-01 · [ ] episode ENSO konsisten dengan `reports/qa/roni.md`.

---

## CGS-H3-02 · Segel holdout

| | |
|---|---|
| Waktu | H3 11.00–13.00 |
| Mode | **SEKUENSIAL**: menunggu dataset v1 (MDE-H3-01) |
| Input | File `_sealed` dari MDE (PIHPS, SP2KP), CHIRPS holdout (CGS-H1-01), `scripts/build_dataset.py` |
| Tools | `build_dataset.py`, `hashlib`, 7-Zip (AES-256, opsional) |
| Handoff | CGS-H6-01 |

**Langkah**
1. Di folder `RENARO_SEALED_DIR`, bangun panel holdout dengan **kode yang sama** (commit dataset v1):
   ```powershell
   python scripts/build_dataset.py --start 2017-07-01 --end <tgl_akhir_holdout> --raw-root $env:RENARO_SEALED_DIR\raw_merged --out $env:RENARO_SEALED_DIR\holdout_v1 --allow-holdout
   ```
   (`raw_merged` = raw bersama + raw tersegel; opsi `--allow-holdout` hanya aktif bila file kunci CGS ada.)
2. Pastikan bagian < 2026-06-01 dari panel ini **identik** dengan `dataset_v1` (cek `content_hash` pada potongan tersebut). Ini membuktikan pipeline sama.
3. Tentukan `tgl_akhir_holdout` = min(tanggal PIHPS terakhir, tanggal CHIRPS *final* terakhir) sesuai protokol. Periode yang hanya punya *prelim* ditandai terpisah.
4. Hitung SHA-256 semua file holdout; isi `docs/holdout_seal.md`:
   ```markdown
   # Holdout seal
   - Disegel oleh: CGS · Waktu: <H3, jam>
   - Commit pipeline: <sha> (tag dataset-v1)
   - Rentang: 2026-06-01 … <tgl_akhir>, n_baris, n_provinsi
   - File + SHA-256: ...
   - Lokasi: di luar repo, akses hanya CGS
   - Status: TERSEGEL
   - Dibuka: (diisi di H6) waktu, commit gate2-freeze, oleh
   ```
5. Hapus salinan `_sealed` dari drive bersama; konfirmasi ke MDE.
6. Commit **hanya** `docs/holdout_seal.md` (tanpa data).

**DoD:** [ ] checksum di-commit · [ ] tidak ada file ≥ 2026-06-01 di drive bersama (`max(date)` dicek semua parquet di `data/`) · [ ] RL menerima notifikasi.

---

## CGS-H4-01 · Set evaluasi per regime

| | |
|---|---|
| Waktu | H4 09.15–12.00 |
| Mode | PARALEL |
| Input | `regime_labels.csv`, split dari `configs/global.yaml` |
| Handoff | MLE (semua evaluasi validasi), MLE-H6-01 (holdout) |

**Langkah**
1. Untuk setiap origin dan bagian (`val`, `test`): tabel `eval_splits/<origin>_<part>.parquet` dengan kolom `date, prov_code, is_target_observed, enso_phase, is_dry, is_extreme_rain, is_normal, label_primary, episode_id`.
2. Fungsi `renaro.eval.regimes.filter(preds, origin, part, regime)` (koordinasi dengan MLE) agar semua model memakai subset identik.
3. `eval_splits/summary.csv`: jumlah node-hari per regime per origin/part; tanda "CI lebar" bila < 200.
4. Untuk holdout: siapkan **definisi** label (berbasis tanggal ≥ 2026-06-01 = "El Niño berkembang" + label kering/ekstrem dari CHIRPS holdout) yang dihitung di CGS-H6-01. Belum dihitung sekarang.

**Output:** `data/processed/eval_splits/` + `summary.csv`.
**DoD:** [ ] tiap origin punya ≥ 2 regime dengan ≥ 200 node-hari, atau keterbatasan dicatat untuk RL.

## CGS-H4-02 · Diagnostik lead-lag hujan asal → harga

| | |
|---|---|
| Waktu | H4 12.00–17.00 |
| Mode | PARALEL |
| Input | `dataset_v1` (hanya **bagian latih O3**, ≤ 2024-06-30), `bps_mask.npy` |
| Handoff | MLE-H4-01 (sanity jeda), laporan |

**Langkah**
1. Agregasikan harga ke pentad (rata-rata log harga per pentad) → log-return pentad per provinsi.
2. Untuk setiap edge BPS `j → i`: korelasi silang `rain_pentad_anom_j(t − ℓ)` vs `Δlog p_i(t)` untuk ℓ = 0…12 pentad, terpisah untuk fase ENSO (El Niño / La Niña / netral) dan untuk asal kering vs tidak.
3. Ringkas: distribusi jeda puncak, proporsi edge dengan korelasi signifikan (koreksi FDR Benjamini–Hochberg), contoh 6 edge terkuat.
4. Interpretasi ditulis sebagai **dependensi prediktif**, bukan arus pasokan.

**Output:** `reports/leadlag/leadlag_edges.csv` (`origin, dest, phase, lag, corr, p, q`), `reports/leadlag/fig_peak_lag_hist.png`, `fig_top_edges.png`, `leadlag_summary.md`.
**DoD:** [ ] hanya memakai data latih · [ ] ringkasan 5 kalimat dikirim ke MLE dan RL.

---

## CGS-H5-01 · Misspesifikasi graph prior + joint climate–graph shift

| | |
|---|---|
| Waktu | H5 09.15–16.00 |
| Mode | **SEKUENSIAL**: menunggu checkpoint Modul 1 dari MLE-H4-01 (`experiments/handoff/module1_for_robustness.yaml`) dan `perturbations/` (MDE-H4-02) |
| Tools | `scripts/robustness.py` (ditulis CGS memakai fungsi eval/predict MLE), PyTorch |
| Koordinasi GPU | GPU dipakai bersama MLE. CGS menjalankan eksperimen **inferensi** (murah) pagi; eksperimen **latih ulang** dijadwalkan di antrean semalam H4→H5 atau di jeda run MLE |
| Handoff | MLE-H6-01, laporan |

**Langkah**
1. **Misspesifikasi saat uji (inferensi):** model Modul 1 (dilatih dengan prior `bps`, O3, 5 seed) dievaluasi pada validasi/uji O3 dengan `candidate_mask` diganti 45 matriks perturbasi + `none`. Ukur MAE dan Δ vs mask asli.
2. **Misspesifikasi saat latih (subset):** latih ulang Modul 1 dengan prior terperturbasi p ∈ {10, 30, 50} × {drop, add, rewire} × seed perturbasi 0 × seed model {0, 1, 2}. Baseline pembanding: GWN dengan prior yang sama.
3. **Joint shift:** pecah hasil langkah 1–2 berdasarkan regime (normal vs kering vs hujan ekstrem vs fase ENSO). Pertanyaan RQ3: apakah degradasi akibat graph keliru **lebih besar** saat regime iklim ekstrem?
4. Kurva: MAE vs p per operasi, garis terpisah per regime.

**Output**
- `reports/robustness/robustness_val.csv`: `model, train_prior, test_prior, op, p, pert_seed, model_seed, mode (test|train), regime, mae, rmse, smape`.
- `reports/robustness/fig_mae_vs_p.png`, `fig_joint_shift.png`, `robustness_summary.md`.

**DoD:** [ ] semua kombinasi langkah 1 lengkap · [ ] langkah 2 minimal p ∈ {10, 50} bila waktu kurang (catat).

---

## CGS-H6-01 · Buka holdout satu kali + jalankan semua model beku

| | |
|---|---|
| Waktu | H6 09.15–11.00 |
| Mode | **SEKUENSIAL**: menunggu tag `gate2-freeze` + `frozen/manifest.yaml` |
| Tools | `scripts/predict.py` (MLE-H5-03) |
| Handoff | MLE-H6-01 |

**Langkah**
1. `git fetch --tags; git checkout gate2-freeze`. Working tree harus bersih.
2. Verifikasi SHA-256 checkpoint di manifest dan SHA-256 holdout di `docs/holdout_seal.md`. Ada yang tidak cocok → **hentikan**, lapor RL.
3. Buat file `HOLDOUT_UNSEALED` di `RENARO_SEALED_DIR` (isi: waktu, commit).
4. Jalankan **sekali**:
   ```powershell
   python scripts/predict.py --manifest frozen/manifest.yaml --context data/processed/dataset_v1 --holdout $env:RENARO_SEALED_DIR\holdout_v1 --out reports/holdout/predictions
   ```
5. Hitung label regime holdout (definisi CGS-H4-01) → `reports/holdout/regime_labels_holdout.csv`.
6. Isi bagian "Dibuka" di `docs/holdout_seal.md`. Commit prediksi (ukurannya kecil) + label.
7. **Aturan pasca-buka:** jika ditemukan bug setelah holdout dibuka, hasil awal **tetap dilaporkan**. Run ulang apa pun diberi label "post-hoc" dan dilaporkan terpisah.

**Output:** `reports/holdout/predictions/preds_<model>_s<seed>.parquet`, `reports/holdout/regime_labels_holdout.csv`, `docs/holdout_seal.md` (diperbarui).
**DoD:** [ ] semua model di manifest punya prediksi 5 seed · [ ] waktu buka tercatat · [ ] tidak ada model di luar manifest yang dijalankan.

## CGS-H6-02 · Dukungan analisis (bersama MLE-H6-01)
- Karakterisasi iklim holdout: lintasan RONI Jun–Nov 2026, peta anomali hujan pentad per provinsi, provinsi yang mengalami kering/ekstrem.
- Tulis `reports/sprint1/05_iklim_dan_regime.md` (ALL-H6-01).

## CGS-H7-01 · Arsip paket iklim

**Isi `release/climate/`**
1. Kode: `src/renaro/climate/`, skrip unduh (termasuk opsi pentad bila dibuat), `w_kab_pixel` builder.
2. Data turunan: `rain_prov_daily.parquet`, `climate_features.parquet`, `climatology.parquet`, `roni.parquet` + `roni_vintage_log.csv`, `availability.csv`, `regime_labels.csv`, `docs/regime_definitions.md`.
3. `SOURCES.md`: sitasi CHIRPS v3 (CHC), NOAA CPC RONI, BPS Statistik Hortikultura (atribusi wajib), sumber batas wilayah + lisensinya.
4. `manifest.csv` CHIRPS (URL + SHA-256) agar unduhan dapat diverifikasi ulang.

**DoD:** [ ] tidak memuat data holdout mentah kecuali diputuskan RL setelah Gate 3 · [ ] setiap file punya baris di `SOURCES.md`.
