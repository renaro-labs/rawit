# CGS-H2 - verification summary

Result: **PASS** (36 checks)

## H2-01 production-weighted rainfall

- 116,892 rows, 3,438 days, 34 provinces.
- Weight matrix 514 x 342,000; 61,825 cells; 0 count mismatch vs H1.
- Area weights 2017-2024; production_2024 weights 2025-2026.

## H2-02 pentad indices

- 23,052 rows, 678 pentads, 34 provinces.
- extreme_5d baseline rate: 5.56%.

## H2-03 availability

- 7 rules; climate `available_at` non-null and >= date.

## H2-04 regime labels (EVAL ONLY)

- 116,892 daily rows, 2017-01-01..2026-05-31.
- Counts: {'la_nina': 58311, 'normal': 28955, 'el_nino': 12722, 'dry': 9804, 'extreme_wet': 7100}.

## Checks

- Total: **36**; failed: **0**.
