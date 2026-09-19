# ARA frontend

The ARA frontend is a standalone Angular application. It uses strict TypeScript
and template checking, ESLint, Prettier, and headless Vitest unit tests.

## Commands

```sh
npm install
npm run format:check
npm run lint
npm test
npm run build:development
npm run build:production
```

`npm start` runs the development server. Browser requests use the same-origin
`/api` and `/auth` paths; deployment infrastructure routes them to the backend
and identity provider. No environment-specific frontend origin is configured.

## Production container

Build the web image from this directory with `docker build -t ara-web .`. The
image builds from `package-lock.json` and its Caddy runtime contains only the
compiled application and Caddy configuration. It serves TLS on port 443 and
expects a read-only certificate mount at `/certificates`. By default it loads
`tls.crt` and `tls.key`; set `CADDY_CERT_FILE` and `CADDY_KEY_FILE` to use
different filenames in that directory. Caddy proxies the unchanged `/api/*`
and `/auth/*` paths to the Compose service named `backend` on port 8000.

Run `npm run smoke:web-image` to build the image and exercise the TLS mount,
SPA fallback, proxy paths and forwarding headers. It requires Docker, OpenSSL,
Curl, Python 3, and `shuf`.

Authentication uses the same-origin `/auth/session`, `/auth/login`, and
`/auth/logout` endpoints. The session response contains server-resolved effective
roles, which control visible navigation only; the API remains authoritative.
Unsafe same-origin requests send the `ara_csrf` double-submit cookie as
`X-CSRF-Token`.

## End-to-end tests

Run `npm run test:e2e` after `npm install` and `npx playwright install chromium`.
The command creates a temporary SQLite database, applies Alembic migrations,
seeds only deterministic fixture data, and starts local FastAPI, Angular, and a
minimal in-process OIDC provider. The provider generates an ephemeral signing
key and performs the normal authorization-code, ID-token validation, secure
cookie, CSRF, and server-side role-resolution flow; it uses no production
credentials. Playwright traces, screenshots, videos, and service logs are kept
under `test-results/` on failure (and logs after a run).

## Synergy Design System

The frontend uses the Synergy 2025 light theme globally. Its SICK Intl fonts
and the icons used by the application are bundled from local packages; the
browser does not fetch them from a CDN.

### Activate the Synergy MCP server in OpenCode

1. Run `npm install` in this `frontend/` directory to install the lockfile-pinned
   development dependency.
2. Quit OpenCode completely, then restart it from the repository root. OpenCode
   loads `.opencode/opencode.json` only when it starts.

The configuration starts the locally installed `syn-mcp` binary over stdio,
using `frontend/synergy-mcp.json` for Angular defaults. It does not use `npx`
and does not download packages when activated.

## Source layout

- `src/app/core/` contains cross-cutting application configuration.
- `src/app/features/` contains routed features. Routes use `loadComponent` so
  features can be loaded lazily.
