#!/usr/bin/env bash
# Pull the latest version and rebuild. Migrations run automatically on start.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose up -d --build
docker image prune -f >/dev/null
echo "Updated to $(git log -1 --format='%h %s')"
