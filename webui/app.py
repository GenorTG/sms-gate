"""
Minimal Web UI for SMS Gate: form (phone + message) and POST /api/send for Zapier.
Uses SMS_GATE_URL, SMS_GATE_USER, SMS_GATE_PASS from env to get JWT and send via sms-gate API.
"""
import os
import re
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

SMS_GATE_BASE = os.environ.get("SMS_GATE_URL", "http://server:3000").rstrip("/")
API_BASE = f"{SMS_GATE_BASE}/api/3rdparty/v1"
SMS_GATE_USER = os.environ.get("SMS_GATE_USER", "")
SMS_GATE_PASS = os.environ.get("SMS_GATE_PASS", "")

_http = requests.Session()


def get_token():
    """Obtain JWT from sms-gate using device credentials from env."""
    if not SMS_GATE_USER or not SMS_GATE_PASS:
        return None, "SMS_GATE_USER and SMS_GATE_PASS must be set"
    resp = _http.post(
        f"{API_BASE}/auth/token",
        auth=(SMS_GATE_USER, SMS_GATE_PASS),
        json={"scopes": ["messages:send"], "ttl": 86400},
        timeout=15,
    )
    if resp.status_code != 201:
        return None, resp.text or f"HTTP {resp.status_code}"
    data = resp.json()
    token = data.get("access_token")
    if not token:
        return None, "No access_token in response"
    return token, None


def send_sms(phone: str, message: str) -> tuple[int, dict]:
    """
    Get JWT and send SMS via sms-gate. Returns (status_code, json_body).
    """
    token, err = get_token()
    if err:
        return 503, {"success": False, "error": err}

    resp = _http.post(
        f"{API_BASE}/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"phoneNumbers": [phone], "textMessage": {"text": message}},
        timeout=15,
    )
    try:
        body = resp.json() if resp.content else {}
    except Exception:
        body = {"raw": resp.text or ""}
    if resp.status_code == 202:
        body["success"] = True
    else:
        body["success"] = False
        body.setdefault("error", resp.text or f"HTTP {resp.status_code}")
    return resp.status_code, body


@app.route("/")
def index():
    """Serve the send-SMS form."""
    return render_template_string(INDEX_HTML)


@app.route("/api/send", methods=["POST"])
def api_send():
    """
    Accept JSON { "phone": "+...", "message": "..." } or form data.
    Returns JSON with success/error.
    """
    if request.is_json:
        data = request.get_json() or {}
        phone = (data.get("phone") or "").strip()
        message = (data.get("message") or "").strip()
    else:
        phone = (request.form.get("phone") or "").strip()
        message = (request.form.get("message") or "").strip()

    if not phone:
        return jsonify({"success": False, "error": "phone is required"}), 400
    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400

    # Basic E.164-ish: allow + and digits
    if not re.match(r"^\+?[0-9]{10,15}$", re.sub(r"[\s\-\(\)]", "", phone)):
        return jsonify({"success": False, "error": "phone must be E.164 (e.g. +48123456789)"}), 400

    status, body = send_sms(phone, message)
    return jsonify(body), status


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Send SMS</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; max-width: 420px; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.25rem; margin-bottom: 1rem; }
    label { display: block; margin-top: 0.75rem; font-weight: 500; }
    input, textarea { width: 100%; padding: 0.5rem; margin-top: 0.25rem; border: 1px solid #ccc; border-radius: 4px; }
    textarea { min-height: 100px; resize: vertical; }
    button { margin-top: 1rem; padding: 0.6rem 1.2rem; background: #333; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
    button:hover { background: #555; }
    .message { margin-top: 1rem; padding: 0.5rem; border-radius: 4px; }
    .message.success { background: #e8f5e9; color: #2e7d32; }
    .message.error { background: #ffebee; color: #c62828; }
  </style>
</head>
<body>
  <h1>Send SMS</h1>
  <form id="form">
    <label for="phone">Phone number (E.164)</label>
    <input type="text" id="phone" name="phone" placeholder="+48123456789" required>
    <label for="msg">Message</label>
    <textarea id="msg" name="message" required></textarea>
    <button type="submit">Send</button>
  </form>
  <div id="out" class="message" style="display:none;"></div>
  <script>
    document.getElementById('form').onsubmit = async function(e) {
      e.preventDefault();
      const out = document.getElementById('out');
      out.style.display = 'none';
      const phone = document.getElementById('phone').value.trim();
      const message = document.getElementById('msg').value.trim();
      try {
        const r = await fetch('/api/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone, message })
        });
        const data = await r.json();
        out.style.display = 'block';
        out.className = 'message ' + (data.success ? 'success' : 'error');
        out.textContent = data.success ? 'Message enqueued.' : (data.error || JSON.stringify(data));
      } catch (err) {
        out.style.display = 'block';
        out.className = 'message error';
        out.textContent = err.message || 'Request failed';
      }
    };
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4842"))
    app.run(host="0.0.0.0", port=port, debug=False)
