"""
Centralized client for SMS Gateway 3rdparty API. All methods take device_user and device_pass.
"""
import os
from typing import Any

import requests

SMS_GATE_BASE = os.environ.get("SMS_GATE_URL", "http://server:3000").rstrip("/")
API_BASE = f"{SMS_GATE_BASE}/api/3rdparty/v1"

_http = requests.Session()


def _api_error_reason(status_code: int, body: Any) -> str:
    """Build a user-friendly error message from API status and body."""
    detail = ""
    if isinstance(body, dict):
        detail = body.get("message") or body.get("error") or body.get("detail") or str(body)
    elif isinstance(body, str) and body.strip():
        detail = body.strip()
    if not detail:
        detail = f"HTTP {status_code}"
    reason = ""
    if status_code == 401:
        reason = "Invalid device username or password, or the device is not registered with this server."
    elif status_code == 403:
        reason = "Access denied (forbidden)."
    elif status_code == 404:
        reason = "Resource not found."
    elif status_code >= 500:
        reason = "Server error; try again later."
    elif status_code >= 400:
        reason = "Request was rejected."
    if reason and detail and detail != f"HTTP {status_code}":
        return f"{reason} Details: {detail}"
    if reason:
        return f"{reason} ({status_code})"
    return detail


def get_token(device_user: str, device_pass: str) -> tuple[str | None, str | None]:
    """Obtain JWT from sms-gate. Returns (token, None) or (None, error_message)."""
    if not device_user or not device_pass:
        return None, "Device username and password are required"
    resp = _http.post(
        f"{API_BASE}/auth/token",
        auth=(device_user.strip(), device_pass),
        json={"scopes": ["messages:send"], "ttl": 86400},
        timeout=15,
    )
    if resp.status_code != 201:
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = resp.text or ""
        return None, _api_error_reason(resp.status_code, body)
    try:
        data = resp.json()
    except Exception:
        return None, "Invalid JSON response"
    token = data.get("access_token")
    if not token:
        return None, "No access_token in response"
    return token, None


def _request(
    method: str,
    path: str,
    device_user: str,
    device_pass: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any] | str]:
    """
    Call 3rdparty API with device credentials. path is relative to API_BASE (e.g. '/devices').
    Returns (status_code, json_body or error_string).
    """
    token, err = get_token(device_user, device_pass)
    if err:
        return 503, err
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{API_BASE}/{path}"
    resp = _http.request(
        method,
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=json,
        params=params,
        timeout=15,
    )
    try:
        body = resp.json() if resp.content else {}
    except Exception:
        body = resp.text or f"HTTP {resp.status_code}"
    return resp.status_code, body


# --- Devices ---


def get_devices(device_user: str, device_pass: str) -> tuple[int, list[dict] | str]:
    """GET /devices. Returns (code, list) or (code, error_str)."""
    code, data = _request("GET", "/devices", device_user, device_pass)
    if code == 200 and isinstance(data, list):
        return code, data
    return code, _api_error_reason(code, data)


def delete_device(
    device_id: str, device_user: str, device_pass: str
) -> tuple[int, None | str]:
    """DELETE /devices/{id}. Returns (code, None) or (code, error_str)."""
    code, data = _request("DELETE", f"/devices/{device_id}", device_user, device_pass)
    if code in (204, 200):
        return code, None
    return code, _api_error_reason(code, data)


# --- Messages ---


def get_messages(
    device_user: str,
    device_pass: str,
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int | None = None,
) -> tuple[int, list[dict] | dict | str]:
    """GET /messages with optional from, to, limit. Returns (code, data) or (code, error_str)."""
    params = {}
    if from_ts:
        params["from"] = from_ts
    if to_ts:
        params["to"] = to_ts
    if limit is not None:
        params["limit"] = str(limit)
    code, data = _request(
        "GET", "/messages", device_user, device_pass, params=params or None
    )
    if code == 200:
        return code, data
    return code, _api_error_reason(code, data)


def get_message(
    message_id: str, device_user: str, device_pass: str
) -> tuple[int, dict | str]:
    """GET /messages/{id}. Returns (code, dict) or (code, error_str)."""
    code, data = _request("GET", f"/messages/{message_id}", device_user, device_pass)
    if code == 200 and isinstance(data, dict):
        return code, data
    return code, _api_error_reason(code, data)


