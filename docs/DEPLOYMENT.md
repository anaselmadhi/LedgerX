# Publish the LedgerX portfolio demo

The current requested target is **local Docker on the Mac, without cloud hosting**. Follow
[LOCAL_DEPLOYMENT.md](LOCAL_DEPLOYMENT.md) for that workflow. The provider steps below are an
optional future path; the local release does not execute them or create cloud resources.

This guide prepares a public demonstration with fictitious EUR. No public deployment has been
created or tested yet. Existing local users and balances are not uploaded by these steps.

## 1. Complete the release checks locally

From the LedgerX directory, with Docker Desktop running:

```bash
bash scripts/verify_local.sh
bash scripts/verify_web.sh --container
```

The second command builds the `production` Docker target and serves it on loopback port 8002.
It uses `ledgerx_bench`, provisions the isolated benchmark administrator, runs read-only smoke
checks, then runs the desktop/mobile fixtures and two live browser journeys. The second live
journey creates two different customers, transfers money between their browser sessions, refunds
it and checks reconciliation. These test records remain in the disposable benchmark database.
The runner stops its temporary API container on exit; it does not stop the personal app or remove
database volumes. Do not run benchmark/browser verification concurrently against that database.

Evidence is written to `artifacts/web-verification.log`, `artifacts/web-container-api.log` and
`artifacts/frontend-browser-results.json`. The schema `0004` release passed all 149 backend tests
and 12 browser cases against the production Docker target on 22 October 2026. It also completed
latency measurements and the personal local deployment. Results are archived under
`artifacts/releases/2026-10-22-projection/`; see [LATENCY_RESULTS.md](LATENCY_RESULTS.md).
These local results do not establish a public deployment or a remote CI run.

## 2. Publish the existing project to GitHub

The supplied GitHub username is `anaselmadhi`; no repository URL or authenticated GitHub connection
has been confirmed. Create a repository for the existing local project and review the files before
pushing. An initial commit can accurately say **Import LedgerX developed locally**. Keep future
fixes and enhancements in focused branches/PRs, with actual validation results and normal dates.

Commit source, migrations, lockfiles, configuration examples and curated documentation/evidence.
Exclude `.env*` except `.env.example`, `.runtime`, `.venv`, `node_modules`, temporary browser files,
database storage, secrets and unreviewed logs. These exclusions are in `.gitignore`; inspect any
additional generated artifacts before publishing. Neither an admin password nor a hosted database
URL belongs in a commit, issue or PR. The PR template is `.github/pull_request_template.md`.

## 3. Create a dedicated PostgreSQL database

Create a Neon account and a **separate project for this public demo**, ideally in the region nearest
the Render service. Select PostgreSQL 16 to match the database version family exercised locally.
Use its **direct connection URL**, without the `-pooler` hostname, and retain TLS parameters such as
`sslmode=require`. LedgerX accepts `postgresql://`, `postgres://` and `postgresql+psycopg://`; the
first two are normalized to the installed psycopg 3 driver.

