# syntax=docker/dockerfile:1
# Keep both the Python runtime and uv toolchain on explicit release tags.
FROM ghcr.io/astral-sh/uv:0.9.13 AS uv

FROM python:3.14.0-slim AS builder

WORKDIR /app

COPY --from=uv /uv /uv
COPY pyproject.toml uv.lock README.md ./

# Exporting from the lock file retains its hashes and installs only the runtime
# dependency set.  Installing into the system prefix avoids copying a build or
# developer virtual environment into the final image.
RUN /uv export --frozen --no-dev --no-emit-project --format requirements-txt \
        --output-file requirements.txt \
    && /uv pip install --system --require-hashes --no-cache -r requirements.txt

FROM python:3.14.0-slim AS runtime

RUN groupadd --gid 10001 ara \
    && useradd --uid 10001 --gid ara --create-home --shell /usr/sbin/nologin ara \
    && mkdir --parents /app/data \
    && chown ara:ara /app/data

WORKDIR /app

# The builder's system prefix contains only lock-file runtime dependencies and
# their console entry points (including Alembic and Uvicorn).
COPY --from=builder /usr/local /usr/local
COPY --chown=ara:ara alembic.ini ./
COPY --chown=ara:ara alembic ./alembic
COPY --chown=ara:ara src ./src
COPY --chown=ara:ara docker-entrypoint.sh /usr/local/bin/ara-entrypoint

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER ara

EXPOSE 8000

# Python's stdlib provides a small health probe without adding curl or another
# runtime package.  Liveness deliberately does not depend on the database.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=2).close()"]

ENTRYPOINT ["ara-entrypoint"]
