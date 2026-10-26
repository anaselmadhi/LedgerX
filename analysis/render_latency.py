"""Plot recorded latency experiments only; never synthesize missing measurements."""

import json
import os
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".runtime/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".runtime/cache"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def render(directory: Path | None = None) -> list[Path]:
    directory = directory or ROOT / "artifacts/latency"
    if not directory.resolve().is_relative_to(ROOT):
        raise ValueError("Latency figures must stay inside LedgerX")
    load_path, profile_path = directory / "open-loop.json", directory / "profiling.json"
    if not load_path.exists() or not profile_path.exists():
        raise ValueError("Run verify_latency.sh first: both measured JSON reports are required")
    load = json.loads(load_path.read_text())
    profile = json.loads(profile_path.read_text())
    if not load.get("completed") or not load.get("runs") or not profile.get("runs"):
        raise ValueError("Incomplete experiments cannot produce the final latency figures")
    if load["source_sha256"] != profile["source_sha256"]:
        raise ValueError("Reports have different source digests; do not combine them")
    destination = directory / "figures"
    destination.mkdir(parents=True, exist_ok=True)
    outputs = []
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

    def save(fig, name):
        for extension in ("png", "svg"):
            path = destination / f"{name}.{extension}"
            fig.savefig(path, dpi=180, bbox_inches="tight")
            outputs.append(path)
        plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), layout="constrained")
    colors = ("#28664e", "#9a4b1f", "#314f9c")
    scenarios = sorted({run["scenario"] for run in load["runs"]})
    for scenario, color in zip(scenarios, colors, strict=False):
        rates = defaultdict(list)
        for run in load["runs"]:
            if run["scenario"] == scenario:
                rates[run["offered_rate_per_second"]].append(run)
        for axis, metric in zip(axes, ("p95", "drop", "error"), strict=True):
            medians = {}
            for rate, runs in sorted(rates.items()):
                values = []
                for run in runs:
                    if metric == "p95":
                        if run["scheduled_latency_ms"] is None:
                            continue
                        value = run["scheduled_latency_ms"]["p95"]
                    else:
                        key = "dropped_arrivals" if metric == "drop" else "unexpected_responses"
                        value = 100 * run[key] / run["offered_requests"]
                    values.append(value)
                if values:
                    axis.scatter([rate] * len(values), values, color=color, alpha=0.45, s=24)
                    medians[rate] = statistics.median(values)
            axis.plot(list(medians), list(medians.values()), color=color, label=scenario)
    for axis, title, unit in zip(
        axes,
        ("Scheduled-to-completion p95", "Dropped arrivals", "Unexpected responses"),
        (
            "Milliseconds · sent requests only",
            "% of all offered arrivals",
            "% of all offered arrivals",
        ),
        strict=True,
    ):
        axis.set(title=title, xlabel="Offered requests / second", ylabel=unit)
        axis.grid(alpha=0.2)
        axis.legend(fontsize=8)
    fig.suptitle(
        "Fixed-arrival HTTP · dots: repetitions; lines: median of repetition statistics\n"
        f"Accounting verified: {load.get('accounting_verified', False)} · "
        f"All load targets met: {load.get('all_targets_met', False)}",
        fontsize=12,
    )
    save(fig, "fixed-arrival-load")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout="constrained")
    for axis, metrics in zip(
        axes,
        (("service", "commit"), ("historical_sum", "projection_lookup")),
        strict=True,
    ):
        for metric, color in zip(metrics, colors, strict=False):
            by_depth = defaultdict(list)
            for run in profile["runs"]:
                if metric in {"service", "commit"}:
                    key = "commit_ms" if metric == "commit" else "service_including_commit_ms"
                    value = run[key]["p95"]
                else:
                    value = run["history_query_plans"][metric][0]["Execution Time"]
                by_depth[run["prepared_transfer_history"]].append(value)
            medians = {}
            for depth, values in sorted(by_depth.items()):
                axis.scatter([depth] * len(values), values, color=color, alpha=0.45, s=24)
                medians[depth] = statistics.median(values)
            axis.plot(list(medians), list(medians.values()), color=color, label=metric)
        axis.set_xscale("symlog", linthresh=1)
        axis.set(xlabel="Prepared transfer history (symlog scale)", ylabel="Milliseconds")
        axis.grid(alpha=0.2)
        axis.legend(fontsize=8)
    axes[0].set_title("Service and commit p95 · cProfile enabled")
    axes[1].set_title("Isolated read query execution · not transfer latency")
    fig.suptitle(
        f"Schema {profile.get('schema', 'unknown')} · median of repetition statistics\n"
        "Source: " + profile["source_sha256"][:16],
        fontsize=12,
    )
    save(fig, "history-and-commit")
    return outputs


if __name__ == "__main__":
    try:
        for output in render():
            print(output.relative_to(ROOT))
    except ValueError as error:
        raise SystemExit(str(error)) from None
