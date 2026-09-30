#!/usr/bin/env sh
# Nightly backup: database dump + stored files (PDFs, logos). Run from the repository directory,
# e.g. cron: 30 2 * * * cd /opt/galenus-formula-manager && ./deploy/backup.sh /var/backups/galenus
# Keeps KEEP_DAYS days of backups (default 14). The backup stays on this server; copy it
# elsewhere too, or a lost server loses its backups with it.
set -eu
DEST="${1:?usage: backup.sh DEST_DIR}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DEST"
chmod 700 "$DEST"
docker compose exec -T db pg_dump -U fm -d fm --format=custom > "$DEST/db-$STAMP.dump"
docker compose run --rm --no-deps -T --entrypoint tar app czf - -C /data . > "$DEST/files-$STAMP.tar.gz"
find "$DEST" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'files-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
echo "Backup written to $DEST (db-$STAMP.dump, files-$STAMP.tar.gz)"
