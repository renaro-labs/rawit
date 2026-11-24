# Holdout seal (CGS-H3-02)

- Disegel oleh: **CGS**
- Waktu: **2026-11-23T22:57:37**
- Commit pipeline: `ebd53abcc020cdf2d14aa6608527b75a758a041e`
- Lokasi: `D:\renaro_sealed\holdout_v1`
- Status: **TERSEGEL**

## Cakupan (metadata saja)

- PIHPS: **8,442 baris**, 2026-06-01 .. 2026-11-23.
- RONI: **6 musim** (2026-MAM, 2026-AMJ, 2026-MJJ, 2026-JJA, 2026-JAS, 2026-ASO).
- CHIRPS final: **153 hari** (2026-06-01 .. 2026-10-31).
- CHIRPS prelim: **20 hari** (2026-11-01 .. 2026-11-20).
- `tgl_akhir_holdout` = min(PIHPS, CHIRPS final) = **2026-10-31**.

## Shared removals

- PIHPS: 8,442 baris holdout dipindah; shared tersisa 147,715 baris (< 2026-06-01).
- PIHPS raw JSON dipindah: pihps_pt1_2025-07-01_2026-06-30.json.gz, pihps_pt1_2026-07-01_2026-11-23.json.gz, pihps_pt4_2025-07-01_2026-06-30.json.gz, pihps_pt4_2026-07-01_2026-11-23.json.gz.
- RONI: 6 musim holdout dipindah; shared tersisa 915 musim.
- RONI raw files dipindah: roni_raw_20261122.txt, roni_episodes.csv, comparison_summary.json, roni_vs_reference.csv.

## Integritas

- `SHA256SUMS.txt` mencakup 196 file di `D:\renaro_sealed\holdout_v1`.
- Checksum file holdout (subset tersegel):
```text
445c0be9bba967aac69eafe18cc7bb894af915839bf4b7caad2eadf19ec18547  sealed/chirps_v3/final_sat/chirps_v3_idn_2026-06.npz
6b2248b0de2d69025bc29eb8893338237d8b7ee20ac57a8235aa015e8c7235b4  sealed/chirps_v3/final_sat/chirps_v3_idn_2026-07.npz
5dd47c903c6ad3331c7a4735728a61752f17c465c8bc07f176b7a0f50fb5529c  sealed/chirps_v3/final_sat/chirps_v3_idn_2026-08.npz
728890532888ef4425e2e86c4965a39b768b098d577ccbd97da0dec7a8c2d07a  sealed/chirps_v3/final_sat/chirps_v3_idn_2026-09.npz
c815f7e01795697e44331f588a9473698f0052b1d5f12498f6f7406ba4020a09  sealed/chirps_v3/final_sat/chirps_v3_idn_2026-10.npz
f0aa99f061d718c91092f3ec43ba650dcc2832214311b905193fe3f2782bf7be  sealed/chirps_v3/final_sat/manifest.csv
eab490c4075f98d1104de54a342f01039c758f914d25afc24125120c49fb4d78  sealed/chirps_v3/prelim_sat/chirps_v3_idn_2026-11.npz
733e104de5e480090ee88b09a3ab88c593507b5b33b09756655fb9f31e77c2a3  sealed/chirps_v3/prelim_sat/manifest.csv
1923d917457956b80b3678eb8038127ab958a547d1323da06baa1df9438f19cd  sealed/enso/comparison_summary.json
1bb1e6bedc4dce7f39e35340420a3d5fc2d083c7f4e9c8ddbb206f7299bf286e  sealed/enso/roni_episodes.csv
7260e9e1dbd5c2886ed6ac06f0c5e8330f6e0e1206d28dd281111557f949849f  sealed/enso/roni_holdout.csv
81154cee10f6929be6089ce169fe5f567b652c139be1e944ac1f4b693e117ca3  sealed/enso/roni_holdout.parquet
1297887f581b6190e459cbbf8bdec9a703ff65c1a229e2de4dd94285254f35c8  sealed/enso/roni_raw_20261122.txt
1c93e9580e2d38ece271143aef57a3256a67ed00418b9b75ebd3d22cd01ac1cb  sealed/enso/roni_vs_reference.csv
adf775d741f64ead449c9afd329167536e1de1b2e4218881a2c18b891f28cfc4  sealed/pihps/json/pihps_pt1_2025-07-01_2026-06-30.json.gz
58d0a3c5d68720518cd87d5062f97e4a250ba5b0235003297aaf06540dbf8e4c  sealed/pihps/json/pihps_pt1_2026-07-01_2026-11-23.json.gz
253c6e97a4914d98f1dc298f676dfdbed7db151d6e7c4a1c08d64967e71b58e9  sealed/pihps/json/pihps_pt4_2025-07-01_2026-06-30.json.gz
7073b328ad2d1a0f99d03d0164d76c69ffeef1aca434534660b0e3504ea3a821  sealed/pihps/json/pihps_pt4_2026-07-01_2026-11-23.json.gz
780df9cada9264ebf4450618aea9a6deb671208adebc9ca7bfd99a2d71f11a27  sealed/pihps/pihps_holdout.csv
```

