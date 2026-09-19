#!/usr/bin/env bash
set -euo pipefail

repository_root="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT

run_with_timeout() {
  local duration=$1
  shift
  timeout --foreground --kill-after=10s "$duration" "$@"
}

mkdir -p "$temporary_directory/secrets" "$temporary_directory/data" "$temporary_directory/certificates"
printf '%s\n' static-oidc-placeholder >"$temporary_directory/secrets/oidc"
printf '%s\n' static-session-placeholder >"$temporary_directory/secrets/session"
printf '%s\n' static-owner-placeholder >"$temporary_directory/secrets/owners"
cat >"$temporary_directory/.env" <<EOF
ARA_PUBLIC_URL=https://ara-smoke.example.test
ARA_OIDC_ISSUER_URL=https://issuer-smoke.example.test
ARA_OIDC_CLIENT_ID=smoke-client
ARA_DATA_DIR=$temporary_directory/data
ARA_CERTIFICATE_DIR=$temporary_directory/certificates
ARA_OIDC_CLIENT_SECRET_FILE=$temporary_directory/secrets/oidc
ARA_SESSION_SECRET_FILE=$temporary_directory/secrets/session
ARA_OWNER_SUBJECTS_FILE=$temporary_directory/secrets/owners
EOF

model="$temporary_directory/compose-model.yaml"
run_with_timeout 60s docker compose --project-directory "$repository_root" --env-file "$temporary_directory/.env" config --quiet
run_with_timeout 60s docker compose --project-directory "$repository_root" --env-file "$temporary_directory/.env" config >"$model"

grep -Fq '/app/data:rw' "$model"
grep -Fq '/certificates:ro' "$model"
grep -Fq 'condition: service_healthy' "$model"
grep -Fq 'internal: true' "$model"
for value in static-oidc-placeholder static-session-placeholder static-owner-placeholder; do
  if grep -Fq "$value" "$model"; then
    printf 'Secret value appeared in rendered Compose model.\n' >&2
    exit 1
  fi
done

printf 'Compose configuration validation passed.\n'
