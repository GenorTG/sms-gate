"""
Web UI for SMS Gate: admin auth, device credentials in session, full control over 3rdparty API.
POST /api/send remains public for Zapier/scripts.
"""
import json
import os
import re

from flask import (
    Flask,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    render_template,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from auth import (
    is_auth_enabled,
    get_secret_key,
    check_credentials,
    login_required,
    should_skip_auth,
)
from sms_gate_client import (
    get_token,
    post_message as client_post_message,
    get_devices,
    delete_device as client_delete_device,
    get_messages,
    get_message,
    get_logs,
    get_webhooks,
    post_webhook,
    delete_webhook as client_delete_webhook,
    get_settings,
    patch_settings,
    get_health_ready,
    SMS_GATE_BASE,
    API_BASE,
)

app = Flask(__name__)
app.secret_key = get_secret_key()

# Behind HTTPS reverse proxy: use X-Forwarded-Proto/Host so redirects use https and correct host
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


@app.context_processor
def inject_device_account_error():
    """Expose device-account validation error to base template."""
    err = session.pop("_device_account_error", None)
    return {"device_account_error": err}


def get_device_creds() -> tuple[str | None, str | None]:
    """Return (device_user, device_pass) from session or (None, None)."""
    return session.get("device_user"), session.get("device_pass")


# --- Auth: before_request and routes ---


@app.before_request
def require_login():
    if should_skip_auth(request.path):
        return
    if session.get("user") is None:
        return redirect(url_for("login", next=request.url))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not is_auth_enabled():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if check_credentials(username, password):
            session["user"] = username
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)
        return render_template("login.html", error="Invalid username or password", username=username)
    return render_template("login.html", error=None, username="")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login") if is_auth_enabled() else url_for("dashboard"))


@app.route("/device-account", methods=["POST"])
@login_required
def set_device_account():
    """Store device credentials in session; validate against API."""
    session["device_user"] = (request.form.get("device_user") or "").strip()
    session["device_pass"] = request.form.get("device_pass") or ""
    next_url = request.form.get("next") or request.referrer or url_for("dashboard")
    # Validate so user sees a clear error instead of "unauthorized" on next page
    if session["device_user"] and session["device_pass"]:
        _, err = get_token(session["device_user"], session["device_pass"])
        if err:
            session["_device_account_error"] = f"Device credentials rejected: {err}"
    return redirect(next_url)


# --- Dashboard ---


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


# --- Page routes (stubs; implemented in following steps) ---


@app.route("/send")
@login_required
def send_sms_page():
    return render_template("send_sms.html")


@app.route("/devices")
@login_required
def devices_page():
    devices = []
    error = session.pop("_devices_error", None)
    user, passwd = get_device_creds()
    if user and passwd:
        code, data = get_devices(user, passwd)
        if code == 200 and isinstance(data, list):
            devices = data
        elif isinstance(data, str):
            error = data
        else:
            error = str(data) if data else f"HTTP {code}"
    return render_template("devices.html", devices=devices, error=error)


@app.route("/devices/<device_id>/delete", methods=["POST"])
@login_required
def delete_device(device_id: str):
    user, passwd = get_device_creds()
    if not user or not passwd:
        return redirect(url_for("devices_page"))
    code, err = client_delete_device(device_id, user, passwd)
    if err:
        session["_devices_error"] = err
    return redirect(url_for("devices_page"))


@app.route("/messages", methods=["GET", "POST"])
@login_required
def messages_page():
    messages = []
    error = session.pop("_messages_error", None)
    success = session.pop("_messages_success", None)
    user, passwd = get_device_creds()
    if request.method == "POST" and request.form.get("action") == "enqueue":
        if not user or not passwd:
            session["_messages_error"] = "Set device credentials first."
            return redirect(url_for("messages_page"))
        phones_raw = (request.form.get("phone") or "").strip()
        text = (request.form.get("text") or "").strip()
        if not phones_raw or not text:
            session["_messages_error"] = "Phone and text required."
            return redirect(url_for("messages_page"))
        phones = [p.strip() for p in re.split(r"[\n,;]+", phones_raw) if p.strip()]
        if not phones:
            session["_messages_error"] = "Enter at least one phone number."
            return redirect(url_for("messages_page"))
        for p in phones:
            if not validate_phone(p):
                session["_messages_error"] = f"Invalid E.164 number: {p}"
                return redirect(url_for("messages_page"))
        code, data = client_post_message(user, passwd, phone_numbers=phones, text=text)
        if code in (200, 202):
            session["_messages_success"] = (
                f"Message enqueued to {len(phones)} recipient(s)." if len(phones) > 1 else "Message enqueued."
            )
        else:
            session["_messages_error"] = str(data) if isinstance(data, str) else data.get("message", str(data))
        return redirect(url_for("messages_page"))
    if user and passwd:
        from_ts = request.args.get("from") or None
        to_ts = request.args.get("to") or None
        limit = request.args.get("limit", type=int)
        code, data = get_messages(user, passwd, from_ts=from_ts, to_ts=to_ts, limit=limit)
        if code == 200 and isinstance(data, list):
            messages = data
        elif isinstance(data, str):
            error = error or data
        else:
            error = error or str(data) if data else f"HTTP {code}"
    return render_template("messages.html", messages=messages, error=error, success=success)


