import pytest

from scripts.benchmark import local_url, percentile


def test_nearest_rank_percentiles_do_not_hide_outliers():
    values = list(range(1, 101))
    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 95
    assert percentile(values, 99) == 99
    assert percentile([2], 99) == 2
    assert percentile([1, 2, 3, 10000], 99) == 10000


def test_empty_samples_are_not_reported_as_zero_latency():
    with pytest.raises(ValueError):
        percentile([], 95)


@pytest.mark.parametrize(
    "url",
    ["https://example.com", "http://example.com", "http://user:password@localhost", "file:///tmp"],
)
def test_benchmark_refuses_remote_targets(url):
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        local_url(url)


def test_failed_benchmark_writes_failed_report_without_fake_samples(tmp_path, monkeypatch):
    import json
    import sys

    from scripts import benchmark

    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    monkeypatch.setattr(benchmark, "source_digest", lambda: "test-source")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark",
            "--requests",
            "1",
            "--concurrency",
            "1",
            "--repeats",
            "1",
            "--scenarios",
            "balance_read",
            "--update-readme",
        ],
    )
    (tmp_path / "README.md").write_text(
        "<!-- BENCHMARK:START -->\nold report\n<!-- BENCHMARK:END -->"
    )

    def failed_auth(client):
        raise RuntimeError("simulated setup failure")

    monkeypatch.setattr(benchmark, "authenticate_benchmark", failed_auth)
    assert benchmark.main() == 1
    report = json.loads((tmp_path / "artifacts" / "benchmark.json").read_text())
    assert report["passed"] is False
    assert report["runs"] == []
    assert report["execution_error"] == "RuntimeError"
    assert "**FAIL**" in (tmp_path / "README.md").read_text()
    assert "old report" not in (tmp_path / "README.md").read_text()
