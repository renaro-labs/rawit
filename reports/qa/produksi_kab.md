# CGS-H1-03 - Produksi/luas cabai per kab/kota + batas wilayah

Status: **DONE untuk data yang tersedia** - 2024 kab/kota lengkap; provinsi 2017-2024; produksi 2025/2026 belum dipublikasikan (per 23 Nov 2026).

## Sumber

- **2024 kab/kota**: Satudata Pertanian, Ditjen Hortikultura, dataset 392, sheet `Cabai Besar-Kab 2024`; file di `source/`. Produksi sumber kuintal -> ton (/10).
- **2017-2023 provinsi**: BPS WebAPI, domain 0000, variabel 61 (`Produksi Tanaman Sayuran`), turvar 132 (`Cabai Besar (Ton)`).
- **Batas**: geoBoundaries gbOpen IDN ADM2 2020; 519 fitur -> 514 kab/kota + 5 non-admin.
- **BPS_API_KEY**: terverifikasi; dipakai untuk seri provinsi. Key tidak disimpan di file hasil.

## Cakupan produksi

| tahun | level | baris | provinsi | total ton |
|---:|---|---:|---:|---:|
| 2017 | provinsi | 34 | 34 | 1,206,265 |
| 2018 | provinsi | 33 | 33 | 1,206,750 |
| 2019 | provinsi | 34 | 34 | 1,214,419 |
| 2020 | provinsi | 34 | 34 | 1,264,193 |
| 2021 | provinsi | 33 | 33 | 1,360,573 |
| 2022 | provinsi | 34 | 34 | 1,475,819 |
| 2023 | provinsi | 33 | 33 | 1,554,499 |
| 2024 | kab/kota | 514 | 34 | 1,469,325 |

Catatan: 2018, 2021, dan 2023 tidak memuat DKI Jakarta (tidak ada baris); provinsi lain lengkap. 2024 memakai 514 kab/kota; agregat provinsi 2024 ada di `produksi_prov_2024.csv`.

## Top 10 kab/kota (2024)

| # | kab_code | kab/kota | provinsi | produksi_ton |
|---:|---|---|---|---:|
| 1 | 1501 | KAB. KERINCI | Jambi | 162,363 |
| 2 | 3205 | KAB. GARUT | Jawa Barat | 105,730 |
| 3 | 3204 | KAB. BANDUNG | Jawa Barat | 89,328 |
| 4 | 1211 | KAB. KARO | Sumatera Utara | 71,664 |
| 5 | 1209 | KAB. SIMALUNGUN | Sumatera Utara | 47,537 |
| 6 | 1106 | KAB. ACEH TENGAH | Aceh | 43,882 |
| 7 | 3401 | KAB. KULON PROGO | DI Yogyakarta | 37,919 |
| 8 | 3203 | KAB. CIANJUR | Jawa Barat | 37,857 |
| 9 | 1303 | KAB. SOLOK | Sumatera Barat | 36,332 |
| 10 | 1307 | KAB. AGAM | Sumatera Barat | 35,040 |

## Join batas dan bobot area

- `boundaries/idn_adm2.gpkg`: 514 fitur, EPSG:4326, atribut `kab_code`, `prov_code`, `n_cells`, `area_weight`, `produksi_ton` 2024.
- Join produksi 2024 ke batas: **514/514 (100%)**; 513 exact + 1 fuzzy (Padangsidimpuan).
- `data/raw/bps/kab_area_weights.csv` memakai 61.825 sel; 42 kota kecil memakai fallback nearest 9; bobot provinsi berjumlah ~1.0.

## BPS WebAPI: apa yang sudah/belum

- Seri **provinsi 2017-2023** berhasil ditarik (235 baris, 34 provinsi; total 1,21-1,55 juta ton/tahun).
- Tabel **kab/kota** BPS tersebar per domain provinsi, dengan ID variabel/subjek, satuan, dan definisi yang berbeda. Probe Jabar/Aceh/Sumut menunjukkan perbedaan unit/scope (mis. 2017 vs 2018) sehingga belum layak digabung tanpa validasi.
- Karena itu `produksi_kab.csv` tetap memakai 2024 Satudata yang sudah tervalidasi; seri provinsi BPS disimpan terpisah.
- Untuk 2017-2023/2025 kab: perlu validasi per domain (var/turvar/unit) atau akses tabel publikasi BPS; jangan mengarang angka.

## Ketersediaan 2025/2026

- Satudata dataset 475 (`DATA PRIORITAS 2025`, rilis 31 Des 2025) masih memuat angka **tahun 2024**; belum ada tabulasi produksi 2025.
- BPS WebAPI var 61/turvar 132 berhenti di 2023; ID tahun 124-126 tidak mengembalikan data.
- Produksi 2025 diperkirakan terbit akhir 2026; 2026 belum tersedia.
- Karena aturan proyek `y-1`, untuk 2025 dan 2026 gunakan produksi 2024 sebagai bobot terakhir yang tersedia, dan catat keterbatasan ini di data card. Jangan mengarang angka.

## DoD

- [x] >=95% kab/kota ter-join ke poligon (514/514 = 100% dari kab/kota aktual).
- [x] Setiap provinsi punya >=1 kab dengan bobot >0.
- [x] Sanity produsen 2024: Jabar #1, Jateng #2, Sumut #3, Jatim #5 (level provinsi).
- [x] Aturan produksi tahun y dipakai mulai y+1 (2024 -> 2025).
- [x] Cakupan data tersedia: 2024 kab/kota + provinsi 2017-2024. 2025/2026 belum terbit (bukan kegagalan pipeline).

