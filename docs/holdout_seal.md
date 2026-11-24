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
