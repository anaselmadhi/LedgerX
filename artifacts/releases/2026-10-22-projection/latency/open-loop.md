# Fixed-arrival HTTP measurements

Measured at 2026-10-22T00:20:43.132477+00:00; source `e4b2ef44e64cfc2b740f92f0273f25d6fc15398d21688b583ba16593350c2b08`.

Latency starts at the scheduled arrival, so generator delay is included. Dropped arrivals have no invented response latency and are counted separately. Percentiles describe sent requests only; always read them alongside drops and errors.

| Scenario | Offered req/s | Run | Sent / offered | Dropped | Errors | p50 ms | p95 ms | p99 ms | Target met | Accounting |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| independent_transfers | 100 | 1 | 500 / 500 | 0 | 0 | 9.90 | 13.14 | 14.84 | True | True |
| independent_transfers | 100 | 2 | 500 / 500 | 0 | 0 | 9.85 | 12.93 | 14.47 | True | True |
| independent_transfers | 100 | 3 | 500 / 500 | 0 | 0 | 12.80 | 38.92 | 117.65 | True | True |
| independent_transfers | 300 | 1 | 959 / 1500 | 541 | 0 | 151.36 | 278.34 | 312.05 | False | True |
| independent_transfers | 300 | 2 | 1500 / 1500 | 0 | 0 | 5.74 | 12.33 | 18.45 | True | True |
| independent_transfers | 300 | 3 | 953 / 1500 | 547 | 0 | 148.72 | 247.76 | 332.85 | False | True |
| independent_transfers | 600 | 1 | 1338 / 3000 | 1662 | 0 | 333.31 | 418.07 | 461.71 | False | True |
| independent_transfers | 600 | 2 | 918 / 3000 | 2082 | 0 | 127.42 | 489.40 | 570.93 | False | True |
| independent_transfers | 600 | 3 | 1515 / 3000 | 1485 | 0 | 302.90 | 386.50 | 435.95 | False | True |
| shared_source | 100 | 1 | 500 / 500 | 0 | 0 | 13.49 | 19.33 | 22.47 | True | True |
| shared_source | 100 | 2 | 500 / 500 | 0 | 0 | 13.60 | 35.18 | 50.33 | True | True |
| shared_source | 100 | 3 | 500 / 500 | 0 | 0 | 13.93 | 24.09 | 38.35 | True | True |
| shared_source | 300 | 1 | 1211 / 1500 | 289 | 0 | 363.42 | 579.72 | 604.94 | False | True |
| shared_source | 300 | 2 | 1500 / 1500 | 0 | 0 | 37.11 | 140.41 | 158.41 | True | True |
| shared_source | 300 | 3 | 1320 / 1500 | 180 | 0 | 230.92 | 923.64 | 959.54 | False | True |
| shared_source | 600 | 1 | 1497 / 3000 | 1503 | 0 | 412.73 | 543.97 | 584.44 | False | True |
| shared_source | 600 | 2 | 1351 / 3000 | 1649 | 0 | 463.27 | 667.10 | 741.31 | False | True |
| shared_source | 600 | 3 | 1377 / 3000 | 1623 | 0 | 466.43 | 703.09 | 720.39 | False | True |

Fixed spacing, not a Poisson/bursty traffic model. Generator and server may share CPU. No sustainable production capacity follows from these short experiments. A met target means no drops/unexpected responses; it does not assert a latency SLO.
Full samples and independent accounting checks: [open-loop.json](open-loop.json).
