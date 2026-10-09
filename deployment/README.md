# Deployment

The root `compose.yaml` runs the API and Caddy web service. Only Caddy publishes
HTTPS (port `443` by default); the API is reachable only from Caddy on the
dedicated internal application network. Caddy additionally has an ingress-only
network for Docker's published-port routing, while the API has an unpublished
egress network so it can contact the configured OIDC issuer and Webex.

## Local development

`../run-dev.sh` is the local-only entrypoint: it generates ignored `.dev/`
certificates, secrets, realm import, and data on its first `up`, then starts the
application and a separate pinned Keycloak Compose project.  Keycloak is bound
to loopback only and is intentionally not connected to an ARA network.  The
browser issuer remains `http://localhost:8080/realms/ara-dev`; the backend uses
the restricted `keycloak` service on a dedicated internal backchannel network
for discovery, token and JWKS requests only.  Use `./run-dev.sh test` for the bounded local verification and
`./run-dev.sh down` to stop while retaining state.  `reset` requires
`ARA_DEV_RESET_CONFIRM=YES` and removes only generated state and the local
Keycloak volume.

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

## Optional Webex bot notifications

Create an ARA bot at <https://developer.webex.com/my-apps/new/bot>. Store only its
token in the ignored `secrets/webex_bot_token` file (no `Bearer` prefix or quotes).
For production, use the same UID `10001` ownership and mode `600` as the other
backend secrets. Enable the optional secret mount with:

```sh
docker compose -f compose.yaml -f compose.webex.yaml up --build -d
```

`ARA_WEBEX_BOT_TOKEN_FILE` on the host may override the source file path. Inside
the backend it is always mounted at `/run/secrets/webex_bot_token`. Use both
Compose files for subsequent recreation and token rotation. Without the overlay,
Webex is disabled and no token file is required.

The local launcher automatically enables Webex when `secrets/webex_bot_token`
exists, falling back to `.dev/secrets/webex_bot_token` if the default file is
absent. Keep the file owned by your local user with mode `600`, then run:

```sh
./run-dev.sh up
```

No Webex enablement flag is needed. If the token file is absent, the launcher
starts the app without Webex. After adding or removing the file, run
`./run-dev.sh up` again to recreate the backend with the matching configuration.
`ARA_WEBEX_BOT_TOKEN_FILE` may override the source path in `.dev/dev.env` or the
host environment (for example, `./.dev/secrets/webex_bot_token`); detection uses
that path instead. A missing custom path disables Webex. A present but empty or
unreadable token file is a configuration error, rather than silently disabling
Webex.

The local Keycloak sample users have example email addresses; real
personal delivery requires the user's OIDC email to identify their Webex account.

In **Group administration**, add **ARA Notification Bot** to the intended group
space, copy its Webex space link (`webexteams://im?space=<UUID>`), paste it into
**Webex space link**, and select **Save space link**. ARA resolves the space through
the bot's room list and keeps its canonical room ID and link. If the space is not
visible, add the bot and try again. Missing/invalid tokens, rate limits, and Webex
outages produce actionable errors and preserve the previous configuration.
Lookups stop after 20 pages or 30 seconds; retry after transient failures.
Existing group room-ID configurations remain active. Clearing and saving the link
disables room notifications without affecting personal messages.
Use **Send test message** to verify the saved configuration, even if the input has
unsaved edits. Tests are queued; **Refresh delivery status**
shows pending, delivered, failed, or skipped outcomes and safe error categories.
Owners and responsible Group Admins can manage this configuration. Role mappings
and group lifecycle administration remain Owner-only.

Room messages announce reservation starts and explicit returns. Each asset's
**Send group-room notifications** checkbox defaults on and can suppress them.
Personal reminders use the reserving user's OIDC email and are independent of
the room and checkbox. Personal start messages apply only to reservations
originally scheduled for the future. Existing asset-level room IDs are discarded
by migration; configure rooms afresh on groups.

The dispatcher runs every 15 seconds in bounded batches of 20. Future-start
catch-up is limited to one hour and excludes reservations already ended; end
reminders catch up for at most 24 hours. Transient failures retry up to six
attempts with exponential backoff; rate limits honor `Retry-After`. Invalid bot
tokens pause all dispatch for 15 minutes and are visible as failed deliveries.
Fix the token and recreate the backend; send another test to verify it. Terminal
failures are not automatically replayed. Completed outbox records are retained
for 30 days and cleaned in batches.

Queue entries are deduplicated locally. If Webex accepts a POST but the response
is lost (or ARA crashes before saving success), retrying can duplicate the remote
message. Delivered means Webex accepted the message, not that the recipient
read it or received a desktop alert. This integration is outbound-only; receiving
bot replies/webhooks is outside this feature.

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

`deployment/scripts/verify-compose.sh` renders and checks the production Compose
model, including secret redaction, mount modes, health dependency, and internal
networking. `deployment/scripts/verify-compose.sh .dev/dev.env` additionally
checks the local Keycloak topology and the live OIDC backchannel network; this
form is run by `run-dev.sh test`.
`deployment/scripts/smoke-compose.sh`
builds and starts the complete deployment with temporary certificates and
placeholder secrets; it tests backend health through TLS/Caddy, confirms the
backend has no published port, verifies placeholders are absent from the model,
assets, and logs where practical, and proves SQLite persistence across backend
replacement. Both scripts remove their temporary deployment resources.
