#!/bin/sh
# Backup for the Docker deployment (run on the server, e.g. daily from cron):
#   0 22 * * * cd /opt/arbuilders && ./scripts/backup_docker.sh >> backups/backup.log 2>&1
set -e
cd "$(dirname "$0")/.."
. ./.env
STAMP=$(date +%Y-%m-%d_%H%M)
docker compose exec -T db pg_dump -U "${DB_USER:-postgres}" -F c -Z 9 "${DB_NAME:-arbuilders}" > "backups/arbuilders_${STAMP}.dump"
# keep 30 days locally; copy offsite (Google Drive / S3 / another PC) with rclone if configured
find backups -name 'arbuilders_*.dump' -mtime +30 -delete
command -v rclone >/dev/null 2>&1 && rclone copy backups remote:arbuilders-backups --include 'arbuilders_*.dump' || true
echo "Backup done: backups/arbuilders_${STAMP}.dump"
