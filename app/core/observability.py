import json
import logging
import re
from time import perf_counter
from uuid import uuid4

from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "ledgerx_http_requests_total", "Completed HTTP requests", ["method", "route", "status"]
)
LATENCY = Histogram(
    "ledgerx_http_request_duration_seconds",
    "HTTP duration including dependency cleanup; process local",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
MONEY_REQUESTS = Counter(
    "ledgerx_money_requests_total",
    "Money operation HTTP outcomes after transaction completion",
    ["operation", "outcome"],
)
logger = logging.getLogger("ledgerx.requests")
error_logger = logging.getLogger("ledgerx.errors")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class ObservabilityMiddleware:
    """Pure ASGI wrapper: no extra task or response-body buffering."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        candidate = next(
            (v.decode("latin1") for k, v in scope["headers"] if k.lower() == b"x-request-id"), ""
        )
        request_id = candidate if SAFE_ID.fullmatch(candidate) else str(uuid4())
        correlation = next(
            (v.decode("latin1") for k, v in scope["headers"] if k.lower() == b"x-correlation-id"),
            "",
        )
        correlation_id = correlation if SAFE_ID.fullmatch(correlation) else request_id
        scope.setdefault("state", {})["request_id"] = request_id
        scope["state"]["correlation_id"] = correlation_id
        started = perf_counter()
        status = 500
        replayed = False
        response_started = False

        async def send_response(message):
            nonlocal status, replayed, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                replayed = (b"idempotency-replayed", b"true") in message.get("headers", [])
                message = {
                    **message,
                    "headers": [
                        *message.get("headers", []),
                        (b"x-request-id", request_id.encode()),
                        (b"x-correlation-id", correlation_id.encode()),
                    ],
                }
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except Exception as error:
            # Starlette's outer ServerErrorMiddleware re-raises unhandled errors
            # to Uvicorn even after a custom 500 handler responds. Catch here so
            # its traceback cannot disclose SQL parameters or arbitrary secrets.
            error_logger.error(
                json.dumps(
                    {
                        "event": "unexpected_error",
                        "type": type(error).__name__,
                        "request_id": request_id,
                        "correlation_id": correlation_id,
                    }
                )
            )
            status = 500
            if response_started:
                # A second response is invalid. Propagate only a sanitized error
                # so the server closes the connection without logging the cause.
                raise RuntimeError("Response failed after headers were sent") from None
            body = json.dumps(
                {
                    "detail": "Internal server error",
                    "code": "internal_error",
                    "request_id": request_id,
                }
            ).encode()
            await send_response(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send_response({"type": "http.response.body", "body": body})
        finally:
            elapsed = perf_counter() - started
            # Never use raw URLs, account IDs, keys or query strings as labels.
            route = getattr(scope.get("route"), "path", "unmatched")
            method = scope["method"]
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                method = "OTHER"
            REQUESTS.labels(method, route, str(status)).inc()
            LATENCY.labels(method, route).observe(elapsed)
            operation = {
                "/transfers": "transfer",
                "/transfers/{transaction_id}/reversal": "reversal",
                "/dev/funding": "funding",
            }.get(route)
            if operation and method == "POST":
                if status == 201:
                    outcome = "replayed" if replayed else "committed"
                elif status == 503:
                    outcome = "unavailable"
                elif status >= 500:
                    outcome = "internal_error"
                elif status in {401, 403, 404}:
                    outcome = "denied"
                else:
                    outcome = "rejected"
                MONEY_REQUESTS.labels(operation, outcome).inc()
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "correlation_id": correlation_id,
                        "method": method,
                        "route": route,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 3),
                    }
                )
            )
