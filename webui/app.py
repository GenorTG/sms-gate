"""
Minimal Web UI for SMS Gate: form (device user, pass, phone, message) and POST /api/send.
Credentials are never stored on the server; they are sent per request (form or API).
"""
import os
import re
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

SMS_GATE_BASE = os.environ.get("SMS_GATE_URL", "http://server:3000").rstrip("/")
API_BASE = f"{SMS_GATE_BASE}/api/3rdparty/v1"

_http = requests.Session()


def get_token(username: str, password: str):
    """Obtain JWT from sms-gate using the given device credentials."""
    if not username or not password:
        return None, "username and password are required"
    resp = _http.post(
        f"{API_BASE}/auth/token",
        auth=(username.strip(), password),
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


def send_sms(username: str, password: str, phone: str, message: str) -> tuple[int, dict]:
    """
    Get JWT with given credentials and send SMS via sms-gate. Returns (status_code, json_body).
    """
    token, err = get_token(username, password)
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


def validate_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(r"^\+?[0-9]{10,15}$", cleaned))


@app.route("/")
def index():
    """Serve the send-SMS form (username, password, phone, message)."""
    return render_template_string(INDEX_HTML)


@app.route("/api/send", methods=["POST"])
def api_send():
    """
    Accept JSON or form: username, password (device credentials), phone, message.
    Credentials are not stored; they are used only for this request.
    """
    if request.is_json:
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        phone = (data.get("phone") or "").strip()
        message = (data.get("message") or "").strip()
    else:
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        phone = (request.form.get("phone") or "").strip()
        message = (request.form.get("message") or "").strip()

    if not username:
        return jsonify({"success": False, "error": "username is required"}), 400
    if not password:
        return jsonify({"success": False, "error": "password is required"}), 400
    if not phone:
        return jsonify({"success": False, "error": "phone is required"}), 400
    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400
    if not validate_phone(phone):
        return jsonify({"success": False, "error": "phone must be E.164 (e.g. +48123456789)"}), 400

    status, body = send_sms(username, password, phone, message)
    return jsonify(body), status


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Send SMS</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; max-width: 440px; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.25rem; margin-bottom: 0.5rem; }
    .section { margin-top: 1.25rem; }
    .section:first-of-type { margin-top: 0; }
    .section-title { font-size: 0.9rem; font-weight: 600; color: #444; margin-bottom: 0.5rem; }
    label { display: block; margin-top: 0.75rem; font-weight: 500; }
    input, textarea { width: 100%; padding: 0.5rem; margin-top: 0.25rem; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem; }
    textarea { min-height: 100px; resize: vertical; }
    .save-row { margin-top: 0.75rem; display: flex; align-items: center; gap: 0.5rem; }
    .save-row input[type="checkbox"] { width: auto; margin: 0; }
    .save-row label { margin: 0; font-weight: normal; font-size: 0.9rem; }
    .hint { font-size: 0.8rem; color: #666; margin-top: 0.2rem; }
    button { margin-top: 1.25rem; padding: 0.6rem 1.2rem; background: #333; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }
    button:hover { background: #555; }
    .message { margin-top: 1rem; padding: 0.5rem; border-radius: 4px; }
    .message.success { background: #e8f5e9; color: #2e7d32; }
    .message.error { background: #ffebee; color: #c62828; }
  </style>
</head>
<body>
  <h1>Send SMS</h1>
  <p class="hint">Use device credentials from the Android app (Settings → Cloud Server). Not stored on the server.</p>

  <form id="form">
    <div class="section">
      <div class="section-title">1. Device credentials</div>
      <label for="user">Device username</label>
      <input type="text" id="user" name="username" placeholder="e.g. A1B2C3" autocomplete="username" required>
      <label for="pass">Device password</label>
      <input type="password" id="pass" name="password" placeholder="From Android app" autocomplete="current-password" required>
      <div class="save-row">
        <input type="checkbox" id="save" name="save">
        <label for="save">Save in this browser for next time (stored only on this device, not on the server)</label>
      </div>
    </div>

    <div class="section">
      <div class="section-title">2. Recipient and message</div>
      <label for="phone">Phone number (E.164)</label>
      <input type="text" id="phone" name="phone" placeholder="+48123456789" required>
      <label for="msg">Message</label>
      <textarea id="msg" name="message" placeholder="Your message..." required></textarea>
    </div>

    <button type="submit">Send SMS</button>
  </form>
  <div id="out" class="message" style="display:none;"></div>

  <script>
    (function() {
      var KEY = 'smsgate_device';
      var form = document.getElementById('form');
      var user = document.getElementById('user');
      var pass = document.getElementById('pass');
      var saveEl = document.getElementById('save');
      var phone = document.getElementById('phone');
      var msg = document.getElementById('msg');
      var out = document.getElementById('out');
      if (!form || !user || !pass || !saveEl || !phone || !msg || !out) return;

      try {
        var saved = localStorage.getItem(KEY);
        if (saved) {
          var o = JSON.parse(saved);
          if (o.u) user.value = o.u;
          if (o.p) pass.value = o.p;
          saveEl.checked = true;
        }
      } catch (e) {}

      form.onsubmit = async function(e) {
        e.preventDefault();
        if (saveEl.checked) {
          try { localStorage.setItem(KEY, JSON.stringify({ u: user.value, p: pass.value })); } catch (err) {}
        } else {
          try { localStorage.removeItem(KEY); } catch (err) {}
        }
        out.style.display = 'none';
        try {
          var r = await fetch('/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: user.value.trim(),
              password: pass.value,
              phone: phone.value.trim(),
              message: msg.value.trim()
            })
          });
          var data = await r.json();
          out.style.display = 'block';
          out.className = 'message ' + (data.success ? 'success' : 'error');
          out.textContent = data.success ? 'Message enqueued.' : (data.error || JSON.stringify(data));
        } catch (err) {
          out.style.display = 'block';
          out.className = 'message error';
          out.textContent = err.message || 'Request failed';
        }
      };
    })();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4842"))
    app.run(host="0.0.0.0", port=port, debug=False)
