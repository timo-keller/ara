# ARA

ARA (Asset Reservation & Allocation) is an internal web application for
managing reservable assets.

## Repository layout

- `backend/` contains the FastAPI application. Python source belongs below
  `backend/src/ara`.
- `frontend/` contains the Angular single-page application and its TypeScript
  source.
- `deployment/` contains deployment-specific configuration and operational
  assets that do not belong to either application.
- `compose.yaml` is the Docker Compose entry point for the complete
  deployment.

The architecture decisions and implementation tickets are recorded in
`.agents_output/`.

## Local prerequisites

- Python and [uv](https://docs.astral.sh/uv/) for backend development
- Node.js and npm for frontend development
- Docker Engine with Docker Compose for container deployment

## Standard commands

Run commands from the relevant application directory after its tooling has
been bootstrapped:

```sh
# Backend
cd backend
uv sync
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest

# Frontend
cd frontend
npm install
npm run lint
npm test
npm run build

# Complete deployment (from the repository root)
docker compose config
docker compose up --build
```

Deployment-specific setup, including local data, certificates, and Docker
secret files, will be documented under `deployment/`. These local files must
not be committed.
