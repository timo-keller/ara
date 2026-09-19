#!/usr/bin/env bash
# A bounded, local-only development launcher. Generated credentials/state stay .dev.
set -Eeuo pipefail

root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$root"
operation=${1:-up}
dev=.dev
env_file=$dev/dev.env
app_compose=(docker compose --project-name ara-dev --env-file "$env_file" -f compose.yaml -f compose.dev.yaml)
kc_compose=(docker compose --project-name ara-dev-keycloak --env-file "$env_file" -f compose.keycloak.dev.yaml)

die() { printf 'run-dev: %s\n' "$*" >&2; exit 1; }
short_timeout=${ARA_DEV_COMMAND_TIMEOUT_SECONDS:-120}
build_timeout=${ARA_DEV_BUILD_TIMEOUT_SECONDS:-1200}
run() { timeout "$short_timeout" "$@"; }
app() { run "${app_compose[@]}" "$@"; }
kc() { run "${kc_compose[@]}" "$@"; }
require_tools() { command -v docker >/dev/null || die 'Docker Compose is required'; run docker compose version >/dev/null || die 'Docker Compose v2 is required'; command -v openssl >/dev/null || die 'openssl is required'; command -v curl >/dev/null || die 'curl is required'; command -v python3 >/dev/null || die 'python3 is required'; command -v timeout >/dev/null || die 'timeout is required'; }
diagnostics() { app ps || true; kc ps || true; app logs --tail=80 || true; kc logs --tail=80 || true; }
trap 'result=$?; diagnostics; exit "$result"' ERR
wait_for() { local description=$1 command=$2 deadline=$((SECONDS + 180)) remaining attempt; while (( SECONDS < deadline )); do remaining=$((deadline - SECONDS)); attempt=$((remaining < 5 ? remaining : 5)); timeout --foreground --kill-after=2s "${attempt}s" bash -c "$command" >/dev/null 2>&1 && return; sleep 2; done; diagnostics; die "timed out waiting for $description"; }

