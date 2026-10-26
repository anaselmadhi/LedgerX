"""Closed-loop HTTP benchmark; setup/warmup and reconciliation are not timed."""

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (
    "balance_read",
    "history_head",
    "history_deep_offset",
    "history_deep_cursor",
    "independent_transfers",
    "shared_source",
    "opposite_directions",
    "idempotent_replay",
    "insufficient_funds",
    "reversals",
)


def percentile(values: list[float], percent: float) -> float:
    """Nearest-rank percentile; no interpolation or invented tail samples."""
    if not values or not 0 < percent <= 100:
        raise ValueError("Nonempty samples and a percentile in (0, 100] are required")
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * percent / 100) - 1]


def source_digest() -> str:
    digest = hashlib.sha256()
    paths = [
        *ROOT.glob("app/**/*.py"),
        *ROOT.glob("alembic/**/*.py"),
        *ROOT.glob("scripts/**/*.py"),
        ROOT / "pyproject.toml",
    ]
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def local_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname
        not in {
            "localhost",
            "127.0.0.1",
            "::1",
            "benchmark-api",
        }
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise argparse.ArgumentTypeError("Use a local demo HTTP URL (localhost or benchmark-api)")
    return value.rstrip("/")


def output_directory(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Artifacts must stay inside the LedgerX directory")
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    body: dict | None = None
    key: str | None = None
    expected_status: int = 201
    expected_id: str | None = None
    movement: tuple[str, str, int] | None = None


@dataclass
class Workload:
    operations: list[Operation]
    balances: dict[str, int] = field(default_factory=dict)


def checked(client: httpx.Client, method: str, path: str, expected: int = 201, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code != expected:
        raise RuntimeError(
            f"Setup/check {method} {path}: {response.status_code} {response.text[:200]}"
        )
    return response.json()


def authenticate_benchmark(client: httpx.Client) -> None:
    password = os.getenv("BENCHMARK_PASSWORD")
    if not password:
        raise RuntimeError("Set BENCHMARK_PASSWORD for the isolated benchmark administrator")
    result = checked(
        client,
        "POST",
        "/auth/login",
        200,
        json={"username": os.getenv("BENCHMARK_USERNAME", "benchmark-admin"), "password": password},
    )
    client.headers["Authorization"] = f"Bearer {result['access_token']}"


def new_account(client: httpx.Client, balances: dict[str, int], amount: int = 0) -> str:
    account = checked(client, "POST", "/accounts", json={})["id"]
    if amount:
        checked(
            client,
            "POST",
            "/dev/funding",
            json={"destination_account_id": account, "amount": amount},
            headers={"Idempotency-Key": str(uuid4())},
        )
    balances[account] = amount
    return account


def transfer_operation(source: str, target: str, key: str | None = None) -> Operation:
    return Operation(
        "POST",
        "/transfers",
        {"source_account_id": source, "destination_account_id": target, "amount": 1},
        key or str(uuid4()),
        movement=(source, target, 1),
    )


def prepare_history(client: httpx.Client, size: int) -> dict[str, str]:
    balances = {}
    source = new_account(client, balances, size + 100)
    target = new_account(client, balances)
    for _ in range(size):
        op = transfer_operation(source, target)
        checked(client, op.method, op.path, json=op.body, headers={"Idempotency-Key": op.key})
    path = f"/accounts/{source}/transactions"
    offset = max(1, size - 25)
    cursor = checked(client, "GET", f"{path}?limit=1&offset={offset - 1}", 200)["next_cursor"]
    if cursor is None:
        raise RuntimeError("History fixture is too small")
    return {
        "history_head": f"{path}?limit=25",
        "history_deep_offset": f"{path}?limit=25&offset={offset}",
        "history_deep_cursor": f"{path}?limit=25&cursor={cursor}",
    }


def prepare(
    client: httpx.Client, name: str, count: int, workers: int, history_paths: dict[str, str]
) -> Workload:
    if name in history_paths:
        return Workload([Operation("GET", history_paths[name], expected_status=200)] * count)
    balances: dict[str, int] = {}
    if name == "balance_read":
        account = new_account(client, balances, 100)
        return Workload(
            [Operation("GET", f"/accounts/{account}/balance", expected_status=200)] * count,
            balances,
        )
    pair_count = workers if name == "independent_transfers" else 1
    pairs = [
        (
            new_account(client, balances, 0 if name == "insufficient_funds" else count + 100),
            new_account(client, balances, count + 100 if name == "opposite_directions" else 0),
        )
        for _ in range(pair_count)
    ]
    operations = []
    replay = None
    if name == "idempotent_replay":
        replay = transfer_operation(*pairs[0])
        result = checked(
            client,
            replay.method,
            replay.path,
            json=replay.body,
            headers={"Idempotency-Key": replay.key},
        )
        balances[pairs[0][0]] -= 1
        balances[pairs[0][1]] += 1
        replay = Operation(
            replay.method, replay.path, replay.body, replay.key, expected_id=result["id"]
        )
    for index in range(count):
        source, target = pairs[index % pair_count]
        if name == "opposite_directions" and index % 2:
            source, target = target, source
        op = transfer_operation(source, target)
        if replay is not None:
            op = replay
        elif name == "insufficient_funds":
            op = Operation(op.method, op.path, op.body, op.key, expected_status=409)
        elif name == "reversals":
            original = checked(
                client, op.method, op.path, json=op.body, headers={"Idempotency-Key": op.key}
            )
            balances[source] -= 1
            balances[target] += 1
            op = Operation(
                "POST",
                f"/transfers/{original['id']}/reversal",
                {"reason": "Benchmark compensation"},
                str(uuid4()),
                movement=(target, source, 1),
            )
        operations.append(op)
    return Workload(operations, balances)


def execute(client: httpx.Client, op: Operation) -> dict:
    started = perf_counter()
    try:
        response = client.request(
            op.method,
            op.path,
            json=op.body,
            headers={"Idempotency-Key": op.key} if op.key else None,
        )
        valid = response.status_code == op.expected_status
        if valid and op.expected_id:
            valid = response.json().get("id") == op.expected_id
        return {
            "ms": (perf_counter() - started) * 1000,
            "status": response.status_code,
            "valid": valid,
        }
    except httpx.HTTPError as error:
        return {
            "ms": (perf_counter() - started) * 1000,
            "status": 0,
            "valid": False,
            "error": type(error).__name__,
        }


def run_case(
    client: httpx.Client,
    name: str,
    count: int,
    workers: int,
    warmup: int,
    repeat: int,
    history_paths: dict[str, str],
) -> dict:
    workload = prepare(client, name, count + warmup, workers, history_paths)
    for op in workload.operations[:warmup]:
        if not execute(client, op)["valid"]:
            raise RuntimeError(f"Warmup failed for {name}")
    measured = workload.operations[warmup:]
    barrier = Barrier(workers + 1)

    def worker(index):
        barrier.wait(timeout=30)
        return [execute(client, measured[i]) for i in range(index, count, workers)]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, i) for i in range(workers)]
        started = perf_counter()
        barrier.wait(timeout=30)
        samples = [sample for future in futures for sample in future.result()]
        duration = perf_counter() - started
    # Assert the exact expected monetary effects, not just a zero global sum.
    for op in workload.operations:
        if op.movement:
            source, target, amount = op.movement
            workload.balances[source] -= amount
            workload.balances[target] += amount
    balance_errors = []
    for account, expected in workload.balances.items():
        actual = checked(client, "GET", f"/accounts/{account}/balance", 200)["balance"]
        if actual != expected:
            balance_errors.append({"account": account, "expected": expected, "actual": actual})
    reconciliation = checked(client, "GET", "/operations/reconciliation", 200)
    times = [sample["ms"] for sample in samples]
    errors = sum(not sample["valid"] for sample in samples)
    return {
        "scenario": name,
        "concurrency": workers,
        "repeat": repeat,
        "requests": count,
        "warmup_requests": warmup,
        "duration_seconds": duration,
        "requests_per_second": count / duration,
        "latency_ms": {
            "min": min(times),
            "mean": statistics.mean(times),
            "p50": percentile(times, 50),
            "p95": percentile(times, 95),
            "p99": percentile(times, 99),
            "max": max(times),
        },
        "statuses": dict(Counter(str(sample["status"]) for sample in samples)),
        "unexpected_responses": errors,
        "unexpected_response_rate_percent": 100 * errors / count,
        "balance_errors": balance_errors,
        "reconciliation": reconciliation,
        "passed": errors == 0 and not balance_errors and reconciliation["consistent"],
        "samples": samples,
    }


