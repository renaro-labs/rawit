# Regime definitions (CGS-H2-04)

**EVAL ONLY.** These labels must never be joined to `panel.parquet` or used as
model features.  The priority order is: `dry` > `extreme_wet` > `el_nino` >
`la_nina` > `normal`.

## ENSO

`enso_phase` comes from the official RONI episode table (`data/raw/enso/roni.csv`),
which applies the NOAA 5-season +/-0.5 rule.  The season covering a date uses the
row whose `center_month` equals the date's month.  `episode_id` is copied from the
episode table; neutral rows use `none`.

## Dry

`rain_pentad_mm < p20_global` for at least 3 consecutive pentads.  `p20_global`
is the 20th percentile of the pre-2018 baseline pentads for the province (2017
in the current scope).  The label is applied to every calendar day in the
qualifying pentad.

## Extreme wet

`extreme_5d == 1`: pentad accumulation above the province's p95 baseline
(5% exceedance in the baseline).  Applied to every day in the pentad.

## Normal

Not dry, not extreme wet, and ENSO neutral.

## Coverage

Only dates `< 2026-06-01` are written.  The holdout is sealed separately.
