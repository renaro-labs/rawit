# CGS-H2 data package

Owner: **CGS (Climate & Geospatial Scientist)**  
Status: **DONE** (2026-11-23)  
Contract: `docs/data_contract.md` v1.0, `configs/global.yaml`, `src/renaro/contract.py`

`data/interim/` is gitignored, so the data files below live locally. QA reports,
the data document, and the Python modules are tracked.

## 1. Paths

| Path | Contents |
|---|---|
| `data/interim/w_kab_pixel.npz` | 514 kab x 342,000 pixel weights (61,825 nonzeros, 42 nearest-9 kabs) |
| `data/interim/rain_prov_daily.parquet` | 116,892 rows: date, prov_code, variant, rain_mm, rain_mm_area, weight_method |
| `data/interim/climate_features.parquet` | 23,052 rows: pentad features + `available_at` |
| `data/interim/climatology.parquet` | 2,448 rows: 34 provinces x 72 pentads (2017 baseline) |
| `data/interim/availability.csv` | 7 availability rules |
| `data/interim/regime_labels.csv` | 116,892 daily EVAL-ONLY labels |
| `src/renaro/climate/rain.py` | H2-01 |
| `src/renaro/climate/pentad.py` | H2-02 |
| `src/renaro/climate/availability.py` | H2-03 |
| `src/renaro/climate/regimes.py` | H2-04 |
| `scripts/cgs/build_kab_pixel_weights.py` | rebuilds the pixel weight matrix |
| `scripts/cgs/verify_cgs_h2.py` | 36-check verifier |
| `reports/qa/rain_prov.md` | H2-01 QA |
| `reports/qa/climate_features.md` | H2-02 QA |
| `reports/qa/chirps_release_lag.md` | H2-03 QA |
| `reports/qa/regime_counts.md` | H2-04 counts per origin |
| `reports/qa/CGS-H2_summary.md` | combined verification |
| `reports/qa/CGS-H2_verification.json` | machine-readable verification |
| `docs/regime_definitions.md` | regime definitions |

## 2. H2-01 - production-weighted rainfall

- Weight matrix reproduces the H1 package exactly: **61,825 cells**, 42
  nearest-9 kabs, **0 count mismatches**.
- 514 kab rows; 342,000 CHIRPS pixels; row-normalised to 1.
- NaN pixels/kabs are re-normalised, never filled with zero.
- **Weighting rule**:
  - 2017-2024: **area weights** (kab-level production history is not published).
  - 2025-2026: **2024 kab production shares** (latest observed; y-1 for 2025).
  - `weight_method` records the rule per row.
- Output: 116,892 rows (34 provinces x 3,438 days), 0 missing rain.
- Annual totals 1,246-4,836 mm; 19 province-years outside the 1,500-4,000 mm
  sanity band (2019 dry east, 2025 wet Banten/Papua). Documented in QA; the band
  is a guard, not a hard rejection.

## 3. H2-02 - pentad indices

- 678 pentads (72/year; 2026 has 30 through May), 34 provinces, 23,052 rows.
- `rain_pentad_mm` = pentad sum; `rain_mm` = daily mean in the pentad.
- Climatology from **2017 only** (pre-2018 rule). `rain_pentad_anom` uses the
  pentad-of-year mean/std with a +/-2 pentad window; `rain_30d_anom` uses the
  6-pentad (30-day) accumulation.
- `dry_spell_days` = 5 x consecutive pentads with `rain_pentad_mm < 5 mm`.
- `extreme_5d` uses the per-province p95 of all baseline pentads; baseline rate
  **5.56%** (target ~5%).
- `rain_30d_anom` has 1,088 edge NaNs (first pentads / windows without a full
  6-pentad baseline); documented.
- `available_at = date + 2 days` (Ops B; applied by H2-03).

## 4. H2-03 - availability

- 7 rules: rain_daily_final, rain_pentad_final, rain_prelim, roni,
  production_weight, calendar, price.
- CHIRPS final/sat: `pentad_end_plus_lag`, lag **2 days** (RL decision).
- CHIRPS prelim: `release_timestamp`, sensitivity 5 days.
- RONI: `vintage_or_conservative_3m`; production: `year_plus_1`.
- `available_at` in `climate_features` is non-null and `>= date`; max
  **2026-06-02** (last pentad + 2 days).
- Note: the helper `assert_available()` in `src/renaro/contract.py` is inverted
  (it requires `available_at <= date`); the correct contract rule
  (`available_at >= date`) is validated directly in `verify_cgs_h2.py`.

## 5. H2-04 - regime labels (EVAL ONLY)

- 116,892 daily rows, 2017-01-01 .. 2026-05-31; no holdout dates.
- Definitions: ENSO from RONI phase; dry = `rain_pentad_mm < p20_global` for
  >= 3 consecutive pentads; extreme = `extreme_5d`; normal = none of the above
  and ENSO neutral.
- ENSO labels use an **as-of join**: the latest season with
  `available_at <= date`, not the season that merely contains the date. This
  prevents future RONI data from leaking into labels.
- Priority: `dry > extreme_wet > el_nino > la_nina > normal`.
- Counts: la_nina 58,311; normal 28,955; el_nino 12,722; dry 9,804;
  extreme_wet 7,100.
- Labels are expanded to every calendar day in the pentad; the evaluation loader
  can restrict to workdays. They must never enter `panel.parquet`.

## 6. Validation

From the repo root:

```powershell
$env:PYTHONPATH="$PWD\src"
python scripts\cgs\build_kab_pixel_weights.py   # only if rebuilding weights
python -m renaro.climate.rain
python -m renaro.climate.pentad
python -m renaro.climate.availability
python -m renaro.climate.regimes
python scripts\cgs\verify_cgs_h2.py
python scripts\cgs\write_cgs_h2_checksums.py
```

`verify_cgs_h2.py` checks 36 conditions: schema, holdout, duplicates, weight
matrix vs H1, area/production methods, pentad counts, baseline extreme rate,
climatology, availability rules, regime priority, and normal definition.

## 7. Limitations

1. **Baseline** is 2017 only because the requested scope starts in 2017. Extend
   to 2008-2017 for a more robust climatology; feature code is unchanged.
2. **Production weights** are only available for 2025-2026 (2024 kab production).
   Earlier years use area weights because kab-level history is not published.
3. **Daily CHIRPS is pentad-disaggregated**; extremes and dry spells are defined
   on pentads. Do not claim independent daily precision.
4. **Regime labels are EVAL ONLY** and must not be joined to model features.
5. **Holdout** (>= 2026-06-01) is outside the repo (`RENARO_SEALED_DIR`).
