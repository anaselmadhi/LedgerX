import asyncio
import json
import logging
from types import SimpleNamespace

import pytest

from app.core.observability import MONEY_REQUESTS, ObservabilityMiddleware


def test_asgi_correlation_and_replay_metrics_do_not_log_secrets(caplog):
    async def endpoint(scope, receive, send):
        scope["route"] = SimpleNamespace(path="/transfers")
        await send(
            {
                "type": "http.response.start",
                "status": 201,
                "headers": [(b"idempotency-replayed", b"true")],
            }
        )
        await send({"type": "http.response.body", "body": b"{}"})

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [
            (b"x-request-id", b"req-1"),
            (b"x-correlation-id", b"flow-1"),
            (b"authorization", b"Bearer secret-token"),
            (b"idempotency-key", b"private-key"),
        ],
    }
    messages = []

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request", "body": b""}

    counter = MONEY_REQUESTS.labels("transfer", "replayed")
    before = counter._value.get()
    with caplog.at_level(logging.INFO, logger="ledgerx.requests"):
        asyncio.run(ObservabilityMiddleware(endpoint)(scope, receive, send))
    assert counter._value.get() == before + 1
    assert (b"x-request-id", b"req-1") in messages[0]["headers"]
    assert (b"x-correlation-id", b"flow-1") in messages[0]["headers"]
    record = json.loads(caplog.records[-1].message)
    assert record["route"] == "/transfers"
    assert record["correlation_id"] == "flow-1"
    assert "secret-token" not in caplog.text
    assert "private-key" not in caplog.text


@pytest.mark.parametrize("headers_sent", [False, True])
def test_unexpected_error_cannot_escape_as_secret_bearing_traceback(caplog, headers_sent):
    async def endpoint(scope, receive, send):
        scope["route"] = SimpleNamespace(path="/transfers")
        if headers_sent:
            await send({"type": "http.response.start", "status": 201, "headers": []})
        raise RuntimeError("password=must-not-leak")

    scope = {"type": "http", "method": "POST", "headers": []}
    messages = []

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request", "body": b""}

    counter = MONEY_REQUESTS.labels("transfer", "internal_error")
    before = counter._value.get()
    with caplog.at_level(logging.INFO, logger="ledgerx"):
        if headers_sent:
            with pytest.raises(RuntimeError, match="Response failed after headers") as caught:
                asyncio.run(ObservabilityMiddleware(endpoint)(scope, receive, send))
            import traceback

            assert "must-not-leak" not in "".join(traceback.format_exception(caught.value))
            assert len(messages) == 1  # No invalid second HTTP response.
        else:
            asyncio.run(ObservabilityMiddleware(endpoint)(scope, receive, send))
            assert messages[0]["status"] == 500
            result = json.loads(messages[1]["body"])
            assert result["code"] == "internal_error"
            assert result["request_id"] == scope["state"]["request_id"]
            assert (b"x-correlation-id", scope["state"]["correlation_id"].encode()) in messages[0][
                "headers"
            ]
    assert counter._value.get() == before + 1
    assert "must-not-leak" not in caplog.text + str(messages)
    assert any(
        json.loads(record.message)["event"] == "unexpected_error" for record in caplog.records
    )
