#!/bin/sh
set -eu

# Validate all required runtime configuration before mutating the database or
# starting Uvicorn.  Alembic then fails the container before the API is served
# if the database is unavailable or a migration cannot be applied.
python -c 'from ara.core.config import get_settings; get_settings()'
alembic upgrade head

# Do not add reload or additional workers: the application lifespan owns the
# single in-process scheduler.  exec makes Uvicorn PID 1 for signal handling.
exec uvicorn ara.main:app --host 0.0.0.0 --port 8000 --workers 1
