#!/usr/bin/env bash
# Pull the latest version and rebuild. Migrations run automatically on start.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
# Installs from before per-user AI settings have no SECRETS_KEY yet.
if ! grep -qE '^SECRETS_KEY=.+' .env || grep -q '^SECRETS_KEY=change-me' .env; then
  sed -i '/^SECRETS_KEY=/d' .env
  echo "SECRETS_KEY=$(openssl rand -hex 32)" >> .env
  echo "Added SECRETS_KEY to .env"
fi
docker compose up -d --build
docker image prune -f >/dev/null
echo "Updated to $(git log -1 --format='%h %s')"
