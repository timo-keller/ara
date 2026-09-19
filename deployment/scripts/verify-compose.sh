#!/usr/bin/env bash
set -euo pipefail

repository_root="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
development_env=${1:-}
[[ -z $development_env || -f $development_env ]] || {
  printf 'Usage: %s .dev/dev.env\n' "$0" >&2
  exit 2
}
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

model="$temporary_directory/compose-model.json"
run_with_timeout 60s docker compose --project-directory "$repository_root" --env-file "$temporary_directory/.env" config --quiet
run_with_timeout 60s docker compose --project-directory "$repository_root" --env-file "$temporary_directory/.env" config --format json >"$model"

arguments=("$model")
if [[ -n $development_env ]]; then
  development_model="$temporary_directory/development-model.json"
  keycloak_model="$temporary_directory/keycloak-model.json"
  run_with_timeout 60s docker compose --project-directory "$repository_root" --env-file "$development_env" -f compose.yaml -f compose.dev.yaml config --format json >"$development_model"
  run_with_timeout 60s docker compose --project-directory "$repository_root" --env-file "$development_env" -f compose.keycloak.dev.yaml config --format json >"$keycloak_model"
  arguments+=("$development_model" "$keycloak_model")
fi

python3 - "${arguments[@]}" <<'PY'
import json
import sys

models = [json.load(open(path)) for path in sys.argv[1:]]
base = models[0]

def networks(model, service):
    value = model["services"][service].get("networks", {})
    return set(value if isinstance(value, dict) else value or [])

def fail(message):
    raise SystemExit(f"Compose topology validation failed: {message}")

def has_mount(service, target, read_only):
    return any(
        volume.get("target") == target
        and volume.get("read_only", False) is read_only
        for volume in base["services"][service].get("volumes", [])
    )

base_text = json.dumps(base)
if not has_mount("backend", "/app/data", False):
    fail("production backend data mount is not read-write")
if not has_mount("web", "/certificates", True):
    fail("production certificate mount is not read-only")
if base["services"]["web"].get("depends_on", {}).get("backend", {}).get("condition") != "service_healthy":
    fail("production web health dependency changed")
if base.get("networks", {}).get("application", {}).get("internal") is not True:
    fail("production application network is not internal")
for value in ("static-oidc-placeholder", "static-session-placeholder", "static-owner-placeholder"):
    if value in base_text:
        fail("secret value appeared in rendered production model")
for forbidden in ("keycloak", "oidc_backchannel", "ARA_OIDC_BACKCHANNEL_URL", "ARA_DEV_"):
    if forbidden in base_text:
        fail(f"production model contains {forbidden!r}")
if "keycloak" in base["services"]:
    fail("production model defines Keycloak")
if not {"application", "backend_egress"} <= networks(base, "backend"):
    fail("production backend networks changed")
if not {"application", "web_ingress"} <= networks(base, "web"):
    fail("production web networks changed")

if len(models) == 1:
    raise SystemExit

development, keycloak = models[1:]
if "oidc_backchannel" not in networks(development, "backend"):
    fail("development backend is missing the OIDC network")
if "oidc_backchannel" in networks(development, "web"):
    fail("web joined the OIDC network")
if networks(keycloak, "keycloak") != {"default", "oidc_backchannel"}:
    fail("Keycloak networks are not isolated")
if networks(keycloak, "keycloak") & {"application", "backend_egress", "web_ingress"}:
    fail("Keycloak joined an ARA application network")
oidc_members = {
    name
    for compose_model in (development, keycloak)
    for name in compose_model["services"]
    if "oidc_backchannel" in networks(compose_model, name)
}
if oidc_members != {"backend", "keycloak"}:
    fail(f"unexpected OIDC network members: {sorted(oidc_members)}")
ports = keycloak["services"]["keycloak"].get("ports", [])
if len(ports) != 1 or ports[0].get("host_ip") != "127.0.0.1":
    fail("Keycloak is not published only on loopback")
PY

if [[ -n $development_env ]]; then
  [[ $(run_with_timeout 20s docker network inspect --format '{{.Internal}}' ara-dev-oidc-backchannel) == true ]] || {
    printf 'Compose topology validation failed: OIDC backchannel is not internal.\n' >&2
    exit 1
  }
fi

printf 'Compose configuration validation passed.\n'
