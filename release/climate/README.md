# RENARO RAWIT — Climate & Geospatial Release (Sprint 1)

Paket ini berisi **kode dan data turunan iklim/geospasial** yang dipakai bersama oleh MDE, MLE, dan RL pada Sprint 1. Paket **tidak** memuat data mentah PIHPS/SP2KP dan **tidak** memuat data holdout (`>= 2026-06-01`).

## Isi paket

| Folder | Isi |
|---|---|
| `code/` | Snapshot `src/renaro/climate/` (`rain.py`, `pentad.py`, `availability.py`, `regimes.py`), CHIRPS downloader, `w_kab_pixel` builder, dan verifier CGS-H2 |
| `data/` | Data turunan shared: hujan provinsi harian, fitur pentad, klimatologi, RONI, availability, label regime (EVAL ONLY), dan matriks bobot kab→piksel |
| `docs/` | `regime_definitions.md` |
| `manifest.csv` | 113 file CHIRPS bulanan: URL COG pertama/terakhir + SHA-256 |
| `manifest_daily.csv` | 3.438 baris manifest CHIRPS harian (URL + status + bytes) |
| `SOURCES.md` | Sitasi, lisensi, dan asal setiap file |
| `SHA256SUMS` | Checksum paket |

## Cakupan data

- CHIRPS v3.0 daily `final/sat`, subset Indonesia: **2017-01-01 .. 2026-05-31** (113 bulan; 3.438 hari; grid 360 × 950; 0,05°).
- RONI NOAA CPC (ERSSTv6, basis 1991–2020): **915 musim shared**, DJF 1950 .. FMA 2026; 6 musim setelah FMA 2026 berada di `RENARO_SEALED_DIR` dan **tidak** termasuk paket.
- Produksi cabai 2024 kab/kota: 514 kab/kota, 34 provinsi; 1.469.325,119 ton. Produksi 2025/2026 belum terbit; bobot 2025–2026 memakai 2024 (aturan `y-1`).
- Batas wilayah: geoBoundaries gbOpen IDN ADM2 2020; 514 kab/kota; EPSG:4326.
- Label regime: 116.892 baris harian, **EVAL ONLY**, 2017-01-01 .. 2026-05-31.

## Cara rebuild

Kode ini adalah snapshot dari repo `renaro-labs/rawit` (tag `sprint1-final`). Cara paling aman adalah memakai tag tersebut, lalu menaruh data mentah di `data/raw/`:

```powershell
git clone --branch sprint1-final https://github.com/renaro-labs/rawit.git
cd rawit
# salin data mentah dari drive bersama ke data/raw/{chirps_v3,bps,boundaries,enso}
$env:PYTHONPATH="$PWD\src"

# 1) CHIRPS (resume-safe; butuh rasterio/GDAL)
python scripts\download_chirps_v3.py --start 2017-01-01 --end 2026-05-31 `
  --variant final/sat --out data\raw\chirps_v3 --source cog --workers 2 --delay 1 --retries 6

# 2) bobot kab/kota -> piksel
python scripts\cgs\build_kab_pixel_weights.py

# 3) hujan provinsi + indeks pentad + availability + label regime
python -m renaro.climate.rain
python -m renaro.climate.pentad
python -m renaro.climate.availability
python -m renaro.climate.regimes

# 4) verifikasi
python scripts\cgs\verify_cgs_h2.py
```

Jika memakai data turunan yang sudah ada, cukup salin isi `data/` ke `data/interim/` dan jalankan verifier.

## Verifikasi yang disarankan

```powershell
python scripts\cgs\verify_cgs_h2.py          # 39 checks PASS
python scripts\cgs\verify_chirps.py --root . # 3.438/3.438 hari OK
python -m pytest -q tests\test_no_leakage.py # 15 passed
```

Cek manual:

- `data/rain_prov_daily.parquet`: 116.892 baris = 34 provinsi × 3.438 hari; 0 `rain_mm` hilang.
- `data/climate_features.parquet`: 23.052 baris; 678 pentad; `rain_pentad_anom` 0 hilang.
- `data/regime_labels.csv`: 116.892 baris; tidak ada tanggal >= 2026-06-01.
- `data/roni.parquet`: 915 baris; tidak ada `(year == 2026) & (center_month >= 4)`.
- `manifest.csv`: 113 baris; setiap baris punya `url_first`, `url_last`, `sha256`.

## Batasan ilmiah

1. Klimatologi baseline hanya **2017**; perlu ekstensi 2008–2017 untuk stabilitas jangka panjang. 1.088 `rain_30d_anom` NaN berasal dari tepi baseline ini.
2. CHIRPS harian adalah **disagregasi pentad**; jangan mengklaim presisi harian independen. Kekeringan/ekstrem didefinisikan pada pentad.
3. Bobot produksi hanya tersedia untuk 2025–2026; 2017–2024 memakai bobot luas. Produksi 2025/2026 belum terbit dan tidak diimputasi.
4. Label regime adalah **EVAL ONLY**; jangan di-join ke panel/fitur.
5. Paket tidak memuat data holdout mentah; holdout dibuka terpisah oleh CGS-H6-01 setelah Gate 2.
6. Matriks bobot 61.825 sel; 42 kota kecil memakai fallback 9 piksel terdekat; NaN piksel tidak diisi nol.

## Lisensi dan sitasi

Lihat `SOURCES.md`. Ringkasnya: CHIRPS (CHC/UCSB), RONI (NOAA CPC), produksi (Satudata Pertanian/BPS), batas wilayah (geoBoundaries, CC BY 3.0 IGO). Data mentah tidak diredistribusi; paket ini hanya data turunan dan kode.
