#!/usr/bin/env bash
# Interactive install: generate secrets, write config.yml and .env, run docker compose.
# After Android app connects, run: ./install-and-run-sms-gate-server.sh --set-credentials

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# --- Prereqs ---
check_prereqs() {
  if ! command -v docker &>/dev/null; then
    echo "Error: docker is not installed or not in PATH." >&2
    exit 1
  fi
  if ! docker compose version &>/dev/null && ! command -v docker-compose &>/dev/null; then
    echo "Error: docker compose (or docker-compose) is not available." >&2
    exit 1
  fi
  if [[ ! -f docker-compose.yml ]] || [[ ! -f config.example.yml ]]; then
    echo "Error: run this script from the repo root (where docker-compose.yml and config.example.yml are)." >&2
    exit 1
  fi
}

# --- --set-credentials mode ---
set_credentials() {
  echo "Web UI credentials (from Android app: Settings -> Cloud Server, after device is connected)."
  read -rp "Device username (from app): " SMS_USER
  read -rsp "Device password (from app): " SMS_PASS
  echo ""
  [[ -n "$SMS_USER" && -n "$SMS_PASS" ]] || { echo "Username and password are required." >&2; exit 1; }

  # Preserve existing DB_PASSWORD if .env exists
  DB_LINE=""
  if [[ -f .env ]]; then
    DB_LINE=$(grep -E '^DB_PASSWORD=' .env 2>/dev/null || true)
  fi
  if [[ -z "$DB_LINE" ]]; then
    DB_LINE="DB_PASSWORD=root"
  fi

  cat > .env << EOF
$DB_LINE
SMS_GATE_USER=$SMS_USER
SMS_GATE_PASS=$SMS_PASS
EOF
  echo "Credentials saved to .env. Restarting webui..."
  docker compose up -d webui
  echo "Web UI credentials updated and webui restarted."
  exit 0
}

[[ "${1:-}" = "--set-credentials" ]] && check_prereqs && set_credentials

# --- Main install ---
check_prereqs

if [[ -f config.yml ]]; then
  read -rp "config.yml already exists. Overwrite and reinstall? (y/N): " OVERWRITE
  [[ "${OVERWRITE,,}" = "y" || "${OVERWRITE,,}" = "yes" ]] || exit 0
fi

echo ""
echo "=== SMS Gate install ==="
echo ""

# 1. Generate JWT
JWT_SECRET=$(openssl rand -base64 32)
echo "JWT secret generated and saved to config."

# 2. Generate private token
PRIVATE_TOKEN=$(openssl rand -hex 24)
echo "Private token generated; save it for the Android app: $PRIVATE_TOKEN"
echo ""

# 3. DB password
read -rp "Database password (press Enter for 'root'): " DB_PASS
DB_PASS="${DB_PASS:-root}"

# 4. Write config.yml (sed with | delimiter to avoid breaking on / and + in JWT)
cp config.example.yml config.yml
# Escape & for sed replacement (safe for base64 and hex)
escape_sed() { printf '%s' "$1" | sed 's/[&\]/\\&/g'; }
apply_sed() { sed "s|$1|$2|g" config.yml > config.yml.tmp && mv config.yml.tmp config.yml; }
apply_sed "your-db-password" "$(escape_sed "$DB_PASS")"
apply_sed "your-private-token" "$(escape_sed "$PRIVATE_TOKEN")"
apply_sed "your-jwt-secret-base64" "$(escape_sed "$JWT_SECRET")"

# 5. Write .env
cat > .env << EOF
DB_PASSWORD=$DB_PASS
SMS_GATE_USER=
SMS_GATE_PASS=
EOF
echo "Created .env (Web UI credentials will be added after you connect the Android app)."
echo ""

# 6. Start stack
echo "Starting Docker stack..."
docker compose up -d

echo "Waiting for services (up to 60s)..."
for i in {1..60}; do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/health 2>/dev/null | grep -q 200; then
    echo ""
    break
  fi
  sleep 1
  printf "."
done
echo ""

# Show recent logs
echo "Recent logs:"
docker compose logs --tail=20
echo ""

# 7. Success message
echo "=== Setup complete ==="
echo ""
echo "Server is running."
echo "  API:    http://localhost:3000"
echo "  Web UI: http://localhost:4842"
echo ""
echo "Private token (save for Android app): $PRIVATE_TOKEN"
echo ""
echo "Next steps:"
echo "  1. Connect your Android app: Settings -> Cloud Server."
echo "     API URL: your server URL + /api/mobile/v1 (e.g. https://your-host/api/mobile/v1)"
echo "     Private token: (the token above)"
echo "  2. After the app shows Username and Password, run:"
echo "     ./install-and-run-sms-gate-server.sh --set-credentials"
echo ""
