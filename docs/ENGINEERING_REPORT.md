# LedgerX engineering report

Last full release verification: 22 October 2026, schema `0004`, including PostgreSQL, migration, latency, production Docker/browser and personal local deployment checks. Archived performance baseline: 20 October 2026. Scope: extend the existing FastAPI/PostgreSQL modular monolith
for fictitious EUR transactions while preserving its double-entry journal and database constraints.

## Delivered behavior

| Requirement | Implementation | Evidence |
|---|---|---|
| PostgreSQL tests and CI | Independent connections, concurrency barriers, migrations, schema drift checks, GitHub Actions PostgreSQL service | Local tests/migrations passed; owner-supplied Actions run #1 summary confirms both jobs passed at `d65fb3c` |
| Authentication and ownership | scrypt passwords, hashed opaque tokens, expiry/revocation, immutable account owners, administrative funding | Security and cross-owner tests passed |
| Refunds | One full compensation, original link/reason, recipient authorization, original-transfer locking and uniqueness | Duplicate, concurrent, insufficient-funds and journal tests passed |
| Independent reconciliation | Single-statement snapshot, independent journal aggregation, structured discrepancy sample, no repair | Healthy ledger and isolated 7-cent corruption tests passed |
| Observability and failures | JSON logs, correlation IDs, Prometheus, sanitized exceptions and bounded DB waits | Redaction, actual lock timeout, simulated failure and rollback-after-flush tests passed |

Additional work: a React/TypeScript workspace, owner-filtered account listing, session-capability
endpoint, exact BigInt JSON transport, browser verification, a French construction PDF,
indexed cursor pagination, local verification script, ten HTTP load scenarios,
service/SQL profiling, a read-only analysis notebook, exported charts and interview documentation.
No microservices, Kafka, Kubernetes, external banking account or remote deployment was introduced.

## Executed verification

### Archived schema `0003` public-demo preparation

Shared login/signup budgets, a two-request authentication concurrency cap, psycopg 3 provider URL
normalization, startup guards and dynamic container ports are implemented. Six throttle tests and
fifteen startup/configuration tests are included in the **115-test backend release**. The production
Docker target installs locked Python dependencies and passed both live browser journeys.

`verify_web.sh --container` checks UI assets, database readiness and access boundaries before its
12 browser cases. All **12 passed in 11.1 seconds**. The second real scenario covers two independent
customer sessions, a transfer, compensation and a global audit. This was executed from the host
terminal, because the coding sandbox cannot access Docker, PostgreSQL TCP or launch Chromium.

`render.yaml` and the deployment guide prepare a free service with TLS database access, a small
pool, funding disabled and manual deployment. At that stage, remote CI and cloud-hosted deployment
had not been executed.

### Subsequent latency work: schema `0004`

A statement-level journal insert trigger maintains an exact account projection from new rows only.
The existing deferred balance checks compare that projection with materialized balances; immutable
journal, transfer-pair, bounds, ownership and idempotency constraints remain. Independent
reconciliation checks both representations against complete journal aggregates. The guarded
migration verifies legacy data before backfilling and refuses discrepancies rather than repairing
balances. Downgrade restores full-history validation without deleting financial data.

Ten new PostgreSQL tests cover direct projection forgery, batched inserts, ignored conflicts,
savepoint rollback, concurrent increments, independent corruption detection and funded migrations.
The first host attempt had 145 passing tests and one cleanup failure: `ALTER TABLE` encountered
a pending deferred trigger after the corruption-detection assertions passed. Cleanup now executes
`SET CONSTRAINTS ALL IMMEDIATE` after repairing the test-only projection and before re-enabling
its guard. This runs the accounting check rather than disabling it.

The complete host rerun passed **147 unit/PostgreSQL tests in 25.75 s + 2 HTTP tests in 0.94 s**,
with **94.12% statement coverage (816/867)**. All ten projection cases passed, as did standalone
migration upgrade/downgrade/upgrade and ORM drift checks. The 147 comprise 77 isolated tests and
70 PostgreSQL-backed tests; the 77 are not additional to the full result. **26 frontend tests,
TypeScript/Vite, Ruff/formatting and 12 production-container browser cases passed**. The browser
suite took 11.6 s, with no failures, skips or flaky retries. Failed and successful runs have separate
archives; the current evidence is `artifacts/releases/2026-10-22-projection/`.

