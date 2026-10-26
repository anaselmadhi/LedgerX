import asyncio
import json

import httpx
import pytest

from scripts.benchmark import Operation, Workload
from scripts.benchmark_open_loop import check_accounting, latency_summary, run_arrivals, summarize


def test_fixed_arrivals_do_not_wait_for_slow_responses():
    async def scenario():
        running = 0
        peak = 0

        async def respond(request):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.05)
            running -= 1
            return httpx.Response(200, json={})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond), base_url="http://localhost"
        ) as client:
            samples, duration = await run_arrivals(
                client,
                [Operation("GET", "/", expected_status=200)] * 20,
                rate=1000,
                max_in_flight=2,
                max_dispatch_lag_ms=10000,
            )
        assert peak <= 2
        assert len(samples) == 20
        assert any(sample["dropped"] for sample in samples)
        for index, sample in enumerate(samples):
            assert sample["index"] == index
            assert sample["scheduled_offset_ms"] == pytest.approx(index, abs=0.001)
            if sample["dropped"]:
                assert sample["latency_ms"] is None
                assert sample["reason"] == "in_flight_limit"
            else:
                assert sample["latency_ms"] >= sample["response_ms"]
                assert sample["valid"]
        result = summarize(samples, 1000, duration)
        assert result["offered_requests"] == result["sent_requests"] + result["dropped_arrivals"]
        assert result["target_met"] is False
        assert result["unexpected_responses"] == 0

    asyncio.run(scenario())


def test_http_failures_and_unknown_outcomes_remain_in_latency_samples():
    async def scenario():
        async def respond(request):
            if request.url.path == "/timeout":
                raise httpx.ReadTimeout("a potentially sensitive URL")
            return httpx.Response(503, json={})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond), base_url="http://localhost"
        ) as client:
            samples, duration = await run_arrivals(
                client,
                [Operation("POST", "/503"), Operation("POST", "/timeout")],
                rate=100,
                max_in_flight=2,
                max_dispatch_lag_ms=10000,
            )
        result = summarize(samples, 100, duration)
        assert result["sent_requests"] == 2
        assert result["unexpected_responses"] == 2
        assert result["unconfirmed_outcomes"] == 1
        assert result["scheduled_latency_ms"] is not None
        assert samples[1]["reason"] == "ReadTimeout"
        assert "sensitive" not in json.dumps(samples)

    asyncio.run(scenario())


def test_unexpected_task_error_is_not_silently_lost():
    async def scenario():
        async def broken(request):
            raise RuntimeError("generator failure")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(broken), base_url="http://localhost"
        ) as client:
            with pytest.raises(RuntimeError, match="generator failure"):
                await run_arrivals(
                    client,
                    [Operation("GET", "/")] * 3,
                    rate=100,
                    max_in_flight=2,
                    max_dispatch_lag_ms=10000,
                )

    asyncio.run(scenario())


def test_unknown_transfer_result_cannot_claim_exact_accounting():
    def respond(request):
        if request.url.path.endswith("/balance"):
            return httpx.Response(200, json={"balance": 10})
        return httpx.Response(200, json={"consistent": True})

    with httpx.Client(
        transport=httpx.MockTransport(respond), base_url="http://localhost"
    ) as client:
        result = check_accounting(
            client,
            Workload([], {"a": 10}),
            [Operation("POST", "/transfers")],
            [{"index": 0, "valid": False, "dropped": False}],
        )
    assert result["balance_errors"] == []
    assert result["reconciliation"]["consistent"] is True
    assert result["acknowledged_effects_fully_verified"] is False


def test_no_responses_does_not_mean_zero_latency():
    assert latency_summary([]) is None
    assert latency_summary([1, 2, 3, 1000])["p99"] == 1000


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf")])
def test_invalid_arrival_rate_is_rejected(rate):
    async def scenario():
        async with httpx.AsyncClient() as client:
            with pytest.raises(ValueError):
                await run_arrivals(
                    client,
                    [Operation("GET", "/")],
                    rate=rate,
                    max_in_flight=1,
                    max_dispatch_lag_ms=100,
                )

    asyncio.run(scenario())


def test_setup_failure_records_incomplete_experiment(tmp_path, monkeypatch):
    import sys

    from scripts import benchmark, benchmark_open_loop

    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    monkeypatch.setattr(benchmark_open_loop, "source_digest", lambda: "test-source")
    monkeypatch.setattr(sys, "argv", ["open-loop"])

    def fail(client):
        raise RuntimeError("secret must not appear in report")

    monkeypatch.setattr(benchmark_open_loop, "authenticate_benchmark", fail)
    assert benchmark_open_loop.main() == 1
    content = (tmp_path / "artifacts/latency/open-loop.json").read_text()
    result = json.loads(content)
    assert result["completed"] is False
    assert result["runs"] == []
    assert result["accounting_verified"] is False
    assert result["all_targets_met"] is False
    assert "secret" not in content
