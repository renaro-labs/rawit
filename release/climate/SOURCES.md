# Sumber, sitasi, dan lisensi — `release/climate`

Setiap file dalam paket ini memiliki baris sumber di bawah. Data mentah tidak
diredistribusi; yang disertakan adalah kode dan data turunan. Paket tidak
memuat data holdout (`>= 2026-06-01`).

## Sitasi utama

1. **CHIRPS v3.0** — Funk, C., Peterson, P., Landsfeld, M., Pedreros, D.,
   Verdin, J., Shukla, S., Husak, G., Rowland, J., Harrison, L., Hoell, A., &
   Michaelsen, J. (2015). *The climate hazards infrared precipitation with
   stations—a new environmental record for monitoring extremes.* Scientific
   Data, 2, 150066. <https://doi.org/10.1038/sdata.2015.66>.
   Data: Climate Hazards Center, UC Santa Barbara,
   <https://data.chc.ucsb.edu/products/CHIRPS/v3.0/>. Varian yang dipakai:
   daily `final/sat` (dan `prelim/sat` hanya untuk uji sensitivitas).
2. **RONI** — NOAA Climate Prediction Center, *Relative Oceanic Niño Index
   (RONI)*, ERSSTv6, basis 1991–2020.
   <https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt>;
   dokumentasi <https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/>.
   Data Pemerintah AS (domain publik); nilai 2–3 musim terakhir bersifat
   provisional.
3. **Produksi cabai** — Satudata Pertanian, Direktorat Jenderal Hortikultura,
   Kementerian Pertanian RI. Dataset 392 (`Cabai Besar-Kab 2024`),
   <https://satudata.pertanian.go.id/datasets/detail_data/392>.
   **Atribusi wajib** ke Satudata Pertanian/BPS. Data mentah tidak
   diredistribusi; hanya turunan bobot yang disertakan.
4. **Batas wilayah** — geoBoundaries gbOpen, Indonesia ADM2 (2020),
   <https://www.geoboundaries.org/api/current/gbOpen/IDN/ADM2/>.
   Lisensi **CC BY 3.0 IGO**; sumber: BPS, World Food Programme, OCHA ROAP.
   ADM1 (2017) memakai ODbL 1.0 (OpenStreetMap/Wambacher).
5. **Kalender** — SKB 3 Menteri (libur nasional, cuti bersama, Ramadan,
   Idulfitri, Iduladha). Dipakai sebagai aturan `known_in_advance` pada
   `availability.csv`; file kalender mentah tidak termasuk paket ini.
6. **Harga PIHPS/SP2KP** — Bank Indonesia / Kemendag. Hanya aturan
   ketersediaan `next_workday` yang dirujuk; data harga tidak termasuk paket
   dan tidak diredistribusi.

## File

| File | Isi | Sumber / lisensi |
|---|---|---|
| `README.md` | Dokumentasi paket | Dokumen proyek RENARO RAWIT |
| `SOURCES.md` | Dokumen ini | Dokumen proyek RENARO RAWIT |
| `code/rain.py` | Produksi hujan provinsi berbobot area/produksi | Kode proyek (CGS-H2-01); data CHIRPS + BPS |
| `code/pentad.py` | Indeks pentad, klimatologi, dry/extreme | Kode proyek (CGS-H2-02); data CHIRPS |
| `code/availability.py` | Tabel aturan `available_at` | Kode proyek (CGS-H2-03); keputusan RL/CGS |
| `code/regimes.py` | Label regime EVAL ONLY | Kode proyek (CGS-H2-04); CHIRPS + RONI |
| `code/build_kab_pixel_weights.py` | Builder matriks bobot kab→piksel | Kode proyek (CGS-H1/H2); geoBoundaries + BPS |
| `code/download_chirps_v3.py` | Downloader CHIRPS COG → NPZ | Kode proyek; sumber CHC/UCSB |
| `code/verify_cgs_h2.py` | Verifier paket H2 | Kode proyek |
| `code/__init__.py` | Inisialisasi paket | Kode proyek |
| `data/rain_prov_daily.parquet` | 116.892 baris hujan provinsi harian | Turunan CHIRPS v3 + bobot BPS/geoBoundaries |
| `data/climate_features.parquet` | 23.052 baris indeks pentad | Turunan CHIRPS v3 + klimatologi 2017 |
| `data/climatology.parquet` | 2.448 baris klimatologi 34 provinsi × 72 pentad | Turunan CHIRPS v3 (baseline 2017) |
| `data/roni.parquet` | 915 musim RONI shared (DJF 1950–FMA 2026) | NOAA CPC RONI (ERSSTv6); domain publik |
| `data/roni_vintage_log.csv` | Log aturan `available_at` RONI | NOAA CPC + keputusan proyek |
| `data/availability.csv` | 7 keluarga aturan ketersediaan | Keputusan protokol/RL; CHIRPS, RONI, BPS, SKB 3 Menteri, PIHPS |
| `data/regime_labels.csv` | 116.892 label harian EVAL ONLY | Turunan CHIRPS + RONI; definisi proyek |
| `data/w_kab_pixel.npz` | 514 kab × 342.000 piksel; 61.825 sel nonzero | Turunan geoBoundaries + BPS + grid CHIRPS |
| `docs/regime_definitions.md` | Definisi resmi regime | Dokumen proyek (CGS-H2-04) |
| `manifest.csv` | 113 file CHIRPS bulanan: URL COG pertama/terakhir + SHA-256 | CHC/UCSB CHIRPS v3.0; checksum dihitung dari file NPZ |
| `manifest_daily.csv` | 3.438 baris manifest CHIRPS harian | CHC/UCSB CHIRPS v3.0 `manifest.csv` |
| `SHA256SUMS` | Checksum seluruh file paket | Dihitung dari paket ini |

## Catatan lisensi

- CHIRPS: data iklim publik CHC/UCSB; sitasi ke Funk et al. (2015).
- RONI: data Pemerintah AS; domain publik; sitasi NOAA CPC.
- Produksi/BPS: data publik Pemerintah Indonesia; **atribusi wajib** ke
  Satudata Pertanian/BPS; data mentah tidak boleh diredistribusi tanpa izin.
- geoBoundaries ADM2: **CC BY 3.0 IGO**; atribusi ke geoBoundaries/BPS/WFP/OCHA.
- Kode proyek: milik Renaro Labs; tidak ada lisensi publik yang dinyatakan
  dalam repo ini. Hubungi pemilik proyek sebelum redistribusi.
- Paket ini **tidak** memuat data PIHPS/SP2KP mentah, data holdout, atau
  checkpoint model.
