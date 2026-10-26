"""Fixed-arrival HTTP load with bounded in-flight work and explicit dropped arrivals."""

import argparse
import asyncio
import json
import math
import os
import platform
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from typing import Any, TypedDict

import httpx

from scripts.benchmark import (
    Operation,
    Workload,
    authenticate_benchmark,
    checked,
    execute,
    local_url,
    output_directory,
    percentile,
    prepare,
    source_digest,
)


class Sample(TypedDict):
    index: int
    scheduled_offset_ms: float
    dispatch_lag_ms: float
    response_ms: float | None
    latency_ms: float | None
    status: int | None
    valid: bool
    dropped: bool
    reason: str | None


def latency_summary(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None  # No responses is not zero latency.
    return {
        "min": min(values),
        "mean": statistics.mean(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values),
    }


async def run_arrivals(
    client: httpx.AsyncClient,
    operations: list[Operation],
    *,
    rate: float,
    max_in_flight: int,
    max_dispatch_lag_ms: float,
) -> tuple[list[Sample], float]:
    """Never wait for a response before scheduling the next arrival.

    Arrivals that exceed the generator's in-flight/lag budget are counted, not
    silently delayed or removed from the offered-load denominator. Each sent
    request records both dispatch-to-completion and scheduled-to-completion time.
    """
    if (
        not operations
        or not math.isfinite(rate)
        or rate <= 0
        or max_in_flight < 1
        or not math.isfinite(max_dispatch_lag_ms)
        or max_dispatch_lag_ms <= 0
    ):
        raise ValueError(
            "Nonempty operations, finite positive rate/lag and an in-flight cap required"
        )
    loop = asyncio.get_running_loop()
    started = loop.time()
    samples: list[Sample] = []
    active: set[asyncio.Task[None]] = set()
    failures: list[BaseException] = []

    def finished(task: asyncio.Task[None]) -> None:
        active.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            failures.append(error)

    async def send(index: int, scheduled: float) -> None:
        dispatched = loop.time()
        op = operations[index]
        status = 0
        valid = False
        reason = None
        try:
            response = await client.request(
                op.method,
                op.path,
                json=op.body,
                headers={"Idempotency-Key": op.key} if op.key else None,
            )
            status = response.status_code
            valid = status == op.expected_status
            if valid and op.expected_id is not None:
                valid = response.json().get("id") == op.expected_id
            if not valid:
                reason = "unexpected_response"
        except (httpx.HTTPError, ValueError) as error:
            reason = type(error).__name__  # No credentials, URLs or financial payloads.
        completed = loop.time()
        samples.append(
            Sample(
                index=index,
                scheduled_offset_ms=(scheduled - started) * 1000,
                dispatch_lag_ms=(dispatched - scheduled) * 1000,
                response_ms=(completed - dispatched) * 1000,
                latency_ms=(completed - scheduled) * 1000,
                status=status,
                valid=valid,
                dropped=False,
                reason=reason,
            )
        )

    try:
        for index in range(len(operations)):
            if failures:
                raise failures[0]
            scheduled = started + index / rate
            # Even an overdue slot yields to the event loop, allowing completed
            # requests to release their in-flight place before admission.
            await asyncio.sleep(max(0, scheduled - loop.time()))
            lag = (loop.time() - scheduled) * 1000
            reason = (
                "generator_late"
                if lag > max_dispatch_lag_ms
                else "in_flight_limit"
                if len(active) >= max_in_flight
                else None
            )
            if reason:
                samples.append(
                    Sample(
                        index=index,
                        scheduled_offset_ms=index / rate * 1000,
                        dispatch_lag_ms=lag,
                        response_ms=None,
                        latency_ms=None,
                        status=None,
                        valid=False,
                        dropped=True,
                        reason=reason,
                    )
                )
                continue
            task = asyncio.create_task(send(index, scheduled))
            active.add(task)
            task.add_done_callback(finished)
        if active:
            await asyncio.gather(*active)
        if failures:
            raise failures[0]
    finally:
        unfinished = list(active)
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.gather(*unfinished, return_exceptions=True)
    return sorted(samples, key=lambda sample: sample["index"]), loop.time() - started


def summarize(samples: list[Sample], rate: float, duration: float) -> dict[str, Any]:
    sent = [sample for sample in samples if not sample["dropped"]]
    dropped = len(samples) - len(sent)
    errors = sum(not sample["valid"] for sample in sent)
    return {
        "offered_requests": len(samples),
        "offered_rate_per_second": rate,
        "arrival_window_seconds": len(samples) / rate,
        "duration_including_drain_seconds": duration,
        "sent_requests": len(sent),
        "dropped_arrivals": dropped,
        "drop_reasons": dict(Counter(s["reason"] for s in samples if s["dropped"])),
        "unexpected_responses": errors,
        "unconfirmed_outcomes": sum(s["status"] == 0 for s in sent),
        "valid_response_rate_including_drain": (len(sent) - errors) / duration
        if duration
        else None,
        "target_met": dropped == 0 and errors == 0,
        "statuses": dict(Counter(str(s["status"]) for s in sent)),
        "scheduled_latency_ms": latency_summary(
            [s["latency_ms"] for s in sent if s["latency_ms"] is not None]
        ),
        "response_latency_ms": latency_summary(
            [s["response_ms"] for s in sent if s["response_ms"] is not None]
        ),
        "dispatch_lag_ms": latency_summary([s["dispatch_lag_ms"] for s in samples]),
    }


def check_accounting(
    client: httpx.Client, workload: Workload, operations: list[Operation], samples: list[Sample]
) -> dict[str, Any]:
    expected = dict(workload.balances)
    for sample in samples:
        op = operations[sample["index"]]
        if sample["valid"] and op.movement:
            source, target, amount = op.movement
            expected[source] -= amount
            expected[target] += amount
    errors = []
    for account, balance in expected.items():
        actual = checked(client, "GET", f"/accounts/{account}/balance", 200)["balance"]
        if actual != balance:
            errors.append({"account": account, "expected": balance, "actual": actual})
    audit = checked(client, "GET", "/operations/reconciliation", 200)
    # A timeout can have committed. Do not retry implicitly, assume no debit, or
    # claim exact accounting from acknowledged responses when any result is unknown.
    uncertain = any(not s["dropped"] and not s["valid"] for s in samples)
    return {
        "balance_errors": errors,
        "reconciliation": audit,
        "acknowledged_effects_fully_verified": not uncertain and not errors and audit["consistent"],
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Fixed-arrival HTTP measurements",
        "",
        f"Measured at {report['started_at']}; source `{report['source_sha256']}`.",
        "",
        "Latency starts at the scheduled arrival, so generator delay is included. "
        "Dropped arrivals have no invented response latency and are counted separately. "
        "Percentiles describe sent requests only; always read them alongside drops and errors.",
        "",
        "| Scenario | Offered req/s | Run | Sent / offered | Dropped | Errors | p50 ms | p95 ms | "
        "p99 ms | Target met | Accounting |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for run in report["runs"]:
        lat = run["scheduled_latency_ms"]
        times = " | ".join(f"{lat[key]:.2f}" if lat else "n/a" for key in ("p50", "p95", "p99"))
        lines.append(
            f"| {run['scenario']} | {run['offered_rate_per_second']:g} | {run['repeat']} | "
            f"{run['sent_requests']} / {run['offered_requests']} | {run['dropped_arrivals']} | "
            f"{run['unexpected_responses']} | {times} | {run['target_met']} | "
            f"{run['acknowledged_effects_fully_verified']} |"
        )
    if report.get("execution_error"):
        lines += ["", f"Incomplete experiment: `{report['execution_error']}`."]
    lines += [
        "",
        "Fixed spacing, not a Poisson/bursty traffic model. Generator and server may share CPU. "
        "No sustainable production capacity follows from these short experiments. "
        "A met target means no drops/unexpected responses; it does not assert a latency SLO.",
        "Full samples and independent accounting checks: [open-loop.json](open-loop.json).",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=local_url, default="http://127.0.0.1:8001")
    parser.add_argument("--rates", type=float, nargs="+", default=[100, 300, 600])
    parser.add_argument("--duration", type=float, default=5)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-in-flight", type=int, default=128)
    parser.add_argument("--max-dispatch-lag-ms", type=float, default=100)
    parser.add_argument("--account-pairs", type=int, default=32)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=["independent_transfers", "shared_source", "balance_read"],
        default=["independent_transfers", "shared_source"],
    )
    parser.add_argument("--output", default="artifacts/latency")
    args = parser.parse_args()
    if (
        not all(
            math.isfinite(n) and n > 0
            for n in [*args.rates, args.duration, args.max_dispatch_lag_ms]
        )
        or not 1 <= args.max_in_flight <= 2048
        or not 1 <= args.account_pairs <= 256
        or not 1 <= args.repeats <= 100
        or not 0 <= args.warmup <= 10000
        or max(args.rates) * args.duration > 1_000_000
    ):
        parser.error("Require finite positive rates/durations and bounded request/worker counts")
    output = output_directory(args.output)
    report: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "source_sha256": source_digest(),
        "kind": "open-loop fixed arrivals; bounded generator; scheduled-to-completion latency",
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
        },
        "config": vars(args),
        "runs": [],
        "completed": False,
    }
    try:
        with httpx.Client(base_url=args.base_url, timeout=20, trust_env=False) as setup:
            authenticate_benchmark(setup)
            report["server"] = checked(setup, "GET", "/health", 200)
            for name in args.scenarios:
                for rate in args.rates:
                    for repeat in range(1, args.repeats + 1):
                        count = math.ceil(rate * args.duration)
                        workload = prepare(setup, name, count + args.warmup, args.account_pairs, {})
                        for op in workload.operations[: args.warmup]:
                            if not execute(setup, op)["valid"]:
                                raise RuntimeError("Warmup failed")
                            if op.movement:
                                source, target, amount = op.movement
                                workload.balances[source] -= amount
                                workload.balances[target] += amount
                        operations = workload.operations[args.warmup :]

                        async def measure(operations=operations, rate=rate):
                            async with httpx.AsyncClient(
                                base_url=args.base_url,
                                timeout=20,
                                trust_env=False,
                                headers={"Authorization": setup.headers["Authorization"]},
                                limits=httpx.Limits(
                                    max_connections=args.max_in_flight,
                                    max_keepalive_connections=args.max_in_flight,
                                ),
                            ) as load:
                                return await run_arrivals(
                                    load,
                                    operations,
                                    rate=rate,
                                    max_in_flight=args.max_in_flight,
                                    max_dispatch_lag_ms=args.max_dispatch_lag_ms,
                                )

                        samples, duration = asyncio.run(measure())
                        run = {
                            "scenario": name,
                            "repeat": repeat,
                            **summarize(samples, rate, duration),
                            **check_accounting(setup, workload, operations, samples),
                            "samples": samples,
                        }
                        report["runs"].append(run)
                        latency = run["scheduled_latency_ms"]
                        p95 = f"{latency['p95']:.2f}ms" if latency else "n/a"
                        print(
                            f"{name} offered={rate:g}/s run={repeat}: "
                            f"sent={run['sent_requests']}/{count} "
                            f"dropped={run['dropped_arrivals']} "
                            f"errors={run['unexpected_responses']} p95={p95} "
                            f"target_met={run['target_met']} "
                            f"accounting={run['acknowledged_effects_fully_verified']}",
                            flush=True,
                        )
                        (output / "open-loop.json").write_text(json.dumps(report, indent=2) + "\n")
        report["completed"] = True
    except Exception as error:
        report["execution_error"] = type(error).__name__
        print(f"Experiment stopped: {type(error).__name__}; inspect server logs.", file=sys.stderr)
    report["accounting_verified"] = bool(report["runs"]) and all(
        r["acknowledged_effects_fully_verified"] for r in report["runs"]
    )
    report["all_targets_met"] = bool(report["runs"]) and all(
        r["target_met"] for r in report["runs"]
    )
    (output / "open-loop.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "open-loop.md").write_text(markdown_report(report))
    # Dropped arrivals can identify a capacity boundary without corrupting data.
    # The report marks those targets unmet even when the experiment itself completes.
    return 0 if report["completed"] and report["accounting_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
