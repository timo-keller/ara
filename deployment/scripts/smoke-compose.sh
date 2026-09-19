#!/usr/bin/env bash
set -euo pipefail

repository_root="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
temporary_directory="$(mktemp -d)"
project="ara-compose-smoke-$RANDOM$RANDOM"
port="$(shuf -i 20000-40000 -n 1)"
compose=(docker compose --project-directory "$repository_root" --project-name "$project" --env-file "$temporary_directory/.env")

run_with_timeout() {
  local duration=$1
  shift
  timeout --foreground --kill-after=30s "$duration" "$@"
}

diagnose_failure() {
  printf 'Compose smoke failure diagnostics for project %s:\n' "$project" >&2
  run_with_timeout 30s "${compose[@]}" ps >&2 || true
  run_with_timeout 60s "${compose[@]}" logs --tail=200 >&2 || true
}

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    diagnose_failure
  fi
  run_with_timeout 2m "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$temporary_directory"
  exit "$status"
}
trap cleanup EXIT INT TERM

mkdir -p "$temporary_directory/secrets" "$temporary_directory/data" "$temporary_directory/certificates"
# The production instructions use a UID 10001-owned host directory.  A
# temporary directory is owned by the invoking user, so make only the smoke
# data directory world-writable rather than requiring sudo in CI.
chmod 755 "$temporary_directory"
chmod 777 "$temporary_directory/data"
printf '%s\n' compose-smoke-oidc-secret >"$temporary_directory/secrets/oidc"
printf '%s\n' compose-smoke-session-secret >"$temporary_directory/secrets/session"
printf '%s\n' compose-smoke-owner-subject >"$temporary_directory/secrets/owners"
# Compose's local file secrets retain host permissions. These disposable
# placeholders are readable by UID 10001 without requiring sudo in CI.
chmod 700 "$temporary_directory/secrets"
chmod 644 "$temporary_directory/secrets"/*
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -keyout "$temporary_directory/certificates/tls.key" -out "$temporary_directory/certificates/tls.crt" -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost' >/dev/null 2>&1
cat >"$temporary_directory/.env" <<EOF
ARA_PUBLIC_URL=https://localhost:$port
ARA_OIDC_ISSUER_URL=https://issuer-smoke.example.test
ARA_OIDC_CLIENT_ID=smoke-client
ARA_DATA_DIR=$temporary_directory/data
ARA_CERTIFICATE_DIR=$temporary_directory/certificates
ARA_HTTPS_PORT=127.0.0.1:$port
ARA_OIDC_CLIENT_SECRET_FILE=$temporary_directory/secrets/oidc
ARA_SESSION_SECRET_FILE=$temporary_directory/secrets/session
ARA_OWNER_SUBJECTS_FILE=$temporary_directory/secrets/owners
EOF

run_with_timeout 60s "${compose[@]}" config >"$temporary_directory/model.yaml"
for value in compose-smoke-oidc-secret compose-smoke-session-secret compose-smoke-owner-subject; do
  ! grep -Fq "$value" "$temporary_directory/model.yaml"
done
run_with_timeout "${ARA_COMPOSE_SMOKE_BUILD_TIMEOUT:-15m}" "${compose[@]}" up --build --detach

wait_for_ready() {
  local deadline=$((SECONDS + ${ARA_COMPOSE_SMOKE_READY_TIMEOUT_SECONDS:-120}))
  while ! curl --silent --fail --max-time 5 --insecure "https://127.0.0.1:$port/api/health/ready" >/dev/null; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      printf 'Timed out waiting for the backend readiness endpoint.\n' >&2
      return 1
    fi
    sleep 2
  done
}

wait_for_ready
curl --silent --fail --max-time 5 --insecure "https://127.0.0.1:$port/" >/dev/null

backend_id="$("${compose[@]}" ps -q backend)"
web_id="$("${compose[@]}" ps -q web)"
test -z "$(docker port "$backend_id")"
test -n "$(docker port "$web_id" 443/tcp)"
docker exec "$backend_id" sh -c 'printf persisted > /app/data/.compose-smoke-marker'
run_with_timeout "${ARA_COMPOSE_SMOKE_RECREATE_TIMEOUT:-5m}" "${compose[@]}" up --detach --force-recreate backend
new_backend_id="$("${compose[@]}" ps -q backend)"
test "$backend_id" != "$new_backend_id"
wait_for_ready
docker exec "$new_backend_id" sh -c 'test "$(cat /app/data/.compose-smoke-marker)" = persisted'
docker exec "$new_backend_id" python -c "import sqlite3; assert sqlite3.connect('/app/data/ara.db').execute('select version_num from alembic_version').fetchone()"
docker exec "$web_id" sh -c 'for value in compose-smoke-oidc-secret compose-smoke-session-secret compose-smoke-owner-subject; do ! grep -R -F -q "$value" /srv; done'
run_with_timeout 60s "${compose[@]}" logs >"$temporary_directory/logs.txt"
for value in compose-smoke-oidc-secret compose-smoke-session-secret compose-smoke-owner-subject; do
  ! grep -Fq "$value" "$temporary_directory/logs.txt"
done

printf 'Compose deployment smoke checks passed.\n'
