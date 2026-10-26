"""Serve the compiled React application without changing the JSON API routes."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

DIST = Path(__file__).resolve().parents[1] / "web"
router = APIRouter(include_in_schema=False)
WEB_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


@router.get("/")
def web_home():
    index = DIST / "index.html"
    if not index.is_file():
        return HTMLResponse(
            "<h1>LedgerX</h1><p>The web interface has not been built yet.</p>"
            "<p>Run <code>bash scripts/frontend.sh build</code> inside LedgerX, "
            'then reload this page. The <a href="/docs">API documentation</a> is available.</p>',
            status_code=503,
            headers=WEB_HEADERS,
        )
    return FileResponse(index, headers=WEB_HEADERS)