prepare() {
  require_tools
  local port=${ARA_DEV_KEYCLOAK_PORT:-8080}
  [[ $port =~ ^[1-9][0-9]{0,4}$ && $port -le 65535 ]] || die 'ARA_DEV_KEYCLOAK_PORT must be a valid TCP port'
  [[ ${ARA_HTTPS_PORT:-443} == 443 ]] || die 'ARA_HTTPS_PORT must remain 443 (the local client redirect URI is https://localhost)'
  mkdir -p "$dev" "$dev/secrets" "$dev/certificates" "$dev/data" "$dev/keycloak"
  chmod 700 "$dev" "$dev/secrets"
  if [[ ! -f $dev/certificates/tls.crt || ! -f $dev/certificates/tls.key ]]; then
    run openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj /CN=localhost -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1' -keyout "$dev/certificates/tls.key" -out "$dev/certificates/tls.crt" >/dev/null 2>&1
  fi
  for secret in oidc_client_secret session_secret keycloak_admin_password owner_password group_admin_password user_password; do
    [[ -f $dev/secrets/$secret ]] || { umask 077; run openssl rand -base64 36 > "$dev/secrets/$secret"; }
  done
  # Keep the existing allowlist mechanism enabled without granting a local user;
  # the development Owner role is deliberately granted by the validated claim.
  [[ -f $dev/secrets/owner_subjects ]] || printf 'no-local-bootstrap-owner\n' > "$dev/secrets/owner_subjects"
  chmod 600 "$dev/secrets"/* "$dev/certificates/tls.key"
  [[ -f $env_file ]] || cat > "$env_file" <<EOF
ARA_PUBLIC_URL=https://localhost
ARA_DEV_UID=$(id -u)
ARA_DEV_GID=$(id -g)
ARA_HTTPS_PORT=443
ARA_DATA_DIR=./.dev/data
ARA_CERTIFICATE_DIR=./.dev/certificates
ARA_OIDC_CLIENT_SECRET_FILE=./.dev/secrets/oidc_client_secret
ARA_SESSION_SECRET_FILE=./.dev/secrets/session_secret
ARA_OWNER_SUBJECTS_FILE=./.dev/secrets/owner_subjects
ARA_OIDC_ISSUER_URL=http://localhost:${port}/realms/ara-dev
ARA_OIDC_BACKCHANNEL_URL=http://keycloak:8080/realms/ara-dev
ARA_OWNER_CLAIM_EXPRESSION=contains(realm_access.roles, 'ara-owner')
ARA_DEV_KEYCLOAK_PORT=${port}
ARA_DEV_KEYCLOAK_PUBLIC_URL=http://localhost:${port}
KEYCLOAK_ADMIN_USERNAME=admin
KEYCLOAK_ADMIN_PASSWORD=$(<"$dev/secrets/keycloak_admin_password")
EOF
  python3 - "$dev" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1]); secret=lambda n:(d/'secrets'/n).read_text().strip()
users = [('owner','owner@example.com','ara-owner','owner_password'),('group-admin','group-admin@example.com','ara-group-admin','group_admin_password'),('user','user@example.com','ara-user','user_password')]
mapper={'name':'realm roles in ID token','protocol':'openid-connect','protocolMapper':'oidc-usermodel-realm-role-mapper','config':{'claim.name':'realm_access.roles','jsonType.label':'String','multivalued':'true','access.token.claim':'true','id.token.claim':'true','userinfo.token.claim':'true'}}
realm={'realm':'ara-dev','enabled':True,'roles':{'realm':[{'name':r} for r in ('ara-owner','ara-group-admin','ara-user')]},'users':[{'username':u,'firstName':u.replace('-',' ').title(),'lastName':'Developer','enabled':True,'email':e,'emailVerified':True,'requiredActions':[],'realmRoles':[r],'credentials':[{'type':'password','value':secret(p),'temporary':False}]} for u,e,r,p in users]}
(d/'keycloak'/'ara-dev-realm.json').write_text(json.dumps(realm), encoding='utf8')
PY
}

network_up() { run docker network inspect ara-dev-oidc-backchannel >/dev/null 2>&1 || run docker network create --internal ara-dev-oidc-backchannel >/dev/null; }
up() { prepare; network_up; local port=${ARA_DEV_KEYCLOAK_PORT:-8080}; timeout "$build_timeout" "${kc_compose[@]}" up -d; wait_for Keycloak "curl --max-time 5 -fsS http://127.0.0.1:${port}/realms/ara-dev/.well-known/openid-configuration"; run python3 deployment/scripts/configure-dev-keycloak.py "$dev"; timeout "$build_timeout" "${app_compose[@]}" up --build -d; wait_for application "curl --max-time 5 -kfsS https://localhost/api/health/ready"; app exec -T backend python - < deployment/scripts/seed-dev.py; printf '\nARA: https://localhost\nLocal-only credentials:\n  owner | owner@example.com | %s\n  group-admin | group-admin@example.com | %s\n  user | user@example.com | %s\nKeycloak: http://localhost:%s\n' "$(<.dev/secrets/owner_password)" "$(<.dev/secrets/group_admin_password)" "$(<.dev/secrets/user_password)" "$port"; }
status() { prepare; app ps; kc ps; }
logs() { prepare; app logs --tail=100 "${@:2}"; kc logs --tail=100; }
down() { [[ -f $env_file ]] || exit 0; app down --remove-orphans; kc down; run docker network rm ara-dev-oidc-backchannel >/dev/null 2>&1 || true; }
reset() { [[ ${ARA_DEV_RESET_CONFIRM:-} == YES ]] || die 'reset removes .dev and ara-dev-keycloak-data; rerun with ARA_DEV_RESET_CONFIRM=YES'; down; run docker volume rm ara-dev-keycloak-data >/dev/null 2>&1 || true; rm -rf "$dev"; }
test() { up; run deployment/scripts/verify-compose.sh "$env_file"; local port=${ARA_DEV_KEYCLOAK_PORT:-8080}; curl --max-time 20 -kfsS https://localhost/api/health/live >/dev/null; curl --max-time 20 -fsS "http://127.0.0.1:${port}/realms/ara-dev/.well-known/openid-configuration" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issuer']=='http://localhost:${port}/realms/ara-dev'; assert d['authorization_endpoint'].startswith('http://localhost:${port}/')"; python3 deployment/scripts/oidc-dev-login.py owner "$(<.dev/secrets/owner_password)" owner@example.com owner; python3 deployment/scripts/oidc-dev-login.py group-admin "$(<.dev/secrets/group_admin_password)" group-admin@example.com group_admin; python3 deployment/scripts/oidc-dev-login.py user "$(<.dev/secrets/user_password)" user@example.com user; app up -d --force-recreate backend; wait_for backend-recreation "curl --max-time 5 -kfsS https://localhost/api/health/ready"; app exec -T backend python - < deployment/scripts/seed-dev.py; app exec -T backend python - <<'PY'
import asyncio
from sqlalchemy import text
from ara.infrastructure.database import create_engine
async def check():
 e=create_engine('sqlite+aiosqlite:////app/data/ara.db')
 async with e.connect() as c:
  assert await c.scalar(text("select count(*) from alembic_version")) == 1
  assert await c.scalar(text("select count(*) from groups where name='ARA Development'")) == 1
  group_id="(select id from groups where name='ARA Development')"
  assert await c.scalar(text(f"select count(*) from role_mappings where group_id={group_id}")) == 2
  assert await c.scalar(text(f"select count(*) from role_mappings where group_id={group_id} and enabled=1 and expression in (\"contains(realm_access.roles, 'ara-group-admin')\", \"contains(realm_access.roles, 'ara-user')\")")) == 2
 await e.dispose()
asyncio.run(check())
PY
printf 'health, discovery, authorization-code login, email claims, roles, migrations, persistence and seeded mappings verified.\n'; }
case "$operation" in up) up;; status) status;; logs) logs "$@";; test) test;; down) down;; reset) reset;; *) die 'usage: ./run-dev.sh [up|status|logs|test|down|reset]';; esac