def markdown_report(report: dict) -> str:
    lines = [
        f"Measured at {report['started_at']}. Source SHA-256: `{report['source_sha256']}`.",
        "",
        f"Run status: **{'PASS' if report['passed'] else 'FAIL'}**. "
        f"API/PostgreSQL: `{report.get('server', 'not reached')}`.",
        f"Load generator: {report['environment']['platform']}; "
        f"Python {report['environment']['python']}; "
        f"{report['environment']['logical_cpus']} logical CPUs.",
        "",
        "Closed-loop HTTP over TCP, persistent connections, one run per row; setup, warmup and "
        "post-run accounting checks excluded. Percentiles use nearest rank. "
        "Expected HTTP 409 refusals are counted separately from unexpected errors.",
        "",
        "| Scenario | Clients | Run | N | req/s | p50 ms | p95 ms | p99 ms | Unexpected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in report["runs"]:
        latency = run["latency_ms"]
        lines.append(
            f"| {run['scenario']} | {run['concurrency']} | {run['repeat']} | {run['requests']} | "
            f"{run['requests_per_second']:.1f} | {latency['p50']:.2f} | {latency['p95']:.2f} | "
            f"{latency['p99']:.2f} | {run['unexpected_responses']} |"
        )
    if report.get("execution_error"):
        lines += ["", f"Run stopped: `{report['execution_error']}`. Partial results only."]
    lines += [
        "",
        "Raw samples, status distributions, exact balance checks and reconciliation: "
        f"[benchmark.json]({report.get('artifact_directory', 'artifacts')}/benchmark.json).",
        "These are local measurements, not a production capacity or SLO guarantee. "
        "A closed-loop generator slows down when the server stalls (coordinated omission).",
    ]
    return "\n".join(lines) + "\n"


def publish_readme(markdown: str):
    path = ROOT / "README.md"
    content = path.read_text()
    start, end = "<!-- BENCHMARK:START -->", "<!-- BENCHMARK:END -->"
    if content.count(start) != 1 or content.count(end) != 1:
        raise RuntimeError("README must contain exactly one benchmark marker pair")
    before = content.split(start)[0]
    after = content.split(end)[1]
    path.write_text(f"{before}{start}\n{markdown}\n{end}{after}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=local_url, default="http://localhost:8001")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 8, 32])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--history-size", type=int, default=1000)
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=list(SCENARIOS))
    parser.add_argument("--output", default="artifacts")
    parser.add_argument("--update-readme", action="store_true")
    args = parser.parse_args()
    if (
        min(args.requests, args.repeats, *args.concurrency) < 1
        or args.warmup < 0
        or args.history_size < 30
        or max(args.concurrency) > args.requests
    ):
        parser.error(
            "Positive counts, clients <= requests, warmup >= 0 and history-size >= 30 required"
        )
    output = output_directory(args.output)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "source_sha256": source_digest(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
        },
        "config": vars(args),
        "artifact_directory": str(output.relative_to(ROOT)),
        "runs": [],
        "passed": False,
    }
    try:
        with httpx.Client(
            base_url=args.base_url,
            timeout=20,
            trust_env=False,
            limits=httpx.Limits(
                max_connections=max(args.concurrency),
                max_keepalive_connections=max(args.concurrency),
            ),
        ) as client:
            authenticate_benchmark(client)
            report["server"] = checked(client, "GET", "/health", 200)
            history_paths = (
                prepare_history(client, args.history_size)
                if any(name.startswith("history_") for name in args.scenarios)
                else {}
            )
            for name in args.scenarios:
                for concurrency in args.concurrency:
                    for repeat in range(1, args.repeats + 1):
                        run = run_case(
                            client,
                            name,
                            args.requests,
                            concurrency,
                            args.warmup,
                            repeat,
                            history_paths,
                        )
                        report["runs"].append(run)
                        print(
                            f"{name} clients={concurrency} run={repeat}: "
                            f"{run['requests_per_second']:.1f} req/s "
                            f"p95={run['latency_ms']['p95']:.2f}ms passed={run['passed']}",
                            flush=True,
                        )
                        (output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
            (output / "metrics.prom").write_text(client.get("/metrics").raise_for_status().text)
        report["passed"] = bool(report["runs"]) and all(run["passed"] for run in report["runs"])
    except Exception as error:
        report["execution_error"] = type(error).__name__
        print(f"Benchmark aborted: {type(error).__name__}; see server logs.", file=sys.stderr)
    (output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    markdown = markdown_report(report)
    (output / "benchmark.md").write_text(
        markdown.replace(f"({report['artifact_directory']}/benchmark.json)", "(benchmark.json)")
    )
    if args.update_readme:
        publish_readme(markdown)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
