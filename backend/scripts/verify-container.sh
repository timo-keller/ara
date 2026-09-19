#!/bin/sh
# Build and exercise the production image without using any real credentials.
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
image=${ARA_BACKEND_IMAGE:-ara-backend-smoke:local}
container="ara-backend-smoke-$$"

cleanup() {
    docker rm --force "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker build --tag "$image" "$project_dir"

common_env() {
    printf '%s\n' \
        'ARA_PUBLIC_URL=https://ara-smoke.example.test' \
        'ARA_OIDC_ISSUER_URL=https://issuer-smoke.example.test' \
        'ARA_OIDC_CLIENT_ID=smoke-client' \
        'ARA_OIDC_CLIENT_SECRET=smoke-oidc-secret' \
        'ARA_SESSION_SECRET=smoke-session-secret' \
        'ARA_OWNER_SUBJECTS=smoke-owner'
}

set --
for setting in $(common_env); do
    set -- "$@" --env "$setting"
done
docker run --detach --name "$container" --publish 127.0.0.1::8000 \
    "$@" "$image" >/dev/null

# The entrypoint must migrate before serving, run non-root, and leave its data
# directory writable.  The revision table proves the migration ran.
attempt=0
until docker exec "$container" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=1)" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -eq 30 ]; then
        docker logs "$container" >&2 || true
        exit 1
    fi
    sleep 1
done
attempt=0
until [ "$(docker inspect --format '{{.State.Health.Status}}' "$container")" = healthy ]; do
    attempt=$((attempt + 1))
    if [ "$attempt" -eq 30 ]; then
        docker inspect --format '{{json .State.Health}}' "$container" >&2
        exit 1
    fi
    sleep 1
done
test "$(docker exec "$container" id -u)" = 10001
docker exec "$container" sh -c 'touch /app/data/.write-test && rm /app/data/.write-test'
docker exec "$container" python -c "import sqlite3; connection = sqlite3.connect('/app/data/ara.db'); assert connection.execute('select version_num from alembic_version').fetchone()"

# One Uvicorn process owns the one scheduler in its application lifespan.
test "$(docker top "$container" | wc -l | tr -d ' ')" = 2
docker top "$container" | grep -q 'uvicorn ara.main:app.*--workers 1'
docker logs "$container" 2>&1 | grep -q 'Scheduler started'

# The final stage has no local developer environment, tests, or credentials.
docker exec "$container" sh -c 'test ! -e /app/.venv && test ! -e /app/tests && test ! -e /app/.env && test ! -e /app/secrets && test ! -e /root/.cache/uv'

# PID 1 receives the stop signal directly because the entrypoint execs Uvicorn.
docker stop --time 10 "$container" >/dev/null

# Required settings and migration connectivity must fail before an API starts.
if docker run --rm --env ARA_PUBLIC_URL=https://ara-smoke.example.test "$image"; then
    exit 1
fi
if docker run --rm "$@" --env ARA_DATABASE_URL=not-a-database-url "$image"; then
    exit 1
fi
