#!/usr/bin/env bash
# Interactive install: generate secrets, write config.yml and .env, run docker compose.
# Device credentials are not stored; enter them in the Web UI or send them in each API request.

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

# --- Main install ---
check_prereqs

# Detect if our stack is already running
STACK_UP=false
if docker compose ps 2>/dev/null | grep -q "Up"; then
  STACK_UP=true
fi

if [[ "$STACK_UP" = true ]]; then
  echo "SMS Gate stack is already running."
  echo "  (U)pdate  — keep database, config, and .env; rebuild images and restart (no re-register phones, no data loss)"
  echo "  (R)einstall — remove everything (containers + volumes), regenerate config and secrets, fresh install"
  echo "  (N)othing — exit without changes"
  read -rp "Choose [U/r/N]: " CHOICE
  CHOICE="${CHOICE:-u}"
  case "${CHOICE,,}" in
    u)
      echo ""
      echo "=== Update (keep data & config) ==="
      echo "Rebuilding images and restarting containers. config.yml, .env, and database are unchanged."
      echo ""
      docker compose build --no-cache
      docker compose up -d
      echo "Waiting for services (up to 60s)..."
      for i in {1..60}; do
        if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4841/health/ready 2>/dev/null | grep -q 200; then
          echo ""
          break
        fi
        sleep 1
        printf "."
      done
      echo ""
      echo "Recent logs:"
      docker compose logs --tail=15
      echo ""
      echo "=== Update complete ==="
      echo "  API:    http://localhost:4841"
      echo "  Web UI: http://localhost:4842"
      echo ""
      exit 0
      ;;
    r)
      echo "Stopping and removing containers and volumes..."
      docker compose down -v
      echo "Done. Reinstalling from scratch..."
      ;;
    *)
      echo "Exiting. No changes made."
      exit 0
      ;;
  esac
elif [[ -f config.yml ]]; then
  echo "config.yml already exists (stack not running)."
  echo "  (S)tart — bring up existing stack (no overwrite)"
  echo "  (O)verwrite — regenerate config and .env, then install from scratch"
  echo "  (N)othing — exit"
  read -rp "Choose [S/o/N]: " CHOICE
  CHOICE="${CHOICE:-s}"
  case "${CHOICE,,}" in
    s)
      echo ""
      echo "Starting existing stack..."
      docker compose up -d
      echo "Waiting for services (up to 60s)..."
      for i in {1..60}; do
        if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4841/health/ready 2>/dev/null | grep -q 200; then
          echo ""
          break
        fi
        sleep 1
        printf "."
      done
      echo ""
      echo "Stack started. API: http://localhost:4841  Web UI: http://localhost:4842"
      exit 0
      ;;
    o)
      echo "Overwriting and reinstalling..."
      ;;
    *)
      echo "Exiting."
      exit 0
      ;;
  esac
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
escape_sed() { printf '%s' "$1" | sed 's/[&\]/\\&/g'; }
apply_sed() { sed "s|$1|$2|g" config.yml > config.yml.tmp && mv config.yml.tmp config.yml; }
apply_sed "your-db-password" "$(escape_sed "$DB_PASS")"
apply_sed "your-private-token" "$(escape_sed "$PRIVATE_TOKEN")"
apply_sed "your-jwt-secret-base64" "$(escape_sed "$JWT_SECRET")"

# 5. Write .env and Web UI admin credentials (default username: admin)
cat > .env << EOF
DB_PASSWORD=$DB_PASS
EOF
read -rp "Web UI admin username [admin]: " WEBUI_USER
WEBUI_USER="${WEBUI_USER:-admin}"
read -rsp "Web UI admin password (leave empty to disable login): " WEBUI_PASS
echo ""
if [[ -n "$WEBUI_USER" && -n "$WEBUI_PASS" ]]; then
  WEBUI_SECRET=$(openssl rand -hex 24)
  echo "WEBUI_ADMIN_USER=$WEBUI_USER" >> .env
  echo "WEBUI_ADMIN_PASSWORD=$WEBUI_PASS" >> .env
  echo "WEBUI_SECRET_KEY=$WEBUI_SECRET" >> .env
  echo "Web UI login enabled (admin user: $WEBUI_USER). Save your password."
else
  echo "Web UI login disabled (no admin user set)."
fi
echo ""

# 6. Build (no cache) and start stack
echo "Building images (no cache, fresh install)..."
docker compose build --no-cache
echo "Starting Docker stack..."
docker compose up -d

echo "Waiting for services (up to 60s)..."
for i in {1..60}; do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4841/health/ready 2>/dev/null | grep -q 200; then
    echo ""
    break
  fi
  sleep 1
  printf "."
done
echo ""

echo "Recent logs:"
docker compose logs --tail=20
echo ""

# 7. Success message
echo "=== Setup complete ==="
echo ""
echo "Server is running."
echo "  API:    http://localhost:4841"
echo "  Web UI: http://localhost:4842"
echo ""
echo "Private token (save for Android app): $PRIVATE_TOKEN"
echo ""
echo "Next steps:"
echo "  1. Connect your Android app: Settings -> Cloud Server."
echo "     API URL: your server URL + /api/mobile/v1 (e.g. https://your-host/api/mobile/v1)"
echo "     Private token: (the token above)"
echo "  2. Open the Web UI: http://localhost:4842"
echo "     If you set a Web UI admin user, log in first. Then set 'Device account' (sms-gate device username/password from the app) to use Devices, Messages, Logs, Webhooks, Settings. Send SMS works from the Web UI or via POST /api/send (public, for Zapier)."
echo ""
echo "Quick check: curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4841/health/ready  (expect 200)"
echo ""
