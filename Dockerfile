FROM node:24-alpine AS web-build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never \
    PATH="/code/.venv/bin:$PATH"
WORKDIR /code
COPY pyproject.toml uv.lock ./
COPY app ./app
COPY --from=web-build /app/web ./app/web
RUN uv sync --frozen --no-dev --no-editable --no-cache
COPY alembic.ini ./
COPY alembic ./alembic
RUN useradd --create-home ledgerx
USER ledgerx
EXPOSE 8000
CMD ["python", "-m", "app.start"]

FROM runtime AS test
USER root
ENV RUFF_NO_CACHE=1 COVERAGE_FILE=/code/artifacts/.coverage
RUN uv sync --frozen --no-editable --no-cache
COPY tests ./tests
COPY scripts ./scripts
USER ledgerx
CMD ["pytest", "-q", "-m", "not e2e", "-p", "no:cacheprovider"]

# Render/plain docker build use the final stage unless a target is specified.
# Keep the default image runnable; the test toolchain stays in the explicit test target.
FROM runtime AS production
