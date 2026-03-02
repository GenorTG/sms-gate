#!/usr/bin/env bash
# Send an SMS via the SMS Gateway private server API.
# Run without arguments for interactive mode (prompts for login, password, number, message).
# Run with args: ./send-sms.sh "+79991234567" "Message text" (uses env SMSGATE_USER, SMSGATE_PASS).
#
# Device Username/Password: Android app → Settings → Cloud Server.

set -e

# Default: localhost (when running on the server). From another machine use: SMSGATE_BASE="https://stealth-dragon.tail793f98.ts.net/api/3rdparty/v1"
DEFAULT_BASE="http://127.0.0.1:3000/api/3rdparty/v1"
BASE="${SMSGATE_BASE:-$DEFAULT_BASE}"

# Defaults for interactive mode — set these to skip typing (press Enter to use)
DEFAULT_USER=""
DEFAULT_PASS=""
DEFAULT_PHONE=""
DEFAULT_MESSAGE=""


get_token() {
  local user="$1"
  local pass="$2"
  local out
  out=$(curl -s -w "\n%{http_code}" --connect-timeout 10 -X POST "${BASE}/auth/token" \
    -u "${user}:${pass}" \
    -H "Content-Type: application/json" \
    -d '{"scopes": ["messages:send"], "ttl": 86400}')
  local body
  body=$(echo "$out" | sed '$d')
  local code
  code=$(echo "$out" | tail -n1)
  if ! echo "$body" | grep -q "access_token"; then
    echo "HTTP $code"
    echo "$body"
    return 1
  fi
  sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' <<< "$body"
}

send_message() {
  local token="$1"
  local phone="$2"
  local text="$3"
  local text_esc
  text_esc=$(printf '%s' "$text" | sed 's/\\/\\\\/g; s/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
  local resp
  resp=$(curl -s -w "\n%{http_code}" -X POST "${BASE}/messages" \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    -d "{\"phoneNumbers\": [\"${phone}\"], \"textMessage\": {\"text\": \"${text_esc}\"}}")
  local http_code
  http_code=$(echo "$resp" | tail -n1)
  local body
  body=$(echo "$resp" | sed '$d')
  echo "$http_code"
  echo "$body"
}

# --- Interactive mode (no arguments) ---
if [[ $# -eq 0 ]]; then
  echo "SMS Gateway — send SMS via your private server"
  echo "Server: $BASE"
  echo ""
  read -rp "Username (from app)${DEFAULT_USER:+ [$DEFAULT_USER]}: " USER
  USER="${USER:-$DEFAULT_USER}"
  read -rsp "Password (from app)${DEFAULT_PASS:+ [set in script]}: " PASS
  echo ""
  PASS="${PASS:-$DEFAULT_PASS}"
  read -rp "Phone number (E.164)${DEFAULT_PHONE:+ [$DEFAULT_PHONE]}: " PHONE
  PHONE="${PHONE:-$DEFAULT_PHONE}"
  read -rp "Message${DEFAULT_MESSAGE:+ [$DEFAULT_MESSAGE]}: " TEXT
  TEXT="${TEXT:-$DEFAULT_MESSAGE}"
  echo ""

  if [[ -z "$USER" || -z "$PASS" || -z "$PHONE" || -z "$TEXT" ]]; then
    echo "Error: username, password, phone and message are required." >&2
    exit 1
  fi

  echo "Getting token..."
  TOKEN=$(get_token "$USER" "$PASS") || {
    echo "" >&2
    echo "Login failed. Server response:" >&2
    echo "$TOKEN" | sed 's/^/  /' >&2
    if echo "$TOKEN" | grep -q "HTTP 000"; then
      echo "" >&2
      echo "HTTP 000 = no response (connection failed). If you're on the server machine, try:" >&2
      echo "  SMSGATE_BASE=\"http://127.0.0.1:3000/api/3rdparty/v1\" $0" >&2
      echo "Or ensure 'tailscale serve 3000' is running and the hostname is reachable." >&2
    fi
    exit 1
  }
  echo "Sending SMS to $PHONE..."
  RESULT=$(send_message "$TOKEN" "$PHONE" "$TEXT")
  HTTP_CODE=$(echo "$RESULT" | head -n1)
  BODY=$(echo "$RESULT" | tail -n +2)
  if [[ "$HTTP_CODE" == "202" ]]; then
    echo "Message enqueued successfully."
    if command -v jq >/dev/null 2>&1; then echo "$BODY" | jq -r '.'; else echo "$BODY"; fi
  else
    echo "Request failed (HTTP $HTTP_CODE). Response:" >&2
    if command -v jq >/dev/null 2>&1; then echo "$BODY" | jq -r '.'; else echo "$BODY"; fi >&2
    exit 1
  fi
  exit 0
fi

# --- Non-interactive mode (args or env) ---
USER="${SMSGATE_USER}"
PASS="${SMSGATE_PASS}"
PHONE="${1}"
TEXT="${2}"

if [[ -z "$USER" || -z "$PASS" ]]; then
  echo "Usage (interactive): $0" >&2
  echo "Usage (with args):   SMSGATE_USER=... SMSGATE_PASS=... $0 <phone_e164> <message>" >&2
  echo "  e.g. SMSGATE_USER=abc SMSGATE_PASS=xyz $0 +79991234567 'Hello'" >&2
  echo "" >&2
  echo "Username/Password: Android app → Settings → Cloud Server." >&2
  exit 1
fi

if [[ -z "$PHONE" || -z "$TEXT" ]]; then
  echo "Usage: $0 <phone_e164> <message>" >&2
  echo "  Phone in E.164 format, e.g. +79991234567" >&2
  exit 1
fi

echo "Getting token..."
TOKEN=$(get_token "$USER" "$PASS") || {
  echo "" >&2
  echo "Login failed. Server response:" >&2
  echo "$TOKEN" | sed 's/^/  /' >&2
  if echo "$TOKEN" | grep -q "HTTP 000"; then
    echo "" >&2
    echo "HTTP 000 = no response. If on the server machine, try: SMSGATE_BASE=\"http://127.0.0.1:3000/api/3rdparty/v1\" $0 ..." >&2
  fi
  exit 1
}
echo "Sending SMS to $PHONE..."
RESULT=$(send_message "$TOKEN" "$PHONE" "$TEXT")
HTTP_CODE=$(echo "$RESULT" | head -n1)
BODY=$(echo "$RESULT" | tail -n +2)
if [[ "$HTTP_CODE" == "202" ]]; then
  echo "Message enqueued successfully."
  if command -v jq >/dev/null 2>&1; then echo "$BODY" | jq -r '.'; else echo "$BODY"; fi
else
  echo "Request failed (HTTP $HTTP_CODE). Response:" >&2
  if command -v jq >/dev/null 2>&1; then echo "$BODY" | jq -r '.'; else echo "$BODY"; fi >&2
  exit 1
fi