`raw_merged/` berisi gabungan data shared + holdout untuk membangun panel holdout; seluruh folder ini berada di luar repo dan hanya boleh diakses CGS.

## DoD

- [x] SHA-256 semua file holdout dicatat.
- [x] Tidak ada file >= 2026-06-01 di drive bersama (diverifikasi).
- [x] Salinan `_sealed` dipindah dari shared; MDE dikonfirmasi: **pending** (belum ada handoff MDE di repo ini).
- [ ] Bagian < 2026-06-01 identik dengan dataset_v1: **BLOCKED** — `scripts/build_dataset.py` (MDE-H3-01) belum ada.
- [ ] Panel `holdout_v1` dibangun: **BLOCKED** pada MDE-H3-01.
- [ ] RL menerima notifikasi: **pending**.

## Dibuka

_Kosong. Hanya CGS-H6-01 yang boleh mengisi bagian ini setelah Gate 2._

## Serah-terima MDE (MDE-H1-01)

- Diserahkan oleh: **MDE** · 2026-11-24T03:16:38+07:00
- Tujuan: `D:\Code\vscode\rawit\_kirim_cgs`
- File: 2 JSON + manifest; salinan di `data\raw\pihps\_sealed` sudah dihapus.
- Penerimaan CGS: _diisi CGS_

```text
0641abc49f261aa4b8e1ad90fd265351067187eda0cd84b4a5f51576821d67d3  pihps_mde/pt1_20260601_20261124.json
cc1303ca2280dd13f7db0c9761011d0e6f1f93d11ff66c129bc2d0be05d5ae12  pihps_mde/pt4_20260601_20261124.json
e8d35474cd6bfa4ec3ede944d0e19abf30f4d18dc9f0f3eb3bfb4f78a5ea093b  pihps_mde/manifest.csv
```

## Serah-terima MDE (MDE-H1-02, SP2KP)

- Diserahkan oleh: **MDE** · 2026-11-24T04:09:12+07:00
- Tujuan: `D:\Code\vscode\rawit\_kirim_cgs\sp2kp`
- File: 38 JSON + manifest; salinan di `data\raw\sp2kp\_sealed` sudah dihapus.
- Penerimaan CGS: _diisi CGS_

