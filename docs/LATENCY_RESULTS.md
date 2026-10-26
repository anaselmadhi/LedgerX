# Measured latency results: 22 October 2026

The host-terminal release completed on the existing Mac with PostgreSQL **16.15**, schema **0004**, and one API process. The production Docker image passed both live browser journeys, the personal database was backed up before migration, and the updated app passed readiness/UI/auth checks at `http://127.0.0.1:8000`. No cloud resources were used.

**Correctness:** 147 unit/PostgreSQL tests in 25.75 s, then two real HTTP tests in 0.94 s; 26 frontend tests; 12 browser tests in 11.6 s. Statement coverage: **816/867 = 94.12%**. Migration round trip and ORM drift check passed. A saved archive is not a tested restore.

All three performance reports have source digest `e4b2ef44e64cfc2b740f92f0273f25d6fc15398d21688b583ba16593350c2b08`. Raw reports and verification evidence are preserved under [`artifacts/releases/2026-10-22-projection`](../artifacts/releases/2026-10-22-projection/manifest.json).

## Closed-loop HTTP

Four scenarios × three concurrency levels × three repetitions × 200 timed requests = **36 cases and 7,200 requests**. Zero unexpected responses; every balance check and reconciliation passed. The values below are medians of the three per-run statistics, not percentiles pooled across runs.

| Scenario | Clients | Median requests/s | Median p95 (ms) |
|---|---:|---:|---:|
| `balance_read` | 1 | 127.8 | 14.02 |
| `balance_read` | 8 | 921.9 | 10.83 |
| `balance_read` | 32 | 741.8 | 63.58 |
| `independent_transfers` | 1 | 170.4 | 7.19 |
| `independent_transfers` | 8 | 459.7 | 20.65 |
| `independent_transfers` | 32 | 403.4 | 112.25 |
| `shared_source` | 1 | 180.4 | 6.52 |
| `shared_source` | 8 | 353.6 | 27.00 |
| `shared_source` | 32 | 304.1 | 136.19 |
| `idempotent_replay` | 1 | 255.2 | 4.92 |
| `idempotent_replay` | 8 | 659.0 | 14.32 |
| `idempotent_replay` | 32 | 606.2 | 80.34 |

## History depth and commit cost

Four history depths × three fresh fixtures × 100 timed transfers = **1,200 measured commits**. Service timings include cProfile overhead. Commit timing includes transaction exit and deferred checks. The last two columns are separate read-query execution times from `EXPLAIN ANALYZE`; they are not complete transfer timings.

| Prepared transfers | Median service p95 (ms) | Median commit p95 (ms) | Historical SUM (ms) | Projection lookup (ms) |
|---:|---:|---:|---:|---:|
| 0 | 4.850 | 0.717 | 0.029 | 0.009 |
| 100 | 4.638 | 0.606 | 0.042 | 0.010 |
| 1000 | 4.748 | 0.601 | 0.113 | 0.010 |
| 10000 | 5.750 | 0.622 | 0.982 | 0.013 |

![Service/commit and isolated query timings](../artifacts/latency/figures/history-and-commit.png)

The measured service p95 remains around 5 ms across these depths, while the independent historical SUM becomes more expensive. Six application SQL executions per measured transfer are observed, versus seven in the older baseline; that difference includes the earlier idempotency-query optimization and cannot be attributed solely to the projection. SQL cursor counts exclude statements inside PostgreSQL triggers.

## Fixed-arrival HTTP load

Two workloads × three offered rates × three 5-second repetitions = **30,000 offered arrivals**. **18,439 were sent, 11,561 were dropped by the generator, zero sent requests produced unexpected responses, and zero outcomes were unconfirmed.** Accounting and reconciliation passed in every case. `all_targets_met` is **false**.

| Workload | Offered requests/s | Sent / offered, all 3 runs | Dropped | Median scheduled p95 (ms) | Runs meeting the load target |
|---|---:|---:|---:|---:|---:|
| `independent_transfers` | 100 | 1,500 / 1,500 | 0 | 13.14 | 3/3 |
| `independent_transfers` | 300 | 3,412 / 4,500 | 1,088 | 247.76 | 1/3 |
| `independent_transfers` | 600 | 3,771 / 9,000 | 5,229 | 418.07 | 0/3 |
| `shared_source` | 100 | 1,500 / 1,500 | 0 | 24.09 | 3/3 |
| `shared_source` | 300 | 4,031 / 4,500 | 469 | 579.72 | 1/3 |
| `shared_source` | 600 | 4,225 / 9,000 | 4,775 | 667.10 | 0/3 |

![Fixed-arrival load, drops and errors](../artifacts/latency/figures/fixed-arrival-load.png)

Of the dropped arrivals, **5,252** exceeded the generator admission-lag threshold and **6,309** reached the in-flight cap. These were not sent to the API and are not server-rejected transfers. Tail percentiles cover sent requests and include dispatch delay; they must be read together with the drops. The generator shares the Mac with the API and Docker database, so these results cannot isolate the server ceiling.

All six 100 requests/s cases met their offered load over these short windows. The 300 requests/s cases were inconsistent, and none of the 600 requests/s cases met the target. This is not a sustained 100 requests/s SLO, a maximum-user guarantee or an AWS sizing result.

## What the comparison can establish

- The incremental design preserves the verified financial invariants and removes full-history sums from commit validation.
- The new depth experiment and isolated query plans support the intended scaling behavior.
- The older 20 October run and the new run differ in revision, database state, test selection and background conditions. They do not establish a controlled end-to-end speedup attributable only to this migration.
- A repeatable worker-count experiment and a separate load-generator host would help distinguish Python CPU pressure, client scheduling, SQL pool waits and account-lock contention. Those experiments have not run.

## Storage snapshot

The benchmark database occupied **54,344,727 bytes (51.83 MiB)** after profiling, with **10 users, 701 accounts, 51,791 transfers and 103,582 journal entries**. This is the disposable benchmark database, not the personal ledger and not a 10,000-customer capacity test. Journal table plus indexes occupied 32,137,216 bytes; indexes account for 21,626,880 of those bytes. The snapshot precedes the later fixed-arrival/browser fixtures. It excludes a complete cluster/WAL/backup storage budget.

## When to run which checks

| Occasion | Appropriate checks |
|---|---|
| Every relevant pull request | Lint/format, unit and PostgreSQL tests, migration checks, frontend build and critical browser journeys |
| Financial/query/concurrency optimization | Targeted profiles and repeated before/after load experiments on comparable environments |
| Capacity or release investigation | Fixed-arrival load, longer soak tests and failure scenarios with explicit objectives |
| Open the already verified local app | `docker compose start db app`; no profiling required |

The existing GitHub Actions workflow runs correctness/build/browser checks; it does not run this full benchmark matrix on every push. The local full-profile release command deliberately combines the experiments for this optimization delivery. Performance testing can also be scheduled or run manually; see [Grafana performance automation guidance](https://grafana.com/docs/k6/latest/testing-guides/automated-performance-testing/).
