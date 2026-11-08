#!/usr/bin/env bash
# =============================================================================
# Smena production deploy (safe subset): rebuild images, rolling restart.
#
#   ./scripts/deploy.sh                  # requires a clean checkout at the
#                                        # commit you want (do `git pull
#                                        # --ff-only` explicitly, see below)
#
# What it deliberately does NOT do:
#   * never removes volumes / databases (no `down`, never `-v`);
#   * never runs `git pull` implicitly — you choose the ref you deploy
#     (release tags: docs/VK_CLOUD_DEPLOY.md);
#   * never downgrades migrations (alembic only goes forward at api start).
#
# Flow: compose config -> build -> up -d -> ps. Migrations are applied by the
# api entrypoint (single instance, retrying while postgres warms up).
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_DIR/compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env}"
COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")

if [ ! -f "$ENV_FILE" ]; then
  echo "deploy: env file not found: $ENV_FILE (cp .env.production.example .env)" >&2
  exit 1
fi
if [ -n "$(git -C "$REPO_DIR" status --porcelain)" ]; then
  echo "deploy: working tree is dirty — commit or stash first; deploying" >&2
  echo "        uncommitted state makes rollbacks impossible." >&2
  exit 1
fi

echo "[deploy] validating compose configuration..."
"${COMPOSE[@]}" config >/dev/null

echo "[deploy] building images..."
"${COMPOSE[@]}" build

echo "[deploy] restarting services (volumes are never touched)..."
"${COMPOSE[@]}" up -d

# `up -d` returns before health checks settle; wait instead of lying.
echo "[deploy] waiting for the stack to become healthy (up to 3 min)..."
deadline=$((SECONDS + 180))
while [ "$SECONDS" -lt "$deadline" ]; do
  unhealthy="$("${COMPOSE[@]}" ps --format '{{.Name}} {{.Status}}' \
    | grep -v -E 'healthy|running' || true)"
  if [ -z "$unhealthy" ]; then break; fi
  sleep 5
done

"${COMPOSE[@]}" ps
echo
echo "[deploy] next: ./scripts/production_smoke.sh https://\$APP_DOMAIN"