Use this URL only in the provider's secret settings or the hidden terminal prompt described below.
Do not put it in `.env.example` or replace the local demo database. The direct connection keeps
startup migrations and connection-level PostgreSQL timeouts predictable. The app has its own
small SQLAlchemy pool, configured here for at most five database connections per process.
See [Neon connection guidance](https://neon.com/docs/guides/sqlalchemy) and
[pooling behavior](https://neon.com/docs/connect/connection-pooling).

## 4. Create the Render service

Create a Render account and connect the GitHub repository. Use **New → Blueprint**, select the
repository and review `render.yaml`. It defines one Docker web service on the **Free** plan in
Frankfurt; it does not provision a paid service or a Render database. Provide `DATABASE_URL` when
the Blueprint asks for the secret. Review the resource/plan before creating it.

The configuration deliberately disables automatic deployment on pushes. Deploy manually after
the relevant CI checks pass. The provider supplies `PORT`; the application reads it, applies Alembic
migrations, then starts one Uvicorn process. If migration fails, the API does not start. The default
Docker stage is the application, not the test runner. Runtime Python dependencies now come from
`uv.lock`; the base OS/Python image tags remain mutable, so bit-for-bit image reproducibility is not
claimed. See [Docker deployment](https://render.com/docs/docker),
[Blueprint fields](https://render.com/docs/blueprint-spec) and
[port binding](https://render.com/docs/web-services).

`PUBLIC_DEMO=true` rejects local/default database credentials, unencrypted database configuration
and the Neon pooled endpoint in the container startup check. `sslmode=require` requests encryption;
it does not, on its own, establish full CA/hostname verification. A stricter TLS policy requires
configuring `verify-full` and the appropriate trusted root certificates.

The platform health check uses `/health/live`, which does not query PostgreSQL on every probe.
The `/health` endpoint checks database access and migration revision and is included in release
smoke checks. A live process can still have an unavailable database; these are different checks.

## 5. Create your remote administrator

Render Free does not provide interactive shell access. From your Mac, run:

```bash
.venv/bin/python -m scripts.create_remote_admin
```

The script prompts invisibly for the **remote direct PostgreSQL URL**, then asks for an administrator
username and password. It never saves the URL or rewrites `.env`. Migrations must already have
succeeded on Render. The new administrator belongs to the remote database, independently of local
administrator. Using the same username in two databases does not synchronize them.

This is an intentional remote write: it creates one administrator. The script does not grant roles
to an existing username or overwrite its password. Keep the database URL private. See
[Render Free limitations](https://render.com/docs/free).

## 6. Verify the deployed application

Replace the example hostname with the URL Render actually assigns:

```bash
.venv/bin/python -m scripts.smoke_public --url https://YOUR-SERVICE.onrender.com
```

This command only reads health, UI/assets and protected endpoints without authentication. It does
not create accounts, send money or run the destructive isolated test suite against the public DB.
It checks that unauthenticated access is rejected. Then manually verify login, a new customer
profile, account creation and the funded transfer/refund scenario before sharing the link.

Demo funding is **off** in the Blueprint. To seed fictitious money, temporarily enable
`ENABLE_DEV_FUNDING=true` in Render, deploy, sign in as your administrator and use **Add demo funds**
on an owned account. You can transfer those funds to demo customers. Disable funding again if no
further issuance is needed. Both settings still require administrator authorization; public signup
never creates an administrator.

## 7. Understand the limits before presenting

| Area | Current behavior |
|---|---|
| Auth admission | Login and signup share a 60-second sliding window: 10 accepted attempts per ASGI peer, 120 globally and two in-flight requests per process by default |
| Auth rejection | HTTP 429 with `Retry-After`; credentials are not verified and no username/password/token is retained by the limiter |
| Proxy trust | Container and local runner disable forwarded-header processing. Visitors behind a proxy/NAT can share one peer budget; this is conservative and can restrict legitimate shared traffic |
| Rate-limit scope | Thread-safe, bounded, in-memory state; reset on restart, not shared between replicas; not per-user lockout or complete abuse/DDoS protection |
| Database | Independent hosted database; five SQL connections maximum per application process in the Blueprint |
| Deployment | One process/instance; migrations at startup. Multiple concurrent deployers require a controlled migration job |
| Recovery | Immutable journal and atomic transactions remain; external backup/restore and incident recovery are not validated |
| Availability | Free hosting can sleep, suspend at quotas or restart; no production availability claim |

The limiter uses a deque of accepted attempt timestamps and per-peer counters protected by a
Python `Lock`. Each accepted event expires once, giving amortized constant work for pruning; a
throttled peer's retry estimate may scan at most the configured global window budget. The critical
section reserves/releases slots only: password hashing and SQL execute outside the lock. This
process-local lock protects an in-memory counter, while financial consistency remains enforced by
PostgreSQL transactions and row locks across workers.

An operator may configure trusted proxy handling after verifying the provider's network and
forwarded-header guarantees. Do not accept arbitrary `X-Forwarded-For` or trust all sources just
to obtain separate client quotas. For multiple replicas, use shared rate control or enforcement at
the trusted ingress. See [Uvicorn proxy settings](https://uvicorn.dev/settings/).

At the time of preparation, Render Free sleeps after 15 idle minutes; Neon Free advertises 1 GB per
project and 100 CU-hours/month. These are provider quotas, not measured LedgerX user capacity.
Render's free Postgres expires after 30 days, which is why this guide uses an independent Neon DB.
Review [Render limits](https://render.com/docs/free), [billing rules](https://render.com/docs/faq)
and [Neon pricing](https://neon.com/pricing) when creating the resources. No cloud account has been
created by the coding agent, and the new configuration still needs its first deployed verification.
