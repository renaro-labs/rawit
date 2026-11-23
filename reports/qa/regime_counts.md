# CGS-H2-04 - regime counts

Node-days are calendar days; the evaluation loader can restrict them to workdays.

| origin | part | regime | node_days | flag |
|---|---|---|---:|---|
| O1 | train | dry | 5,596 |  |
| O1 | train | extreme_wet | 3,011 |  |
| O1 | train | el_nino | 6,237 |  |
| O1 | train | la_nina | 28,205 |  |
| O1 | train | normal | 12,745 |  |
| O1 | val | dry | 51 | CI lebar |
| O1 | val | extreme_wet | 596 |  |
| O1 | val | el_nino | 0 | CI lebar |
| O1 | val | la_nina | 5,609 |  |
| O1 | val | normal | 0 | CI lebar |
| O1 | test | dry | 1,990 |  |
| O1 | test | extreme_wet | 402 |  |
| O1 | test | el_nino | 4,349 |  |
| O1 | test | la_nina | 2,817 |  |
| O1 | test | normal | 2,852 |  |
| O2 | train | dry | 5,838 |  |
| O2 | train | extreme_wet | 3,901 |  |
| O2 | train | el_nino | 6,237 |  |
| O2 | train | la_nina | 36,631 |  |
| O2 | train | normal | 15,597 |  |
| O2 | val | dry | 1,799 |  |
| O2 | val | extreme_wet | 108 | CI lebar |
| O2 | val | el_nino | 4,349 |  |
| O2 | val | la_nina | 0 | CI lebar |
| O2 | val | normal | 0 | CI lebar |
| O2 | test | dry | 1,066 |  |
| O2 | test | extreme_wet | 797 |  |
| O2 | test | el_nino | 1,739 |  |
| O2 | test | la_nina | 4,396 |  |
| O2 | test | normal | 4,446 |  |
| O3 | train | dry | 7,897 |  |
| O3 | train | extreme_wet | 4,514 |  |
| O3 | train | el_nino | 12,325 |  |
| O3 | train | la_nina | 36,631 |  |
| O3 | train | normal | 19,281 |  |
| O3 | val | dry | 806 |  |
| O3 | val | extreme_wet | 292 |  |
| O3 | val | el_nino | 0 | CI lebar |
| O3 | val | la_nina | 4,396 |  |
| O3 | val | normal | 762 |  |
| O3 | test | dry | 661 |  |
| O3 | test | extreme_wet | 1,585 |  |
| O3 | test | el_nino | 0 | CI lebar |
| O3 | test | la_nina | 9,820 |  |
| O3 | test | normal | 5,478 |  |
| HOLDOUT | train | dry | 9,109 |  |
| HOLDOUT | train | extreme_wet | 5,974 |  |
| HOLDOUT | train | el_nino | 12,325 |  |
| HOLDOUT | train | la_nina | 49,199 |  |
| HOLDOUT | train | normal | 22,707 |  |
| HOLDOUT | val | dry | 255 |  |
| HOLDOUT | val | extreme_wet | 417 |  |
| HOLDOUT | val | el_nino | 0 | CI lebar |
| HOLDOUT | val | la_nina | 1,648 |  |
| HOLDOUT | val | normal | 2,814 |  |
| HOLDOUT | test | SEALED |  |  |

## Total by regime (all dates < 2026-06-01)

| regime | node_days |
|---|---:|
| la_nina | 55,565 |
| normal | 32,098 |
| el_nino | 12,325 |
| dry | 9,804 |
| extreme_wet | 7,100 |