```text
459fe410cbece26ef28ffecb51967695a278165ea7df717c5c7d6d59d56fb845  sp2kp_mde/l1_p11_20260601_20261124.json
336b83e1bb937d744f03b8b4138fc9a345f1203831bf48ade651ac5bcfed5d44  sp2kp_mde/l1_p12_20260601_20261124.json
2d1c43877aca9350d3eeb2218687c0c8f9da793a9884688e91bcd92d59efd551  sp2kp_mde/l1_p13_20260601_20261124.json
92877e459725445f860d619f5e0c5a86c3ec076604f82524cbc3b0027e28d84c  sp2kp_mde/l1_p14_20260601_20261124.json
40c07018a751f8af0a3fb8cf98c987f49e161035fa09e78b6933e3d689e75464  sp2kp_mde/l1_p15_20260601_20261124.json
a7d7c18521b344df788c602121a00611306d13c8fec258559ea7dc9d84d83e0a  sp2kp_mde/l1_p16_20260601_20261124.json
57178c67893d2a14de730d640ccfbf5b1b1afb0db8d06df848785090022f2e2b  sp2kp_mde/l1_p17_20260601_20261124.json
003837acc6daa2f17be1078063c91da3a5d974ad3c55312bcd9dedafb55f7d66  sp2kp_mde/l1_p18_20260601_20261124.json
4214663dad48b98b6fde7aa41edb3ed28d1e2378fe6fe847f4593b63becf93e2  sp2kp_mde/l1_p19_20260601_20261124.json
a07b2938d0d4a7971fb86ba312630e5561bd47f3d468cf5cf99a16fddfc229ab  sp2kp_mde/l1_p21_20260601_20261124.json
6e5cb70e20723027fdde65be63b9f78c00caa60d63bcc208ea61aea6e85a57c6  sp2kp_mde/l1_p31_20260601_20261124.json
b7b8398b0c8663a4f1fd40293664e519722d785c1b3eecd0b865d051e87573e8  sp2kp_mde/l1_p32_20260601_20261124.json
0a902d8e9df3b08e99fe5dde0bf85f7e542ff189e4e62725617041f67c76ef57  sp2kp_mde/l1_p33_20260601_20261124.json
bfaa1eee8316ddf4541339a228f0151654fea7ca265895d77c7e1f0d6d2d60e5  sp2kp_mde/l1_p34_20260601_20261124.json
591bb8fb27eeb9a6a15b2b549f459b5987faa9b5a8150446d75220ea5231fee4  sp2kp_mde/l1_p35_20260601_20261124.json
6d9a4b2032cced415da8e3a505fb855a76465fb8d7e6493f2c66cbcb177d9d8a  sp2kp_mde/l1_p36_20260601_20261124.json
75df8bba546bc12fa6f15cb98678895af1d3755eb25b1794d87c1373f4eb3bef  sp2kp_mde/l1_p51_20260601_20261124.json
8be00ddb58d5db58cb3f8bacb3719d25c4ba8d409d65747baa6bc89323df2e11  sp2kp_mde/l1_p52_20260601_20261124.json
a66ca8f4a7f3cb2cb2368ca6fd29f7ad9d37fb171b13f139c602844d8d02cb83  sp2kp_mde/l1_p53_20260601_20261124.json
c44be3ad4d0582cae5e825f921326da31ffd99b6c1e3727455228f1cf893be36  sp2kp_mde/l1_p61_20260601_20261124.json
e0c2483c5b414077273407786b0a99ffa88a8a45c1f5610b9285ed5b354efb92  sp2kp_mde/l1_p62_20260601_20261124.json
545abb4180019d3ab8bd3f7d3eb97a5cceb4510ee5d183bb507525ebac9865c5  sp2kp_mde/l1_p63_20260601_20261124.json
8fd663b1cb9d08ebbd5ea20fc599c8252736c32e02a67c6bc01c621dc81550c5  sp2kp_mde/l1_p64_20260601_20261124.json
465c1e0fceca9c5954763eba38be529a1c36a3bb60e6de943fbf81d5c1870ef3  sp2kp_mde/l1_p65_20260601_20261124.json
ef3b2cd0857fa5b26ff6e830864c2777ecfb0a7da5fd913773e1b01c7482352c  sp2kp_mde/l1_p71_20260601_20261124.json
4f797e7f63ba6fbdc891e1d6eef707354d1aa3cc72097d902c13d923466ad32d  sp2kp_mde/l1_p72_20260601_20261124.json
aa474f2fb17ad5a88fadc2bb1bb3be98d2a725e34ea0e9e84133afd6eb82a6a6  sp2kp_mde/l1_p73_20260601_20261124.json
372e61aa6d0126bd021419648227ae5c7f315dd82b1cd8cf64c01d5b6278922d  sp2kp_mde/l1_p74_20260601_20261124.json
710de7c2489c91be6f692088753d743c0e9f12ee7c8134b26eb473a657810398  sp2kp_mde/l1_p75_20260601_20261124.json
243e4371d9ac29165cdb68e04c71afe06f179cb8cfb8ef1a5468455e35d150bb  sp2kp_mde/l1_p76_20260601_20261124.json
a9d5c3284bb481a54b5af37a322fc5b9f6f34543da1dbfbffa25281f6df46158  sp2kp_mde/l1_p81_20260601_20261124.json
af16ba00cd5678d9b153d5ebbabc588290f5f01cf57c7057f5ac8cb156bb6cd3  sp2kp_mde/l1_p82_20260601_20261124.json
8a35ae1a8756ef8f925a9cc3940c04d15191d6342f0cee441fdecae4a61ee724  sp2kp_mde/l1_p91_20260601_20261124.json
ba3c070801bc5c714c7dfb5c0ea623306f8811bfc870eebd92c7e8aac4229987  sp2kp_mde/l1_p92_20260601_20261124.json
0c609cae55325ddc3d32cd6eedc5e80ffbf19c2b73e39c6ef09b41273d8c157f  sp2kp_mde/l1_p93_20260601_20261124.json
12b80dbd26a40389de92ebf46b4693813cfdf4cc19db8e903b7bc0ab75b4a211  sp2kp_mde/l1_p94_20260601_20261124.json
250e82115119aa0df05dc3b8457190d69edc5c7c680c8794dee5487c843f412d  sp2kp_mde/l1_p95_20260601_20261124.json
f67d4abbc4e08475bdf09e5cae902e840acf2bb5e163f1891599d5beee78ef29  sp2kp_mde/l1_p96_20260601_20261124.json
7f7dd04e492496825cc7947f9dd767357e3266f1a98af1c9c88c1964757bd038  sp2kp_mde/manifest.csv
```

