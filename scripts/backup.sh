#!/usr/bin/env bash
# =============================================================================
# Smena production backup: PostgreSQL dump + uploads archive.
#
#   ./scripts/backup.sh                       # uses ./.env, writes ./backups/
#   ENV_FILE=.env.production BACKUP_DIR=/opt/smena/backups ./scripts/backup.sh
#
# Guarantees:
#   * no secret is ever printed or written to the backup listing;
#   * non-zero exit on ANY failure (safe for cron);
#   * non-destructive: only reads (pg_dump inside the postgres container —
#     the password already lives in its environment, nothing is passed on the
#     command line where `ps` could see it).
# Restore procedure: docs/RESTORE.md.
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_DIR/compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env}"
BACKUP_DIR="${BACKUP_DIR:-$REPO_DIR/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")

if [ ! -f "$ENV_FILE" ]; then
  echo "backup: env file not found: $ENV_FILE" >&2
  exit 1
fi
mkdir -p "$BACKUP_DIR"

# The compose env file, not the shell, is the source of truth for the DB
# identity; take the last assignment of each key (same semantics compose uses).
DB_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
DB_NAME="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
: "${DB_USER:=smena}"
: "${DB_NAME:=smena}"

DB_DUMP="$BACKUP_DIR/smena-db-$STAMP.dump"
UP_TARBALL="$BACKUP_DIR/smena-uploads-$STAMP.tar.gz"

echo "[backup] postgres dump -> $DB_DUMP"
# -T: stream without a TTY; pg_dump runs INSIDE the container using its own
# POSTGRES_* environment (custom user/db from the same env file).
"${COMPOSE[@]}" exec -T postgres \
  pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$DB_DUMP"

echo "[backup] uploads archive -> $UP_TARBALL"
# The api container mounts the uploads volume at /data/uploads; streaming tar
# from it needs no extra container and never touches the DB.
"${COMPOSE[@]}" exec -T api \
  tar czf - -C /data/uploads . > "$UP_TARBALL"

# Integrity spot-checks: the dump must start with the PGDMP magic, the tar
# must list. Fail loudly rather than ship a corrupt "backup".
head -c 5 "$DB_DUMP" | grep -q PGDMP || { echo "backup: DB dump looks corrupt" >&2; exit 1; }
tar tzf "$UP_TARBALL" >/dev/null || { echo "backup: uploads archive looks corrupt" >&2; exit 1; }

# Cheap retention: keep the newest 14 of each kind.
ls -1t "$BACKUP_DIR"/smena-db-*.dump     2>/dev/null | tail -n +15 | xargs -r rm -f
ls -1t "$BACKUP_DIR"/smena-uploads-*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm -f

echo "[backup] done: $(du -h "$DB_DUMP" "$UP_TARBALL" | awk '{print $1" "$2}' | paste -sd' - ')"
