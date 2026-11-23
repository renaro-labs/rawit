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

## Applied ranges

- Climate: 2017-01-05 .. 2026-05-31; `available_at` 2017-01-07 .. 2026-06-02.
- RONI: 921 seasons; `available_at` non-null = 921.

## Evidence and limitation

- CHC does not publish a historical vintage archive for every daily file; the operational preliminary files appear about 2 days after the pentad end. The RL-approved Opsi B uses `pentad_end + 2 days` for final/sat and keeps Opsi A (`prelim_sim = pentad_end + 5 days`) as a sensitivity rule.
- Final/sat is used as a proxy for the preliminary release; this is a deliberate, documented approximation, not an assumed actual timestamp.
- RONI uses the CPC vintage date when available and otherwise the conservative `center_month + 3 months` rule; see `roni_vintage_log.csv`.
- Production weights use `year + 1` (2024 production affects 2025 onward).
