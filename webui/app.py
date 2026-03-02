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
    """Store device credentials in session for API calls."""
    session["device_user"] = (request.form.get("device_user") or "").strip()
    session["device_pass"] = request.form.get("device_pass") or ""
    next_url = request.form.get("next") or request.referrer or url_for("dashboard")
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
        phone = (request.form.get("phone") or "").strip()
        text = (request.form.get("text") or "").strip()
        if not phone or not text:
            session["_messages_error"] = "Phone and text required."
            return redirect(url_for("messages_page"))
        if not validate_phone(phone):
            session["_messages_error"] = "Phone must be E.164."
            return redirect(url_for("messages_page"))
        code, data = client_post_message(user, passwd, phone_numbers=[phone], text=text)
        if code in (200, 202):
            session["_messages_success"] = "Message enqueued."
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
    user, passwd = get_device_creds()
    if user and passwd:
        from_ts = request.args.get("from") or None
        to_ts = request.args.get("to") or None
        code, data = get_logs(user, passwd, from_ts=from_ts, to_ts=to_ts)
        if code == 200 and isinstance(data, list):
            entries = data
        elif isinstance(data, str):
            error = data
        else:
            error = str(data) if data else f"HTTP {code}"
    return render_template("logs.html", entries=entries, error=error)


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
        events_str = (request.form.get("events") or "").strip()
        if not url_val:
            session["_webhooks_error"] = "URL required."
            return redirect(url_for("webhooks_page"))
        events = [e.strip() for e in events_str.split(",") if e.strip()] if events_str else []
        payload = {"url": url_val}
        if events:
            payload["events"] = events
        code, data = post_webhook(user, passwd, payload)
        if code in (200, 201):
            session["_webhooks_success"] = "Webhook added."
        else:
            session["_webhooks_error"] = str(data) if isinstance(data, str) else data.get("message", str(data)) if isinstance(data, dict) else str(data)
        return redirect(url_for("webhooks_page"))
    if user and passwd:
        code, data = get_webhooks(user, passwd)
        if code == 200 and isinstance(data, list):
            webhooks = data
        elif isinstance(data, str):
            error = data
        else:
            error = str(data) if data else f"HTTP {code}"
    return render_template("webhooks.html", webhooks=webhooks, error=error, success=success)


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
    Public endpoint: JSON or form with username, password (device), phone, message.
    Unchanged for Zapier/scripts.
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

    status, body = client_post_message(
        username, password, phone_numbers=[phone], text=message
    )
    if status == 202:
        return jsonify({"success": True, **body} if isinstance(body, dict) else {"success": True}), status
    err = body.get("error", body) if isinstance(body, dict) else body
    return jsonify({"success": False, "error": str(err)}), status


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4842"))
    app.run(host="0.0.0.0", port=port, debug=False)