## Penerimaan CGS - Handout MDE (2026-11-24)

- Diterima oleh: **CGS** - 2026-11-24
- Lokasi arsip: `D:\renaro_sealed\holdout_v1\handoff_mde_2026-11-24\`
- File: `pihps_sealed_mde.zip` (27.019 B) + `sp2kp_sealed_mde.zip` (40.346 B) + `VALIDATION.md` + `SHA256SUMS.txt`
- PIHPS: 2 JSON + manifest; `http_status=200`; SHA256 cocok 2/2; cakupan 2026-06-01..2026-11-24.
- Uji silang PIHPS: 8.023/8.023 nilai beririsan identik dengan `sealed/pihps/pihps_holdout.csv` (max |selisih| = 0 Rp/kg).
- SP2KP: 38 provinsi, 38 file; `http_status=200`; SHA256 cocok 38/38; cakupan 2026-06-01..2026-11-24.
- Catatan: handout SP2KP hanya periode sealed; data 2024-02..2026-05 belum diserahkan (tindak lanjut MDE-H1-02).

```text
fca055f3227b18df0f8ff83bd5ebab2f70173bc540a2598a358e6ff3e227fb58  pihps_sealed_mde.zip
c2ba2fd0fc5fa8e17c8b9dec6f867968863dab1fc27ba91a88dac626d056f6c4  sp2kp_sealed_mde.zip
```

## Penerimaan CGS - SP2KP Shared (2026-11-25)

- Diterima oleh: **CGS** - 2026-11-25
- Sumber: `sp2kp_shared_mde-new.zip` (259.774 B), dipindah ke `dist/` dan diekstrak ke `data/raw/sp2kp` + `data/interim/sp2kp_long.parquet`.
- Isi: 114 JSON (38 provinsi x 3 jendela) + `manifest.csv` + `master_provinsi.json` + parquet + `sp2kp_coverage.md` + `SHA256SUMS.txt`.
- Integritas: SHA256SUMS 117/117 cocok; manifest 114/114 `http_status=200`.
- Cakupan: 2024-02-01..2026-05-29 (< holdout), 38 provinsi sumber, 23.066 entri, 34/34 provinsi kontrak ter-map.
- Parquet: 20.638 baris (34 x 607 hari), NaN 1.853 (9,0%), `is_aggregated=True` 1.214 baris (91 dan 94).
- Reproduksi ulang dari JSON mentah dengan `src/renaro/data/sp2kp.py`: **20.638 baris identik, max |selisih| = 0**, flag agregasi dan `n_source_prov` identik.
- Tidak ada tanggal >= 2026-06-01 (0 baris holdout).
- Catatan: data ini **hanya untuk validasi silang MDE-H2-01**, bukan fitur/target.
