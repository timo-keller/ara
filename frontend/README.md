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
