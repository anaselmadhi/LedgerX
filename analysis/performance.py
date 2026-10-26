"""Plot recorded measurements; never connect to the API or database."""

import json
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
COLORS = ["#165DDB", "#00856A", "#C46B00", "#8B46B0"]
LABELS = {
    "balance_read": "Balance read",
    "independent_transfers": "Independent transfers",
    "shared_source": "Shared source",
    "reversals": "Full refunds",
}


def load_reports():
    benchmark = json.loads((ROOT / "artifacts/benchmark.json").read_text())
    profiling = json.loads((ROOT / "artifacts/profiling.json").read_text())
    if not benchmark["passed"] or not benchmark["runs"]:
        raise ValueError("Refusing to present a failed/empty benchmark as a successful baseline")
    for run in benchmark["runs"]:
        if (
            not run["passed"]
            or run["balance_errors"]
            or not run["reconciliation"]["consistent"]
            or run["requests"] != len(run["samples"])
        ):
            raise ValueError("Inconsistent benchmark evidence")
    if any(not run["reconciliation"]["consistent"] for run in profiling["runs"]):
        raise ValueError("Profiling accounting checks did not pass")
    if benchmark["source_sha256"] != profiling["source_sha256"]:
        raise ValueError("HTTP and profiling data refer to different source revisions")
    return benchmark, profiling


def style():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.17,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def concurrency_figure(benchmark):
    style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    clients = sorted({run["concurrency"] for run in benchmark["runs"]})
    for color, (scenario, label) in zip(COLORS, LABELS.items(), strict=True):
        groups = [
            [
                run
                for run in benchmark["runs"]
                if run["scenario"] == scenario and run["concurrency"] == count
            ]
            for count in clients
        ]
        if any(not group for group in groups):
            continue
        for axis, metric in zip(axes, ["requests_per_second", "p95"], strict=True):
            values = [
                [run[metric] if metric != "p95" else run["latency_ms"]["p95"] for run in group]
                for group in groups
            ]
            center = [median(group) for group in values]
            interval = [
                [mid - min(group) for mid, group in zip(center, values, strict=True)],
                [max(group) - mid for mid, group in zip(center, values, strict=True)],
            ]
            axis.errorbar(
                clients,
                center,
                yerr=interval,
                marker="o",
                capsize=4,
                linewidth=2,
                color=color,
                label=label,
            )
    for axis in axes:
        axis.set_xscale("log", base=2)
        axis.set_xticks(clients, [str(value) for value in clients])
        axis.set_xlabel("Concurrent clients")
        axis.set_ylim(bottom=0)
    axes[0].set(title="HTTP throughput", ylabel="Requests / second")
    axes[1].set(title="HTTP p95 latency", ylabel="Milliseconds")
    axes[0].legend(frameon=False, fontsize=9)
    fig.suptitle("LedgerX · Concurrency and contention", fontsize=17, fontweight="bold")
    fig.text(
        0.5,
        0.015,
        "Median across 3 repetitions; whiskers = observed min–max, not confidence intervals. "
        "200 requests / repetition.",
        ha="center",
        fontsize=9,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.93))
    return fig


def distribution_figure(benchmark):
    style()
    fig, axis = plt.subplots(figsize=(10, 5))
    cases = [
        ("independent_transfers", 8),
        ("shared_source", 8),
        ("independent_transfers", 32),
        ("shared_source", 32),
    ]
    for color, (scenario, clients) in zip(COLORS, cases, strict=True):
        samples = sorted(
            sample["ms"]
            for run in benchmark["runs"]
            if run["scenario"] == scenario and run["concurrency"] == clients
            for sample in run["samples"]
        )
        if samples:
            axis.step(
                samples,
                [100 * (i + 1) / len(samples) for i in range(len(samples))],
                where="post",
                color=color,
                linewidth=2,
                label=f"{LABELS[scenario]} · {clients} clients · n={len(samples)}",
            )
    axis.set_xscale("log")
    axis.set(
        xlabel="Response latency (ms, logarithmic scale)",
        ylabel="Cumulative share of requests (%)",
        ylim=(0, 101),
        title="LedgerX · Full latency distributions",
    )
    axis.axhline(95, color="#666666", linewidth=0.8, linestyle="--")
    axis.legend(frameon=False, loc="lower right", fontsize=9)
    fig.text(
        0.5,
        0.01,
        "All raw samples from 3 repetitions; no outliers removed. Closed-loop local experiment.",
        ha="center",
        fontsize=9,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fig


def profiling_figure(profiling):
    style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    runs = profiling["runs"]
    positions = list(range(len(runs)))
    for color, percentile in zip(COLORS[:3], ["p50", "p95", "p99"], strict=True):
        axes[0].plot(
            positions,
            [run["service_including_commit_ms"][percentile] for run in runs],
            marker="o",
            linewidth=2,
            label=percentile,
            color=color,
        )
    for index, (name, color) in enumerate(zip(["offset", "cursor"], COLORS, strict=False)):
        axes[1].bar(
            [pos + (index - 0.5) * 0.32 for pos in positions],
            [run["history_query_plans"][name][0]["Execution Time"] for run in runs],
            width=0.3,
            color=color,
            label=name,
        )
    for axis in axes:
        axis.set_xticks(positions, [str(run["prepared_transfer_history"]) for run in runs])
        axis.set_xlabel("Initial prepared transfer history")
        axis.set_ylim(bottom=0)
        axis.legend(frameon=False)
    axes[0].set(title="Service + commit (cProfile enabled)", ylabel="Milliseconds")
    axes[1].set(title="History SQL: EXPLAIN ANALYZE", ylabel="Execution time (ms)")
    fig.suptitle("LedgerX · Service and SQL profiling", fontsize=17, fontweight="bold")
    fig.text(
        0.5,
        0.015,
        "100 committed transfers per history depth. SQL plan times are single observations; "
        "they are not HTTP latencies.",
        ha="center",
        fontsize=9,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.93))
    return fig
