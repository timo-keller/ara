FROM node:22.22.3-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . ./
RUN npm run build:production && npm run verify:production-output

FROM caddy:2.10.2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist/ara-frontend/browser /srv

EXPOSE 443
