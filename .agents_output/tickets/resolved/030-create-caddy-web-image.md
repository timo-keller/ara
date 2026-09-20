# 030 - Create Caddy web image

## Goal

Build Angular and serve it through a minimal Caddy runtime image.

## Scope

- Add the multi-stage Angular and Caddy Dockerfile.
- Serve static assets with SPA fallback and compression.
- Proxy `/api/*` and `/auth/*` to the backend.
- Load a custom certificate and key from `/certificates`.

## Acceptance Criteria

- The runtime image does not contain Node tooling or MCP packages.
- Angular deep links return the application entry point.
- API and auth requests preserve their expected paths and headers.
- Caddy starts with certificates from the mounted directory.

## Dependencies

- Ticket 021
- Ticket 023
