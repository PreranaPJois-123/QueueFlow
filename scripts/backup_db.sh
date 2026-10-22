#!/usr/bin/env sh
# Dump the QueueFlow PostgreSQL database from the running Compose stack.
# Usage (from the project root): ./scripts/backup_db.sh [backup_dir]
# Keeps the 7 most recent dumps. Copy dumps off the instance for real safety.
set -eu
DIR="${1:-./backups}"
mkdir -p "$DIR"
FILE="$DIR/queueflow-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose exec -T postgres pg_dump -U queueflow -d queueflow --no-owner | gzip > "$FILE"
[ -s "$FILE" ] || { echo "Backup failed: empty dump" >&2; rm -f "$FILE"; exit 1; }
ls -1t "$DIR"/queueflow-*.sql.gz | tail -n +8 | xargs -r rm -f
echo "Backup written: $FILE"
# Restore: gunzip -c FILE | docker compose exec -T postgres psql -U queueflow -d queueflow
