#!/bin/sh
# Container entrypoint: apply migrations (retrying while PostgreSQL warms up),
# then hand over to uvicorn via exec (PID 1 signal handling).
set -eu

echo "[entrypoint] applying database migrations..."
retries=0
until alembic upgrade head; do
    retries=$((retries + 1))
    if [ "$retries" -ge 15 ]; then
        echo "[entrypoint] migrations still failing after 15 attempts — giving up" >&2
        exit 1
    fi
    echo "[entrypoint] database not ready; retry $retries/15 in 2s..." >&2
    sleep 2
done

echo "[entrypoint] starting API on ${API_HOST:-0.0.0.0}:${API_PORT:-8000}"
exec uvicorn smena_api.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"