The new runner separates service/commit time, read query plans, closed-loop HTTP and fixed-arrival
HTTP. It records offered/sent/dropped work, scheduled latency and unknown outcomes without inventing
latencies for drops. See [the design proof and reproducible protocol](LATENCY.md). The performance
baseline below is historical. Current measurements and their limits are in
[LATENCY_RESULTS.md](LATENCY_RESULTS.md); they are not a controlled causal speedup comparison.

The 22 October local release runner sequences correctness, latency and production-container browser
checks before updating the personal application. It builds before stopping that app, takes a private
`pg_dump` archive, inspects its contents, records its digest and checks the expected schema after
startup. Failure-injection tests cover early abort, incomplete backups, failed deployment, stale
schema and concurrent releases. Compose configuration and shell syntax checks passed. Actual Docker execution, backup creation, migration and app smoke checks passed. Backup
restoration and long-duration availability testing remain unverified.
See [the local workflow and failure behavior](LOCAL_DEPLOYMENT.md).

### Manual remote demonstration and repository publication

On 26 October, the owner reported successful access and transfers from a friend's computer through
the temporary Cloudflare tunnel. A subsequent administrator screenshot at 23:27:58 local time
showed **Everything balances**, with 7 accounts, 8 transfers and 16 journal entries. This is a
manual observation reported by the owner; it adds no automated test count or load/uptime guarantee.

