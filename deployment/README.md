# Deployment

The root `compose.yaml` runs the API and Caddy web service. Only Caddy publishes
HTTPS (port `443` by default); the API is reachable only from Caddy on the
dedicated internal application network. Caddy additionally has an ingress-only
network for Docker's published-port routing, while the API has an unpublished
egress network so it can contact the configured OIDC issuer.

## Host setup

From the repository root, create local directories and three one-line secret
files, then make the data directory writable by the API image user (UID/GID
`10001`):

```sh
mkdir -p data certificates secrets
install -m 600 /dev/null secrets/oidc_client_secret secrets/session_secret secrets/owner_subjects
chown 10001:10001 data
chown 10001:10001 secrets/oidc_client_secret secrets/session_secret secrets/owner_subjects
chmod 700 secrets
chmod 600 secrets/oidc_client_secret secrets/session_secret secrets/owner_subjects
cp .env.example .env
```

Fill the empty secret files with, respectively, the OIDC client secret, a long random
session secret, and the comma- or newline-separated bootstrap Owner subjects.
They are Docker `file` secrets, mounted only in the backend at `/run/secrets`;
never place their values in `.env`, Compose environment entries, or source
files. Compose's local file-secret implementation retains host file access
permissions, so the UID `10001` ownership and mode `600` above are required for
the non-root backend to read them. `data`, `certificates`, `secrets`, and `.env`
are ignored by Git.

Place the complete certificate chain and unencrypted private key in
`certificates/tls.crt` and `certificates/tls.key`. Caddy reads this bind mount
read-only. Set `ARA_CERTIFICATE_DIR`, `CADDY_CERT_FILE`, and `CADDY_KEY_FILE`
in `.env` to use another directory or names. Ensure Docker can read both files;
the key should normally be mode `600` and owned by the account running Docker.
Set the non-secret public URL and OIDC settings in `.env` before startup.

## Start and observe

```sh
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs -f backend web
curl --fail --cacert certificates/tls.crt https://localhost/api/health/ready
```

`web` is started only after the backend image healthcheck is healthy. The API
entrypoint applies migrations before serving. Both services restart unless
explicitly stopped; the backend receives 30 seconds to stop its scheduler and
finish request shutdown, while Caddy receives 15 seconds for graceful proxy
shutdown. The deployment intentionally runs exactly one backend container and
one Uvicorn worker: its SQLite write model and in-process APScheduler are not
safe to scale horizontally.

## Persistence, backup, and maintenance

The exact data mount is `${ARA_DATA_DIR:-./data}:/app/data:rw`; `ara.db` and its
SQLite WAL/SHM files live on the host. Verify persistence after a replacement:

```sh
docker compose up -d --force-recreate backend
docker compose exec backend python -c "import sqlite3; print(sqlite3.connect('/app/data/ara.db').execute('select version_num from alembic_version').fetchone())"
```

Do not copy only `ara.db` while the service is running: SQLite WAL state can be
lost. Stop the backend first, or use a SQLite-consistent backup mechanism that
includes a checkpoint/online backup and its WAL files. Back up the data directory
and secret files securely; the database contains application data and the
secrets are not recoverable from Compose.

To rotate a secret, replace the relevant host secret file with restrictive
permissions and recreate the backend (`docker compose up -d --force-recreate
backend`). Rotation invalidates dependent OIDC/session material as appropriate.
Check backend logs and health after every rotation; do not use `docker compose
config` output or logs as a place to store secret values.

To replace a certificate, atomically install the new chain and key under the
configured names, then gracefully reload Caddy:

```sh
docker compose exec web caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Validate the new certificate before reload and retain the prior pair until the
reload succeeds. If key/certificate filenames change, update `.env` and recreate
the web container instead. Caddy cannot read certificate files outside its
read-only `/certificates` mount.

## Reproducible checks

`deployment/scripts/verify-compose.sh` renders and statically checks the
configuration using temporary placeholder files. `deployment/scripts/smoke-compose.sh`
builds and starts the complete deployment with temporary certificates and
placeholder secrets; it tests backend health through TLS/Caddy, confirms the
backend has no published port, verifies placeholders are absent from the model,
assets, and logs where practical, and proves SQLite persistence across backend
replacement. Both scripts remove their temporary deployment resources.
