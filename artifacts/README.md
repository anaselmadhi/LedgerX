# Verification artifacts

Run `bash scripts/verify_local.sh --benchmark` from the repository root for local Python and an
already running PostgreSQL server. Alternatively, `bash scripts/verify.sh --benchmark` uses Docker.
It performs lint/format checks, PostgreSQL integration tests, migration round trips,
HTTP end-to-end tests, load scenarios and function/SQL profiling.

Generated files:

| File | Evidence |
|---|---|
| `unit.xml` | Earlier isolated unit-test execution |
| `projection-unit.xml` | Initial schema 0004 database-free tests; not a PostgreSQL verification |
| `current-unit.xml` | Current isolated suite, including release and schema-aware smoke tests |
| `local-release-unit.xml` | Release failure-injection tests with simulated commands; not actual Docker execution |
| `local-release-preparation.json` | Source digest and executed versus pending checks for the local release work |
| `local-release.log` | Local release runner output, generated when the host executes it |
| `open-loop-unit.xml` | Tests of scheduling, dropped arrivals, failure accounting and report honesty |
| `projection-database-attempt.xml` | Sandbox attempt blocked before test execution by PostgreSQL connection permissions |
| `local-verification.log` | Local verification console output, including any failed stage |
| `local-performance.log` | Separate performance-only run output |
| `local-api.log` | Temporary API logs for local E2E/benchmark investigation |
| `integration.xml` | Actual PostgreSQL test results, JUnit |
| `coverage.xml` | Coverage from integration and unit tests; excludes separate E2E execution |
| `e2e.xml` | Real TCP/HTTP payment lifecycle and concurrent retry tests |
| `benchmark.json` | Raw latency samples, statuses, environment, source digest, balance checks |
| `benchmark.md` | Human-readable per-scenario, per-concurrency, per-repetition results |
| `metrics.prom` | Prometheus snapshot after load |
| `profiling.json` | Service timings, SQL calls, PostgreSQL settings and EXPLAIN ANALYZE plans |
| `profile-depth-*.txt` | Top 30 functions by cumulative time (cProfile) |
| `profile-depth-*.prof` | Binary cProfile input for local inspection |
| `figures/*.png`, `figures/*.svg` | Charts generated from the recorded JSON, with all repetitions |

No benchmark numbers have been fabricated. Dependencies were installed from the host terminal;
the coding sandbox still denies Docker socket and localhost TCP access. Host-terminal verification
saves its actual results here. The recorded baseline passed 88 unit/integration tests, 2 HTTP E2E
tests and all 90 benchmark cases (18,000 timed requests). Refer to the engineering report for context.

`benchmark.md` is inserted into the README by `--update-readme` (local or container execution).
Do not compare runs with different source digests, database histories, VM resources,
worker counts or concurrency settings as if they were controlled before/after measurements.

The profiler adds fresh fixtures to `ledgerx_bench`; it does not truncate databases.
The migration round-trip command explicitly clears only a guarded `_test` database.
Do not run migration verification concurrently with integration tests.

`baseline/` preserves the first complete run before the idempotency `INSERT … RETURNING`
optimization. Its raw JSON and figures remain available for comparison. Sequential local runs
are not a randomized controlled experiment; compare SQL operation counts separately from latency.


## React workspace verification

`web-verification.log` records `scripts/verify_web.sh`. This performs the frontend format/unit/build
checks and then Playwright against controlled desktop/mobile fixtures plus a real FastAPI server
using the isolated `_bench` PostgreSQL database. `frontend-browser-results.json` records the
per-test result; `frontend-browser/` contains failure diagnostics. Browser traces are disabled to
avoid writing bearer tokens and request bodies into trace archives.

`frontend-desktop-login.png`, `frontend-desktop-dashboard.png`, and the matching mobile captures
are actual browser screenshots using explicitly synthetic test fixtures. These fixtures never
ship in the app. A fresh real account starts empty. Screenshots are visual evidence, not throughput
benchmarks or a claim that the controlled fixture is a real database.

The archived schema 0003 release (21 October) passed **113 unit/integration tests +
2 HTTP tests**, with **812/863 statements covered (94.09%)**. All **12 browser tests passed**, including
two real journeys against the production Docker target. These reports are preserved under
`releases/2026-10-21-pre-projection/` with a manifest of source digests. The earlier 88 + 2 / 93%
results remain under `baseline/` with the measured performance run.

The current schema 0004 release passed **147 unit/PostgreSQL + 2 HTTP tests**, **26 frontend
tests** and **12 browser cases**, with **816/867 statements covered (94.12%)**. Migration round
trip, production Docker build and personal local deployment passed. Evidence is preserved under
`releases/2026-10-22-projection/`, including a manifest of report digests. The first host attempt's
145 passes and one cleanup failure remain under `releases/2026-10-22-projection-first-run/`.
The fixed cleanup passed the complete rerun. A backup archive was inspected, not restore-tested.

## Temporary HTTPS sharing

`scripts/share_local.sh` and `compose.share.yaml` provide an opt-in Cloudflare Quick Tunnel.
The host verified script control flow with four simulated Docker scenarios. On 26 October the
user's Docker run passed app/database readiness and Cloudflare connectivity prechecks. Later that
day, the owner reported successful remote access/transfers and supplied a clean reconciliation
screenshot (7 accounts, 8 transfers, 16 journal entries). This manual observation is described in
`docs/SHARING.md`; it is not an additional automated test artifact. The public URL is ephemeral and
is not archived here.

## Current latency experiment

`bash scripts/verify_latency.sh` writes to `latency/`: closed-loop `benchmark.json`, service/commit
`profiling.json`, fixed-arrival `open-loop.json`/`.md`, cProfile files and runner/API logs.
The 22 October run measured 7,200 closed-loop requests, 1,200 profiled transfers and 30,000 offered
fixed-arrival requests. Of the latter, 11,561 were dropped by the generator; all accounting checks
passed, but not all traffic targets were met. See `docs/LATENCY_RESULTS.md` for interpretation.
`analysis/render_latency.py` generated the PNG/SVG figures from reports with matching source
digests. The archived baseline is unchanged.
