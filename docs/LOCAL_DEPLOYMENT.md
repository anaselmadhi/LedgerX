# Run and update LedgerX on your Mac

This is the current deployment target: Docker Desktop on your Mac, with the React UI and FastAPI
served together at **http://127.0.0.1:8000**, and PostgreSQL stored in `.runtime/postgres`.
It requires no cloud account. Your existing administrator, customer profiles and financial accounts
belong to that database and survive an application-container rebuild.

## Validate, measure, back up, then launch

Open Docker Desktop. From the LedgerX directory, run one command:

```bash
ENABLE_DEV_FUNDING=true bash scripts/release_local.sh --full-profile
```

The explicit funding flag lets an authenticated administrator issue fictitious EUR in the UI.
Omit it if funding should remain disabled. The command uses the existing project-local Python,
Node and browser dependencies; it does not install software globally. Docker may download build
images and locked dependencies. It performs the following steps serially:

1. Start the local PostgreSQL container; run lint, unit/integration tests, migration round trips
   and real HTTP tests against the isolated `_test` and `_bench` databases.
2. Run the latency matrix, service/commit profiling and fixed-arrival HTTP experiments. Reports go
   to `artifacts/latency/`; the archived baseline stays intact.
3. Build the production Docker target and run its browser journeys on `ledgerx_bench`.
4. Build the personal application image while its previous container can still serve requests.
5. Stop the personal app, save `ledgerx` with `pg_dump`, inspect the archive with `pg_restore --list`
   and record a SHA-256 digest. Private backup files stay under `.runtime/backups/`.
6. Start the new app, apply its transactional migrations and check the exact expected schema,
   compiled UI/assets and unauthenticated access restrictions.

Open **http://127.0.0.1:8000** only after the final `PASS`. Use your existing login. Creating an
administrator again is unnecessary. For a brand-new database only, provision one interactively:

```bash
docker compose exec app python -m app.cli create-admin
```

Without `--full-profile`, the runner uses the shorter latency smoke experiment. That mode checks
the pipeline; use the full repeated experiment for presentation results. Even a completed load
experiment can have unmet traffic targets: inspect drops, errors and `target_met` before making
performance claims. A successful release is not a latency/SLO guarantee.

The runner rejects remote Docker contexts and database/Compose overrides, pins this project's
Compose file and prevents two release runners from running together. Do not run standalone
benchmark/browser/migration scripts concurrently against their shared disposable databases.
Stop other local API processes using ports 8000–8003 first. A quiet Mac gives more comparable
performance measurements.

## Everyday use after a verified release

Keep Docker Desktop running, then start the existing containers:

```bash
docker compose start db app
```

Open the same localhost address. No terminal administrator login is required to keep the server
running; users sign in through the web interface. The frontend keeps sessions in memory, so a page
reload requires signing in again.

```bash
# See container readiness or diagnose a startup problem:
docker compose ps
docker compose logs --tail=100 app

# Stop the application and database without deleting their data:
docker compose stop app db
```

The app and database use `restart: unless-stopped`: Docker can restart them after a daemon restart
unless you explicitly stopped them. This does not keep a sleeping or powered-off Mac available.
See [Docker restart policy](https://docs.docker.com/reference/compose-file/services/#restart).

## Failure and recovery behavior

| Failure | Runner behavior |
|---|---|
| Correctness, latency accounting, browser or build failure | Stop the release before stopping/migrating the personal app |
| Backup failure | Remove the incomplete archive; restart the previous app container if it was running; no new migration |
| New app fails migration/readiness/smoke checks | Stop the new app; retain the database and completed backup; no automatic restore/downgrade |
| Second release starts | Refuse while `.runtime/local-release.lock` exists |
| One Ctrl+C interrupts verification | Stop the release and remove its lock; do not proceed to migration |

Read `artifacts/local-release.log` and the failing stage's report. A backup contains private user
data, password hashes and token hashes; `.runtime` is excluded from Git and Docker build context.
Its files are created with owner-only permissions. A digest plus a readable archive is **not a
successful restore test**. Restoring to a separate database and verifying reconciliation remains
required before claiming recovery readiness. A backup on the same disk does not protect against
losing that disk. See [PostgreSQL backup documentation](https://www.postgresql.org/docs/16/app-pgdump.html).

The runner never deletes database volumes or restores over your personal database. If it is killed
forcibly and leaves its lock directory, first confirm no release process is running before removing
that empty directory. A normal success, error or handled interruption cleans up the lock.
The logging reader ignores Ctrl+C long enough for cleanup to finish. Cleanup also tolerates a
closed logging pipe. A regression test interrupts an isolated process group with SIGINT and checks
that the lock disappears and no personal database update starts.

## Sharing without cloud hosting

The app and database ports remain bound to loopback. The optional
[sharing guide](SHARING.md) uses a separate temporary HTTPS connector:

```bash
bash scripts/share_local.sh
```

Docker must be running. Send the printed `https://...trycloudflare.com` address to your friend,
who registers their own customer login in the UI. Keep the Mac awake and the sharing terminal open;
Ctrl+C ends the tunnel. No cloud account or global install is required. On 26 October the helper
passed its API check and the Cloudflare connector registered; its network prechecks passed. The
owner subsequently reported successful remote access and transfers from a friend's computer,
followed by a clean administrator reconciliation; see [the manual evidence](SHARING.md#verification-boundary).
A stopped Docker engine does not mean your app or data disappeared, and does not require
rerunning the full release.

## Verification status

The complete host-terminal release passed on **22 October 2026, schema 0004**: 149 backend tests,
26 frontend tests, 12 browser cases, migration round trip and ORM drift checks. The production
Docker target was built, the personal database was backed up and migrated, and the updated app
passed schema/UI/auth checks. Results are archived under
`artifacts/releases/2026-10-22-projection/`; see [the measured results](LATENCY_RESULTS.md).

The first attempt stopped on a fault-injection cleanup error before updating the personal app.
That error is fixed and the complete rerun passed. Release failure-injection tests separately
exercise simulated Docker failures and SIGINT cleanup. A saved and readable backup archive has
not yet been restored into a separate database. Temporary remote access has been reported manually;
cloud hosting remains unexecuted. The owner-supplied GitHub Actions run #1 summary reports both
jobs passed at `d65fb3c`; see the [CI evidence](../artifacts/ci/initial-run-summary.json).
