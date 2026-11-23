# PIHPS — endpoint `GetGridDataKomoditas` (MDE-H1-01)

- **Status**: TERVERIFIKASI (2026-11-24). Semua parameter dan format tanggal cocok dengan request asli dari DevTools (`pihps_request_example.txt`), dengan unduhan tim 2026-11-22, dan dengan 16 file JSON nyata.
- **Pemilik**: MDE (@dio)
- **Dipakai oleh**: `src/renaro/data/pihps.py` (unduh + manifest), `src/renaro/data/pihps_parse.py` (JSON → long table)
- **Contoh request asli**: `docs/sources/pihps_request_example.txt` (Copy as cURL, Chrome 157, cookie dan XSRF-TOKEN dihapus)

## 1. Endpoint

| Item | Nilai |
|---|---|
| Halaman UI | `https://www.bi.go.id/hargapangan/TabelHarga/PasarTradisionalKomoditas` |
| URL data | `https://www.bi.go.id/hargapangan/WebSite/TabelHarga/GetGridDataKomoditas` |
| Metode | `GET` (XHR) |
| Auth | Tanpa API key. Situs memasang cookie sesi/antiforgery saat halaman utama dibuka; scraper membuka `https://www.bi.go.id/hargapangan` dulu dengan `requests.Session`. |
| Header | `X-Requested-With: XMLHttpRequest`, `Accept: application/json, text/javascript, */*; q=0.01`. Browser juga mengirim header `XSRF-TOKEN` dan cookie `WSAntiforgeryCookie`/`TS*` (per sesi). Scraper hanya memakai cookie sesi dari halaman utama, sama seperti unduhan tim dan pangan.id. Bila `--probe` mendapat 400/403, token XSRF perlu diambil dari halaman lalu dikirim sebagai header. |

## 2. Parameter

| Parameter | Nilai kita | Arti | Diverifikasi DevTools? |
|---|---|---|---|
| `price_type_id` | `1` / `4` | 1 = pasar tradisional (target), 4 = produsen (fitur). 2 = pasar modern (tidak dipakai). | [x] |
| `comcat_id` | `com_14` | Cabai Merah Keriting | [x] |
| `province_id` | `""` (kosong) | kosong = semua provinsi dalam satu respons | [x] |
| `regency_id` | `""` | kosong = tanpa filter kab/kota | [x] |
| `showKota` | `false` | jangan pecah ke kota | [x] |
| `showPasar` | `false` | jangan pecah ke pasar | [x] |
| `tipe_laporan` | `1` | 1 = harian (cek nilai mingguan/bulanan di dropdown) | [x] |
| `start_date` | `YYYY-MM-DD` | tanggal awal, inklusif | [x] `YYYY-MM-DD` |
| `end_date` | `YYYY-MM-DD` | tanggal akhir, inklusif | [x] `YYYY-MM-DD` |
| `_` | epoch ms | cache-buster jQuery, nilai bebas | [x] |

Kalau DevTools menunjukkan nama atau format lain (misalnya `dd/MM/yyyy` atau `province_id=0` untuk "semua"), ubah konstanta `PARAM_*`/`DATE_FMT` dan `request_params()` di `pihps.py`, lalu centang tabel ini.

## 3. Struktur respons

```json
{"data": [
  {"no": "",  "name": "Semua Provinsi", "level": 0, "01/03/2024": "50,000", "...": "..."},
  {"no": "1", "name": "Aceh",           "level": 1, "01/03/2024": "44,750", "04/03/2024": "-"},
  "..."
]}
```

- Satu baris per wilayah. `level 0` = nasional, `level 1` = provinsi, `level ≥ 2` = kota/pasar (muncul bila `showKota=true`). Parser hanya mengambil `level == 1`.
- Kolom tanggal berformat `dd/mm/yyyy`, satu kolom per hari kerja.
- Nilai berupa string rupiah bulat dengan pemisah ribuan (`"44,750"`; bisa juga `"44.750"`). `"-"`, kosong, `null`, atau `"0"` dibaca sebagai missing (NaN), bukan 0.

## 4. Jebakan yang sudah diketahui

