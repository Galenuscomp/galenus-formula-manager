#!/usr/bin/env bash
# One-time setup of Galenus Formula Manager on a fresh Ubuntu 24.04 DigitalOcean droplet.
# Run as root:  bash install.sh
# Safe to re-run: every step checks what already exists.
set -euo pipefail

REPO_SSH="git@github.com:Galenuscomp/galenus-formula-manager.git"
APP_DIR="/opt/galenus-formula-manager"
KEY="/root/.ssh/galenus_deploy"
DOMAIN="${DOMAIN:-galenus.info}"

[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo -i)"; exit 1; }
say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl ca-certificates ufw openssl python3 >/dev/null

if ! command -v docker >/dev/null; then
  say "Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi

say "Firewall: allowing SSH, HTTP and HTTPS only"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

if [ ! -d "$APP_DIR/.git" ]; then
  if [ ! -f "$KEY" ]; then
    say "Creating a read-only deploy key for GitHub"
    mkdir -p /root/.ssh && chmod 700 /root/.ssh
    ssh-keygen -t ed25519 -N "" -C "galenus-droplet" -f "$KEY" >/dev/null
    ssh-keyscan -t ed25519 github.com >> /root/.ssh/known_hosts 2>/dev/null
  fi
  echo
  echo "Add this key in GitHub: repository Settings > Deploy keys > Add deploy key"
  echo "(title: droplet, leave 'Allow write access' UNCHECKED):"
  echo
  cat "$KEY.pub"
  echo
  read -r -p "Press Enter after adding the key... " _
  say "Cloning the repository"
  GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes" git clone -q "$REPO_SSH" "$APP_DIR"
  git -C "$APP_DIR" config core.sshCommand "ssh -i $KEY -o IdentitiesOnly=yes"
fi
cd "$APP_DIR"

if [ ! -f .env ]; then
  say "Creating .env"
  cp .env.example .env
  chmod 600 .env
  read -r -s -p "Anthropic API key (input hidden, Enter to skip): " AKEY; echo
  python3 - "$DOMAIN" "$(openssl rand -hex 24)" "$AKEY" <<'PY'
import sys, re
domain, pg, akey = sys.argv[1:4]
p = ".env"
s = open(p).read()
s = re.sub(r"(?m)^DOMAIN=.*$", f"DOMAIN={domain}", s)
s = re.sub(r"(?m)^POSTGRES_PASSWORD=.*$", f"POSTGRES_PASSWORD={pg}", s)
if akey:
    s = re.sub(r"(?m)^ANTHROPIC_API_KEY=.*$", f"ANTHROPIC_API_KEY={akey}", s)
else:
    s = re.sub(r"(?m)^AI_PROVIDER=.*$", "AI_PROVIDER=none", s)
open(p, "w").write(s)
PY
fi

say "Checking DNS for $DOMAIN"
MYIP="$(curl -4 -fsS https://api.ipify.org || true)"
DNSIP="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)"
if [ -n "$MYIP" ] && [ "$MYIP" != "$DNSIP" ]; then
  echo "WARNING: $DOMAIN points to '${DNSIP:-nothing}', this server is $MYIP."
  echo "HTTPS will start working once the DNS A record points here (it retries automatically)."
fi

say "Building and starting (first build takes a few minutes)"
docker compose up -d --build

say "Waiting for the application"
for _ in $(seq 1 60); do
  docker compose exec -T app python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/healthz')" 2>/dev/null && break
  sleep 3
done

if ! docker compose exec -T app python -c "
from sqlalchemy import select, func
from app.db import session_factory
from app.models import User
with session_factory()() as db:
    raise SystemExit(0 if db.scalar(select(func.count()).select_from(User).where(User.role=='admin')) else 1)
" 2>/dev/null; then
  say "Create the first administrator"
  read -r -p "Admin e-mail: " AEMAIL
  read -r -p "Admin full name: " ANAME
  docker compose exec app python -m app.cli create-user --email "$AEMAIL" --name "$ANAME" --role admin
fi

say "Done: https://$DOMAIN"
echo "Updates later:  cd $APP_DIR && ./deploy/update.sh"
