# CGS-H1 data package

Owner: **CGS (Climate & Geospatial Scientist)**  
Status: **DONE for available data** (2026-11-23)  
Contract: `docs/data_contract.md` v1.0, `configs/global.yaml`, `src/renaro/contract.py`

`data/raw/` is gitignored by this repo, so the data files below live locally and
are **not** committed. QA reports, helper scripts, and this document are tracked.

## 1. Paths

| Path | Contents | Status |
|---|---|---|
| `data/raw/chirps_v3/` | 113 monthly NPZ (2017-01..2026-05), `manifest.csv`, `clim/climatology_2017_monthly.npz`, QA metadata | DONE |
| `data/raw/enso/` | `roni.csv` (915 shared seasons), `roni.parquet`, vintage log; 2026 holdout snapshots are in `RENARO_SEALED_DIR` | DONE |
| `data/raw/bps/` | `produksi_kab.csv` (514 kab/kota, 2024), `produksi_prov.csv` (2017-2024), area weights, join audit, source XLSX | DONE (available data) |
| `data/raw/boundaries/` | `idn_adm2.gpkg` (514 features, EPSG:4326), ADM2 GeoJSON, ADM2->ADM1 mapping | DONE |
| `data/interim/roni.parquet` | contract path for the RONI table | DONE |
| `reports/qa/chirps_download.md` | CHIRPS coverage/QA | DONE |
| `reports/qa/roni.md` | RONI QA | DONE |
| `reports/qa/produksi_kab.md` | production/boundary QA | DONE |
| `reports/qa/CGS-H1_summary.md` | combined verification report | DONE |
| `reports/qa/CGS-H1_verification.json` | machine-readable verification (586 checks) | DONE |

## 2. H1-01 - CHIRPS v3 daily, Indonesia subset

- **Coverage**: 2017-01-01 .. 2026-05-31 = **113 months / 3,438 days**, 0 failed.
- **Grid**: 360 x 950, lat `6.475 .. -11.475`, lon `94.025 .. 141.475`, 0.05 deg.
- **Units**: `precip` float32 mm/day, NaN for sea/no-data cells (98,174 valid cells/day).
- **Format**: monthly NPZ (`lat`, `lon`, `time`, `precip`, `variant`) from the COG
  downloader. The playbook mentions yearly NetCDF in `final_sat/<YYYY>/`; the COG
  path writes monthly NPZ because xarray/netCDF4 is not installed. Grid and units
  are identical.
- **Provenance**: CHC `products/CHIRPS/v3.0/daily/final/sat`, COG subset over the
  Indonesia bbox; `manifest.csv` records URL, variant, bytes, status per day.
- **Climatology**: `clim/climatology_2017_monthly.npz` (12 monthly means from
  2017 only, pre-2018). This is a one-year baseline; extend to 2008-2017 if a
  longer climatology is required.
- **Holdout**: dates >= `2026-06-01` are **not** in this folder. They are in
  `$RENARO_SEALED_DIR/chirps_v3/` (outside the repo), per the contract:
  - `final_sat/2026H2`: 2026-06-01 .. 2026-10-31, 153/153 days ok.
  - `prelim_sat/2026H2`: 2026-11-01 .. 2026-11-20, 20/20 days ok (preliminary).
  - Total 173 holdout days; 2026-12 does not exist yet (2026-11-23).
- **Scientific note**: daily CHIRPS is disaggregated from pentads; do not claim
  independent daily precision. Extremes/dry spells are defined on pentad
  accumulations (see `docs/decisions/ALL-H1-01.md`).

## 3. H1-02 - RONI

- `roni.csv`: **915 shared seasons**, DJF 1950 .. FMA 2026; columns
  `season, year, center_month, roni, vintage_date, available_at, raw_phase, phase, episode_id`.
  The original 921-row table included MAM-ASO 2026; those 6 seasons were moved to
  `RENARO_SEALED_DIR` by CGS-H3-02.
- `available_at`: conservative `center_month + 3` months (no historical vintage
  archive); the recent seasons are provisional.
- Contract check passed (`check_columns`, `check_unique`; primary key
  `season, year, vintage_date`).
- `roni.parquet` is identical to the CSV (max abs diff 0.0).
- 2018-19 El Nino: 7 consecutive seasons >= +0.5 (SON 2018-MAM 2019).
- 2026 MJJ-ASO reaches +1.97 but is sealed (not in shared) and has not completed
  5 seasons, so it is not labeled an El Nino episode in shared data.

## 4. H1-03 - production and boundaries

- **2024 kab/kota**: 514 rows, 34 provinces, 1,469,325.119 tons; source Satudata
  Pertanian, Ditjen Hortikultura, dataset 392, `Cabai Besar-Kab 2024`.
- **Province series**: 2017-2024, 269 rows (2018/2021/2023 lack a DKI Jakarta row;
  DKI Jakarta is 0 in 2017/2019/2020/2022). Source BPS WebAPI var 61/turvar 132
  (2017-2023) + Satudata 2024.
- **Boundaries**: `idn_adm2.gpkg` 514 features; join to production 514/514 (100%;
  513 exact + 1 fuzzy). 5 non-admin features excluded.
- **Area weights**: `kab_area_weights.csv`, 61,825 cells; 42 small cities use the
  nearest-9 fallback; province sums ~1.0.
- **2025/2026**: not published yet. Satudata dataset 475 (`DATA PRIORITAS 2025`,
  released 31 Dec 2025) still tabulates 2024; BPS WebAPI stops at 2023. Use 2024
  as the last observed production (rule `y-1`) and document the limitation. Do
  not fabricate numbers.
- Province codes match `PROV_CODES` in `src/renaro/contract.py` (34 old-structure
  provinces, `"11"`..`"94"`).

## 5. Validation

Run from the repo root:

```powershell
$env:PYTHONPATH="$PWD\src"
python scripts\cgs\verify_chirps.py --root .
python scripts\cgs\verify_h1.py --root .

python -c "import pandas as pd; from renaro import contract as c; r=pd.read_csv('data/raw/enso/roni.csv'); c.check_columns(r,'roni'); c.check_unique(r,'roni'); print('roni OK')"
```

`verify_h1.py` checks 586 conditions: month/day counts, grid bounds, holdout,
manifest status, RONI/parquet identity, production totals, province codes, and
the GeoPackage feature count. The summary is written to
`reports/qa/CGS-H1_summary.md`.

## 6. Reproduction

```powershell
# CHIRPS (resume-safe)
python scripts\download_chirps_v3.py --start 2017-01-01 --end 2026-05-31 `
  --variant final/sat --out data\raw\chirps_v3 --source cog --workers 2 --delay 1 --retries 6

# RONI
python ..\supplychain\result\CGS-H1-02\build_roni.py

# Production/boundaries
python ..\supplychain\result\CGS-H1-03\build_h1_03.py
```
