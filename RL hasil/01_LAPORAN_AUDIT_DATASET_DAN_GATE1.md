# Laporan 1 â€” Audit Presisi Dataset Bundle & Kesiapan Gate 1
**Disusun oleh:** RL (*Research Lead*)  
**Tanggal Audit:** 23 November 2026  
**Sumber Data Terkait:** [02_status_audit_dataset_bundle.csv](./csv_laporan/02_status_audit_dataset_bundle.csv), [03_cakupan_harga_pihps_34_provinsi_gate1.csv](./csv_laporan/03_cakupan_harga_pihps_34_provinsi_gate1.csv)

---

## 1. Hasil Verifikasi Integritas Bundle (`manifest.csv` & `SHA256SUMS`)

* **Total File Terverifikasi di Bundle**: **74/74 file (100%)** cocok ukuran byte dan checksum SHA-256 (193,57 MiB).
* **9 Item yang Tercatat `MISSING` di `manifest.csv` Awal** dan Status Terkininya:
  1. `data/ref` $\to$ **SELESAI DIBUAT RL** (`data/ref/provinces.csv` berisi pemetaan 34 provinsi: `contract_node_idx`, `prov_code` BPS 2 digit, `prov_name`, `iso_code`, `panel_dev_node_id`).
  2. `data/raw/bps` $\to$ PDF Poldis BPS 2022 sudah ada dan **selesai didigitasi** ke `bps_mask_2022.csv` & `bps_mask.npy`; tinggal `produksi_kab.csv` oleh CGS (`CGS-H1-03`).
  3. `data/raw/sp2kp` $\to$ Tugas MDE (`MDE-H1-02`) untuk validasi silang harga.
  4. `data/processed/eval_splits` $\to$ Jadwal CGS (`CGS-H4-01`) menggunakan batas `O1/O2/O3` yang sudah dikunci RL di [04_rolling_origin_splits_RL_H1_01.csv](./csv_laporan/04_rolling_origin_splits_RL_H1_01.csv).
  5. `data/processed/graph_priors` & `6. data/processed/perturbations` $\to$ Jadwal MDE (`MDE-H4-01` & `MDE-H4-02`) dari `bps_mask.npy` dan `distance_km.csv`.
  7. `docs/data_card.md`, `8. docs/holdout_seal.md`, `9. docs/regime_definitions.md` $\to$ Jadwal MDE & CGS pada H2â€“H3.

---

## 2. Audit Cakupan Harga 34 Provinsi (Syarat Gate 1: $\ge 20$ Provinsi, Cakupan $\ge 90\%$, $\ge 5$ Tahun)

Berdasarkan pemeriksaan atas `data/processed/dataset_v1/panel_dev.parquet` (**74.630 baris** = 34 provinsi $\times$ 2.195 hari kerja dari `2018-01-01` s/d `2026-05-29` $\approx 8{,}44$ tahun):

* **Keputusan RL**: **34 dari 34 provinsi (100%) LULUS syarat cakupan harga pasar tradisional Gate 1** (seluruhnya berada di rentang **95,67% â€“ 97,63%**, jauh di atas ambang minimum 90%).
* **Catatan Harga Produsen (`price_type=4`)**: Hanya digunakan sebagai fitur tambahan (bukan target). Dua provinsi tidak memiliki laporan harga produsen di PIHPS (**DKI Jakarta [`31`]** dan **Bali [`51`]** = `0,00%`), serta dua provinsi memiliki cakupan rendah (**Maluku Utara [`82`]** = `15,13%` dan **NTT [`53`]** = `50,16%`).

