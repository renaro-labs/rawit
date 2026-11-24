# QA — Mask BPS Poldis cabai merah 2022 (`MDE-H2-03`)

_Dibuat otomatis oleh `python -m renaro.data.bps_mask`. Audit naratif lengkap RL+MDE: [`bps_mask_rl_audit.md`](bps_mask_rl_audit.md)._

Sumber: BPS, *Distribusi Perdagangan Komoditas Cabai Merah di Indonesia 2022* (`data/raw/bps/BPS0000-distribusi_perdagangan_komoditas_cabai_merah_di_indonesia_2022.pdf`), bab provinsi hal. PDF 45–177 (diagram di halaman pertama tiap bab).

Konvensi: `bps_mask.npy` **A[i, j] = 1 bila j → i** (baris = tujuan, kolom = asal), urutan baris = `PROVINCES` di `contract.py` / `data/ref/provinces.csv`. `bps_mask_2022.csv` = transpos (baris = pemasok).

## Ringkasan

| Metrik | Nilai |
|---|---|
| Entri (kemunculan edge per halaman) | 195 |
| Edge berarah unik | **99** |
| Densitas (dari 34×33 = 1122 pasangan) | **8.82%** (ekspektasi tim ±14%, bukan target keras) |
| Edge terkonfirmasi 2 kotak (asal+tujuan) | 96 |
| Edge hanya 1 kotak | 3 (3.03%) |
| Edge typo BPS (terkonfirmasi narasi) | 2 (2.02%) → 97 edge bersih |
| Bab provinsi dengan entri | 33/34 |
| Provinsi tanpa asal (in-degree 0) | Papua (`94`) |
| Provinsi tanpa tujuan (out-degree 0) | Riau (`14`), Kepulauan Bangka Belitung (`19`), Kepulauan Riau (`21`), Nusa Tenggara Timur (`53`), Kalimantan Utara (`65`), Sulawesi Barat (`76`), Maluku Utara (`82`), Papua Barat (`91`), Papua (`94`) |

## Cakupan 34 provinsi

33 bab punya entri edge. Tanpa entri: Papua (`94`) hal. 177 — **tidak ada data antarprovinsi** (diagram tidak mencantumkan provinsi asal/tujuan; seluruh pasokan dari dalam provinsi).

**Keputusan RL untuk RQ0 (c)**: Papua (`94`) memakai rata-rata hujan 3 provinsi terdekat (centroid): Papua Barat `91`, Maluku `81`, Maluku Utara `82`.

## Verifikasi ganda

1. **Bilateral (dua kotak di dua halaman)** — tiap edge idealnya tercetak di kotak PENJUALAN provinsi asal *dan* kotak PEMBELIAN provinsi tujuan.
   - 96/99 simetris; 3 hanya satu kotak → ketidaksesuaian **3.03%**, salah cetak terkonfirmasi **2.02%** (< 5% ✅).

| Edge (asal → tujuan) | Halaman | Kotak | Hasil audit |
|---|---|---|---|
| Nusa Tenggara Barat (`52`) → Jawa Timur (`35`) | 113 | tujuan | TYPO BPS hal. 113: narasi hal. 114 NTB hanya ke Babel; hal. 101-102 Jatim hanya dari Jateng/Bali/Sulsel. |
| Sulawesi Selatan (`73`) → Kalimantan Timur (`64`) | 149 | tujuan | VALID: narasi hal. 134 (Kaltim) & 150 (Sulsel) menyebut Sulsel memasok Kaltim. |
| Sulawesi Tenggara (`74`) → Kalimantan Timur (`64`) | 133 | asal | TYPO BPS hal. 133: narasi hal. 134 menyebut Sulsel, hal. 154 Sultra hanya ke Sulsel & Maluku. |

Mask literal memuat semua edge tercetak (aturan *put 1 for every printed link*); filter `n_confirmations == 2` di `bps_mask.csv` untuk uji sensitivitas.

2. **Teks PyMuPDF vs entri**: PDF belum ada di `data/raw/bps/BPS0000-distribusi_perdagangan_komoditas_cabai_merah_di_indonesia_2022.pdf` saat laporan dibuat — jalankan ulang setelah PDF ditaruh.

## Derajat per provinsi

| Kode | Provinsi | Hal. | In (asal) | Out (tujuan) |
|---|---|---|---|---|
| 11 | Aceh | 45 | 1 | 2 |
| 12 | Sumatera Utara | 49 | 1 | 6 |
| 13 | Sumatera Barat | 53 | 8 | 3 |
| 14 | Riau | 57 | 4 | 0 |
| 15 | Jambi | 61 | 2 | 2 |
| 16 | Sumatera Selatan | 65 | 6 | 4 |
| 17 | Bengkulu | 69 | 6 | 4 |
| 18 | Lampung | 73 | 4 | 4 |
| 19 | Kepulauan Bangka Belitung | 77 | 9 | 0 |
| 21 | Kepulauan Riau | 81 | 3 | 0 |
| 31 | DKI Jakarta | 85 | 5 | 5 |
| 32 | Jawa Barat | 89 | 5 | 4 |
| 33 | Jawa Tengah | 93 | 3 | 15 |
| 34 | DI Yogyakarta | 97 | 1 | 5 |
| 35 | Jawa Timur | 101 | 4 | 16 |
| 36 | Banten | 105 | 4 | 2 |
| 51 | Bali | 109 | 1 | 1 |
| 52 | Nusa Tenggara Barat | 113 | 1 | 2 |
| 53 | Nusa Tenggara Timur | 117 | 1 | 0 |
| 61 | Kalimantan Barat | 121 | 3 | 1 |
| 62 | Kalimantan Tengah | 125 | 4 | 1 |
| 63 | Kalimantan Selatan | 129 | 2 | 1 |
| 64 | Kalimantan Timur | 133 | 4 | 1 |
| 65 | Kalimantan Utara | 137 | 2 | 0 |
| 71 | Sulawesi Utara | 141 | 1 | 1 |
| 72 | Sulawesi Tengah | 145 | 2 | 4 |
| 73 | Sulawesi Selatan | 149 | 2 | 9 |
| 74 | Sulawesi Tenggara | 153 | 1 | 3 |
| 75 | Gorontalo | 157 | 1 | 2 |
| 76 | Sulawesi Barat | 161 | 2 | 0 |
| 81 | Maluku | 165 | 3 | 1 |
| 82 | Maluku Utara | 169 | 1 | 0 |
| 91 | Papua Barat | 173 | 2 | 0 |
| 94 | Papua | 177 | 0 | 0 |

Top pemasok (out): Jawa Timur 16, Jawa Tengah 15, Sulawesi Selatan 9, Sumatera Utara 6, DKI Jakarta 5

Top pembeli (in): Kepulauan Bangka Belitung 9, Sumatera Barat 8, Sumatera Selatan 6, Bengkulu 6, DKI Jakarta 5

## Catatan

- `share_pct` kosong untuk semua edge: diagram Poldis 2022 tidak mencetak persentase per provinsi; mask dipakai biner.
- Luar negeri / lainnya dibuang; diagonal 0.
- Densitas nyata 8.82% di bawah ekspektasi ±14% — dilaporkan apa adanya (tidak ada edge yang diinferensikan).
