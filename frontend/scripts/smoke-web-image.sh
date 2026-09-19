#!/usr/bin/env bash
set -euo pipefail

image="ara-web-smoke:local"
network="ara-web-smoke-${RANDOM}${RANDOM}"
backend="ara-web-smoke-backend-${RANDOM}${RANDOM}"
web="ara-web-smoke-web-${RANDOM}${RANDOM}"
temporary_directory="$(mktemp -d)"
port="$(shuf -i 20000-40000 -n 1)"

cleanup() {
  docker rm -f "$web" "$backend" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  rm -rf "$temporary_directory"
}
trap cleanup EXIT

openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -keyout "$temporary_directory/tls.key" \
  -out "$temporary_directory/tls.crt" \
  -subj '/CN=localhost' \
  -addext 'subjectAltName=DNS:localhost' >/dev/null 2>&1

docker build --tag "$image" .
docker run --rm \
  --mount "type=bind,source=$temporary_directory,target=/certificates,readonly" \
  --entrypoint caddy "$image" validate --config /etc/caddy/Caddyfile --adapter caddyfile

cat >"$temporary_directory/backend.py" <<'PYTHON'
from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(
            {
                "path": self.path,
                "host": self.headers.get("Host"),
                "forwarded_for": self.headers.get("X-Forwarded-For"),
                "forwarded_host": self.headers.get("X-Forwarded-Host"),
                "forwarded_proto": self.headers.get("X-Forwarded-Proto"),
                "real_ip": self.headers.get("X-Real-IP"),
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


HTTPServer(("", 8000), Handler).serve_forever()
PYTHON

docker network create "$network" >/dev/null
docker run -d --name "$backend" --network "$network" --network-alias backend \
  --mount "type=bind,source=$temporary_directory/backend.py,target=/backend.py,readonly" \
  python:3.13.2-alpine python /backend.py >/dev/null
docker run -d --name "$web" --network "$network" -p "$port:443" \
  --mount "type=bind,source=$temporary_directory,target=/certificates,readonly" \
  "$image" >/dev/null

web_ready=false
for _ in $(seq 1 20); do
  if curl --silent --fail --insecure "https://localhost:$port/" >/dev/null; then
    web_ready=true
    break
  fi
  sleep 1
done

if [ "$web_ready" != true ]; then
  docker logs "$web"
  exit 1
fi

index="$(curl --silent --show-error --fail --insecure "https://localhost:$port/")"
deep_link="$(curl --silent --show-error --fail --insecure "https://localhost:$port/reservations/calendar")"
test "$deep_link" = "$index"
compression_headers="$(curl --silent --show-error --fail --insecure --dump-header - --output /dev/null \
  --header 'Accept-Encoding: gzip' "https://localhost:$port/")"
case "$compression_headers" in
  *[Cc]ontent-[Ee]ncoding:\ gzip*) ;;
  *) exit 1 ;;
esac

for path in '/api/health/live?probe=1' '/auth/session?return_to=%2F'; do
  if ! response=$(curl --silent --show-error --fail --insecure "https://localhost:$port$path"); then
    docker logs "$web"
    exit 1
  fi
  if [ -z "$response" ]; then
    docker logs "$web"
    exit 1
  fi
  python3 -c '
import json, sys
response = json.load(sys.stdin)
assert response["path"] == sys.argv[1]
assert response["host"] == sys.argv[2]
assert response["forwarded_for"]
assert response["forwarded_host"] == sys.argv[2]
assert response["forwarded_proto"] == "https"
assert response["real_ip"]
' "$path" "localhost:$port" <<<"$response"
done

docker run --rm --entrypoint sh "$image" -c '
  ! command -v node &&
  ! test -e /app &&
  ! test -e /srv/node_modules &&
  ! test -e /srv/synergy-mcp.json &&
  ! grep -R -q -E "@synergy-design-system/mcp|syn-mcp" /srv
'

printf 'Web image smoke checks passed.\n'
