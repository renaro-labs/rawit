# CGS-H1 - verification summary

Generated: 2026-11-23T22:59:16  
Result: **PASS** (587 checks)

## H1-01 CHIRPS

- 113 bulan, 3438 hari (2017-01 .. 2026-05).
- Manifest: {'ok': 3438}.
- Klimatologi: `data/raw/chirps_v3/clim/climatology_2017_monthly.npz`.

## H1-02 RONI

- 915 musim, 1950-2026; parquet identik.

## H1-03 Produksi + batas

- Kab/kota 2024: 514 baris, 34 provinsi, 1,469,325 ton.
- Provinsi: [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024].
- GeoPackage: 514 fitur.

## Checks

- Total: **587**; gagal: **0**.

Semua check lulus (bulan, hari, grid, holdout, manifest, RONI, produksi, batas).