def post_message(
    device_user: str,
    device_pass: str,
    *,
    phone_numbers: list[str],
    text: str | None = None,
    device_id: str | None = None,
) -> tuple[int, dict | str]:
    """POST /messages (enqueue). Returns (code, body dict) or (code, error_str)."""
    payload: dict[str, Any] = {"phoneNumbers": phone_numbers}
    if text is not None:
        payload["textMessage"] = {"text": text}
    if device_id:
        payload["deviceId"] = device_id
    code, data = _request("POST", "/messages", device_user, device_pass, json=payload)
    if code in (200, 202) and isinstance(data, dict):
        return code, data
    return code, _api_error_reason(code, data)


# --- Logs ---


def get_logs(
    device_user: str,
    device_pass: str,
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> tuple[int, list[dict] | str]:
    """GET /logs?from=...&to=.... Returns (code, list) or (code, error_str)."""
    params = {}
    if from_ts:
        params["from"] = from_ts
    if to_ts:
        params["to"] = to_ts
    code, data = _request(
        "GET", "/logs", device_user, device_pass, params=params or None
    )
    if code == 200 and isinstance(data, list):
        return code, data
    return code, _api_error_reason(code, data)


# --- Webhooks ---


def get_webhooks(device_user: str, device_pass: str) -> tuple[int, list[dict] | str]:
    """GET /webhooks. Returns (code, list) or (code, error_str)."""
    code, data = _request("GET", "/webhooks", device_user, device_pass)
    if code == 200 and isinstance(data, list):
        return code, data
    return code, _api_error_reason(code, data)


def post_webhook(
    device_user: str, device_pass: str, payload: dict[str, Any]
) -> tuple[int, dict | str]:
    """POST /webhooks. Returns (code, body) or (code, error_str)."""
    code, data = _request("POST", "/webhooks", device_user, device_pass, json=payload)
    if code in (200, 201) and isinstance(data, dict):
        return code, data
    return code, _api_error_reason(code, data)


def delete_webhook(
    webhook_id: str, device_user: str, device_pass: str
) -> tuple[int, None | str]:
    """DELETE /webhooks/{id}. Returns (code, None) or (code, error_str)."""
    code, data = _request(
        "DELETE", f"/webhooks/{webhook_id}", device_user, device_pass
    )
    if code in (204, 200):
        return code, None
    return code, _api_error_reason(code, data)


# --- Settings ---


def get_settings(device_user: str, device_pass: str) -> tuple[int, dict | str]:
    """GET /settings. Returns (code, dict) or (code, error_str)."""
    code, data = _request("GET", "/settings", device_user, device_pass)
    if code == 200 and isinstance(data, dict):
        return code, data
    return code, _api_error_reason(code, data)


def patch_settings(
    device_user: str, device_pass: str, payload: dict[str, Any]
) -> tuple[int, dict | str]:
    """PATCH /settings. Returns (code, body) or (code, error_str)."""
    code, data = _request("PATCH", "/settings", device_user, device_pass, json=payload)
    if code == 200 and isinstance(data, dict):
        return code, data
    return code, _api_error_reason(code, data)


# --- Health (root, no auth typically) ---


def get_health_ready() -> tuple[int, dict | str]:
    """GET /health/ready (server root, no device auth). Returns (code, dict) or (code, error_str)."""
    try:
        resp = _http.get(f"{SMS_GATE_BASE}/health/ready", timeout=10)
        data = resp.json() if resp.content else {}
        return resp.status_code, data if isinstance(data, dict) else str(data)
    except Exception as e:
        return 0, str(e)


def get_health_live() -> tuple[int, dict | str]:
    """GET /health/live. Returns (code, dict) or (code, error_str)."""
    try:
        resp = _http.get(f"{SMS_GATE_BASE}/health/live", timeout=10)
        data = resp.json() if resp.content else {}
        return resp.status_code, data if isinstance(data, dict) else str(data)
    except Exception as e:
        return 0, str(e)


def get_version() -> tuple[int, dict | str]:
    """GET / (version). Returns (code, dict) or (code, error_str)."""
    try:
        resp = _http.get(f"{SMS_GATE_BASE}/", timeout=10)
        data = resp.json() if resp.content else {}
        return resp.status_code, data if isinstance(data, dict) else str(data)
    except Exception as e:
        return 0, str(e)
