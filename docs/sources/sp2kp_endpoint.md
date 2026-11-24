# SP2KP Kemendag — endpoint harga harian (MDE-H1-02)

- **Status**: DRAF. Endpoint dan parameter diambil dari bundel JavaScript situs `sp2kp.kemendag.go.id` dan scraper terbuka (lihat §6); **belum** dicocokkan dengan request asli dari DevTools dan belum diuji dari jaringan tim.
- **Pemilik**: MDE (@dio) · **Dipakai oleh**: `src/renaro/data/sp2kp.py`
- **Contoh request asli**: `docs/sources/sp2kp_request_example.txt` — **BELUM ADA**
- **Peran data**: **hanya validasi silang** terhadap PIHPS (MDE-H2-01). **Dilarang** dipakai sebagai fitur atau target.

## 1. Endpoint

| Fungsi | Metode | URL |
|---|---|---|
| Master provinsi | GET | `https://api-sp2kp.kemendag.go.id/master/api/wilayah/provinsi?take=100` |
| Harga harian per wilayah (dipakai) | POST `multipart/form-data` | `https://api-sp2kp.kemendag.go.id/report/api/average-price/export-area-daily-json` |
| Harga rata-rata publik (disebut brief) | GET | `https://api-sp2kp.kemendag.go.id/report/api/average-price-public` |

Tanpa API key. Header yang dikirim: `Origin`/`Referer: https://sp2kp.kemendag.go.id`, `Accept: application/json`.

### Kenapa bukan `average-price-public`?
Brief menyebut `average-price-public`. Menurut probe pihak lain, endpoint ini mengembalikan **baris entri mentah yang dipaginasi** (`data, totalCount, summary, meta`). Setiap baris memuat objek `creator` berisi **data pribadi petugas** (nama, email, NIP). Endpoint ini tidak cocok disimpan "apa adanya" di drive tim. `export-area-daily-json` mengembalikan **harga rata-rata harian per wilayah** tanpa data pribadi. `--probe` mencetak struktur keduanya (hanya nama kunci, tanpa nilai) supaya pilihan ini bisa dikonfirmasi.

## 1b. Halaman sumber di situs

Halaman publik **Statistik → Area** (`https://sp2kp.kemendag.go.id/statistik/area`) memanggil `export-area-daily-json` saat tombol **Lihat** ditekan. Field `level` diisi otomatis oleh halaman: Provinsi = "Nasional" → 0; pilih satu provinsi → **1**; ditambah Kab/Kota → 2; ditambah Pasar → 3. UI membatasi Tanggal Akhir paling jauh 30 hari dari Tanggal Awal. Apakah API juga membatasi rentang ini diuji lewat `--probe`.

## 2. Parameter `export-area-daily-json`

| Field form | Nilai kita | Arti | Diverifikasi DevTools? |
|---|---|---|---|
| `start_date` / `end_date` | `YYYY-MM-DD` | rentang inklusif; per tahun kalender (opsi `--chunk-days N` bila respons terpotong) | [ ] |
| `level` | `1` | 0 nasional, 1 provinsi, 2 kab/kota, 3 pasar | [ ] |
| `variant_ids` | `2` | Cabai Merah Keriting (kg) | [ ] |
| `kode_provinsi` | kode Kemendagri 2 digit | satu provinsi per request | [ ] |
| `kode_kab_kota`, `pasar_id` | `""` | tidak difilter | [ ] |
| `skip_sat_sun` | `true` | lewati Sabtu–Minggu | [ ] |
| `tipe_komoditas` | `1` | komoditas pokok | [ ] |

## 3. Struktur respons (dari scraper rujukan)

```json
{"status": "success", "data": [
  {"variant_id": 2, "variant": "Cabai Merah Keriting", "satuan": "kg", "kuantitas": 1, "order": 3,
   "daftarHarga": [{"date": "2024-03-01", "harga": 50000}, "..."]}
]}
```

`harga` 0/kosong = tidak ada pencatatan → NaN (bukan 0).

## 4. Jebakan kode provinsi (penting)

SP2KP memakai **kode Kemendagri pasca-pemekaran**, sedangkan kontrak memakai **kode BPS lama**:

| Nama SP2KP | Kode SP2KP | Kode kontrak (BPS lama) |
|---|---|---|
| Papua | 91 | **94** |
| Papua Barat | 92 | **91** |
| Papua Selatan | 93 | 94 (digabung) |
| Papua Tengah | 94 | 94 (digabung) |
| Papua Pegunungan | 95 | 94 (digabung) |
| Papua Barat Daya | 96 | 91 (digabung) |

Karena kode `91` dan `94` artinya berbeda di kedua sistem, pemetaan 38 → 34 dilakukan **lewat nama**, bukan kode. Nilai 91/94 dihitung sebagai rata-rata sederhana provinsi sumber yang punya harga pada hari itu, dengan `is_aggregated=True`, `n_source_prov`, dan `source_prov_names`. Nama yang tidak dikenal membuat proses gagal, bukan dibuang diam-diam.

## 5. Output

- `data/raw/sp2kp/master_provinsi.json`, `data/raw/sp2kp/l1_p{kode}_{YYYYMMDD}_{YYYYMMDD}.json` (body respons byte-persis), `data/raw/sp2kp/manifest.csv`.
- `data/raw/sp2kp/_sealed/` hanya dengan `--include-sealed` (≥ 2026-06-01).
- `data/interim/sp2kp_long.parquet`: `date, prov_code, commodity, price_type=2, price, is_aggregated, n_source_prov, source_prov_names, source="sp2kp", available_at` (= hari kerja berikutnya).

## 6. Rujukan

- Bundel JS `sp2kp.kemendag.go.id` (fungsi `statistikJsonHarian` → `export-area-daily-json`, `fetchDataPublic` → `average-price-public`), terekam di github.com/RobyArjuna/scraping-commodity-sk2kp (`tmp_sp2kp_chunks/`).
- github.com/RobyArjuna/scraping-commodity-sk2kp `scrape_sp2kp_blitar.py`; github.com/Rianfirnanda/lintasAIprojection `pipeline/konektor_sp2kp.py` (form multipart, `variant_id=2` = Cabai Merah Keriting); github.com/yys-4/pangan-watch `reports/01_data_discovery.md` (data tersedia sejak 2024).