| Idx Kontrak | Kode BPS | Provinsi | Kode ISO | Hari Kerja | Target Valid (Tradisional) | Cakupan Target (%) | Valid Produsen | Cakupan Produsen (%) | BPS Out-Degree (Menjual ke) | BPS In-Degree (Membeli dari) |
|---:|:---:|:---|:---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | `11` | Aceh | `ID-AC` | 2195 | 2118 | **96,49%** | 1897 | 86,42% | 2 | 1 |
| 1 | `12` | Sumatera Utara | `ID-SU` | 2195 | 2123 | **96,72%** | 1929 | 87,88% | 6 | 1 |
| 2 | `13` | Sumatera Barat | `ID-SB` | 2195 | 2104 | **95,85%** | 1909 | 86,97% | 3 | 8 |
| 3 | `14` | Riau | `ID-RI` | 2195 | 2115 | **96,36%** | 1901 | 86,61% | 0 | 4 |
| 4 | `15` | Jambi | `ID-JA` | 2195 | 2101 | **95,72%** | 1850 | 84,28% | 2 | 2 |
| 5 | `16` | Sumatera Selatan | `ID-SS` | 2195 | 2104 | **95,85%** | 1644 | 74,90% | 4 | 6 |
| 6 | `17` | Bengkulu | `ID-BE` | 2195 | 2110 | **96,13%** | 1809 | 82,41% | 4 | 6 |
| 7 | `18` | Lampung | `ID-LA` | 2195 | 2117 | **96,45%** | 1858 | 84,65% | 4 | 4 |
| 8 | `19` | Kepulauan Bangka Belitung | `ID-BB` | 2195 | 2111 | **96,17%** | 1830 | 83,37% | 0 | 9 |
| 9 | `21` | Kepulauan Riau | `ID-KR` | 2195 | 2110 | **96,13%** | 1846 | 84,10% | 0 | 3 |
| 10 | `31` | DKI Jakarta | `ID-JK` | 2195 | 2106 | **95,95%** | 0 | 0,00% | 5 | 5 |
| 11 | `32` | Jawa Barat | `ID-JB` | 2195 | 2119 | **96,54%** | 1946 | 88,66% | 4 | 5 |
| 12 | `33` | Jawa Tengah | `ID-JT` | 2195 | 2143 | **97,63%** | 2011 | 91,62% | 15 | 3 |
| 13 | `34` | DI Yogyakarta | `ID-YO` | 2195 | 2119 | **96,54%** | 1893 | 86,24% | 5 | 1 |
| 14 | `35` | Jawa Timur | `ID-JI` | 2195 | 2124 | **96,77%** | 1902 | 86,65% | 16 | 4 |
| 15 | `36` | Banten | `ID-BT` | 2195 | 2114 | **96,31%** | 1714 | 78,09% | 2 | 4 |
| 16 | `51` | Bali | `ID-BA` | 2195 | 2108 | **96,04%** | 0 | 0,00% | 1 | 1 |
| 17 | `52` | Nusa Tenggara Barat | `ID-NB` | 2195 | 2114 | **96,31%** | 1859 | 84,69% | 2 | 1 |
| 18 | `53` | Nusa Tenggara Timur | `ID-NT` | 2195 | 2110 | **96,13%** | 1101 | 50,16% | 0 | 1 |
| 19 | `61` | Kalimantan Barat | `ID-KB` | 2195 | 2105 | **95,90%** | 1729 | 78,77% | 1 | 3 |
| 20 | `62` | Kalimantan Tengah | `ID-KT` | 2195 | 2103 | **95,81%** | 1465 | 66,74% | 1 | 4 |
| 21 | `63` | Kalimantan Selatan | `ID-KS` | 2195 | 2119 | **96,54%** | 1812 | 82,55% | 1 | 2 |
| 22 | `64` | Kalimantan Timur | `ID-KI` | 2195 | 2114 | **96,31%** | 1922 | 87,56% | 1 | 4 |
| 23 | `65` | Kalimantan Utara | `ID-KU` | 2195 | 2105 | **95,90%** | 1944 | 88,56% | 0 | 2 |
| 24 | `71` | Sulawesi Utara | `ID-SA` | 2195 | 2106 | **95,95%** | 1844 | 84,01% | 1 | 1 |
| 25 | `72` | Sulawesi Tengah | `ID-ST` | 2195 | 2107 | **95,99%** | 1838 | 83,74% | 4 | 2 |
| 26 | `73` | Sulawesi Selatan | `ID-SN` | 2195 | 2111 | **96,17%** | 1892 | 86,20% | 9 | 2 |
| 27 | `74` | Sulawesi Tenggara | `ID-SG` | 2195 | 2119 | **96,54%** | 1987 | 90,52% | 3 | 1 |
| 28 | `75` | Gorontalo | `ID-GO` | 2195 | 2121 | **96,63%** | 1493 | 68,02% | 2 | 1 |
| 29 | `76` | Sulawesi Barat | `ID-SR` | 2195 | 2118 | **96,49%** | 1892 | 86,20% | 0 | 2 |
| 30 | `81` | Maluku | `ID-MA` | 2195 | 2100 | **95,67%** | 1852 | 84,37% | 1 | 3 |
| 31 | `82` | Maluku Utara | `ID-MU` | 2195 | 2104 | **95,85%** | 332 | 15,13% | 0 | 1 |
| 32 | `91` | Papua Barat | `ID-PB` | 2195 | 2130 | **97,04%** | 1900 | 86,56% | 0 | 2 |
| 33 | `94` | Papua | `ID-PA` | 2195 | 2138 | **97,40%** | 1804 | 82,19% | 0 | 0 |

---

## 3. Audit Gap CHIRPS v3 & Pengaman Holdout

1. **Gap Unduhan CHIRPS v3 (`data/raw/chirps_v3/`)**:
   * Tersedia saat ini: 16 file `.npz` bulanan (`chirps_v3_idn_2018-01.npz` s/d `chirps_v3_idn_2019-04.npz` = **485 hari**, masing-masing berdimensi `(n_days, 360, 950)` dengan 98.174 piksel valid per hari).
   * Kekurangan: **91 bulan** (`2019-05` s/d `2026-11` = **2.761 hari**).
   * Akibatnya, ke-13 kolom iklim di `panel_dev.parquet` (`rain_1d` s/d `clim_age_days`) masih bernilai `NaN` (`0/74.630`).
2. **Audit Pengaman Holdout ($\ge$ `2026-06-01`)**:
   * `panel_dev.parquet` **AMAN** (`max_date = 2026-05-29`).
   * Namun `data/raw/pihps/pihps_cabai_merah_keriting_province.csv` masih menyimpan **8.442 baris** tanggal `2026-06-01` s/d `2026-11-23` (126 hari kerja), dan `data/raw/enso/enso_indices_tidy.csv` menyimpan 4 musim pada periode holdout (`MJJ 2026`, `JJA 2026`, `JAS 2026`, `ASO 2026`). CGS wajib menjalankan penyegelan fisik pada `CGS-H3-02`.

