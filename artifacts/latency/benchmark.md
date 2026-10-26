Measured at 2026-10-22T00:18:40.899645+00:00. Source SHA-256: `e4b2ef44e64cfc2b740f92f0273f25d6fc15398d21688b583ba16593350c2b08`.

Run status: **PASS**. API/PostgreSQL: `{'status': 'ok', 'version': '0.3.0', 'schema': '0004', 'postgresql': '16.15'}`.
Load generator: macOS-15.6-arm64-arm-64bit; Python 3.12.12; 10 logical CPUs.

Closed-loop HTTP over TCP, persistent connections, one run per row; setup, warmup and post-run accounting checks excluded. Percentiles use nearest rank. Expected HTTP 409 refusals are counted separately from unexpected errors.

| Scenario | Clients | Run | N | req/s | p50 ms | p95 ms | p99 ms | Unexpected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| balance_read | 1 | 1 | 200 | 257.1 | 3.74 | 5.76 | 6.23 | 0 |
| balance_read | 1 | 2 | 200 | 127.8 | 6.95 | 14.02 | 15.70 | 0 |
| balance_read | 1 | 3 | 200 | 98.4 | 9.52 | 17.86 | 23.98 | 0 |
| balance_read | 8 | 1 | 200 | 794.4 | 8.45 | 13.78 | 44.41 | 0 |
| balance_read | 8 | 2 | 200 | 949.6 | 8.20 | 10.53 | 11.09 | 0 |
| balance_read | 8 | 3 | 200 | 921.9 | 8.29 | 10.83 | 13.77 | 0 |
| balance_read | 32 | 1 | 200 | 741.8 | 38.91 | 57.80 | 67.79 | 0 |
| balance_read | 32 | 2 | 200 | 673.9 | 39.96 | 69.36 | 78.70 | 0 |
| balance_read | 32 | 3 | 200 | 791.7 | 35.24 | 63.58 | 73.70 | 0 |
| independent_transfers | 1 | 1 | 200 | 171.7 | 5.59 | 6.83 | 7.83 | 0 |
| independent_transfers | 1 | 2 | 200 | 170.4 | 5.57 | 7.19 | 9.23 | 0 |
| independent_transfers | 1 | 3 | 200 | 156.8 | 5.82 | 8.97 | 10.99 | 0 |
| independent_transfers | 8 | 1 | 200 | 412.8 | 18.16 | 26.49 | 34.10 | 0 |
| independent_transfers | 8 | 2 | 200 | 459.7 | 17.22 | 20.65 | 22.36 | 0 |
| independent_transfers | 8 | 3 | 200 | 480.2 | 16.29 | 19.18 | 20.69 | 0 |
| independent_transfers | 32 | 1 | 200 | 403.4 | 74.39 | 102.65 | 117.51 | 0 |
| independent_transfers | 32 | 2 | 200 | 405.0 | 72.11 | 112.25 | 129.75 | 0 |
| independent_transfers | 32 | 3 | 200 | 358.8 | 82.27 | 115.09 | 120.60 | 0 |
| shared_source | 1 | 1 | 200 | 182.7 | 5.30 | 6.56 | 7.10 | 0 |
| shared_source | 1 | 2 | 200 | 180.4 | 5.30 | 6.35 | 7.59 | 0 |
| shared_source | 1 | 3 | 200 | 179.7 | 5.45 | 6.52 | 6.81 | 0 |
| shared_source | 8 | 1 | 200 | 353.6 | 22.26 | 26.89 | 28.24 | 0 |
| shared_source | 8 | 2 | 200 | 337.2 | 21.84 | 32.39 | 36.44 | 0 |
| shared_source | 8 | 3 | 200 | 360.0 | 21.36 | 27.00 | 27.92 | 0 |
| shared_source | 32 | 1 | 200 | 304.1 | 99.80 | 130.45 | 156.51 | 0 |
| shared_source | 32 | 2 | 200 | 302.4 | 100.57 | 148.30 | 174.03 | 0 |
| shared_source | 32 | 3 | 200 | 309.0 | 97.09 | 136.19 | 157.81 | 0 |
| idempotent_replay | 1 | 1 | 200 | 259.2 | 3.76 | 4.78 | 5.55 | 0 |
| idempotent_replay | 1 | 2 | 200 | 242.6 | 3.85 | 5.71 | 6.33 | 0 |
| idempotent_replay | 1 | 3 | 200 | 255.2 | 3.79 | 4.92 | 5.54 | 0 |
| idempotent_replay | 8 | 1 | 200 | 671.7 | 11.63 | 14.31 | 15.91 | 0 |
| idempotent_replay | 8 | 2 | 200 | 621.5 | 12.10 | 18.22 | 27.65 | 0 |
| idempotent_replay | 8 | 3 | 200 | 659.0 | 11.86 | 14.32 | 16.23 | 0 |
| idempotent_replay | 32 | 1 | 200 | 606.2 | 48.17 | 75.35 | 92.32 | 0 |
| idempotent_replay | 32 | 2 | 200 | 602.2 | 47.67 | 85.80 | 96.16 | 0 |
| idempotent_replay | 32 | 3 | 200 | 606.2 | 48.15 | 80.34 | 95.69 | 0 |

Raw samples, status distributions, exact balance checks and reconciliation: [benchmark.json](benchmark.json).
These are local measurements, not a production capacity or SLO guarantee. A closed-loop generator slows down when the server stalls (coordinated omission).