@app.route("/messages/<message_id>")
@login_required
def message_detail(message_id: str):
    user, passwd = get_device_creds()
    detail_str = None
    error = None
    if user and passwd:
        code, data = get_message(message_id, user, passwd)
        if code == 200 and isinstance(data, dict):
            detail_str = json.dumps(data, indent=2)
        else:
            error = str(data) if isinstance(data, str) else data.get("message", str(data)) if isinstance(data, dict) else f"HTTP {code}"
    return render_template("message_detail.html", message_id=message_id, detail_str=detail_str, error=error)


@app.route("/logs")
@login_required
def logs_page():
    entries = []
    error = None
    logs_unavailable_message = None  # Friendly message when cloud/server blocks logs
    user, passwd = get_device_creds()
    if user and passwd:
        from_ts = request.args.get("from") or None
        to_ts = request.args.get("to") or None
        code, data = get_logs(user, passwd, from_ts=from_ts, to_ts=to_ts)
        if code == 200 and isinstance(data, list):
            entries = data
        elif isinstance(data, str):
            if "privacy" in data.lower() or "not accessible" in data.lower() or "not available" in data.lower():
                logs_unavailable_message = (
                    "Logs are not available through the Cloud server for device privacy. "
                    "View logs in the Android app or when using a local server."
                )
            else:
                error = data
        else:
            raw = str(data) if data else f"HTTP {code}"
            if "privacy" in raw.lower() or "not accessible" in raw.lower():
                logs_unavailable_message = (
                    "Logs are not available through the Cloud server for device privacy. "
                    "View logs in the Android app or when using a local server."
                )
            else:
                error = raw
    return render_template(
        "logs.html",
        entries=entries,
        error=error,
        logs_unavailable_message=logs_unavailable_message,
    )


@app.route("/webhooks", methods=["GET", "POST"])
@login_required
def webhooks_page():
    webhooks = []
    error = session.pop("_webhooks_error", None)
    success = session.pop("_webhooks_success", None)
    user, passwd = get_device_creds()
    if request.method == "POST" and request.form.get("action") == "add":
        if not user or not passwd:
            session["_webhooks_error"] = "Set device credentials first."
            return redirect(url_for("webhooks_page"))
        url_val = (request.form.get("url") or "").strip()
        if not url_val:
            session["_webhooks_error"] = "URL required."
            return redirect(url_for("webhooks_page"))
        # API accepts one event per webhook; get list of selected event names
        selected_events = request.form.getlist("event") or []
        selected_events = [e.strip() for e in selected_events if e.strip()]
        device_id = (request.form.get("device_id") or "").strip() or None
        if not selected_events:
            session["_webhooks_error"] = "Select at least one event."
            return redirect(url_for("webhooks_page"))
        added = 0
        for event_name in selected_events:
            payload = {"url": url_val, "event": event_name}
            if device_id:
                payload["device_id"] = device_id
            code, data = post_webhook(user, passwd, payload)
            if code in (200, 201):
                added += 1
            else:
                err = str(data) if isinstance(data, str) else (data.get("message", str(data)) if isinstance(data, dict) else str(data))
                session["_webhooks_error"] = f"Event {event_name}: {err}"
                return redirect(url_for("webhooks_page"))
        if added:
            session["_webhooks_success"] = f"Added {added} webhook(s)."
        return redirect(url_for("webhooks_page"))
    if user and passwd:
        code, data = get_webhooks(user, passwd)
        if code == 200 and isinstance(data, list):
            webhooks = data
        elif isinstance(data, str):
            error = data
        else:
            error = str(data) if data else f"HTTP {code}"
    # Event picker: id, label, short payload description (per docs.sms-gate.app)
    webhook_events = [
        ("sms:received", "SMS received", "messageId, message, sender, recipient, receivedAt"),
        ("sms:data-received", "SMS data received", "messageId, data (base64), sender, receivedAt"),
        ("mms:received", "MMS received", "messageId, subject, size, sender, receivedAt"),
        ("sms:sent", "SMS sent", "messageId, recipient, sender, sentAt, partsCount"),
        ("sms:delivered", "SMS delivered", "messageId, recipient, deliveredAt"),
        ("sms:failed", "SMS failed", "messageId, recipient, reason, failedAt"),
        ("system:ping", "System ping", "health (healthcheck status)"),
    ]
    return render_template(
        "webhooks.html",
        webhooks=webhooks,
        error=error,
        success=success,
        webhook_events=webhook_events,
    )


