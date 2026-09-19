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

## Source layout

- `src/app/core/` contains cross-cutting application configuration.
- `src/app/features/` contains routed features. Routes use `loadComponent` so
  features can be loaded lazily.
