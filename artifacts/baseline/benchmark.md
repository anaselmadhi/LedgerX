Measured at 2026-10-20T19:26:00.751332+00:00. Source SHA-256: `fa464ac0c5212908af39e90f58d7f72be7fe2c879fc5d9e64832602232d5c3ae`.

Run status: **PASS**. API/PostgreSQL: `{'status': 'ok', 'version': '0.3.0', 'schema': '0003', 'postgresql': '16.15'}`.
Load generator: macOS-15.6-arm64-arm-64bit; Python 3.12.12; 10 logical CPUs.

Closed-loop HTTP over TCP, persistent connections, one run per row; setup, warmup and post-run accounting checks excluded. Percentiles use nearest rank. Expected HTTP 409 refusals are counted separately from unexpected errors.

| Scenario | Clients | Run | N | req/s | p50 ms | p95 ms | p99 ms | Unexpected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| balance_read | 1 | 1 | 200 | 405.7 | 2.38 | 3.41 | 3.77 | 0 |
| balance_read | 1 | 2 | 200 | 397.9 | 2.38 | 3.45 | 3.65 | 0 |
| balance_read | 1 | 3 | 200 | 380.1 | 2.43 | 3.64 | 4.44 | 0 |
| balance_read | 8 | 1 | 200 | 839.7 | 8.47 | 11.51 | 28.73 | 0 |
| balance_read | 8 | 2 | 200 | 926.5 | 8.43 | 10.38 | 11.42 | 0 |
| balance_read | 8 | 3 | 200 | 939.4 | 8.20 | 10.44 | 11.90 | 0 |
| balance_read | 32 | 1 | 200 | 785.2 | 35.20 | 68.96 | 78.29 | 0 |
| balance_read | 32 | 2 | 200 | 774.6 | 36.45 | 62.33 | 69.16 | 0 |
| balance_read | 32 | 3 | 200 | 849.3 | 33.54 | 54.28 | 63.64 | 0 |
| history_head | 1 | 1 | 200 | 261.4 | 3.64 | 5.08 | 5.69 | 0 |
| history_head | 1 | 2 | 200 | 215.3 | 4.49 | 5.69 | 5.86 | 0 |
| history_head | 1 | 3 | 200 | 205.3 | 4.72 | 5.97 | 7.00 | 0 |
| history_head | 8 | 1 | 200 | 656.6 | 11.54 | 16.25 | 19.26 | 0 |
| history_head | 8 | 2 | 200 | 686.9 | 11.22 | 15.14 | 15.99 | 0 |
| history_head | 8 | 3 | 200 | 646.4 | 11.44 | 16.72 | 25.64 | 0 |
| history_head | 32 | 1 | 200 | 645.9 | 45.58 | 69.82 | 81.14 | 0 |
| history_head | 32 | 2 | 200 | 643.3 | 45.41 | 70.70 | 80.94 | 0 |
| history_head | 32 | 3 | 200 | 605.2 | 49.50 | 73.33 | 89.51 | 0 |
| history_deep_offset | 1 | 1 | 200 | 259.0 | 3.72 | 5.02 | 5.30 | 0 |
| history_deep_offset | 1 | 2 | 200 | 225.9 | 4.29 | 5.38 | 5.61 | 0 |
| history_deep_offset | 1 | 3 | 200 | 222.5 | 4.38 | 5.49 | 5.76 | 0 |
| history_deep_offset | 8 | 1 | 200 | 675.9 | 11.45 | 14.65 | 16.43 | 0 |
| history_deep_offset | 8 | 2 | 200 | 676.0 | 11.19 | 14.64 | 17.96 | 0 |
| history_deep_offset | 8 | 3 | 200 | 670.9 | 11.41 | 15.81 | 18.45 | 0 |
| history_deep_offset | 32 | 1 | 200 | 634.8 | 43.01 | 83.00 | 89.08 | 0 |
| history_deep_offset | 32 | 2 | 200 | 637.9 | 45.55 | 73.37 | 86.44 | 0 |
| history_deep_offset | 32 | 3 | 200 | 633.5 | 45.76 | 69.99 | 85.34 | 0 |
| history_deep_cursor | 1 | 1 | 200 | 259.2 | 3.61 | 4.84 | 5.78 | 0 |
| history_deep_cursor | 1 | 2 | 200 | 222.5 | 4.37 | 5.58 | 6.98 | 0 |
| history_deep_cursor | 1 | 3 | 200 | 208.6 | 4.63 | 5.83 | 6.52 | 0 |
| history_deep_cursor | 8 | 1 | 200 | 679.9 | 11.24 | 15.12 | 16.11 | 0 |
| history_deep_cursor | 8 | 2 | 200 | 640.5 | 11.74 | 15.62 | 19.09 | 0 |
| history_deep_cursor | 8 | 3 | 200 | 651.9 | 11.83 | 15.47 | 17.48 | 0 |
| history_deep_cursor | 32 | 1 | 200 | 610.3 | 48.47 | 70.05 | 81.01 | 0 |
| history_deep_cursor | 32 | 2 | 200 | 604.1 | 49.49 | 74.21 | 85.98 | 0 |
| history_deep_cursor | 32 | 3 | 200 | 640.0 | 45.56 | 71.51 | 81.78 | 0 |
| independent_transfers | 1 | 1 | 200 | 174.4 | 5.49 | 6.74 | 8.55 | 0 |
| independent_transfers | 1 | 2 | 200 | 181.4 | 5.36 | 6.68 | 7.46 | 0 |
| independent_transfers | 1 | 3 | 200 | 178.2 | 5.43 | 6.62 | 7.69 | 0 |
| independent_transfers | 8 | 1 | 200 | 438.0 | 17.84 | 22.32 | 23.87 | 0 |
| independent_transfers | 8 | 2 | 200 | 449.1 | 17.55 | 21.13 | 23.82 | 0 |
| independent_transfers | 8 | 3 | 200 | 443.1 | 17.68 | 21.44 | 22.65 | 0 |
| independent_transfers | 32 | 1 | 200 | 388.3 | 77.30 | 111.25 | 121.33 | 0 |
| independent_transfers | 32 | 2 | 200 | 395.2 | 76.51 | 106.43 | 118.87 | 0 |
| independent_transfers | 32 | 3 | 200 | 390.0 | 76.67 | 113.42 | 122.71 | 0 |
| shared_source | 1 | 1 | 200 | 175.3 | 5.57 | 6.93 | 7.73 | 0 |
| shared_source | 1 | 2 | 200 | 174.7 | 5.57 | 6.66 | 7.53 | 0 |
| shared_source | 1 | 3 | 200 | 171.7 | 5.64 | 6.85 | 8.27 | 0 |
| shared_source | 8 | 1 | 200 | 359.3 | 14.61 | 48.83 | 67.65 | 0 |
| shared_source | 8 | 2 | 200 | 365.5 | 12.75 | 56.52 | 99.99 | 0 |
| shared_source | 8 | 3 | 200 | 370.2 | 12.85 | 57.41 | 75.45 | 0 |
| shared_source | 32 | 1 | 200 | 312.7 | 54.04 | 254.98 | 312.02 | 0 |
| shared_source | 32 | 2 | 200 | 306.0 | 53.85 | 238.17 | 287.57 | 0 |
| shared_source | 32 | 3 | 200 | 307.2 | 53.23 | 287.78 | 373.94 | 0 |
| opposite_directions | 1 | 1 | 200 | 173.5 | 5.60 | 6.71 | 7.85 | 0 |
| opposite_directions | 1 | 2 | 200 | 175.9 | 5.54 | 6.79 | 7.66 | 0 |
| opposite_directions | 1 | 3 | 200 | 175.4 | 5.57 | 6.64 | 8.07 | 0 |
| opposite_directions | 8 | 1 | 200 | 373.7 | 15.43 | 41.91 | 50.35 | 0 |
| opposite_directions | 8 | 2 | 200 | 356.0 | 13.43 | 60.46 | 97.07 | 0 |
| opposite_directions | 8 | 3 | 200 | 358.3 | 13.36 | 54.01 | 79.49 | 0 |
| opposite_directions | 32 | 1 | 200 | 303.0 | 50.44 | 261.77 | 294.26 | 0 |
| opposite_directions | 32 | 2 | 200 | 312.3 | 52.60 | 266.41 | 305.76 | 0 |
| opposite_directions | 32 | 3 | 200 | 311.6 | 52.52 | 291.14 | 344.74 | 0 |
| idempotent_replay | 1 | 1 | 200 | 253.3 | 3.77 | 4.98 | 6.20 | 0 |
| idempotent_replay | 1 | 2 | 200 | 259.2 | 3.74 | 4.98 | 5.66 | 0 |
| idempotent_replay | 1 | 3 | 200 | 258.9 | 3.75 | 4.90 | 5.12 | 0 |
| idempotent_replay | 8 | 1 | 200 | 678.6 | 11.51 | 14.27 | 16.57 | 0 |
| idempotent_replay | 8 | 2 | 200 | 650.6 | 11.72 | 16.24 | 18.28 | 0 |
| idempotent_replay | 8 | 3 | 200 | 684.9 | 11.35 | 14.36 | 18.06 | 0 |
| idempotent_replay | 32 | 1 | 200 | 605.1 | 49.22 | 75.41 | 86.73 | 0 |
| idempotent_replay | 32 | 2 | 200 | 625.4 | 47.35 | 76.81 | 92.42 | 0 |
| idempotent_replay | 32 | 3 | 200 | 570.6 | 49.19 | 97.14 | 110.17 | 0 |
| insufficient_funds | 1 | 1 | 200 | 209.3 | 4.57 | 5.85 | 8.00 | 0 |
| insufficient_funds | 1 | 2 | 200 | 187.7 | 5.28 | 6.63 | 7.61 | 0 |
| insufficient_funds | 1 | 3 | 200 | 174.8 | 5.55 | 7.07 | 7.73 | 0 |
| insufficient_funds | 8 | 1 | 200 | 620.1 | 12.29 | 16.61 | 20.00 | 0 |
| insufficient_funds | 8 | 2 | 200 | 619.5 | 12.57 | 15.87 | 17.75 | 0 |
| insufficient_funds | 8 | 3 | 200 | 577.7 | 13.01 | 19.94 | 32.21 | 0 |
| insufficient_funds | 32 | 1 | 200 | 573.8 | 51.16 | 78.41 | 95.64 | 0 |
| insufficient_funds | 32 | 2 | 200 | 546.9 | 54.00 | 92.23 | 114.34 | 0 |
| insufficient_funds | 32 | 3 | 200 | 579.6 | 50.30 | 82.09 | 97.29 | 0 |
| reversals | 1 | 1 | 200 | 148.8 | 6.44 | 7.64 | 8.46 | 0 |
| reversals | 1 | 2 | 200 | 161.0 | 6.24 | 7.29 | 8.06 | 0 |
| reversals | 1 | 3 | 200 | 178.6 | 5.47 | 6.61 | 6.87 | 0 |
| reversals | 8 | 1 | 200 | 317.6 | 17.96 | 50.41 | 68.09 | 0 |
| reversals | 8 | 2 | 200 | 337.4 | 21.40 | 41.04 | 47.08 | 0 |
| reversals | 8 | 3 | 200 | 333.6 | 20.06 | 41.53 | 46.48 | 0 |
| reversals | 32 | 1 | 200 | 275.5 | 62.25 | 255.82 | 311.44 | 0 |
| reversals | 32 | 2 | 200 | 281.2 | 59.33 | 308.23 | 350.86 | 0 |
| reversals | 32 | 3 | 200 | 290.3 | 62.33 | 238.03 | 283.77 | 0 |

Raw samples, status distributions, exact balance checks and reconciliation: [benchmark.json](benchmark.json).
These are local measurements, not a production capacity or SLO guarantee. A closed-loop generator slows down when the server stalls (coordinated omission).
