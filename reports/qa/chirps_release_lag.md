# CHIRPS / RONI release lag and availability rules

Sumber keputusan: `docs/decisions/ALL-H1-01.md` (Keputusan 3) dan `docs/data_contract.md` v1.0.

## Rule table

| feature_family | source | variant | rule | lag_days | decided_by |
|---|---|---|---|---:|---|
| rain_daily_final | CHIRPS v3.0 daily final/sat | final_sat | pentad_end_plus_lag | 2.0 | RL |
| rain_pentad_final | CHIRPS v3.0 daily final/sat | final_sat | pentad_end_plus_lag | 2.0 | RL |
| rain_prelim | CHIRPS v3.0 daily prelim/sat | prelim_sat | release_timestamp | 5.0 | CGS |
| roni | CPC NOAA RONI (ERSSTv6) | all | vintage_or_conservative_3m | nan | CGS |
| production_weight | Satudata Pertanian / BPS | all | year_plus_1 | nan | protocol |
| calendar | SKB 3 Menteri | all | known_in_advance | nan | protocol |
| price | PIHPS / SP2KP | all | next_workday | 1.0 | protocol |

## Feature dictionary coverage

- `docs/feature_dict.csv`: **24** features, **7** families.
- Every family in the dictionary has exactly one row in `availability.csv`; `src/renaro/climate/availability.py` fails if a family is missing or if its source/variant/rule/lag disagree.

## Applied ranges

- Climate: 2017-01-05 .. 2026-05-31; `available_at` 2017-01-07 .. 2026-06-02.
- RONI: 915 seasons; `available_at` non-null = 915.

## HTTP HEAD probe (actual)

Evidence: `reports/qa/chirps_release_lag_probe.csv`; probed at **2026-11-23T17:56:59Z**. `lag_days` = date in `Last-Modified` minus date encoded in the filename. Only headers returned by CHC are recorded; missing headers remain blank.

| variant | file_date | status | last_modified | lag_days |
|---|---|---:|---|---:|
| final | 2026-08-01 | 200 | Wed, 18 Nov 2026 16:42:20 GMT | 109 |
| final | 2026-09-01 | 200 | Wed, 18 Nov 2026 16:43:17 GMT | 78 |
| final | 2026-09-16 | 200 | Wed, 18 Nov 2026 16:43:35 GMT | 63 |
| final | 2026-10-01 | 200 | Wed, 18 Nov 2026 16:44:13 GMT | 48 |
| final | 2026-10-16 | 200 | Wed, 18 Nov 2026 16:44:30 GMT | 33 |
| final | 2026-10-31 | 200 | Wed, 18 Nov 2026 16:44:45 GMT | 18 |
| prelim | 2026-10-01 | 200 | Wed, 07 Oct 2026 15:59:14 GMT | 6 |
| prelim | 2026-10-16 | 200 | Thu, 22 Oct 2026 15:59:38 GMT | 6 |
| prelim | 2026-10-31 | 200 | Mon, 02 Nov 2026 20:31:51 GMT | 2 |
| prelim | 2026-11-01 | 200 | Mon, 09 Nov 2026 18:28:17 GMT | 8 |
| prelim | 2026-11-10 | 200 | Thu, 12 Nov 2026 18:01:18 GMT | 2 |
| prelim | 2026-11-20 | 200 | Sun, 22 Nov 2026 17:04:08 GMT | 2 |

- `final`: 6/6 HTTP 200; `lag_days` 18..109 (median 55.5).
- `prelim`: 6/6 HTTP 200; `lag_days` 2..8 (median 4.0).
- Prelim spot-check: 6 files, lags 6, 6, 2, 8, 2, 2 days. Recent files are 2 days after the date; older gaps reach 6-8 days. This supports the 2-day operational proxy (Opsi B) as a spot-check, not as a historical vintage archive.

## Evidence and limitation

- CHC does not publish a historical vintage archive for every daily file. The probe above records the headers that were actually served; it is a spot-check, not a reconstruction of each file's original release date.
- The RL-approved Opsi B uses `pentad_end + 2 days` for final/sat and keeps Opsi A (`prelim_sim = pentad_end + 5 days`) as a sensitivity rule. Final/sat is used as a proxy for the preliminary release; this is a deliberate, documented approximation, not an assumed actual timestamp.
- RONI uses the CPC vintage date when available and otherwise the conservative `center_month + 3 months` rule; see `roni_vintage_log.csv`.
- Production weights use `year + 1` (2024 production affects 2025 onward).
