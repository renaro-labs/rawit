# CGS-H2-04 - regime counts

Node-days are calendar days; the evaluation loader can restrict them to workdays.

| origin | part | regime | node_days | flag |
|---|---|---|---:|---|
| O1 | train | dry | 5,596 |  |
| O1 | train | extreme_wet | 3,011 |  |
| O1 | train | el_nino | 5,918 |  |
| O1 | train | la_nina | 27,799 |  |
| O1 | train | normal | 13,470 |  |
| O1 | val | dry | 51 | CI lebar |
| O1 | val | extreme_wet | 596 |  |
| O1 | val | el_nino | 0 | CI lebar |
| O1 | val | la_nina | 5,609 |  |
| O1 | val | normal | 0 | CI lebar |
| O1 | test | dry | 1,990 |  |
| O1 | test | extreme_wet | 402 |  |
| O1 | test | el_nino | 2,341 |  |
| O1 | test | la_nina | 5,669 |  |
| O1 | test | normal | 2,008 |  |
| O2 | train | dry | 5,838 |  |
| O2 | train | extreme_wet | 3,901 |  |
| O2 | train | el_nino | 5,918 |  |
| O2 | train | la_nina | 39,077 |  |
| O2 | train | normal | 13,470 |  |
| O2 | val | dry | 1,799 |  |
| O2 | val | extreme_wet | 108 | CI lebar |
| O2 | val | el_nino | 2,341 |  |
| O2 | val | la_nina | 0 | CI lebar |
| O2 | val | normal | 2,008 |  |
| O2 | test | dry | 1,066 |  |
| O2 | test | extreme_wet | 797 |  |
| O2 | test | el_nino | 4,463 |  |
| O2 | test | la_nina | 1,880 |  |
| O2 | test | normal | 4,238 |  |
| O3 | train | dry | 7,897 |  |
| O3 | train | extreme_wet | 4,514 |  |
| O3 | train | el_nino | 12,722 |  |
| O3 | train | la_nina | 39,077 |  |
| O3 | train | normal | 16,438 |  |
| O3 | val | dry | 806 |  |
| O3 | val | extreme_wet | 292 |  |
| O3 | val | el_nino | 0 | CI lebar |
| O3 | val | la_nina | 1,880 |  |
| O3 | val | normal | 3,278 |  |
| O3 | test | dry | 661 |  |
| O3 | test | extreme_wet | 1,585 |  |
| O3 | test | el_nino | 0 | CI lebar |
| O3 | test | la_nina | 12,518 |  |
| O3 | test | normal | 2,780 |  |
| HOLDOUT | train | dry | 9,109 |  |
| HOLDOUT | train | extreme_wet | 5,974 |  |
| HOLDOUT | train | el_nino | 12,722 |  |
| HOLDOUT | train | la_nina | 49,013 |  |
| HOLDOUT | train | normal | 22,496 |  |
| HOLDOUT | val | dry | 255 |  |
| HOLDOUT | val | extreme_wet | 417 |  |
| HOLDOUT | val | el_nino | 0 | CI lebar |
| HOLDOUT | val | la_nina | 4,462 |  |
| HOLDOUT | val | normal | 0 | CI lebar |
| HOLDOUT | test | SEALED |  |  |

## Total by regime (all dates < 2026-06-01)

| regime | node_days |
|---|---:|
| la_nina | 58,311 |
| normal | 28,955 |
| el_nino | 12,722 |
| dry | 9,804 |
| extreme_wet | 7,100 |