@app.route("/webhooks/<webhook_id>/delete", methods=["POST"])
@login_required
def delete_webhook(webhook_id: str):
    user, passwd = get_device_creds()
    if not user or not passwd:
        return redirect(url_for("webhooks_page"))
    code, err = client_delete_webhook(webhook_id, user, passwd)
    if err:
        session["_webhooks_error"] = err
    return redirect(url_for("webhooks_page"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    settings_data = None
    error = session.pop("_settings_error", None)
    user, passwd = get_device_creds()
    if request.method == "POST" and request.form.get("action") == "patch":
        if not user or not passwd:
            session["_settings_error"] = "Set device credentials first."
            return redirect(url_for("settings_page"))
        patch_json = (request.form.get("patch_json") or "").strip()
        if not patch_json:
            session["_settings_error"] = "JSON body required."
            return redirect(url_for("settings_page"))
        try:
            payload = json.loads(patch_json)
        except json.JSONDecodeError as e:
            session["_settings_error"] = f"Invalid JSON: {e}"
            return redirect(url_for("settings_page"))
        code, data = patch_settings(user, passwd, payload)
        if code == 200:
            return redirect(url_for("settings_page"))
        session["_settings_error"] = str(data) if isinstance(data, str) else data.get("message", str(data)) if isinstance(data, dict) else str(data)
        return redirect(url_for("settings_page"))
    if user and passwd:
        code, data = get_settings(user, passwd)
        if code == 200 and isinstance(data, dict):
            settings_data = json.dumps(data, indent=2)
        elif isinstance(data, str):
            error = data
        else:
            error = str(data) if data else f"HTTP {code}"
    return render_template("settings.html", settings_data=settings_data, error=error)


@app.route("/health")
@login_required
def health_page():
    health_data = None
    error = None
    code, data = get_health_ready()
    if code == 200 and isinstance(data, dict):
        health_data = json.dumps(data, indent=2)
    elif isinstance(data, str):
        error = data
    else:
        error = str(data) if data else f"HTTP {code}"
    return render_template("health.html", health_data=health_data, error=error)


# --- API Request Builder (copy-pastable curl / fetch) ---

# Operations for the request builder: method, path (with :id placeholders), auth, and param definitions
API_BUILDER_OPERATIONS = [
    {
        "id": "auth-token",
        "label": "Get JWT token",
        "method": "POST",
        "path": "/api/3rdparty/v1/auth/token",
        "auth": "basic",
        "body": {"scopes": ["messages:send", "messages:read", "messages:list", "devices:list", "devices:delete", "logs:read", "webhooks:list", "webhooks:write", "webhooks:delete", "settings:read", "settings:write"], "ttl": 86400},
        "pathParams": [],
        "queryParams": [],
    },
    {"id": "devices-list", "label": "List devices", "method": "GET", "path": "/api/3rdparty/v1/devices", "auth": "bearer", "pathParams": [], "queryParams": []},
    {"id": "devices-delete", "label": "Delete device", "method": "DELETE", "path": "/api/3rdparty/v1/devices/:id", "auth": "bearer", "pathParams": [{"name": "id", "placeholder": "device ID"}], "queryParams": []},
    {"id": "messages-list", "label": "List messages", "method": "GET", "path": "/api/3rdparty/v1/messages", "auth": "bearer", "pathParams": [], "queryParams": [{"name": "from", "example": ""}, {"name": "to", "example": ""}, {"name": "limit", "example": "20"}]},
    {"id": "messages-get", "label": "Get message", "method": "GET", "path": "/api/3rdparty/v1/messages/:id", "auth": "bearer", "pathParams": [{"name": "id", "placeholder": "message ID"}], "queryParams": []},
    {
        "id": "messages-send",
        "label": "Send message",
        "method": "POST",
        "path": "/api/3rdparty/v1/messages",
        "auth": "bearer",
        "bodyTemplate": {"phoneNumbers": [], "textMessage": {"text": ""}},
        "pathParams": [],
        "queryParams": [],
    },
    {"id": "logs-list", "label": "List logs", "method": "GET", "path": "/api/3rdparty/v1/logs", "auth": "bearer", "pathParams": [], "queryParams": [{"name": "from", "example": ""}, {"name": "to", "example": ""}]},
    {"id": "webhooks-list", "label": "List webhooks", "method": "GET", "path": "/api/3rdparty/v1/webhooks", "auth": "bearer", "pathParams": [], "queryParams": []},
    {
        "id": "webhooks-add",
        "label": "Add webhook",
        "method": "POST",
        "path": "/api/3rdparty/v1/webhooks",
        "auth": "bearer",
        "bodyTemplate": {"url": "", "event": "sms:received"},
        "pathParams": [],
        "queryParams": [],
    },
    {"id": "webhooks-delete", "label": "Delete webhook", "method": "DELETE", "path": "/api/3rdparty/v1/webhooks/:id", "auth": "bearer", "pathParams": [{"name": "id", "placeholder": "webhook ID"}], "queryParams": []},
    {"id": "settings-get", "label": "Get settings", "method": "GET", "path": "/api/3rdparty/v1/settings", "auth": "bearer", "pathParams": [], "queryParams": []},
    {"id": "settings-patch", "label": "Patch settings", "method": "PATCH", "path": "/api/3rdparty/v1/settings", "auth": "bearer", "bodyTemplate": {}, "pathParams": [], "queryParams": []},
    {"id": "health-ready", "label": "Health ready", "method": "GET", "path": "/health/ready", "auth": "none", "pathParams": [], "queryParams": []},
]


@app.route("/api-builder")
@login_required
def api_builder_page():
    return render_template(
        "api_builder.html",
        operations=API_BUILDER_OPERATIONS,
        default_device_user=session.get("device_user") or "",
    )


# --- Send SMS: page and API (API stays public) ---


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


def validate_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(r"^\+?[0-9]{10,15}$", cleaned))


@app.route("/api/send", methods=["POST"])
def api_send():
    """
    Public endpoint: JSON or form with username, password (device), phone/phones, message.
    Accepts single "phone" or "phones" (array or comma/newline/semicolon-separated).
    """
    if request.is_json:
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        message = (data.get("message") or "").strip()
        phone = (data.get("phone") or "").strip()
        raw_phones = data.get("phones")
        if raw_phones is None:
            phones = [p.strip() for p in re.split(r"[\n,;]+", phone) if p.strip()] if phone else []
        elif isinstance(raw_phones, str):
            phones = [p.strip() for p in re.split(r"[\n,;]+", raw_phones) if p.strip()]
        else:
            phones = [str(p).strip() for p in raw_phones if str(p).strip()]
    else:
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        message = (request.form.get("message") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        phones = [p.strip() for p in re.split(r"[\n,;]+", phone) if p.strip()]

    if not username:
        return jsonify({"success": False, "error": "username is required"}), 400
    if not password:
        return jsonify({"success": False, "error": "password is required"}), 400
    if not phones:
        return jsonify({"success": False, "error": "phone or phones is required"}), 400
    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400
    for p in phones:
        if not validate_phone(p):
            return jsonify({"success": False, "error": f"phone must be E.164: {p}"}), 400

    status, body = client_post_message(
        username, password, phone_numbers=phones, text=message
    )
    if status == 202:
        return jsonify({"success": True, **body} if isinstance(body, dict) else {"success": True}), status
    err = body.get("error", body) if isinstance(body, dict) else body
    return jsonify({"success": False, "error": str(err)}), status


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4842"))
    app.run(host="0.0.0.0", port=port, debug=False)
