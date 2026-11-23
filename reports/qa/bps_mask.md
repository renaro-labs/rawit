# Laporan 2 — Ekstraksi & Audit Bilateral Mask Graph BPS Poldis 2022 (`MDE-H2-03`)
**Disusun oleh:** RL (*Research Lead*) bersama MDE  
**Tanggal:** 23 November 2026  
**File CSV Terkait:**
* [07_bps_mask_2022_matriks_34x34.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/07_bps_mask_2022_matriks_34x34.csv) *(Matriks 34x34)*
* [08_bps_mask_2022_daftar_99_edges_audit.csv](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/csv_laporan/08_bps_mask_2022_daftar_99_edges_audit.csv) *(Daftar lengkap 99 edges + kode BPS + jarak km + halaman PDF + status bilateral)*
* [supporting_data/bps_mask.npy](file:///c:/Users/ALIM/Downloads/rawit_sprint1_datasets_partial/RL%20hasil/supporting_data/bps_mask.npy) *(Array `34x34 uint8` sesuai kontrak `A[i,j]=1` bila `j -> i`)*

---

## 1. Metodologi Ekstraksi & Verifikasi Ganda

Seluruh **34 bab provinsi** pada publikasi BPS *Distribusi Perdagangan Komoditas Cabai Merah di Indonesia 2022* (halaman PDF 45–177 / halaman cetak 32–164) telah diekstrak menggunakan **dua metode independen**:
1. **Ekstraksi terprogram koordinat blok teks PDF** (`PyMuPDF` `get_text("blocks")` untuk kolom kiri `WILAYAH PEMBELIAN DARI LUAR PROVINSI` dan kolom kanan `WILAYAH PENJUALAN KE LUAR PROVINSI`).
2. **Pemeriksaan visual 100% halaman diagram dan halaman narasi** (`page_045.png` s/d `page_177.png` + halaman narasi `PENDISTRIBUSIAN DARI/KE LUAR PROVINSI`).

Kedua metode menghasilkan **kecocokan 100% (34/34 halaman provinsi)**.

---

## 2. Statistik Struktur Graph BPS Poldis 2022

* **Jumlah Node**: 34 provinsi (`N_NODES = 34`, pasangan terarah maksimum $34 \times 33 = 1.122$).
* **Jumlah Directed Edges (`1`)**: **99 directed edges** (densitas graph = **`8,82%`**).
* **Pemasok Antarprovinsi Terbesar (*Top Hubs / Out-Degree*)**:
  1. **Jawa Timur (`35`)**: menjual ke **16 provinsi**
  2. **Jawa Tengah (`33`)**: menjual ke **15 provinsi**
  3. **Sulawesi Selatan (`73`)**: menjual ke **9 provinsi**
  4. **Sumatera Utara (`12`)**: menjual ke **6 provinsi**
  5. **DKI Jakarta (`31`)** & **DI Yogyakarta (`34`)**: masing-masing menjual ke **5 provinsi**
* **Pembeli Antarprovinsi Terbesar (*Top Buyers / In-Degree*)**:
  1. **Kepulauan Bangka Belitung (`19`)**: membeli dari **9 provinsi**
  2. **Sumatera Barat (`13`)**: membeli dari **8 provinsi**
  3. **Bengkulu (`17`)** & **Sumatera Selatan (`16`)**: masing-masing membeli dari **6 provinsi**
  4. **DKI Jakarta (`31`)** & **Jawa Barat (`32`)**: masing-masing membeli dari **5 provinsi**
* **Provinsi dengan *In-Degree* $= 0$ (Tanpa Pemasok Luar Provinsi di Poldis 2022)**:
  * **Papua (`94`)** (Halaman PDF 177 / cetak 164): 100% distribusi berasal dari produksi dalam provinsi (`in_degree = 0`, `out_degree = 0`).
  * **Keputusan Protokol RL untuk RQ0 `(c)`**: Untuk node Papua (`94`), fitur hujan wilayah asal menggunakan rata-rata 3 provinsi terdekat berdasarkan jarak centroid (`distance_km.csv`), yaitu **Papua Barat (`91`, 700,3 km)**, **Maluku (`81`, 977,1 km)**, dan **Maluku Utara (`82`, 1.350,0 km)**.

---

## 3. Temuan Audit Silang Bilateral (96 Simetris + 3 Asimetris)

Dari 99 directed edges:
* **96 directed edges (`96,97%`) tercatat simetris di kedua halaman** (tercetak di kotak `WILAYAH PENJUALAN KE LUAR PROVINSI` pada halaman provinsi asal **dan** di kotak `WILAYAH PEMBELIAN DARI LUAR PROVINSI` pada halaman provinsi tujuan).
* **3 directed edges hanya tercetak di satu halaman diagram** akibat 2 salah ketik (*typo*) pada kotak diagram infografis BPS ketika dikonfirmasi terhadap halaman narasi resmi:

| Edge (`src -> dst`) | Tercetak di Diagram | Bunyi Narasi Resmi di Halaman Sebelahnya | Kesimpulan Audit RL |
| :--- | :--- | :--- | :--- |
| **`Sulawesi Selatan (73) -> Kalimantan Timur (64)`** | Hal. PDF 149 (Penjualan Sulsel) | **Hal. PDF 134 (Kaltim)** & **Hal. PDF 150 (Sulsel)** sama-sama menyebut Kaltim membeli dari **Jawa Timur, Sulawesi Tengah, dan Sulawesi Selatan**. | **Edge Valid** (terkonfirmasi narasi kedua provinsi). |
| **`Sulawesi Tenggara (74) -> Kalimantan Timur (64)`** | Hal. PDF 133 (Pembelian Kaltim) | **Hal. PDF 134 (Kaltim)** menyebut *Sulawesi Selatan* (bukan Sultra), dan **Hal. PDF 154 (Sultra)** menyebut Sultra hanya menjual ke 2 provinsi (*Sulawesi Selatan dan Maluku*). | **Typo Kotak Diagram BPS Hal. 133** (`SULAWESI TENGGARA` salah ketik dari `SULAWESI SELATAN`). |
| **`Nusa Tenggara Barat (52) -> Jawa Timur (35)`** | Hal. PDF 113 (Penjualan NTB) | **Hal. PDF 114 (NTB)** menyebut NTB hanya menjual ke **1 provinsi lain (Kep. Bangka Belitung)**, dan **Hal. PDF 101–102 (Jatim)** hanya membeli dari 3 provinsi (*Jateng, Bali, Sulsel*). | **Typo Kotak Diagram BPS Hal. 113** (`JAWA TIMUR` ikut tercetak di kotak penjualan NTB). |

> **Catatan Penggunaan di Pipeline**: Sesuai instruksi `bps_mask_README.md` (*"Do not infer links that are not printed; put 1 for every printed link"*), matriks standar `bps_mask_2022.csv` dan `bps_mask.npy` memuat ke-99 edge literal, sementara kolom `n_confirmations` di `supporting_data/bps_mask.csv` (`2` vs `1`) memungkinkan filter instan ke 97 edge bersih bila diperlukan saat uji sensitivitas.
