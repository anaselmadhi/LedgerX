"""Profile the synchronous service + real PostgreSQL; distinct from HTTP latency."""

import argparse
import cProfile
import io
import json
import os
import platform
import pstats
import resource
import shutil
import sys
from collections import defaultdict
from datetime import UTC, datetime
from time import perf_counter

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db.models import SYSTEM_ACCOUNT_ID, Account
from app.db.session import create_db_engine
from app.schemas.transfer import TransferCreate
from app.services.account_service import create_account
from app.services.reconciliation_service import reconcile
from app.services.transfer_service import transfer_money
from scripts.benchmark import ROOT, output_directory, percentile, source_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-sizes", type=int, nargs="+", default=[0, 100, 1000])
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()
    if args.samples < 1 or min(args.history_sizes) < 0 or args.repeats < 1:
        parser.error("samples/repeats must be positive and history sizes nonnegative")
    url = os.environ.get("PROFILE_DATABASE_URL", "")
    parsed = make_url(url) if url else None
    if (
        parsed is None
        or parsed.get_backend_name() != "postgresql"
        or not (parsed.database or "").endswith("_bench")
    ):
        parser.error("Set PROFILE_DATABASE_URL to an isolated PostgreSQL database ending in _bench")
    output = output_directory(args.output)
    engine = create_db_engine(url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "source_sha256": source_digest(),
        "kind": "service + PostgreSQL, cProfile enabled; no HTTP",
        "config": vars(args),
        "runs": [],
    }
    sql_times = defaultdict(list)
    measuring = False

    @event.listens_for(engine, "before_cursor_execute")
    def before_sql(connection, cursor, statement, parameters, context, executemany):
        if measuring:
            context.profile_started = perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_sql(connection, cursor, statement, parameters, context, executemany):
        if measuring:
            sql_times[" ".join(statement.split())].append(
                (perf_counter() - context.profile_started) * 1000
            )

    with sessions() as session:
        report["postgresql"] = session.scalar(text("SELECT version()"))
        report["schema"] = session.scalar(text("SELECT version_num FROM alembic_version"))
        report["database_settings"] = dict(
            session.execute(
                text("""
            SELECT name, setting FROM pg_settings WHERE name IN (
                'fsync', 'synchronous_commit', 'shared_buffers', 'max_connections',
                'lock_timeout', 'statement_timeout'
            )
        """)
            ).all()
        )
    for depth, repeat in (
        (depth, repeat) for depth in args.history_sizes for repeat in range(1, args.repeats + 1)
    ):
        with sessions.begin() as session:
            source = create_account(session, "EUR").id
            target = create_account(session, "EUR").id
            transfer_money(
                session,
                TransferCreate(
                    source_account_id=SYSTEM_ACCOUNT_ID,
                    destination_account_id=source,
                    amount=depth + args.samples + 100,
                ),
                funding=True,
            )
        forward = TransferCreate(source_account_id=source, destination_account_id=target, amount=1)
        backward = TransferCreate(source_account_id=target, destination_account_id=source, amount=1)
        for index in range(depth):
            with sessions.begin() as session:
                transfer_money(session, forward if index % 2 == 0 else backward)
        sql_times.clear()
        profile = cProfile.Profile()
        durations = []
        commit_durations = []

        def workload(forward, backward, source, durations, commit_durations):
            for index in range(args.samples):
                started = perf_counter()
                with sessions.begin() as session:
                    transfer_money(
                        session,
                        forward if index % 2 == 0 else backward,
                        f"profile-{source}-{index}",
                    )
                    committing = perf_counter()
                commit_durations.append((perf_counter() - committing) * 1000)
                durations.append((perf_counter() - started) * 1000)

        measuring = True
        try:
            profile.runcall(workload, forward, backward, source, durations, commit_durations)
        finally:
            measuring = False
        suffix = f"-run-{repeat}" if args.repeats > 1 else ""
        profile.dump_stats(str(output / f"profile-depth-{depth}{suffix}.prof"))
        stream = io.StringIO()
        pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(30)
        (output / f"profile-depth-{depth}{suffix}.txt").write_text(stream.getvalue())
        offset = max(0, depth + args.samples - 25)
        with sessions() as session:
            expected_movement = depth % 2 + args.samples % 2
            expected_source = depth + args.samples + 100 - expected_movement
            if (
                session.get(Account, source).balance != expected_source
                or session.get(Account, target).balance != expected_movement
            ):
                raise RuntimeError("Profiling workload produced incorrect balances")
            audit = reconcile(session)
            if not audit.consistent:
                raise RuntimeError("Profiling workload failed reconciliation")
            session.execute(text("ANALYZE ledger_entries"))
            position = session.execute(
                text("""
                SELECT created_at, id FROM ledger_entries WHERE account_id = :account
                ORDER BY created_at DESC, id DESC LIMIT 1 OFFSET :offset
            """),
                {"account": source, "offset": max(0, offset - 1)},
            ).one()
            plans = {}
            for name, query in (
                (
                    "historical_sum",
                    "SELECT coalesce(sum(amount), 0) FROM ledger_entries "
                    "WHERE account_id = :account",
                ),
                (
                    "projection_lookup",
                    "SELECT balance, ledger_balance FROM accounts WHERE id = :account",
                ),
            ):
                plans[name] = session.scalar(
                    text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"), {"account": source}
                )
            for name, predicate, suffix in (
                ("offset", "", "OFFSET :offset"),
                ("cursor", "AND (created_at, id) < (:created, :entry)" if offset else "", ""),
            ):
                # SQL fragments are fixed constants above, never caller input.
                query = text(f"""
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    SELECT * FROM ledger_entries WHERE account_id = :account {predicate}
                    ORDER BY created_at DESC, id DESC LIMIT 25 {suffix}
                """)
                plans[name] = session.scalar(
                    query,
                    {
                        "account": source,
                        "offset": offset,
                        "created": position[0],
                        "entry": position[1],
                    },
                )
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() != "Darwin":
            rss *= 1024
        run = {
            "prepared_transfer_history": depth,
            "repeat": repeat,
            "initial_history_entries": {"source": depth + 1, "target": depth},
            "reconciliation": audit.model_dump(mode="json"),
            "samples": args.samples,
            "commit_ms": {
                "p50": percentile(commit_durations, 50),
                "p95": percentile(commit_durations, 95),
                "p99": percentile(commit_durations, 99),
            },
            "raw_commit_ms": commit_durations,
            "service_including_commit_ms": {
                "p50": percentile(durations, 50),
                "p95": percentile(durations, 95),
                "p99": percentile(durations, 99),
            },
            "process_peak_rss_bytes_including_setup": rss,
            "sql_execute_excluding_commit": [
                {
                    "statement": statement,
                    "calls": len(values),
                    "total_ms": sum(values),
                    "p95_ms": percentile(values, 95),
                }
                for statement, values in sorted(
                    sql_times.items(), key=lambda item: sum(item[1]), reverse=True
                )
            ],
            "history_query_plans": plans,
            "service_samples_ms": durations,
        }
        report["runs"].append(run)
        print(
            f"Profile depth={depth} run={repeat}: p95={percentile(durations, 95):.2f}ms; "
            f"commit p95={percentile(commit_durations, 95):.2f}ms; "
            f"SQL calls={sum(len(v) for v in sql_times.values())}",
            flush=True,
        )
    # Read-only footprint snapshot after the workload. Never extrapolate user
    # capacity directly from free disk or a short burst benchmark.
    with sessions() as session:
        report["storage"] = {
            "checked_at": datetime.now(UTC).isoformat(),
            "database_bytes": session.scalar(text("SELECT pg_database_size(current_database())")),
            "relations": [
                dict(row)
                for row in session.execute(
                    text("""
                SELECT c.relname AS relation,
                    pg_table_size(c.oid) AS table_bytes,
                    pg_indexes_size(c.oid) AS index_bytes,
                    pg_total_relation_size(c.oid) AS total_bytes
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                ORDER BY c.relname
            """)
                ).mappings()
            ],
            "row_counts": {
                table: session.scalar(text(f"SELECT count(*) FROM {table}"))
                for table in (
                    "users",
                    "auth_tokens",
                    "accounts",
                    "transfers",
                    "ledger_entries",
                    "idempotency_records",
                )
            },
        }
    host_disk = shutil.disk_usage(ROOT)
    report["storage"]["generator_host_filesystem"] = {
        "total_bytes": host_disk.total,
        "used_bytes": host_disk.used,
        "free_bytes": host_disk.free,
        "scope": "shared host filesystem, not dedicated database capacity or container quota",
    }
    engine.dispose()
    (output / "profiling.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
