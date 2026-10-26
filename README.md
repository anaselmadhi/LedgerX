# LedgerX — transactional financial backend & React workspace

LedgerX is an independently developed fintech portfolio project built with Python, FastAPI,
SQLAlchemy 2 and PostgreSQL. It demonstrates exact monetary arithmetic, authenticated account
ownership, double-entry bookkeeping, concurrent spending protection, persistent idempotency,
compensating transfers, reconciliation and reproducible verification. A React + TypeScript workspace
now exposes the same authenticated API through an original responsive interface.

Designed for a backend engineering interview, including a Revolut interview; not affiliated with
Revolut. This is a local system for fictitious funds, not a production banking service.

**Verified local release — schema `0004`, 22 October 2026:** **149 backend tests**
(147 unit/PostgreSQL + 2 real HTTP), **26 frontend tests** and **12 browser tests** passed, including
two live journeys against the production Docker target. Statement coverage: **94.12% (816/867)**.
Migration round trips and ORM drift checks passed. The personal Docker app was backed up, migrated
and passed schema/UI/auth smoke checks at **http://127.0.0.1:8000**. Reports are preserved in
[the release evidence archive](artifacts/releases/2026-10-22-projection/manifest.json).

**Measured latency work:** an incremental journal projection replaces repeated full-history sums
during balance validation; independent reconciliation remains. The repeated service p95 was
**4.85 ms at depth 0 and 5.75 ms at depth 10,000**. All **7,200 closed-loop requests** passed.
Fixed-arrival tests preserved accounting but dropped **11,561 of 30,000 offered arrivals** at
higher loads; not all load targets were met. These short local experiments are not a maximum-user
guarantee or a controlled end-to-end speedup claim. See [measured results](docs/LATENCY_RESULTS.md)
and [design/methodology](docs/LATENCY.md).