The initial local import and GitHub starter README were merged, and the owner supplied a successful
push of `d65fb3c` to [the repository](https://github.com/anaselmadhi/LedgerX). The owner then supplied
the [GitHub Actions](https://github.com/anaselmadhi/LedgerX/actions) run #1 summary: **Success**,
with `verify` passing in **11 min 24 s** and `container-browser` in **1 min 34 s**. The overall
duration was **11 min 27 s**; the jobs run concurrently. The two reported artifact names and SHA-256
digests are recorded in [the CI evidence summary](../artifacts/ci/initial-run-summary.json).
The archives were not downloaded or independently hash-checked, and no remote per-test counts
are inferred from the run summary. This evidence applies to `d65fb3c` only.

The successful run also reported two Node 20 action-runtime warnings and two `ubuntu-latest`
migration notices. The frontend build already selected Node 24. The workflow now selects the
Node 24 compatible major releases of checkout, setup-python, setup-node and upload-artifact, and
pins both jobs to `ubuntu-24.04`. These changes are pending their own pull-request CI run; the
initial success above does not verify them. The runner and action releases are documented by
[GitHub's Node migration notice](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/)
and [the Ubuntu image rollout](https://github.com/actions/runner-images/issues/14748).

Authentication limits are process-local and peer-based. Forwarded-header processing is disabled
in the supplied startup paths; multiple visitors behind a proxy can share the same budget. Limits
reset on restart and do not replace shared ingress controls. No database schema or financial
invariant was removed for these changes.

### Archived schema `0003` verification snapshot

The developer's macOS terminal executed integration, container/browser and performance commands against real
PostgreSQL. The coding sandbox inspected their saved artifacts; its Docker socket and localhost
TCP connections remain restricted. These are actual host-terminal results, not simulated database
results or a claim that the sandbox executed inaccessible commands.

| Check | Observed result | Artifact |
|---|---|---|
| Python | 3.12.12; resolved dependencies installed | `uv.lock` |
| PostgreSQL | 16.15 | `artifacts/benchmark.json` |
| Ruff lint/format | Passed; 65 backend/test/tool Python files at that snapshot | `artifacts/releases/2026-10-21-pre-projection/local-verification.log` |
| Unit + PostgreSQL integration | **113 passed, 0 failed, 19.40 seconds** | `artifacts/releases/2026-10-21-pre-projection/integration.xml` |
| Statement coverage | **94.09%**, 812/863 statements | `artifacts/releases/2026-10-21-pre-projection/coverage.xml` |
| Migration round trip | Upgrade → base → head passed on disposable `_test` | `artifacts/releases/2026-10-21-pre-projection/local-verification.log` |
| Alembic drift check | No new upgrade operations detected | Same log |
| Real HTTP E2E | **2 passed, 0 failed, 0.87 seconds** | `artifacts/releases/2026-10-21-pre-projection/e2e.xml` |
| HTTP benchmark | **90/90 cases passed; 18,000 timed requests; zero unexpected responses** | `artifacts/benchmark.json` |
| Accounting after benchmark | Every case passed exact balances and reconciliation | Same JSON |
| Service/SQL profiling | 300 committed transfers over 3 prepared-history depths; all audits passed | `artifacts/profiling.json` |
| Remote GitHub Actions | Not executed | Workflow present |
| Production Docker target and browser | Build and smoke checks succeeded; **12 browser cases passed** | Archived `web-verification.log` and `frontend-browser-results.json` |

The 113-test suite contains 53 isolated tests and 60 PostgreSQL-backed tests. Its `2 deselected` are
the two E2E tests run successfully in the next stage. **All 115 backend tests ran successfully across the
two invocations.** Coverage is a statement-execution measure, not correctness or exhaustive schedule
coverage. The interactive admin CLI remains uncovered and is included in the denominator.

The first test run emitted an Alembic `path_separator` deprecation warning. Adding
`path_separator=os` resolves it; loading the migration configuration confirmed head `0003` without
the warning. The locked Starlette release also warns that its HTTPX-based TestClient is deprecated
in favor of HTTPX2. That supported interface passed the tests; no warning filter or unverified
dependency upgrade was used to conceal it. Track the transition when updating dependencies.

## Frontend delivery and verification

The React 19/TypeScript workspace is built by Vite and served from FastAPI at `/`, with hashed assets
under `/assets`; existing API routes remain compatible. The application includes signup/login,
account creation/listing, balances, transfer review/receipt, cursor-based activity, full refunds,
administrative funding and independent reconciliation. No schema revision was required for the two
new owner-scoped read endpoints. Backend tests exercise their authorization and pagination.

A disposed API session clears its token and callbacks, preventing a late 401 from an old request
from invalidating a newly opened session; a dedicated async regression test covers this race.

The frontend preserves cents as BigInt, including JSON input/output, with lossless-json. Monetary
intents retain an immutable payload and the same key across retries. A lost-response scenario
simulates a committed debit followed by a transport failure; the test asserts only one debit and
identical keys/bodies on retry. Browser tokens and pending intents remain in memory; refresh loses
the session and pending key, which is an explicit recovery limitation.

Executed: **26 Vitest tests passed**, strict TypeScript compilation passed, Vite build succeeded.
Observed bundle after the projection-audit UI update: about **272.89 kB JS / 84.65 kB gzip** and
**29.84 kB CSS / 7.29 kB gzip**. Gzip sizes are build estimates; FastAPI static compression and
browser Core Web Vitals have not been measured/configured as performance claims.

The schema `0003` release passed all ten controlled desktop/mobile cases and both real Docker →
PostgreSQL journeys. Four earlier fixture failures came from an insecure origin blocking
`crypto.randomUUID`; one mobile case raced login. HTTPS fixtures and waiting for the authenticated
heading resolved these without weakening assertions. The successful rerun is archived with source
digests under `artifacts/releases/2026-10-21-pre-projection/`.

Desktop and mobile screenshots were visually inspected. The design uses authored SVG geometry,
system fonts and local CSS. A complete accessibility/cross-browser audit is not claimed. The projection UI passed unit/type/build checks and the full schema `0004` browser rerun
(12/12 in 11.6 s). The first remote CI subsequently passed both jobs at `d65fb3c`, according to
the owner-supplied Actions summary above.

## Current measured performance: schema `0004`

The new run includes 7,200 closed-loop requests, 1,200 profiled transfers and 18 fixed-arrival
cases. Median per-run service p95 was 4.85 ms at depth zero and 5.75 ms at depth 10,000; median
commit p95 was 0.717 and 0.622 ms respectively. These include profiling overhead and are separate
from HTTP latency. Six application SQL executions per transfer were observed.

All six short 100 requests/s fixed-arrival cases met the load target. At 300 requests/s only two
of six did, and at 600 none did. Of 30,000 offered arrivals, 18,439 were sent and 11,561 dropped by
the generator. Zero sent requests had unexpected responses or unconfirmed outcomes; all accounting
checks passed. This is not a sustained SLO or a measured maximum number of users.
See [the full tables, graphs, storage snapshot and methodology](LATENCY_RESULTS.md).

## Archived 20 October performance baseline

Environment: macOS 15.6 ARM64, Python 3.12.12, 10 logical CPUs reported by the generator, PostgreSQL
16.15, one local Uvicorn process, default pool 10 + 10 overflow. Docker VM allocation and background
host load were not recorded; logical CPUs are not a dedicated CPU allocation.

Baseline source SHA-256: `fa464ac0c5212908af39e90f58d7f72be7fe2c879fc5d9e64832602232d5c3ae`.
This digest covers backend, migrations, benchmark/profiler scripts and `pyproject.toml`; it does not
cover notebooks, documentation, dependency lockfile or all environment settings.

The following are **medians of three repetition-level measurements**, not pooled percentiles.
Each repetition contains 200 timed requests after 20 warmups.

| Workload | Clients | Median req/s | Median of p95 (ms) |
|---|---:|---:|---:|
| Balance reads | 8 | 926.5 | 10.44 |
| Independent transfers | 8 | 443.1 | 21.44 |
| Independent transfers | 32 | 390.0 | 111.25 |
| Shared-source transfers | 8 | 365.5 | 56.52 |
| Shared-source transfers | 32 | 307.2 | 254.98 |
| Idempotent replays | 8 | 678.6 | 14.36 |
| Full refunds | 8 | 333.6 | 41.53 |
| Full refunds | 32 | 281.2 | 255.82 |

Eight clients outperformed 32 on these workloads. Shared accounts show longer tails than independent
transfers. This is consistent with lock contention and queueing; the observations do not isolate
pool wait, scheduling, driver I/O and every database cost. No production capacity/SLO claim follows.

Service profiling includes cProfile overhead and commit, and excludes HTTP/authentication:

| Initial history | Transfers measured | p50 ms | p95 ms | p99 ms | Cursor SQL calls |
|---|---:|---:|---:|---:|---:|
| 0 | 100 | 6.43 | 9.75 | 14.59 | 700 |
| 100 | 100 | 14.79 | 22.62 | 29.57 | 700 |
| 1,000 | 100 | 10.00 | 20.11 | 23.60 | 700 |

The non-monotonic results do not establish a scaling law or isolate trigger overhead. At initial
depth 1,000, single SQL plan observations showed 0.274 ms for offset versus 0.016 ms for cursor.
The cursor plan used an index scan; the offset plan included a sort. These are single warm-data
`EXPLAIN ANALYZE` observations, not a 17× HTTP speedup. HTTP deep-history results were similar and
did not establish a cursor latency advantage at this dataset size.

The recorded settings include `fsync=on` and `synchronous_commit=on`. Cursor-execute timing excludes
commit and its deferred checks. cProfile cumulative times overlap through the call tree and must
not be added as independent costs. RSS includes setup and is process peak memory, not per-request
allocation or PostgreSQL memory.

Charts: [concurrency](../artifacts/figures/concurrency.png),
[latency distributions](../artifacts/figures/latency-distribution.png),
[profiling](../artifacts/figures/profiling.png).
Analysis: [executed read-only notebook](../analysis/ledgerx_performance.ipynb).

## Correctness fixes and architectural reasoning

**Fresh locked balances.** An entity already loaded in SQLAlchemy's identity map can remain stale
after acquiring a row lock. `populate_existing=True` explicitly refreshes locked account objects.
A regression test verifies that a stale preloaded balance cannot authorize a second overspend.

**Transaction ownership.** Token lookup uses a short completed read transaction before the route's
monetary transaction. This prevents SQLAlchemy autobegin conflicts. Services flush but do not commit;
debit, credit, immutable entries and idempotency completion share one commit.

**Scoped immutable retries.** The primary key is `(principal_id, operation, key)`, separating users
and operations. Concurrent reservations wait for the winner's commit/rollback. Failures are not
cached. Database triggers reject unfinished committed reservations or mutated completed results.

**Safe compensations.** Refunds lock the original with `FOR NO KEY UPDATE`, compatible with FK
`KEY SHARE`, then lock account UUIDs in deterministic order. The unique original reference and DB
validation provide independent enforcement. Only the original recipient can refund; its funds are
checked normally. Partial refunds require a different cumulative invariant and are not implemented.

**Preserved migration history.** Pre-authentication funds and journal rows stay intact, assigned to
disabled `_legacy` rather than an arbitrary signup. Migration `0003` drains deferred account events
before subsequent `ALTER TABLE` statements. A funded legacy upgrade and guarded refusal of a lossy
downgrade passed on PostgreSQL. Only the explicit disposable-test verifier truncates test data.

**Independent snapshots.** Reconciliation is one SQL statement to avoid false drift between separate
reads. It never calls posting code or repairs balances. Cursor history uses `(created_at, id)` to
handle tied timestamps but does not preserve a snapshot across HTTP pages.

**Failures and logs.** Tests inspect state from a fresh session after injected failures. Real lock
timeout yields a retryable 503; the same key succeeds after contention ends. Unexpected exceptions
are caught inside the ASGI wrapper so their raw messages are not re-raised to Uvicorn. After headers
are sent, only a sanitized error escapes and the failed response is closed.

**Intentional trade-offs.** The monolith retains a single transaction boundary. Synchronous driver
work uses FastAPI threads and bounded pooled connections. Integer cents avoid rounding. Materialized
balances make reads cheap, while deferred journal sums grow with account history. Opaque tokens
support revocation/current-role checks at the cost of one DB lookup per authenticated request.
Full reconciliation is an administrative full scan, not a cheap health probe.

## Compatibility, limits and recovery

Existing monetary payloads retain integer EUR cents and default currency. Optional idempotency keys
and legacy offset pagination remain supported. Authentication is a necessary API change: private
account/money endpoints now require bearer tokens; funding additionally requires an admin and the
development flag. Admins cannot spend arbitrary customer accounts. Legacy records remain disabled;
there is no public account-claim endpoint.

Before commit, an exception rolls back the whole financial operation. After a successful commit,
a lost HTTP response leaves the caller uncertain. Retry the same payload with the same key to
recover the original result. An interrupted commit may be ambiguous; an HTTP error alone does not
prove that money did not move. The application does not blindly retry financial work.

Remaining limitations: fictitious EUR only, full refunds only, no bank settlement, distributed rate limiting,
MFA/password recovery, TLS termination, expired-token cleanup, idempotency retention, backup/restore
drills, replication/failover, scheduled audit or production SLO evidence. Metrics are process-local.
Funding serializes on the system account. Privileged DB roles can bypass triggers. Demo credentials
and DB roles are local-development defaults, not a production security configuration.

Performance limitations of the archived results: closed-loop load/coordinated omission, three
repetitions, limited p99 samples, accumulating fixtures and sequential rather than randomized cases.
The new incremental projection and fixed-arrival generator are implemented but still require
PostgreSQL correctness and performance execution. Additional row updates/WAL can cost more for
small histories; no speedup or capacity rating is assumed. External notifications would justify a
transactional outbox, which is not implemented. Soak tests and production SLO evidence remain absent.

## Reproduce and remaining delivery checks

```bash
docker compose up -d db
bash scripts/verify_local.sh
bash scripts/verify_local.sh --benchmark-only
# Existing Anaconda environment contains Matplotlib and nbformat:
MPLCONFIGDIR="$PWD/.runtime/matplotlib" python3 -m analysis.render_report
```

The local script starts and stops only its own temporary API. Reports, cache, test files and
PostgreSQL bind-mounted data stay under LedgerX; Docker manages its own engine/VM storage.
The local/CI and Docker dependency graphs use `uv.lock`. The schema `0004` production target was
built and exercised through both real browser journeys, then deployed locally after a personal
database backup. Current reports and source digests are archived under
`artifacts/releases/2026-10-22-projection/`. The `0003` verification and 20 October performance
baseline remain separately labelled above. Reproduction commands are not pending checks for the
already verified revision. Backup archive inspection is not proof of successful restoration.
No cloud-hosted deployment has been created. Temporary remote access has been reported manually,
the repository has been published, and the owner-supplied GitHub Actions run #1 summary reports
both jobs passed at `d65fb3c`. Later revisions require their own checks.
The project's starting-code provenance has not been independently audited; modifications were
developed with AI assistance using standard documented patterns.
