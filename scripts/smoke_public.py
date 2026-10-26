"""Read-only checks for the deployed shell, assets, database readiness and auth boundary."""

import argparse
import json
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        value = values.get("src") if tag == "script" else values.get("href")
        if tag in {"script", "link"} and value and value.startswith("/assets/"):
            self.paths.append(value)


def validate_origin(value: str) -> str:
    url = urlsplit(value)
    local_http = url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not url.hostname
        or (url.scheme != "https" and not local_http)
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
    ):
        raise ValueError("Provide an HTTPS origin, or HTTP on localhost, with no credentials/path.")
    return value.rstrip("/")


def check(origin: str, expected_schema: str | None = None) -> None:
    origin = validate_origin(origin)

    def get(path: str, status: int = 200):
        # Sixty seconds permits a first cold start; failures remain explicit.
        try:
            response = urlopen(origin + path, timeout=60)
        except HTTPError as error:
            response = error
        with response:
            if response.status != status:
                raise RuntimeError(f"{path}: expected HTTP {status}, got {response.status}")
            if urlsplit(response.url).netloc != urlsplit(origin).netloc:
                raise RuntimeError("Unexpected cross-origin redirect")
            return response.headers, response.read(2_000_000)

    for path in ("/health/live", "/health"):
        _, body = get(path)
        health = json.loads(body)
        if health.get("status") != "ok":
            raise RuntimeError(f"{path}: not ready")
        if path == "/health" and expected_schema is not None:
            if health.get("schema") != expected_schema:
                raise RuntimeError("Deployed schema does not match the local release")
    headers, html = get("/")
    if "default-src 'none'" not in headers.get("content-security-policy", ""):
        raise RuntimeError("Missing expected UI content security policy")
    assets = AssetParser()
    assets.feed(html.decode("utf-8"))
    if not any(path.endswith(".js") for path in assets.paths):
        raise RuntimeError("Compiled JavaScript bundle missing")
    for path in assets.paths:
        # Defensive validation even though these paths come from the app's own HTML.
        if not urljoin(origin + "/", path).startswith(origin + "/assets/"):
            raise RuntimeError("Unexpected asset URL")
        get(path)
    for path in ("/auth/me", "/accounts", "/operations/reconciliation", "/metrics"):
        get(path, status=401)
    print("PASS: UI/assets, database readiness and unauthenticated access checks.")
    print("Read-only smoke check; no users, accounts, funding or transfers were created.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--current-schema", action="store_true", help="Require the schema revision in local source"
    )
    args = parser.parse_args()
    try:
        expected_schema = None
        if args.current_schema:
            from app.core.config import SCHEMA_REVISION

            expected_schema = SCHEMA_REVISION
        check(args.url, expected_schema=expected_schema)
    except (ValueError, RuntimeError, URLError, TimeoutError, OSError) as exc:
        # Network exceptions may contain URLs. Keep output safe and bounded.
        raise SystemExit(f"FAIL: deployment smoke check ({type(exc).__name__}).") from None


if __name__ == "__main__":
    main()