The archived 20 October HTTP experiment completed **90 cases / 18,000 timed requests with zero
unexpected responses** and correct accounting. Those numbers describe its archived revision,
not schema `0004`. On 26 October, the project owner reported successful remote access and transfers
from a friend's computer through the temporary HTTPS tunnel. The subsequent administrator
reconciliation showed **7 accounts, 8 transfers, 16 journal entries and no discrepancies**.
The repository is now published on GitHub; the [remote CI result](https://github.com/anaselmadhi/LedgerX/actions)
still needs verification. A cloud-hosted deployment has not been executed. See the
[sharing guide](docs/SHARING.md), [deployment guide](docs/DEPLOYMENT.md) and
[GitHub workflow](docs/GITHUB_WORKFLOW.md).

[Architecture](#4-architecture-and-object-oriented-design) ·
[Measured results](#13-profiling-and-measured-statistics) ·
[Analysis notebook](analysis/ledgerx_performance.ipynb) ·
[Engineering report](docs/ENGINEERING_REPORT.md) ·
[Demo walkthrough](docs/DEMO.md) ·
[Construction PDF, in French](output/pdf/ledgerx-construction-pas-a-pas.pdf)

## Contents

1. [Local development](#1-local-development)
2. [Working API examples](#2-working-api-examples)
3. [Technology decisions](#3-technology-decisions)
4. [Architecture and object-oriented design](#4-architecture-and-object-oriented-design)
5. [Accounting and schema](#5-accounting-and-schema)
6. [Authentication and authorization](#6-authentication-and-authorization)
7. [Transactions and concurrency](#7-transactions-and-concurrency)
8. [Persistent idempotency](#8-persistent-idempotency)
9. [Reversals and reconciliation](#9-reversals-and-reconciliation)
10. [Algorithms and data structures](#10-algorithms-and-data-structures)
11. [Protocols, observability and failures](#11-protocols-observability-and-failures)
12. [Tests and CI](#12-tests-and-ci)
13. [Profiling and measured statistics](#13-profiling-and-measured-statistics)
14. [Engineering challenges and debugging](#14-engineering-challenges-and-debugging)
15. [Docker, deployment and limits](#15-docker-deployment-and-limits)
16. [React workspace and frontend decisions](#16-react-workspace-and-frontend-decisions)
17. [Scaling the project: future AWS investment](#17-scaling-the-project-future-aws-investment)

## 1. Local development

Python 3.12+, uv and a real PostgreSQL 16 server are required for the complete application.
No cloud account, paid API or external banking connection is needed.

```bash
# Run inside LedgerX. Cache, virtual environment and temporary files stay here.
mkdir -p .runtime/tmp .runtime/cache
TMPDIR="$PWD/.runtime/tmp" UV_CACHE_DIR="$PWD/.runtime/cache/uv" \
  UV_PYTHON_DOWNLOADS=never uv sync --frozen --python 3.12

cp .env.example .env
```

If Docker Desktop is available, `docker compose up -d db` starts **only PostgreSQL**; Python stays
in the local virtual environment. Run the command inside this repository, not your home directory.
It initializes `ledgerx`, `ledgerx_test` and `ledgerx_bench` on a fresh data directory.

Configure `DATABASE_URL` in `.env` for a local PostgreSQL database. The example uses
`postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx`. The application does not create
the PostgreSQL server or role. If using Docker for PostgreSQL later, the final section supplies
the equivalent setup.

```bash
.venv/bin/alembic upgrade head

# Interactively create the local administrator; password is not a command-line argument.
.venv/bin/python -m app.cli create-admin

# Funding is fictitious, administrative and explicitly enabled.
ENABLE_DEV_FUNDING=true .venv/bin/uvicorn app.main:app --reload
```

To use the **web interface**, build it once and start the same FastAPI server:

```bash
bash scripts/setup_frontend.sh       # Node 24 under .runtime/tools/node; no global install
bash scripts/frontend.sh install     # npm ci when the committed lockfile is present
bash scripts/frontend.sh build       # TypeScript check + static build under app/web
ENABLE_DEV_FUNDING=true bash scripts/run_local.sh
```

Open **http://127.0.0.1:8000**. Register a profile or sign in with your locally created administrator.
A normal signup starts with no accounts and cannot fund itself. The [five-minute demo](docs/DEMO.md)
explains the complete flow. After the initial build, Node is not needed to serve the interface.

Open [Swagger UI](http://localhost:8000/docs). Register or log in, then paste the returned bearer
token into **Authorize**. A normal signup never grants administrator access.

For the currently executable unit subset:

```bash
.venv/bin/pytest -q -m 'not integration and not e2e' --basetemp=.runtime/pytest-unit
```

`uv.lock` records the dependency resolution installed in the Python 3.12 environment. Use
`uv sync --frozen` for the locked local/CI graph. Docker now uses that lockfile with uv 0.12.3,
excluding development dependencies from the runtime. The schema `0004` production image passed
its container/browser checks and local deployment. Base image tags remain mutable.

## 2. Working API examples

The examples assume migrations are applied, the server is running with development funding
enabled, and `app.cli create-admin` has provisioned an administrator.

```bash
# Create a customer. The response never contains a password or password hash.
curl -s http://localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"local-demo-passphrase-123"}'

curl -s http://localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"local-demo-passphrase-123"}'

# Paste access_token from the login response, then create two accounts.
TOKEN='PASTE_ALICE_ACCESS_TOKEN'
curl -s http://localhost:8000/accounts -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{}'
curl -s http://localhost:8000/accounts -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{}'
```

Log in as the administrator using `/auth/login`. Set `ADMIN_TOKEN` from that response and substitute
the two account UUIDs:

```bash
ADMIN_TOKEN='PASTE_ADMIN_ACCESS_TOKEN'
SOURCE='PASTE_FIRST_ACCOUNT_UUID'
TARGET='PASTE_SECOND_ACCOUNT_UUID'

# 100 EUR of demonstration funds.
curl -s http://localhost:8000/dev/funding \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: funding-demo-1' \
  -d "{\"destination_account_id\":\"$SOURCE\",\"amount\":10000}"

# 15 EUR transfer. Repeating this exact command returns the original transfer.
curl -s http://localhost:8000/transfers \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: payment-demo-1' \
  -d "{\"source_account_id\":\"$SOURCE\",\"destination_account_id\":\"$TARGET\",\"amount\":1500}"

TRANSFER='PASTE_TRANSFER_UUID'
curl -s "http://localhost:8000/transfers/$TRANSFER/reversal" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: refund-demo-1' -d '{"reason":"Customer requested a refund"}'

curl -s http://localhost:8000/operations/reconciliation \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Both accounts above belong to Alice. Across different owners, only the **original recipient**
can initiate a refund: that recipient owns the account debited by the compensation. A sender
cannot claw back another customer's money.

| Method | Endpoint | Access / result |
|---|---|---|
| POST | `/auth/register` | Public; normal customer, 201 |
| POST | `/auth/login` | Public credentials; expiring opaque token, 200 |
| POST | `/auth/logout` | Revoke current token, 204 |
| GET | `/auth/me` | Current identity and UI capabilities; no token/hash exposed |
| GET | `/accounts` | Owner-filtered pages; `limit` 1–100 and UUID `after`; `next_after` |
| POST | `/accounts` | Authenticated; account belongs to caller, 201 |
| GET | `/accounts/{id}` | Owner only |
| GET | `/accounts/{id}/balance` | Owner only; integer cents |
| GET | `/accounts/{id}/transactions` | Owner only; `limit`, `cursor`, legacy `offset` |
| POST | `/transfers` | Source owner; atomic debit/credit, 201 |
| GET | `/transfers/{id}` | Owner of source or destination |
| POST | `/transfers/{id}/reversal` | Original recipient; one full compensation, 201 |
| POST | `/dev/funding` | Administrator + development flag |
| GET | `/operations/reconciliation` | Administrator; full audit |
| GET | `/metrics` | Administrator; Prometheus exposition |
| GET | `/health` | Public; DB connectivity and schema readiness |
| GET | `/health/live` | Public; process liveness without DB |

Unauthorized requests return 401 with `WWW-Authenticate: Bearer`. Non-administrators requesting
administrative operations receive 403. Another owner's resources return 404 to avoid confirming
their existence. Invalid payloads return 422; insufficient funds, key conflicts and duplicate
refunds return 409. Temporary database failures return 503 with `Retry-After: 1`.

Business errors include `code`, `detail` and `request_id`. Validation errors omit rejected input,
which prevents echoing a supplied password. Successful idempotent replays return 201 with the
original transfer data and `Idempotency-Replayed: true`.

## 3. Technology decisions

| Technology | Used for | Why it is appropriate here |
|---|---|---|
| Python 3.12+ | Domain/service logic, tools | Readable logic, exact integers, mature test ecosystem |
| FastAPI | HTTP routes, dependencies, OpenAPI | Explicit contracts and reusable authentication dependencies |
| React 19 + TypeScript | Browser workspace and typed UI contracts | Component composition, explicit state and compile-time checks |
| Vite + Node 24 | Frontend development/build only | Static bundle served by the existing FastAPI process |
| BigInt + lossless-json | Exact integer money in the browser | Preserve API amounts beyond JavaScript Number's safe integer range |
| Vitest + Playwright | Frontend unit and browser verification | Precision/retries, responsive interactions and the live API journey |
| Pydantic v2 | Request/response DTOs, configuration | Reject invalid data before money operations |
| Uvicorn / ASGI | HTTP serving and middleware | Standard Python web-server interface |
| SQLAlchemy 2 | Typed entities, SQL, sessions | Identity map and Unit of Work with explicit transaction scope |
| Psycopg 3 | PostgreSQL driver | Real PostgreSQL transactions, error codes and row locks |
| PostgreSQL 16 | Authoritative data | MVCC, unique indexes, foreign keys and deferred constraint triggers |
| Alembic | Versioned migrations | Reviewable schema, rollback guards and drift detection |
| `hashlib.scrypt` | Password hashing | Salted memory-hard KDF available without an extra native package |
| `secrets` / SHA-256 | Opaque tokens and token digests | 256-bit random secrets; only their digest is stored |
| Prometheus client | Counters and histograms | Route-level latency and money-operation outcomes |
| pytest / HTTPX | Unit, integration and HTTP E2E | Real database concurrency and actual TCP request scenarios |
| cProfile / pstats | Service profiling | Attribute time to functions and driver/commit calls |
| EXPLAIN ANALYZE / BUFFERS | Query profiling | Inspect executed plans and index behavior |
| Ruff | Lint and formatting | Consistent, reviewable Python |
| GitHub Actions | Verification workflow | Tests against PostgreSQL, migrations, coverage and live HTTP |
| Docker Compose | Optional local orchestration | Isolated application/test/benchmark databases |

## 4. Architecture and object-oriented design

```mermaid
flowchart LR
  C["Client / E2E / benchmark"] --> H["HTTP + Uvicorn"]
  H --> M["ASGI correlation and metrics"]
  M --> A["FastAPI + validated DTOs"]
  A --> U["Authentication / ownership"]
  U --> S["Account, transfer, reversal services"]
  S --> I["Scoped idempotency reservation"]
  S --> D["SQLAlchemy Session / Unit of Work"]
  I --> D
  D --> P[("PostgreSQL + integrity triggers")]
  A --> R["Administrative reconciliation"]
  R --> P
```

A modular monolith keeps each monetary effect within one database transaction. Splitting debit,
credit and idempotency across services would introduce distributed failure modes without improving
the demonstrated use case. There is no Kafka, Redis, Kubernetes, gRPC, external payment processor
or hidden background job.

```text
app/api/                         HTTP contracts, authentication dependencies, transactions
app/schemas/                     Pydantic request/response types
app/services/account_service.py  Accounts and indexed history
app/services/transfer_service.py Transfers and full compensations
app/services/idempotency_service.py Scoped transactional reservations
app/services/auth_service.py     Registration, tokens, immutable request principal
app/services/reconciliation_service.py Independent read-only accounting audit
app/db/                          Typed ORM mappings, engine and session factory
app/core/                        Configuration, security, errors, cursors and metrics
app/cli.py                       Interactive administrator provisioning
alembic/versions/                 Schema, constraints, triggers and migrations
tests/                           Unit, PostgreSQL, concurrency and real HTTP tests
scripts/                         Verification, benchmarks and profiling
analysis/                        Notebook, chart functions, report/PDF generators
frontend/src/                    React views, exact-money utilities and HTTP client
frontend/tests/                  Monetary precision and request/retry unit tests
frontend/e2e/                    Desktop/mobile fixtures and real PostgreSQL UI journey
app/web/                         Generated static bundle; excluded from source control
```

The HTTP route owns `with session.begin()`. Services flush SQL but do not commit; a failing service
or failing commit rolls back the entire operation. The authentication dependency completes its
short read transaction before the route starts the monetary transaction. That avoids SQLAlchemy's
“transaction already begun” error caused by implicit autobegin during authentication.

Object-oriented responsibilities are deliberate:

- `User`, `Account`, `Transfer`, `LedgerEntry`, `AuthToken` and `IdempotencyRecord` are typed ORM
  entities with stable identity. `Base` supplies declarative mapping behavior.
- Request and response classes are boundary DTOs: persistence models are not accepted as input.
  `extra="forbid"` prevents callers from injecting `owner_id` or `is_admin`.
- `Session` supplies the identity map and Unit of Work; `sessionmaker` is the factory. One session
  is used by one request/worker at a time.
- Frozen `Principal` represents the authenticated identity after the auth read transaction.
- `DomainError` separates expected business rejection from infrastructure failure.
- `ObservabilityMiddleware` encapsulates the ASGI wrapper. Benchmark `Operation` is a frozen
  request description; `Workload` holds fixture state and expected balances.

Stateless service orchestration uses functions and composition. A repository interface wrapping
one SQLAlchemy implementation or a deep inheritance hierarchy would add indirection without a
second useful implementation. This is not presented as a full DDD or event-sourcing framework.

## 5. Accounting and schema

Amounts are integer EUR cents: `1500` means EUR 15.00. Booleans, numeric strings, fractions,
zero and negative transfer amounts are rejected. The maximum is `9_000_000_000_000_000_000`,
below PostgreSQL signed BIGINT's maximum. Python checks prospective balances before SQL writes;
database constraints supply additional bounds.

The API accepts a larger integer range than JavaScript `Number` can exactly represent. A JavaScript
client needs an exact-integer JSON strategy or a smaller client-side maximum. The included React
client uses BigInt and lossless-json for full-range integer transport. Only EUR is supported;
the design does not assume that every real currency has two decimal places.

| Table | Main fields | Constraints / indexes |
|---|---|---|
| `users` | UUID, normalized username, password hash, active/admin flags | Unique username |
| `auth_tokens` | SHA-256 digest, user FK, expiry, revocation time | Digest PK; user/expiry indexes |
| `accounts` | UUID, immutable owner FK, currency, balance, private journal projection, system flag | EUR; bounded balance; nonnegative customer balance; projection guarded by triggers |
| `transfers` | UUID, source/destination FKs, amount, currency | Distinct accounts, positive bounded amount, immutable |
| `transfers` reversal metadata | Original-transfer FK, reason | Unique original reference; exact compensation validation |
| `ledger_entries` | UUID, transfer FK, account FK, signed amount | Immutable; unique `(transaction_id, account_id)` |
| `idempotency_records` | Principal, operation, key, fingerprint, result FK | Composite PK; completed result immutable |

For A sending 1500 cents to B, the journal records `A: -1500` and `B: +1500`.
Their sum is zero. The materialized balances change by those amounts and must equal the sum
of each account's immutable journal entries.

The dedicated system account is the counterpart for fictitious funding. It may be negative;
customer accounts may not. The system account has no customer owner and cannot be accessed through
normal account routes or used in ordinary transfers.

Deferred constraint triggers check the final transaction state:

1. Exactly two entries per transfer, with correct accounts, signs, amounts and currency.
2. Materialized balance equals the journal total for every affected account.
3. Idempotency reservations have a completed transfer reference at commit.

Immediate checks reject journal/transfer mutations, account identity or ownership changes, invalid
compensations and changes to completed idempotency results. A zero global sum alone is insufficient:
it could hide posting to the wrong accounts.

Deferral permits intermediate states while inserting the transfer and entries. `flush()` sends SQL;
only commit makes the transaction durable. Database owners can disable triggers or truncate data:
these checks are not tamper-proof protection against a privileged database administrator.

**Schema `0004` optimization:** an `AFTER INSERT` statement trigger groups only newly inserted
journal rows and updates a private exact projection, in UUID order. Deferred checks compare the
materialized balance with that projection by primary key. New projections start at zero; direct
projection changes are rejected. No historical entries are scanned on this balance-validation path.
Independent reconciliation still calculates full journal totals and checks both representations.
This trades additional account updates/storage for eliminating history-dependent validation work;
see [the invariant proof, migration limits and measurement protocol](docs/LATENCY.md).

### Migration compatibility

- `0001`: initial schema, system account, immutable journal and deferred balance/entry checks.
- `0002`: bounds, full reversal metadata, operation-scoped keys, account identity and key protection.
- `0003`: users, token digests, immutable ownership and principal-scoped idempotency.
- `0004`: verified projection backfill, insert-only incremental maintenance and deferred point checks;
  downgrade restores the previous validator without changing financial records.

Existing pre-authentication customer accounts and keys are preserved under a disabled `_legacy`
principal. They are not silently assigned to a new signup. Claiming legacy accounts would require
an explicit, audited migration; there is no public claim endpoint.

Downgrades refuse to discard reversal audit metadata, collapse conflicting key scopes or erase
active authentication data. The round-trip verifier first clears only a guarded disposable `_test`
database. It does not weaken production constraints.

## 6. Authentication and authorization

Passwords use scrypt with `N=32768, r=8, p=3`, a random 16-byte salt and a 32-byte derived key.
The stored encoding contains the algorithm/parameters/salt/hash; verification uses a constant-time
digest comparison. This is one of the documented scrypt memory/CPU trade-offs in the
[OWASP password-storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#scrypt).
The implementation uses [Python's scrypt API](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt).

Passwords are 12–128 characters. Unknown or inactive usernames still run a dummy password hash
verification to reduce timing differences. Login failures use the same generic message.
Validation responses and application logs do not echo passwords or bearer tokens.

Login creates a 32-random-byte opaque token. Only its SHA-256 digest is stored, together with the
user, expiry and revocation time. SHA-256 is appropriate here because the input is a high-entropy
random token; human passwords use scrypt instead.

Default token lifetime is one hour, configurable from 5 minutes to 24 hours. Each authenticated
request checks token validity and current user activity/role in PostgreSQL. Logout revokes the
current token. Login responses use `Cache-Control: no-store`. There are no refresh tokens,
password-reset flows, MFA or external identity providers.

Authorization rules:

- Accounts are created for the authenticated user; ownership is immutable.
- Balance and history access requires ownership.
- Sending money requires ownership of the source account, including for an administrator.
- A recipient may view the transfer but not the sender's full account or history.
- A refund requires ownership of the original recipient account.
- Demo funding requires an administrator and `ENABLE_DEV_FUNDING=true`.
- Reconciliation and metrics require an administrator.
- Idempotency keys are scoped to the authenticated principal, preventing cross-user response reuse.

Internal services also support trusted in-process calls for fixtures/profiling. The HTTP boundary
always passes the authenticated actor; it is not an alternative public authentication bypass.
Login and signup share a process-local sliding-window limiter: by default, 10 accepted attempts
per ASGI peer and 120 overall per 60 seconds, with at most two in-flight authentication requests.
Successful attempts also count. HTTP 429 includes `Retry-After`; rejected requests do not execute
password hashing. A bounded deque and counters are protected by a thread lock; hashing/SQL run
outside that lock. Tests cover concurrent admission, expiry, failure cleanup and forged forwarding
headers. Container/local startup does not trust forwarded headers; users behind one proxy can share
a budget. Limits reset on restart and are not distributed across replicas. Details and configuration
are in the [deployment guide](docs/DEPLOYMENT.md).

Production hardening still needs verified TLS deployment, broader abuse protection,
token-retention cleanup, password recovery,
least-privilege DB roles and an operational security review. A revocation does not cancel a request
that already passed authentication.

## 7. Transactions and concurrency

Routes are synchronous `def` functions. FastAPI executes blocking database work in worker threads.
Uvicorn handles ASGI I/O; there are no blocking Psycopg calls inside asynchronous route bodies.
This supports concurrent database waits, not unlimited CPU parallelism under conventional CPython.

The pool defaults to 10 persistent connections plus 10 overflow connections. Every worker/request
has its own session; sharing one mutable session across concurrent workers is forbidden.
Additional API processes multiply the connection budget and require deployment-level sizing.

### GIL, threads and additional processes

The current container starts **one Uvicorn process** (`workers=1`). LedgerX does not use Python
`multiprocessing` or a `ProcessPoolExecutor` in the application. Synchronous routes run through
Starlette's thread pool, allowing other requests to progress during database I/O. Under the
project's conventional CPython 3.12 runtime, the GIL limits simultaneous Python bytecode execution
within one process; it does not make a multi-statement transfer atomic. See
[Starlette's thread pool](https://starlette.dev/threadpool/) and
[Python's GIL/threading guidance](https://docs.python.org/3.12/library/threading.html).

Additional Uvicorn processes would each have their own interpreter/GIL and could improve throughput
if Python CPU work is the limiting resource. They would not remove PostgreSQL lock contention on
one account and could worsen tail latency if they overwhelm database connections or CPU. There is
no measured multi-process speedup for LedgerX yet. A useful next experiment compares one, two and
four processes with the same total SQL connection budget, workload and latency/error targets.
Before deploying that configuration, auth admission limits must be coordinated across processes,
Prometheus collection must account for each process, and migrations must run once before workers.

The test/load tools are separate: concurrency tests and the closed-loop benchmark use
`ThreadPoolExecutor`; the fixed-arrival generator uses `asyncio` tasks. These create concurrent
clients, not additional application workers. Financial exclusion and atomicity remain PostgreSQL
responsibilities across all threads and processes.

### Ordered row locks

At READ COMMITTED isolation, both accounts are selected with `ORDER BY id FOR UPDATE`.
Funds are checked only after locking. With 10000 cents and two simultaneous 8000-cent debits,
one request commits and the next sees 2000 and fails. Disjoint account pairs can execute independently.
See [PostgreSQL row-lock behavior](https://www.postgresql.org/docs/16/explicit-locking.html#LOCKING-ROWS).

READ COMMITTED is sufficient for this protocol because every balance-changing path first locks
the affected accounts and account identity is immutable. A later locking statement sees committed
changes after waiting; this is different from relying on an earlier unprotected balance read.
Serializable isolation would require an explicit serialization-failure retry policy and does not
replace business idempotency. A process-local Python mutex would not coordinate other API workers
or processes; PostgreSQL owns the locks shared by all participants.

```mermaid
sequenceDiagram
    participant A as Request A
    participant B as Request B
    participant DB as PostgreSQL
    A->>DB: Lock ordered accounts, source = 10000
    B->>DB: Same lock, waits
    A->>DB: Debit/credit 8000, write entries/key
    A->>DB: Commit, source = 2000
    DB-->>B: Lock acquired, current source = 2000
    B->>DB: Insufficient funds, rollback reservation
```

Sorting immutable UUIDs gives A→B and B→A the same lock order, reducing deadlocks. All application
money-writing paths follow this order. It is not a claim that arbitrary future SQL paths cannot
introduce a deadlock.

The locking query uses `populate_existing=True`: SQLAlchemy's identity map might already contain a
stale balance loaded before another transaction committed. Row locking alone does not guarantee
that the cached object is refreshed. A dedicated regression test exercises that exact case.
See [SQLAlchemy session behavior](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).

Reversals reserve their key, lock the original transfer with `FOR NO KEY UPDATE`, check for an
existing compensation, then acquire the ordered account locks. The original lock is compatible with
foreign-key `KEY SHARE` checks; the unique reversal reference is an independent backstop.

| Resource | Coordination | Why this choice |
|---|---|---|
| New idempotency key | Unique-index insertion, held until transaction end | A competing insert waits for the winning commit/rollback |
| Existing idempotency key | `FOR UPDATE` | Serialize replay/conflict decisions on the persisted result |
| Original transfer during refund | `FOR NO KEY UPDATE` | Serialize refunds while allowing foreign-key key-share checks |
| Source and destination accounts | `FOR UPDATE`, ordered by UUID | Check fresh funds and update both balances without lost updates |
| Independent reconciliation | One read-only statement snapshot | Compare balances/entries at the same committed instant |

Locks live until the outer transaction commits or rolls back, not until a service function returns.
The posting service never performs external HTTP calls or user interaction while holding money
locks. Account history reads use MVCC and do not take these exclusive posting locks.

### Bounded waits

| Setting | Default | Meaning |
|---|---:|---|
| Connection establishment | 5 s | `DB_CONNECT_TIMEOUT_SECONDS` |
| Pool checkout | 5 s | `DB_POOL_TIMEOUT_SECONDS` |
| Database lock wait | 2000 ms | `DB_LOCK_TIMEOUT_MS` |
| SQL statement | 10000 ms | `DB_STATEMENT_TIMEOUT_MS` |
| Idle transaction | 15000 ms | `DB_IDLE_TRANSACTION_TIMEOUT_MS` |

These bounds are not an overall HTTP deadline. Lock timeout, deadlock, serialization failure and
connection failures receive a sanitized 503. The server does not retry monetary work automatically.
Clients should use bounded retries/backoff with the same idempotency key.

## 8. Persistent idempotency

Keys are optional for backward API compatibility but should be supplied for every retryable money
request. They are case-sensitive, 1–128 printable non-space ASCII characters.
The database key is `(principal_id, operation, key)`; operation is transfer, funding or reversal.

1. Normalize the validated payload through Pydantic, including UUIDs and default EUR.
2. Serialize canonical JSON with sorted keys/fixed separators, then compute SHA-256.
3. Reserve with `INSERT ... ON CONFLICT DO NOTHING RETURNING ...` inside the monetary transaction.
   A newly inserted row is returned immediately: this transaction already owns its uncommitted
   reservation, so a separate SELECT cannot strengthen it.
4. On conflict, the insertion waits for the owner's commit/rollback. If no new row was inserted,
   a subsequent locked SELECT sees the committed result at READ COMMITTED.
5. Same fingerprint and completed result returns the original transfer ID, timestamp and data.
6. Changed payload returns `409 idempotency_conflict`.
7. On success, persist the result reference and monetary effects in the same commit.

Failures are not cached. If funds are insufficient or an exception occurs after flush, the
reservation rolls back. A later retry can succeed after funding. Keys currently never expire.
Reversal fingerprints include the original transfer ID and normalized reason.

A connection failure after commit can leave the client uncertain whether money moved. Retrying
the same key resolves that ambiguity. Atomic SQL alone cannot prevent two independent HTTP retries
from executing twice without a key. This is one committed effect per successful key/payload,
not a claim of exactly-once network delivery.

## 9. Reversals and reconciliation

A full refund creates a new transfer and two new ledger entries. It never edits the original
transfer or journal. `reversal_of` links the compensation to its original; a reason is required.
The DB validates exact opposite accounts, amount and currency.

Only one full compensation may exist per original. Partial/excess refunds, reversal of a reversal
and reversal of demonstration funding are rejected/unsupported. The original recipient must have
the funds; refunding cannot force a customer overdraft. Concurrent requests serialize on the
original transfer, and same-key retries return the existing compensation.

The independent reconciliation service recalculates journal totals with SQL, without invoking
the posting service or changing balances. In a single MVCC statement it checks:

- Stored balance versus journal sum for every account.
- Exactly two correctly matching entries per transfer.
- Global signed journal sum and total balance, including the system account.

Its structured response includes a check timestamp, counts, inconsistency totals and up to 100
account-level discrepancy details: stored balance, recalculated balance and difference.
The count remains complete even if the detail sample is capped. Schema `0004` also reports
`projection_mismatched_accounts` and `projection_discrepancies`, independently comparing the private
projection with the recalculated journal. A discrepancy in either representation fails the audit.

One SQL statement avoids false discrepancies if a transfer commits between otherwise separate
balance and journal reads. A deliberate corruption test bypasses only the balance trigger inside
the isolated `_test` database, restores it, and verifies that the audit detects a 7-cent mismatch
without repairing it. Normal application code never disables constraints or modifies balances
outside posting.

This full scan is an explicit administrative diagnostic, not a cheap readiness probe or a scheduled
reconciliation worker.

## 10. Algorithms and data structures

Let `A` = accounts, `E` = entries, `Eₐ` = entries of one account, `K` = idempotency records,
`L` = page size and `O` = offset. Estimates describe logical work; cache, locks, MVCC and storage
determine actual latency.

| Operation | Algorithm / structure | Approximate work |
|---|---|---|
| Monetary calculation | Python integer / SQL BIGINT | Constant number of bounded additions/subtractions |
| Account lookup | UUID B-tree PK | O(log A) lookup |
| Lock acquisition order | Sort two immutable UUIDs | O(1) for this fixed-size transfer |
| Loaded-account lookup | Python dict, UUID → entity | Average O(1); two objects |
| Payload identity | Canonical JSON + SHA-256 | O(P) in payload bytes |
| Retry reservation | Composite unique B-tree | O(log K), plus contention |
| Transfer integrity | Unique `(transaction_id, account_id)` | Indexed lookup plus two expected rows |
| Balance trigger, archived `0003` | Indexed account-entry scan and SUM | O(Eₐ) aggregation |
| Balance validation, `0004` | Add new-entry deltas; deferred projection comparison | Two account updates/lookups for a transfer, approximately O(log A); independent of Eₐ |
| Offset history | Index scan, skip O rows | O(log E + O + L) |
| Cursor history | Lexicographic index seek | O(log E + L) access path |
| Full reconciliation | Grouped sums/counts and joins | Scans/aggregation proportional to dataset; plan-dependent memory/sorts |
| Benchmark percentile | Sort samples, nearest-rank lookup | O(N log N), O(N) stored samples |
| Password verification | scrypt | Intentionally costly CPU/memory work, outside payment benchmarks |

History uses B-tree `(account_id, created_at, id)` and descending order. The UUID tie-breaker matters
because multiple entries can share a transaction timestamp. A cursor seeks strictly below
`(created_at, id)` and fetches `limit+1` to detect another page.

The base64url cursor contains version, account ID, timestamp and entry UUID. It is validated and
bound to an account, but unsigned: it is pagination state, not an authorization credential.
Authorization is checked independently. Legacy offset is supported but deprecated; a nonzero offset
cannot be combined with a cursor.

Cursor paging avoids ordinary offset shifts from new rows ahead of the current position.
It does not preserve a snapshot across requests. A transaction started earlier can commit later
and become visible during traversal. An exact point-in-time export needs a separate snapshot design.

## 11. Protocols, observability and failures

Clients communicate through HTTP/JSON, UTF-8, standard status codes and OpenAPI. UUIDs and ISO-8601
timestamps are strings; money is an integer. Authentication uses the `Authorization: Bearer` header,
not a URL query parameter.

The API communicates with PostgreSQL over Psycopg's PostgreSQL TCP protocol, using SQLAlchemy's
connection pool. The HTTP response is sent after commit, but response delivery and database commit
cannot be one atomic operation. Prometheus pulls `/metrics` through HTTP with an administrator token.
No broker, event-delivery protocol or distributed transaction coordinator is implemented.

The pure ASGI wrapper adds safe bounded `X-Request-ID` and `X-Correlation-ID` values. An invalid or
missing request ID becomes a UUID; a missing correlation ID defaults to that request ID.
Structured request summaries log method, route template, status and duration. The `ledgerx` logger
defaults to INFO with a console handler when no host logging configuration exists. Existing host
handlers are preserved. Error events are JSON without SQL parameters or secrets. The ASGI wrapper
catches unexpected exceptions before Uvicorn can log their raw messages/tracebacks. If a response
already started, it raises a sanitized error so the server closes the connection safely. Use
`--no-access-log` with Uvicorn to suppress its separate raw-path access logs.

| Metric | Labels / purpose |
|---|---|
| `ledgerx_http_requests_total` | Method, route template, status |
| `ledgerx_http_request_duration_seconds` | Method, route template; latency histogram |
| `ledgerx_money_requests_total` | Transfer/funding/reversal; committed, replayed, rejected, denied, unavailable or internal_error |

Counters are updated after the request/transaction completes; a replay is distinguished from a
new committed operation. Labels never contain raw account IDs, keys, tokens or arbitrary URLs.
Unmatched routes have a fixed label. Metrics are process-local; multiple Uvicorn processes require
explicit Prometheus multiprocess configuration or per-process scraping.

Failure behavior:

- Before commit, exceptions roll back entries, balances, transfer and reservation together.
- After commit, a lost response is resolved by retrying the same key.
- Expected business rejection produces a stable 4xx code.
- Temporary DB failures produce 503/Retry-After, without automatic server retries.
- Integrity failures and unexpected exceptions produce a sanitized 500.
- Authentication failure cannot reach a monetary route.

Database durability depends on PostgreSQL WAL/fsync and storage. Backups, point-in-time recovery,
restore drills, replication, distributed rate limiting and a full incident-response process are not
implemented. Authentication has bounded process-local admission control.
Separate balance/history requests observe separate snapshots.

## 12. Tests and CI

| Layer | Coverage implemented |
|---|---|
| Unit | Strict amounts, self-transfer, cursor validation, password hashes, token generation, metric redaction, percentile calculations |
| API + PostgreSQL | Balances, history, system accounts, exact limits, funding, missing resources |
| Authentication | No-token access, ownership, role injection, generic login errors, expiry, revocation, disabled users |
| Authorization | Cross-owner reads/debits, private transfer lookup, recipient-only refund, principal-scoped keys |
| Idempotency | Retry, payload conflict, normalization, funding scopes, rollback and retry |
| Integrity | Incomplete transfer, independent balance update, immutable journal/identity/key, incomplete reservation |
| Fault injection | Crash after flush; database failure sanitization; no leaked effect from a fresh session |
| Concurrency | Overspending, same key, opposite directions, eight simultaneous debits, same/different-key refunds |
| Reconciliation | Consistent ledger and deliberate isolated corruption without repair |
| E2E | Actual HTTP/TCP payment/refund lifecycle and eight concurrent retries |
| Migrations | Legacy financial data preservation, loss-preventing downgrade, empty-test round trip, ORM drift check |

Concurrency tests use independent sessions/connections, barriers and PostgreSQL backend PID checks.
SQLite and a single test transaction cannot reproduce these lock semantics. Tests cover concrete
interleavings; they do not prove every possible schedule.

With local PostgreSQL and an explicitly disposable database:

```bash
# Complete local verification: lint, tests, migrations, temporary API and HTTP E2E.
# Clears ledgerx_test; appends fixtures to ledgerx_bench. Does not clear ledgerx.
bash scripts/verify_local.sh

# Individual steps:
TEST_DATABASE_URL=postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx_test \
  .venv/bin/pytest -q -m 'not e2e'
.venv/bin/ruff check app tests scripts alembic
.venv/bin/ruff format --check app tests scripts alembic

# Destructive ONLY to the dedicated _test database; run serially after tests.
DATABASE_URL=postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx_test \
  .venv/bin/python -m scripts.verify_migrations
```

GitHub Actions provisions PostgreSQL 16, runs lint/formatting, unit/integration tests with coverage,
migration verification, starts Uvicorn and runs the real HTTP E2E tests. It also installs the locked
frontend dependencies, checks formatting/types, runs Vitest, builds the UI and runs Playwright
against both controlled fixtures and the real API. JUnit, coverage, browser results and API logs
are uploaded. The workflow is published; inspect
[GitHub Actions](https://github.com/anaselmadhi/LedgerX/actions) for the remote result, which has not
yet been verified in this report.

Verification is tracked by revision, so executed results and pending work stay distinct:

| Revision / check | Observed result |
|---|---|
| Archived `0003`: unit + real PostgreSQL integration | **113 passed in 19.40 s**, zero failures |
| Archived `0003`: real HTTP E2E | **2 passed in 0.87 s** |
| Archived `0003`: statement coverage | **94.09%**, 812/863 statements |
| Archived `0003`: migration round trip + ORM drift | Passed on the guarded `_test` database |
| Archived `0003`: production Docker browser suite | **12 passed in 11.1 s**, including two live PostgreSQL journeys |
| Current `0004`: isolated Python tests | **77 passed in 4.12 s**, including ten load-generator and fourteen release/smoke tests |
| Current `0004`: frontend format/unit/types/build | Passed; **26 unit tests** |
| Current `0004`: Ruff and formatting | Passed; 77 Python files including analysis tools/notebook |
| Current `0004`: unit/PostgreSQL + real HTTP | **147 passed in 25.75 s + 2 passed in 0.94 s** |
| Current `0004`: statement coverage | **94.12%**, 816/867 statements |
| Current `0004`: migrations / ORM drift | Round trip passed; no new upgrade operations |
| Current `0004`: production Docker browser | **12 passed in 11.6 s**, zero skipped/flaky cases |
| Current `0004`: personal local release | Backup archive created; migration and schema/UI/auth smoke checks passed |
| Archived 20 October performance experiment | **90/90 cases**, 18,000 measured requests, zero unexpected responses |
| New latency experiment | 36 closed-loop cases, 1,200 profiled transfers, 18 fixed-arrival cases; accounting verified, high-load targets unmet |
| Remote browser demonstration, 26 October | Owner reported successful remote access/transfers; administrator reconciliation found no discrepancies |
| Remote CI | Workflow published; result awaiting verification |
| Cloud-hosted deployment | Not executed |

The archived 115-test backend release consists of 53 isolated tests, 60 PostgreSQL-backed tests and two
separate HTTP tests. Its `deselected` counts are selection filters; all 115 ran across the two
invocations. The current revision adds ten projection integration tests, ten generator unit tests
and fourteen release/smoke tests. Coverage includes the uncovered interactive administrator CLI.

The current suite contains 77 isolated tests, 70 PostgreSQL-backed tests and two separate HTTP
tests. All 149 passed on the host. Reports are archived under
`artifacts/releases/2026-10-22-projection/`; the older `0003` archive remains separate.
The coding sandbox cannot access localhost PostgreSQL or Docker; host-terminal reports supply
the executed integration/deployment evidence. The first `0004` run exposed a test-cleanup ordering
error; that failure and its subsequent correction are documented in the engineering report.

The initial run had deprecation warnings: Alembic configuration now explicitly uses
`path_separator=os`; the locked Starlette TestClient still supports HTTPX but warns about a future
HTTPX2 transition. That warning is documented, not suppressed; all tests passed with the locked graph.

The unit-suite runtime is a test observation, not an API latency statistic.
See [engineering report](docs/ENGINEERING_REPORT.md) and [artifact descriptions](artifacts/README.md).

## 13. Profiling and measured statistics

### Current schema `0004` results: 22 October 2026

The full local release passed 149 backend, 26 frontend and 12 browser tests. The following
measurements come from `artifacts/latency/` and the immutable release archive. See
[the full results and storage snapshot](docs/LATENCY_RESULTS.md) for source digests and evidence.

### Closed-loop HTTP

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

### History depth and commit cost

Four history depths × three fresh fixtures × 100 timed transfers = **1,200 measured commits**. Service timings include cProfile overhead. Commit timing includes transaction exit and deferred checks. The last two columns are separate read-query execution times from `EXPLAIN ANALYZE`; they are not complete transfer timings.

| Prepared transfers | Median service p95 (ms) | Median commit p95 (ms) | Historical SUM (ms) | Projection lookup (ms) |
|---:|---:|---:|---:|---:|
| 0 | 4.850 | 0.717 | 0.029 | 0.009 |
| 100 | 4.638 | 0.606 | 0.042 | 0.010 |
| 1000 | 4.748 | 0.601 | 0.113 | 0.010 |
| 10000 | 5.750 | 0.622 | 0.982 | 0.013 |

![Service/commit and isolated query timings](artifacts/latency/figures/history-and-commit.png)

The measured service p95 remains around 5 ms across these depths, while the independent historical SUM becomes more expensive. Six application SQL executions per measured transfer are observed, versus seven in the older baseline; that difference includes the earlier idempotency-query optimization and cannot be attributed solely to the projection. SQL cursor counts exclude statements inside PostgreSQL triggers.

### Fixed-arrival HTTP load

Two workloads × three offered rates × three 5-second repetitions = **30,000 offered arrivals**. **18,439 were sent, 11,561 were dropped by the generator, zero sent requests produced unexpected responses, and zero outcomes were unconfirmed.** Accounting and reconciliation passed in every case. `all_targets_met` is **false**.

| Workload | Offered requests/s | Sent / offered, all 3 runs | Dropped | Median scheduled p95 (ms) | Runs meeting the load target |
|---|---:|---:|---:|---:|---:|
| `independent_transfers` | 100 | 1,500 / 1,500 | 0 | 13.14 | 3/3 |
| `independent_transfers` | 300 | 3,412 / 4,500 | 1,088 | 247.76 | 1/3 |
| `independent_transfers` | 600 | 3,771 / 9,000 | 5,229 | 418.07 | 0/3 |
| `shared_source` | 100 | 1,500 / 1,500 | 0 | 24.09 | 3/3 |
| `shared_source` | 300 | 4,031 / 4,500 | 469 | 579.72 | 1/3 |
| `shared_source` | 600 | 4,225 / 9,000 | 4,775 | 667.10 | 0/3 |

![Fixed-arrival load, drops and errors](artifacts/latency/figures/fixed-arrival-load.png)

Of the dropped arrivals, **5,252** exceeded the generator admission-lag threshold and **6,309** reached the in-flight cap. These were not sent to the API and are not server-rejected transfers. Tail percentiles cover sent requests and include dispatch delay; they must be read together with the drops. The generator shares the Mac with the API and Docker database, so these results cannot isolate the server ceiling.

All six 100 requests/s cases met their offered load over these short windows. The 300 requests/s cases were inconsistent, and none of the 600 requests/s cases met the target. This is not a sustained 100 requests/s SLO, a maximum-user guarantee or an AWS sizing result.

### What the comparison can establish

- The incremental design preserves the verified financial invariants and removes full-history sums from commit validation.
- The new depth experiment and isolated query plans support the intended scaling behavior.
- The older 20 October run and the new run differ in revision, database state, test selection and background conditions. They do not establish a controlled end-to-end speedup attributable only to this migration.
- A repeatable worker-count experiment and a separate load-generator host would help distinguish Python CPU pressure, client scheduling, SQL pool waits and account-lock contention. Those experiments have not run.


### Archived 20 October baseline and reproduction protocol

The remaining baseline tables in this section describe the earlier revision, not schema `0004`.

### HTTP experiment design

The default matrix measures **200 requests per case**, concurrency **1, 8 and 32**, **3 repetitions**
and **20 warmup requests per case**: **90 cases / 18,000 timed requests**, plus setup and warmup.
History fixtures contain 1,000 seeded transfers. All requests authenticate; password hashing/login
occurs before the measured workload. Per-request token checks remain part of measured HTTP latency.

| Scenario | What it exercises |
|---|---|
| `balance_read` | Indexed balance lookup |
| `history_head` | First 25 entries |
| `history_deep_offset` | Deep pagination with skipped rows |
| `history_deep_cursor` | Equivalent page through a cursor seek |
| `independent_transfers` | One account pair per worker |
| `shared_source` | Account contention with sufficient total funds |
| `opposite_directions` | Ordered locking for both directions |
| `idempotent_replay` | Same successful key, same transfer ID |
| `insufficient_funds` | Expected 409 responses, no money movement |
| `reversals` | Exact full compensations of prepared transfers |

The generator uses actual TCP HTTP, persistent connections and a closed-loop worker model:
one request per worker is outstanding at a time. Setup, warmup, auditing and file writing are excluded
from the measured interval. Every case saves raw latencies, min/mean/p50/p95/p99/max, throughput,
HTTP status counts, unexpected-error rate, exact expected balances and reconciliation.

A 409 in the refusal scenario is expected, but is not a successful transfer. A 201 replay is not
a new payment. Reported requests/second must not be relabelled new payments/second.
Any unexpected status, incorrect replay ID, balance mismatch or failed audit marks the run failed.

The JSON includes the source SHA-256, timestamp, generator OS/Python/CPU count, API/PostgreSQL
versions and workload parameters. It does not automatically know Docker's full host/VM CPU/RAM
allocation or unrelated host load; record those when sharing a performance claim.

For a local server connected to a dedicated `ledgerx_bench` database:

```bash
# One command for all checks plus performance measurements:
bash scripts/verify_local.sh --benchmark

# If the test suite already passed, measure performance without repeating it:
bash scripts/verify_local.sh --benchmark-only

# Or run each stage separately:
# Use a dedicated terminal/session for the benchmark database configuration.
export DATABASE_URL=postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx_bench
export BENCHMARK_PASSWORD=ledgerx-local-benchmark-password
.venv/bin/python -m scripts.prepare_benchmark
ENABLE_DEV_FUNDING=true .venv/bin/uvicorn app.main:app --port 8001

# In another terminal:
BENCHMARK_PASSWORD=ledgerx-local-benchmark-password \
  .venv/bin/python -m scripts.benchmark --update-readme

# Optional shorter smoke run:
BENCHMARK_PASSWORD=ledgerx-local-benchmark-password \
  .venv/bin/python -m scripts.benchmark --requests 50 --concurrency 1 8 \
  --repeats 1 --warmup 5 --history-size 100
```

The provisioning script is guarded to `_bench` databases (or `_test` under CI) and never overwrites
an existing password. Demo credentials are only for that local isolated database.
Benchmarks add fresh fixtures instead of truncating data; successive runs increase global history.

### Function and SQL profiling

```bash
PROFILE_DATABASE_URL=postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx_bench \
  .venv/bin/python -m scripts.profile_workload
```

This executes 100 service transactions at starting history depths 0, 100 and 1,000. It emits:

- cProfile binary files and the top 30 functions by cumulative time.
- Full service duration including commit, plus raw samples and percentiles.
- SQL execution counts and times, excluding DBAPI commit.
- Peak process RSS including setup; PostgreSQL version and relevant settings.
- Actual JSON `EXPLAIN (ANALYZE, BUFFERS)` plans for offset/cursor history queries.

Deferred integrity triggers run during commit. Their cost is included in the service timer and
cProfile, but not SQLAlchemy cursor-execute timings. Service profiling excludes HTTP/authentication
and includes profiler overhead; its times are explicitly distinct from the HTTP measurements.

### Actual results

The baseline was collected on macOS 15.6 ARM64, Python 3.12.12 and PostgreSQL 16.15, with one API
process. The generator reports 10 logical CPUs; the Docker VM allocation/background load was not
recorded. Each value below is the **median of three repetition-level values** (200 requests each),
including the median of the three p95 estimates rather than a pooled percentile.

| Workload | Clients | Median req/s | Median p95 ms |
|---|---:|---:|---:|
| Balance reads | 8 | 926.5 | 10.44 |
| Independent transfers | 8 | 443.1 | 21.44 |
| Independent transfers | 32 | 390.0 | 111.25 |
| Shared-source transfers | 8 | 365.5 | 56.52 |
| Shared-source transfers | 32 | 307.2 | 254.98 |
| Full refunds | 8 | 333.6 | 41.53 |
| Full refunds | 32 | 281.2 | 255.82 |

![Observed HTTP throughput and p95 latency by concurrency](artifacts/figures/concurrency.png)

Eight clients outperformed 32 in these workloads. Shared accounts show longer tails than independent
transfers, consistent with contention/queueing. These observations do not isolate every bottleneck.

![All measured transfer latencies, including outliers](artifacts/figures/latency-distribution.png)

Service profiling is separate from HTTP timing and includes cProfile overhead and commit:

| Initial history | Measured transfers | p50 ms | p95 ms | p99 ms | SQL cursor calls |
|---|---:|---:|---:|---:|---:|
| 0 | 100 | 6.43 | 9.75 | 14.59 | 700 |
| 100 | 100 | 14.79 | 22.62 | 29.57 | 700 |
| 1,000 | 100 | 10.00 | 20.11 | 23.60 | 700 |

![Measured service and history-query profiling](artifacts/figures/profiling.png)

The service timings are non-monotonic; they do not establish a scaling law for trigger cost.
At initial history 1,000, single `EXPLAIN ANALYZE` observations measured 0.274 ms for offset versus
0.016 ms for cursor. The HTTP history results remained similar: this is **not** evidence of a 17×
end-to-end improvement. Raw plans, SQL calls, RSS and samples are in [profiling.json](artifacts/profiling.json).

The [analysis notebook](analysis/ledgerx_performance.ipynb) contains real captured outputs and
commentary. Its code cells are executed sequentially through the Python renderer, without
starting a Jupyter server; it records that execution method in its metadata. Matplotlib/Jupyter
are available in the existing Anaconda environment and are separate from the backend dependencies.

```bash
# Regenerate charts and the notebook from existing measurements; no API/database access:
MPLCONFIGDIR="$PWD/.runtime/matplotlib" python3 -m analysis.render_report
# Optional interactive exploration, using a kernel with Matplotlib:
JUPYTER_RUNTIME_DIR="$PWD/.runtime/jupyter" JUPYTER_DATA_DIR="$PWD/.runtime/jupyter-data" \
  JUPYTER_CONFIG_DIR="$PWD/.runtime/jupyter-config" IPYTHONDIR="$PWD/.runtime/ipython" \
  XDG_CACHE_HOME="$PWD/.runtime/cache" jupyter lab analysis/ledgerx_performance.ipynb
```

The complete per-repetition table follows. If collecting a new baseline, regenerate charts and
review the interpretation above; it describes the 20 October 2026 baseline.

<!-- BENCHMARK:START -->
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

Raw samples, status distributions, exact balance checks and reconciliation: [benchmark.json](artifacts/benchmark.json).
These are local measurements, not a production capacity or SLO guarantee. A closed-loop generator slows down when the server stalls (coordinated omission).

<!-- BENCHMARK:END -->

### How to discuss results

Compare independent versus shared-account writes to expose contention. Compare increasing history
depths to examine trigger cost. Compare offset/cursor plans to justify the composite index.
Concurrency above the useful pool/database capacity can increase p95/p99 without increasing
throughput; use measurements to find that point.

Three repetitions expose some noise but are not a capacity study. A p99 from 200 samples has few
tail observations. A closed-loop generator slows when the server stalls, so it can underrepresent
latency under a fixed arrival rate (coordinated omission). The separate fixed-arrival experiment has now run on schema `0004`. It counts dropped arrivals
and includes dispatch lag in scheduled-to-completion latency. See
[the current results](docs/LATENCY_RESULTS.md); higher offered loads were not consistently met. Long-duration
soak tests and production SLO evidence remain absent.

## 14. Engineering challenges and debugging

This section records actual implementation work and its evidence. A risk found during code review
is distinguished from an observed failure and from a deliberately injected test fault. These
examples are reproducible engineering cases, not claims about production incidents.

| Challenge | Diagnosis and reasoning | Resolution and evidence |
|---|---|---|
| A locked ORM entity can still contain an old balance | PostgreSQL row locking and SQLAlchemy's identity map are separate mechanisms; a previously loaded object may not refresh automatically | Add `populate_existing=True` to the ordered locking query. A real-PostgreSQL regression test preloads stale data, commits a competing debit, then verifies overspending is refused |
| Authentication can open a transaction before the route | SQLAlchemy implicitly begins on a SELECT; starting another top-level transaction after token lookup would conflict | Complete a short auth read transaction and pass an immutable principal into the route. Authenticated money paths passed integration/E2E tests |
| Opposite-direction transfers can acquire locks in opposite order | Locking source then destination creates a possible A→B / B→A cycle | Sort immutable UUIDs and lock in one order. Independent-connection tests cover opposite directions and eight competing debits; arbitrary future paths still require review |
| Refund locking interacts with foreign keys | Locking the original too strongly can conflict with FK `KEY SHARE` checks; uniqueness alone does not provide a friendly domain response | Use `FOR NO KEY UPDATE` on the original, ordered account locks, and a unique original reference. Same/different-key concurrent refund tests passed |
| A refund must not become an unauthorized clawback | The original sender's ability to see a transfer does not authorize debiting its recipient | Require ownership of the original destination and sufficient funds. Cross-owner refund and insufficient-funds tests passed |
| A retry key can collide across users or operations | A global namespace could expose another principal's response or conflate funding and transfers | Composite `(principal_id, operation, key)`, canonical payload fingerprint, transactional reservation. Scope, conflict and concurrent-retry tests passed |
| Financial changes can be flushed before an exception | SQL flush is not commit; a successful intermediate INSERT/UPDATE must not be treated as a complete payment | Inject an exception after posting flush, then inspect through a fresh session. Balances, entries, transfer and reservation roll back; same-key retry succeeds |
| Migration updates can leave deferred trigger events pending | Updating legacy account ownership queues accounting checks; later ALTER TABLE statements can encounter PostgreSQL's pending-event restriction | Drain deferred events before subsequent schema changes. The migration test upgrades funded legacy records and verifies money, entries and keys remain intact |
| Downgrading can destroy audit/security information | Removing authentication or reversal columns is not safely reversible once those features contain data | Refuse lossy downgrades transactionally. Verify rejection preserves version/users; perform full round trips only after explicit disposable-test cleanup |
| Reconciliation can report false drift across changing snapshots | Separate balance and ledger queries can straddle a concurrent commit | Aggregate independently in one MVCC statement. Healthy-ledger and deliberately corrupted-data tests verify detection without silent repair; the snapshot race is a design risk, not a claimed production incident |
| New rows can shift offset pages and timestamps can tie | Ordering by timestamp alone is ambiguous; deep offsets also scan skipped rows | Use `(created_at, id)` cursor seeks and an account-bound validated cursor. Tests cover equal timestamps and new inserts; HTTP pages still do not share one snapshot |
| Sanitizing a JSON error does not necessarily sanitize server logs | Starlette can re-raise an exception to Uvicorn after a custom 500 response; raw exception text may contain secrets | Catch unexpected errors inside the ASGI wrapper and log only safe metadata. Tests inject a fake secret before/after response headers and inspect logs/traceback output |
| A failed benchmark can leave an old success report visible | Aborting during setup or midway through a matrix must not silently preserve a successful README result | Write explicit failed/partial artifacts, including empty sample sets, and replace the marked README block. A failure-injection unit test verifies this behavior |
| More clients increased tail latency without increasing throughput | Actual measurements showed higher p95 with 32 clients than with 8 for the recorded transfer workloads | Preserve all samples and compare contention scenarios. Document the observed limit; do not increase pool size blindly or turn off integrity checks |
| The new-key path performed an unnecessary SQL read | Profiling recorded 700 cursor operations for 100 transfers, including a SELECT immediately after a successful reservation INSERT | Use `INSERT … RETURNING` for a new reservation, whose uncommitted unique key is already owned. Existing keys retain a locked SELECT. The original profile is archived; the 22 October run observes 600 cursor executions per 100 transfers, with the full correctness suite passing |
| Faster SQL does not prove faster HTTP | The baseline cursor plan took 0.016 ms versus 0.274 ms for offset at depth 1000, while HTTP history timings stayed close | Keep plan, profiled-service and HTTP results separate. Attribute no 17× end-to-end speedup to those isolated plan observations |
| Development tooling was unavailable inside the coding sandbox | PyPI DNS failed initially; Docker socket and localhost TCP access were denied. Commands launched from the home directory also could not find project configuration | Install dependencies/run PostgreSQL checks from the developer's terminal inside LedgerX. A local verification script stores inspectable results and manages its own temporary API |

### Debugging a stale-balance race

The regression scenario is deliberately specific. Session A loads an account with 10000 cents.
Session B debits that account and commits. Session A then attempts another payment. A database lock
must protect a funds check against the **new** committed balance; inspecting an old Python object
would defeat that intention. The fix refreshes ORM state as part of the locking SELECT, and the
test asserts both the domain refusal and the unchanged final balance.

This combines an application-layer concern (identity-map state) with a database-layer concern
(row serialization). Merely adding `FOR UPDATE` is not a complete explanation of the fix.

### Optimizing one round trip without weakening accounting

The original new-key flow inserted the reservation, selected it with a lock, locked the accounts,
inserted the transfer, updated balances, inserted entries and completed the reservation. The profile
recorded seven cursor-execute operations per service transfer; batched row writes count as one
cursor operation here, not as one row or necessarily one protocol packet.

The revised insertion returns the ORM reservation directly. Its uncommitted unique-index entry
already makes competing insertions wait for commit/rollback, so a second SELECT adds no protection
for that newly created row. On conflict, no row is returned and the locked SELECT remains necessary
to read the winner using the next READ COMMITTED snapshot. The surrounding transaction and all
accounting constraints remain intact.

The measurable structural target is one fewer cursor operation per new keyed transfer. Any claim
about HTTP latency or throughput needs the separate recorded run, accounting checks and environment
caveats; subtracting SQL operations does not automatically establish a percentage speedup.

### Explaining this work in an interview

Use an evidence-backed sequence: invariant → minimal reproduction or design risk → observation →
correction → regression check → remaining limit. The failure tests deliberately simulate errors;
they are not stories about an actual outage. The [French interview notes](INTERVIEW_NOTES.md)
provide examples. Explain the decisions, reproduce the tests and distinguish measurements from
assumptions about performance.

## 15. Docker, deployment and limits

### What the measured capacity actually means

These are **22 October observations**, not hard user limits. A benchmark client repeatedly issues
requests; a signed-in person may spend most of their time reading a screen. Registered accounts,
active sessions, in-flight HTTP requests and simultaneous database transactions are different counts.

| Dimension | Observed/configured value | Interpretation and limitation |
|---|---|---|
| Closed-loop HTTP clients tested | 1, 8 and 32 | Maximum sustainable concurrency is unknown; the separate fixed-arrival generator caps in-flight work at 128 |
| Independent transfers, 8 clients | Median 459.7 req/s; median p95 20.65 ms | Three short local runs; excludes login/setup; not a sustained-load SLO |
| Independent transfers, 32 clients | Median 403.4 req/s; median p95 112.25 ms | More concurrency already increases queuing without increasing throughput |
| Shared-source transfers, 32 clients | Median 304.1 req/s; median p95 136.19 ms | One source's row lock serializes spending; no promise of parallel writes to that balance |
| API SQL connection pool | 10 persistent + up to 10 overflow per process | At most 20 checked-out connections per configured process; other requests may wait |
| PostgreSQL connection setting observed | 100 | Shared across API, test/admin connections and reserved slots; not 100 application users |
| Registered users / total accounts | No benchmark-derived ceiling | No dataset or workload currently proves a maximum; do not translate 32 clients into 32 users |
| Lock / SQL / pool waits | 2 s / 10 s / 5 s | Individual bounds, not a guaranteed HTTP deadline |
| Browser request timeout | 20 s | Cancels the browser wait; a server commit can still have happened. Retry the same payment key |
| Token lifetime | 3,600 s by default | Reload removes the in-memory browser session; token expiry is enforced by the API |
| Filesystem free space snapshot | About 180.05 GiB, 20 October 2026 | Shared Mac volume, not reserved database capacity; `artifacts/storage-host.json` |
| PostgreSQL cluster allocation snapshot | About 115.31 MiB | Whole cluster including all databases and WAL; not bytes per transaction or per user |
| Benchmark database snapshot, 22 October | 51.83 MiB; 10 users, 701 accounts, 51,791 transfers, 103,582 entries | Includes database indexes; excludes full cluster/WAL/backups; not a 10,000-customer test |
| Fixed-arrival traffic | All six short 100 req/s cases met the target; 300/600 req/s were not consistently met | Same Mac generates and serves traffic; not a sustained SLO or a maximum-user count |

For illustration only, 100 people each issuing one request every ten seconds create about 10 req/s.
That calculation is an arrival-rate model, **not evidence that the app safely supports 100 users**.
The mix of writes/reads, contention, user behavior, hardware and acceptable p95 all matter.

Disk capacity must budget heap data, indexes, idempotency/token retention, WAL, vacuum headroom,
backups and other Mac files. No reliable “maximum users with this disk” can be computed from the
cluster-size snapshot. The project has neither a retention policy nor a sustained storage-growth test.

### Run locally and share a demonstration

| Option | What someone can use | Cost/account requirements and limits |
|---|---|---|
| Local Mac | Web app at `http://127.0.0.1:8000`; Swagger at `/docs` | No cloud account. Your Mac and PostgreSQL must be running |
| Share the repository | Recipient installs dependencies and runs their own copy | They need Python, Node for the build and PostgreSQL; no live access to your database |
| Screen share / recorded demo | Show the UI, tests and reports | No deployment or public endpoint required; simplest interview demonstration |
| Temporary HTTPS tunnel | Remote browser reaches your running local FastAPI app | Manual remote access/transfers reported on 26 October; subsequent reconciliation passed |
| Hosted application | Public HTTPS endpoint and persistent PostgreSQL | Hosting and operations need planning; not deployed or claimed production-ready |

A temporary tunnel can avoid purchasing a domain or cloud VM. Cloudflare's documented Quick Tunnel
option creates an ephemeral address without an account; it has no uptime guarantee and a limit of
200 in-flight requests. That provider limit says nothing about LedgerX's tested capacity. The opt-in
[sharing helper](docs/SHARING.md) was used for the manually reported remote access and transfers
on 26 October. This observation is separate from the automated browser suite and does not establish
uptime or capacity. Start another session with Docker running:
`bash scripts/share_local.sh`. See [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
Before sharing, protect admin credentials and restrict access to the demonstration. Loopback binding
is deliberate; changing it alone is not a complete deployment.

Docker is optional for coding. The supplied local orchestration provides PostgreSQL 16, the main
API, a test runner and a separate benchmark API. No cloud registration is required.

For the current **Mac-only deployment**, the [local deployment guide](docs/LOCAL_DEPLOYMENT.md)
provides a serial correctness → latency → Docker/browser → backup → app update workflow:

```bash
ENABLE_DEV_FUNDING=true bash scripts/release_local.sh --full-profile
```

The runner preserves existing users/accounts and saves a private `pg_dump` archive before migrating
the personal database. Failed checks stop the release; it never restores over the ledger
automatically. The archive check is not a completed restore test. After a successful release, use
`docker compose start db app` and open `http://127.0.0.1:8000`. No new administrator is needed.
The runner passed its real Docker execution on 22 October, in addition to simulated failure-path
and SIGINT cleanup tests. No profiling is needed to start the already verified app day to day.

```bash
# Manual setup alternative; use the release runner above when updating existing data:
ENABLE_DEV_FUNDING=true docker compose up --build -d --wait app
# Only for a database that does not already have an administrator:
docker compose exec app python -m app.cli create-admin

# Lint, PostgreSQL suite, migration round trip and real HTTP E2E:
bash scripts/verify.sh

# Also run the full benchmark and profiling; update this README with actual stats:
bash scripts/verify.sh --benchmark
```

Main API binds to localhost:8000, benchmark API to localhost:8001, PostgreSQL to localhost:5432.
Funding is disabled by default for the main API; the benchmark API explicitly enables fictitious
funding and uses only `ledgerx_bench`. Integration tests use only `ledgerx_test`.
Run the test/migration pipeline serially; it deliberately clears disposable test data.

Database files are bind-mounted inside `.runtime/postgres`, caches/temp examples use `.runtime`,
and reports use `artifacts`. Docker's own engine/VM storage is managed by Docker itself.
An older configuration used a named volume; this change does not delete or automatically migrate it.

The runtime image runs as a non-root user. A test image includes tooling. Startup migrates then
runs one Uvicorn worker. A multi-replica deployment should move migrations into a single controlled
job and configure total database connections and multiprocess metrics explicitly.

Local HTTP and database traffic are unencrypted on loopback/the Compose network. A deployed system
requires TLS, managed secrets, isolated database networking, robust abuse protection and
least-privilege database roles. Those requirements are not satisfied merely by having a Dockerfile.

Remaining product/operational limits:

- Fictitious EUR funding only; no bank settlement, FX, fees or card integrations.
- No partial refunds, scheduled payments or approval workflow.
- No password recovery, MFA, refresh tokens, shared rate limiting or expired-token cleanup.
- No idempotency-key retention policy; account creation itself is not idempotent.
- The incremental projection adds row updates/WAL; measured latency results do not establish a sustained capacity limit.
- Funding and shared-source transfers serialize on their account locks.
- No outbox, durable notifications, backup/restore validation or disaster recovery evidence.
- No application deadlock retry, whole-request deadline or proven capacity target.

The incremental projection and independent reconciliation are verified on PostgreSQL in schema
`0004`; short-run latency evidence and load limitations are published above. Further changes
should follow those results. External notifications would justify a transactional outbox and idempotent consumer;
that extension is not implemented.

See [French interview preparation](INTERVIEW_NOTES.md) for the presentation narrative and
[engineering report](docs/ENGINEERING_REPORT.md) for fixes, evidence and remaining work.

## 16. React workspace and frontend decisions

![LedgerX desktop workspace, using explicitly synthetic browser-test fixtures](artifacts/frontend-desktop-dashboard.png)

The screenshot is a captured browser test with synthetic fixtures, not real customer money or a
prepopulated application. Fresh profiles start empty. The [login screenshot](artifacts/frontend-desktop-login.png)
and [mobile screenshot](artifacts/frontend-mobile-dashboard.png) show the responsive layouts.

### Features and honest scope

| Screen | Implemented behavior |
|---|---|
| Sign in / create profile | Username/password forms, validation, API errors, normal-user signup |
| Overview | Selected account's exact balance; seven-day activity bars from loaded entries; incoming/outgoing totals explicitly scoped to loaded activity |
| My accounts | Owner-filtered pagination, EUR account creation, account ID for receiving, exact balance, creation date |
| Send money | Source from owned accounts; destination UUID or another loaded account; decimal-to-cents validation; review before submission |
| Payment receipt | Persisted transaction ID returned by the backend, copy action, refresh of accounts/history |
| Activity | Cursor pagination, incoming/outgoing filters, payment details fetched on demand |
| Refund | Original recipient returns the full amount with a reason; the backend checks funds, ownership and duplicate compensation |
| Operations | Administrator-triggered independent reconciliation with counts and discrepancy sample; no balance repair |
| Demo funding | Administrator and feature flag required; applies to the selected owned account |

No placeholder card controls, fabricated merchants, fake balances or external bank connections are
presented as functioning features. The visual card on the sign-in screen is decorative branding,
not a payment-card product. The UI uses English for interview demonstrations; the walkthrough and
construction PDF are in French.

### Why these frontend technologies

React components separate authentication, the dashboard, activity, reusable dialogs and monetary
actions. TypeScript describes the API boundary and makes money a `bigint`, distinct from strings
and numeric display coordinates. Local state and a small HTTP client are sufficient for this
workspace; a Redux store, SSR framework or second application backend would add complexity to
the current requirements. See the official [React build-tool guidance](https://react.dev/learn/build-a-react-app-from-scratch)
and [Vite guide](https://vite.dev/guide/).

Vite compiles the application into `app/web/index.html` and hashed `/assets` files. FastAPI serves
these on the same origin as the API, so there is no production CORS configuration or frontend
Node server. Vite's development server proxies API paths to port 8000. Docker now includes a Node
build stage and copies the resulting assets into the Python runtime. The schema `0004` production
image passed all 12 browser cases, including two real PostgreSQL journeys, and the local app was
deployed successfully. `bash scripts/verify_web.sh --container` reproduces the isolated container
checks when future changes need validation.

CSS design tokens, responsive grids, authored SVG icons and system fonts produce the visual design.
There are no remotely loaded font/image dependencies or copied product templates. Native dialogs
provide modal focus behavior; visible labels, skip navigation, reduced-motion styles and keyboard
controls are included. This is not a claim of a complete accessibility audit or WCAG certification.

### Exact money across HTTP

The UI accepts `12.34` or `12,34`, splits the decimal string and computes
`BigInt(whole) * 100n + BigInt(fraction)`. Exponents, grouping, negatives, zero and more than two
decimal places are rejected. No `parseFloat`, floating-point multiplication or silent rounding
participates in a transfer amount.

[`lossless-json`](https://github.com/josdejong/lossless-json) parses JSON integers as BigInt and
serializes BigInt back as JSON number tokens, preserving the existing strict integer API contract.
Formatting divides cents by `100n` and appends the two-digit remainder. A regression test sends
and formats `9007199254740993` cents, above `Number.MAX_SAFE_INTEGER`. The SQL/API maximum remains
`9_000_000_000_000_000_000` cents. Only chart geometry converts a bounded normalized ratio to Number;
the underlying money and labels stay exact.

### Request state, concurrency and retry behavior

```mermaid
stateDiagram-v2
    [*] --> Edit
    Edit --> Review: validate amount and destination
    Review --> Pending: freeze payload + generate request key
    Pending --> Receipt: committed result received
    Pending --> Uncertain: timeout / network loss / 5xx
    Uncertain --> Pending: retry identical key and payload
    Pending --> Rejected: definite 4xx business rejection
    Rejected --> Edit: correct request
    Receipt --> [*]
```

`PaymentIntent` owns a serialized immutable payload and one cryptographically random request key.
Buttons disable while a submission is pending; a synchronous ref also guards duplicate click
handlers before the next render. The server remains the authority for atomicity and funds.
There is no automatic money retry. After an ambiguous failure, editing is disabled and the UI
offers a retry with the same intent. A tab-close warning and explicit close confirmation explain
that reloading discards the in-memory intent. A refreshed balance/history must be checked before
starting a different request if that intent was lost.

Twenty seconds is a browser response timeout, not a server rollback guarantee. Authentication
expiry and logout clear the UI; a reload signs out because tokens are held in memory only.
Neither bearer tokens nor monetary intents are persisted in local/session storage. The API
rechecks token activity/role for each authenticated request. Memory-only tokens reduce persistence
exposure but do not eliminate XSS risks or provide cross-tab continuity.

History loads guard against stale asynchronous completions when the selected account changes.
Account/history pages are bounded; the account list fetches 50 rows, with explicit load-more, and
history fetches 20 per page. The current history implementation refetches the displayed prefix
when extending it, prioritizing simple consistency of the loaded sequence over infinite-scroll
cache complexity. No whole-history snapshot is promised across HTTP requests. Manual refresh is
provided; no polling, WebSocket or optimistic balance mutation is used.

UI capabilities from `/auth/me` control which admin actions are shown; these flags are conveniences,
not authorization. The existing dependencies enforce the same rules on the server. `/accounts`
applies the owner predicate before UUID keyset pagination, excludes the system account and returns
`next_after`. A newly created UUID may fall before an existing cursor; refresh restarts the list.
The owner index and primary key already exist. No new financial schema migration was needed.

### Browser security and verification

The compiled HTML is served with a restrictive Content Security Policy, frame denial, no-referrer
and no-store headers. There are no inline executable scripts in the production build. React
escapes text; API errors never echo passwords. Browser features used for random keys and clipboard
require modern browsers; open on localhost or HTTPS. Arbitrary LAN HTTP is not supported.

```bash
bash scripts/frontend.sh check       # formatting, 26 unit tests, type checking and build
bash scripts/frontend.sh browsers    # first-time Chromium installation under .runtime
bash scripts/verify_web.sh           # controlled desktop/mobile cases + real PostgreSQL journey
```

The controlled browser scenarios verify empty profiles, account creation, exact balances,
memory-only sessions, refunds, admin capabilities and retry after a simulated lost response **after
the fixture commits the payment**. They assert the same key/body on both requests and one debit.
Fixtures are test code, never bundled with the app. HTTPS fixture URLs exercise the same secure
browser context as a public deployment. The real test performs signup, two account creations,
admin funding, a transfer, a refund, balance checks and reconciliation through a real FastAPI
server and PostgreSQL. It requires the isolated verification runner.

**Verified schema `0004` result, 22 October:** **12/12 browser cases passed in 11.6 seconds**,
with no failures, skips or flaky retries: five desktop fixtures, five mobile fixtures and two real
Docker/PostgreSQL journeys. Earlier insecure fixture origins and a mobile-login race were fixed
without weakening assertions. The second live journey uses two independent customers, transfers,
a refund and reconciliation. Current reports are archived under
`artifacts/releases/2026-10-22-projection/`; the older `0003` release remains separate.

### Installation scripts, not vendored dependencies

| Command | Purpose / files affected |
|---|---|
| `setup_frontend.sh` | Downloads Node 24 from nodejs.org, verifies the published SHA-256 and extracts under `.runtime/tools/node` |
| `frontend.sh install` | Uses `npm ci` with `frontend/package-lock.json`; packages under `frontend/node_modules`, cache under `.runtime/cache/npm` |
| `frontend.sh build` | Type checks and generates `app/web`; no API process started |
| `frontend.sh dev` | Starts loopback Vite development server with proxy to FastAPI |
| `frontend.sh browsers` | Installs test Chromium under `.runtime/browsers` |
| `verify_web.sh` | Uses only PostgreSQL `_bench`, owns a temporary API process on port 8002, runs tests, then stops that process |
| `run_local.sh` | Applies migrations to the configured application database, then serves UI/API on loopback port 8000 |

The first setup resolves the latest Node 24 patch; subsequent calls keep the project-local runtime.
Checksums come over HTTPS from the same publisher; they detect corruption but are not a detached
signature trust chain. CI and Docker select the Node 24 series, while npm dependencies are locked.
No script installs global npm packages, edits shell profiles or needs a cloud account. Keep scripts,
lockfiles and source code in the repository; exclude caches, credentials, node_modules and generated
build output. The directory restriction concerns project writes; Docker manages its own existing VM.

## 17. Scaling the project: future AWS investment

Ten thousand registered customers do not imply ten thousand simultaneous requests. Their profile
and account rows are a modest dataset; transaction history, indexes, concurrency, retained tokens,
logs and backups determine the practical resource requirement. No AWS capacity has been tested.
The local 1/8/32-client experiments cannot be converted into an AWS maximum-user guarantee.

### An always-running AWS budget

Planning date: **21 October 2026**. Region assumption: **Europe/Frankfurt**. Prices below use
**AWS Lightsail Linux plans with public IPv4**, which include SSD and transfer allowances. These
are AWS virtual servers suitable for the existing Docker deployment, not Lambda functions. The
application remains running between requests. Monthly planning assumes continuous operation
(approximately 730 hours), no free-tier credits or long-term commitment, and USD before tax.

| Stage | Infrastructure and official base charge/month | Planning budget/month | What the investment buys |
|---|---|---:|---|
| Public portfolio demo | One 2-vCPU / 4-GB / 80-GB instance: **$24**; app and PostgreSQL together | **$30–40** | Simple deployment; a starting point for a 10,000-profile fixture and load tests |
| More database cache | One 2-vCPU / 8-GB / 160-GB instance: **$44** | **$50–65** | More RAM/cache/storage; not twice as many CPU cores or a promised throughput multiplier |
| More compute and memory | One 4-vCPU / 16-GB / 320-GB instance: **$84** | **$95–120** | More headroom; evaluate extra API workers only after measuring CPU/pool/lock limits |
| Separate managed database | 4-GB app instance **$24** + encrypted 4-GB / 120-GB managed PostgreSQL **$60** | **$95–115** | App/DB resource separation and managed database operations; one app remains a failure point |
| Redundant application and database | Two 4-GB app instances **$48** + load balancer **$18** + 4-GB managed PostgreSQL HA **$120** | **$200–240** | Redundancy and failover; not a guarantee of more write throughput or zero downtime |

Base charges come from [AWS Lightsail pricing](https://aws.amazon.com/lightsail/pricing/).
Planning ranges are our estimates: a small allowance for snapshots/logs, not AWS quotes or billing
caps. They exclude domain registration, taxes, premium support and transfer/storage overages. Snapshot
cost depends on retained data, not just the provisioned disk size. Recheck the regional console
before purchasing; no AWS resource or account has been created for this project.

The smaller general-purpose instances are burstable. A short benchmark can consume accumulated
CPU credit and overstate sustainable performance. Run a sustained load test and monitor credits,
CPU, memory and disk before sizing for continuous traffic. For sustained high CPU, compare an
appropriately sized non-burstable EC2 configuration rather than assuming a bigger burst plan solves
every bottleneck. See [AWS CPU baseline guidance](https://docs.aws.amazon.com/lightsail/latest/userguide/baseline-cpu-performance.html).

Managed database HA keeps a standby in another Availability Zone for failover; the standby is not
an extra writer that doubles transfer capacity. See [AWS database HA](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-high-availability-databases.html).
Lightsail offers PostgreSQL 16; select that version family until other versions have been tested.
See [supported database engines](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-choosing-a-database.html).

### Determine concurrency from workload, not account count

| Usage assumption | Offered traffic | Interpretation |
|---|---:|---|
| 10,000 registered profiles, nobody using the site | Approximately zero customer requests/s | Stored profiles do not continuously consume an API worker |
| 100 active visitors, one HTTP request every 10 seconds each | 10 requests/s | Arithmetic scenario, not a measured capacity |
| 1,000 active visitors at the same rate | 100 requests/s | Reads, transfers and login hashing have different costs |
| 10,000 active visitors at the same rate | 1,000 requests/s | Must be load-tested; not certified by the current local results |
| 1,000 requests arriving at once | A burst of 1,000 requests | Requires queue/admission control; not equivalent to 1,000 registered users |

These examples count HTTP requests, not UI clicks: one click may trigger several API calls. Before
claiming capacity, create 10,000 synthetic customer profiles in an isolated environment, seed a
representative journal, run 8/32/64/128 concurrent-request stages plus fixed-arrival load and a soak
test. Agree on a latency/error objective, for example p95 below 200 ms and less than 0.1% unexpected
responses; these are proposed acceptance criteria, not achieved service guarantees. Record the
largest sustained rate that meets them and preserves exact balances/reconciliation.

### What to optimize or buy next

| Observed bottleneck or risk | Next action | Expected benefit / boundary |
|---|---|---|
| Write validation grows with account history | Monitor the verified `0004` incremental projection and reconciliation | Remove repeated historical sums; measure the additional update/WAL trade-off |
| Deep history reads | Keep composite indexes and cursor pagination; inspect query plans | Avoid scanning skipped rows; not a reason to cache financial balances outside PostgreSQL |
| Database disk/cache pressure | Measure relation/index sizes and I/O; add RAM or storage where needed | Size for the retained journal, not just customer profiles |
| API CPU saturation | Profile; evaluate extra workers/instances | Share authentication limits, collect multiprocess metrics and cap total DB connections first |
| Database connection wait | Tune the sum of all worker pools against the database budget | A thousand users do not need a thousand database connections |
| Many debits from one account | Preserve ordered locking; bound admission/queues | Extra API replicas cannot parallelize conflicting writes to the same balance |
| Risk of losing data | Automate backups and test restore to a separate database | Recovery capability; snapshots alone are not a restore test |
| Need for maintenance/failure continuity | Separate DB, then redundant app and DB failover | Availability investment, distinct from a latency optimization |

For journal growth, suppose 10,000 customers each initiate one transfer per day: **3.65 million
transfers and 7.3 million journal entries per year**, before funding/refunds. At a hypothetical
**1–3 KiB per complete transfer footprint**, that is approximately **3.5–10.4 GiB/year** before WAL,
backups and extra bloat. This size-per-transfer range is an explicit planning assumption, not a
LedgerX measurement. Measure `pg_total_relation_size`, row counts and growth under representative
data before choosing retention or storage. Ten transfers per day multiplies those figures by ten.

For this portfolio, start with the first tier and retain an explicit budget alert. Upgrade only
after observing the limiting resource. The current code uses one API process; the multiple-instance
tiers above describe future engineering work, not a configuration already delivered or validated.