1. **Papua pasca-pemekaran.** Mulai 2022–2023, PIHPS bisa menampilkan `Papua Selatan`, `Papua Tengah`, `Papua Pegunungan`, dan `Papua Barat Daya`. Kontrak kita memakai 34 provinsi struktur lama (`91` Papua Barat, `94` Papua). Parser menyimpan **nama mentah**; keputusan agregasi atau pemetaan ada di MDE-H2-01. Jangan meniru pemetaan pangan.id (`Papua Barat → 92`, `Papua Tengah → 94`) karena itu kode BPS baru dan bertabrakan dengan kontrak.
2. **Holdout.** Tidak ada request yang melewati `2026-06-01`. `WINDOWS` berhenti di `2026-05-31`. Holdout sudah disegel CGS (`docs/holdout_seal.md`), jadi `--include-sealed` hanya dipakai bila CGS meminta.
3. **Penamaan file (playbook 2/2)**: `data/raw/pihps/pt{tipe}_{YYYYMMDD}_{YYYYMMDD}.json`, berisi body respons byte-persis, plus `data/raw/pihps/manifest.csv` (`file, price_type, start, end, n_bytes, sha256, fetched_at, http_status`, ditambah `n_rows, n_date_cols, url`). Holdout masuk ke `data/raw/pihps/_sealed/` dengan manifest sendiri. File unduhan tim (`json/pihps_pt*_YYYY-MM-DD_*.json[.gz]`, jendela Jul–Jun) tetap bisa di-parse lewat `--parse-dir data/raw/pihps/json`, sebagai pembanding.
4. **Sopan ke server.** Jeda ≥ 5 detik antar-request dan retry maksimal 3 kali dengan backoff.

## 5. Status data mentah yang sudah ada (`data/raw/pihps/`, dicek 2026-11-24)

- Sumber: `pihps-extracted.zip` (rilis terbaru tim). 16 file `.json` byte-identik dengan isi `.json.gz` versi sebelumnya; `.json.gz` lama sudah dihapus. Manifest ekstraksi tim disimpan sebagai `extract_manifest.csv`, supaya tidak bentrok dengan `manifest.csv` milik scraper.

- JSON tipe 1 & 4: jendela Jul–Jun, `2017-07-01 .. 2025-06-30` (16 file). File `2025-07-01_2026-06-30` melewati holdout, sehingga ikut disegel CGS. Akibatnya **JSON untuk 2025-07-01 .. 2026-05-31 tidak ada**, dan periode ini hanya ada di CSV.
- `pihps.py --parse-only` atas 16 JSON: 127.791 baris. Dibandingkan dengan `pihps_cabai_merah_keriting_province.csv`: 127.530 baris cocok, **0 selisih nilai**. 261 baris ekstra = baris rusak `Dum` (level 1) di file 2021-07..2022-06.
- Nama provinsi: 34 nama struktur lama + `Semua Provinsi` (level 0). Tidak ada nama provinsi Papua hasil pemekaran.
- Tipe 1: setiap hari kerja sejak 2018 memuat 34 baris provinsi. Tipe 4: 31 provinsi dengan harga valid.
- `pihps_2025_2026_province.json` (dikirim tim 2026-11-24): bukan respons API mentah. Isinya potongan dari CSV bersama (`note`: *Derived from shared CSV*), 23.920 baris, 2025-01-01 .. 2026-05-29, 34 provinsi, tanpa baris nasional, tanpa tanggal holdout. Hasil pengecekan: identik dengan CSV, 0 selisih nilai. File ini tidak menutup celah JSON mentah Jul 2025 – Mei 2026; untuk provenance, unduh ulang jendela itu dengan `--start 2025-07-01 --end 2026-05-31`.
- `README.md` di folder itu ditulis sebelum penyegelan dan masih memuat ringkasan periode ≥ 2026-06-01 (rentang, contoh nilai). Minta CGS memotong bagian itu.

## 6. Temuan vs brief (jumlah provinsi berharga valid)

| Tipe | Brief | Data (unduhan tim) |
|---|---|---|
| 1 | 27 provinsi pada Jul 2017; 34 sejak Jan 2018 | 31 pada Jul 2017, 33 pada Agu–Sep 2017, 34 sejak Okt 2017; setiap hari kerja sejak 2018 memuat 34 baris |
| 4 | 29 provinsi 2019; 32 provinsi 2020 | 29 pada 2018 (mulai 2018-03-26), 31 sejak 2019; DKI Jakarta & Bali tidak pernah ada |

Validasi `pihps_parse.validate_long` memakai batas brief sebagai batas bawah (≥ 27 di Jul 2017, 34 baris/hari sejak 2018).

## 7. Pembanding

- pangan.id: `src/lib/pihps.ts` (fungsi `fetchPihpsCommodityTable`) dan `scripts/scraper.py` (`fetch_prices_for_date_range`) di github.com/gnatnib/pangan.id. Parameternya sama dengan tabel di atas.
