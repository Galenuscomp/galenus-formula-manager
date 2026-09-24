#!/usr/bin/env sh
# Nightly backup: database dump + stored PDFs. Run from the repository directory,
# e.g. cron: 30 2 * * * cd /opt/formula-manager && ./deploy/backup.sh /backups
set -eu
DEST="${1:?usage: backup.sh DEST_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DEST"
docker compose exec -T db pg_dump -U fm -d fm --format=custom > "$DEST/db-$STAMP.dump"
docker compose run --rm --no-deps -T --entrypoint tar app czf - -C /data . > "$DEST/files-$STAMP.tar.gz"
echo "Backup written to $DEST (db-$STAMP.dump, files-$STAMP.tar.gz)"
