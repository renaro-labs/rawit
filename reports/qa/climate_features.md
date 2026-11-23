# CGS-H2-02 - pentad climate indices

- Rows: **23,052**, provinces: **34**, pentads: **678**.
- Coverage: **2017-01-05 .. 2026-05-31**.
- Missing `rain_pentad_anom`: **0** (edge pentads); `rain_30d_anom`: **1088**.
- Baseline: **2017-01-01 .. 2017-12-31** (5–5 samples/window).
- `extreme_5d` rate in baseline: **5.56%** (target ~5%).
- `dry_spell_days > 0` rate in baseline: **7.15%**.
- `extreme_5d` uses the per-province p95 of all baseline pentads; this keeps the baseline rate near 5% with a one-year baseline. `p20_global` is used for the dry flag in CGS-H2-04.

## Per year

| year | pentads | extreme_5d % | dry-spell rows |
|---:|---:|---:|---:|
| 2017 | 72 | 5.56% | 175 |
| 2018 | 72 | 4.66% | 345 |
| 2019 | 72 | 3.19% | 501 |
| 2020 | 72 | 6.09% | 173 |
| 2021 | 72 | 7.68% | 127 |
| 2022 | 72 | 6.70% | 77 |
| 2023 | 72 | 3.15% | 351 |
| 2024 | 72 | 6.41% | 255 |
| 2025 | 72 | 9.31% | 114 |
| 2026 | 30 | 8.04% | 44 |

## Notes

- Pentad = days 1-5, 6-10, 11-15, 16-20, 21-25, 26-end (72 per year).
- `rain_pentad_mm` is the sum; `rain_mm` is the daily mean in the pentad.
- `dry_spell_days` = 5 x consecutive pentads with `rain_pentad_mm < 5 mm`.
- Baseline is 2017 only because the requested scope starts in 2017. Extend to 2008-2017 for a more robust climatology; the feature code is unchanged.
