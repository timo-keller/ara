# 037 - Add one-command Keycloak development environment

## Goal

Start and test a complete local ARA environment through one repository
entrypoint, including an independent Dockerized Keycloak identity provider.

## Scope

- Add an executable root-level `run-dev.sh` supporting `up` (the default),
  `status`, `logs`, `test`, `down`, and `reset`.
- Generate missing local TLS material, application secrets, directories, and
  ignored development configuration without replacing existing state.
- Build, migrate, start, and health-check the complete application with bounded
  waits and useful failure diagnostics.
- Run a pinned Keycloak image through a separate development Compose project.
  Do not attach it to ARA's internal `application`, `backend_egress`, or
  `web_ingress` networks.
- Publish Keycloak only on loopback at
  `http://localhost:${ARA_DEV_KEYCLOAK_PORT:-8080}` and persist its development
  state separately from ARA data.
- Import an idempotent `ara-dev` realm and confidential ARA client configured
  for the authorization-code flow, `https://localhost/auth/callback`, and the
  `https://localhost` web origin.
- Include Keycloak realm roles in the signed `realm_access.roles` claim.
- Create these deterministic, email-verified development users:

  | Username | Email | Keycloak realm role |
  | --- | --- | --- |
  | `owner` | `owner@example.com` | `ara-owner` |
  | `group-admin` | `group-admin@example.com` | `ara-group-admin` |
  | `user` | `user@example.com` | `ara-user` |

- Return `email` and `email_verified` OIDC claims and use email as visible
  identity where appropriate.
- Keep the public, strictly validated issuer at
  `http://localhost:${ARA_DEV_KEYCLOAK_PORT:-8080}/realms/ara-dev` while adding
  an optional backend-only OIDC backchannel setting. Connect only Keycloak and
  the backend to a separate, development-only OIDC backchannel network because
  Linux containers cannot reach a Docker port bound strictly to host loopback.
  The web container must not join this network.
- Use the backchannel only for server-side discovery, token, and JWKS requests;
  browser authorization and ID-token issuer validation must continue to use the
  public issuer. Production behavior must remain unchanged when it is absent.
- Address Keycloak by its private alias only on the OIDC backchannel network;
  do not expose that alias or network in production Compose.
- Retain the Owner subject allowlist and add an optional, validated Owner claim
  expression. Configure development to use
  `contains(realm_access.roles, 'ara-owner')`; either the allowlist or this
  expression may grant global Owner access.
- Fail configuration/startup for an invalid configured Owner expression rather
  than granting access or failing silently.
- Idempotently seed one local group named `ARA Development` outside production
  startup, with these mappings:
  - `contains(realm_access.roles, 'ara-group-admin')` to `group_admin`.
  - `contains(realm_access.roles, 'ara-user')` to `user`.
- Do not add unauthenticated development endpoints or include development seed
  tooling in production images.
- Keep the production Compose model unchanged and store generated development
  files under ignored `.dev/`.
- Print application URL, Keycloak URL, and local user credentials after
  successful startup.
- Preserve ARA and Keycloak data across normal restarts. Require explicit
  confirmation before `reset`, and remove only generated development state and
  development volumes.

## Acceptance Criteria

- From a fresh checkout, `./run-dev.sh` is the only command needed to prepare
  and start the local application when Docker Compose is installed.
- Keycloak runs in Docker without attachment to ARA's application, ingress, or
  egress networks. Its only shared connection is the dedicated development
  OIDC backchannel network with the backend, and all host-published development
  ports bind to `127.0.0.1`.
- The browser reaches Keycloak through `localhost`, while the backend reaches
  it through the dedicated private backchannel without weakening issuer
  validation.
- Real OIDC login, callback, token exchange, JWKS validation, session creation,
  and logout work locally.
- `owner@example.com` receives global Owner access through `ara-owner`.
- `group-admin@example.com` receives Group Admin access only to
  `ARA Development` through `ara-group-admin`.
- `user@example.com` receives User access only to `ARA Development` through
  `ara-user`.
- Repeated startup does not regenerate secrets or duplicate the seeded group or
  mappings.
- `test` verifies service health, OIDC discovery/login, API proxying,
  migrations, persistence, email claims, and all three role resolutions without
  production credentials.
- Generated credentials, certificates, realm output, databases, and Keycloak
  state are ignored by Git.
- Production Compose and production images contain neither Keycloak nor
  development credentials or seed tooling.
- Build, startup, health, test, and shutdown operations have bounded timeouts
  and actionable diagnostics.

## Dependencies

- Ticket 009
- Ticket 032
- Ticket 033
