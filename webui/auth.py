"""
Web UI admin authentication: env-based username/password, session.
"""
import os
from functools import wraps

from flask import session, redirect, url_for, request


def is_auth_enabled() -> bool:
    """True if WEBUI_ADMIN_USER and WEBUI_ADMIN_PASSWORD are set."""
    return bool(
        os.environ.get("WEBUI_ADMIN_USER") and os.environ.get("WEBUI_ADMIN_PASSWORD")
    )


def get_secret_key() -> str:
    """Session signing secret; required when auth is enabled."""
    key = os.environ.get("WEBUI_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if is_auth_enabled() and not key:
        raise RuntimeError(
            "WEBUI_SECRET_KEY or SECRET_KEY must be set when Web UI auth is enabled"
        )
    return key or "dev-insecure-secret-change-in-production"


def check_credentials(username: str, password: str) -> bool:
    """Return True if username/password match env."""
    if not is_auth_enabled():
        return True
    return (
        username == os.environ.get("WEBUI_ADMIN_USER")
        and password == os.environ.get("WEBUI_ADMIN_PASSWORD")
    )


def login_required(f):
    """Decorator: redirect to login if auth enabled and session has no user."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        if not is_auth_enabled():
            return f(*args, **kwargs)
        if session.get("user") is None:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)

    return wrapped


def get_public_paths():
    """Paths that do not require login when auth is enabled."""
    return {"/login", "/api/send", "/static"}


def should_skip_auth(path: str) -> bool:
    """True if path is public or auth is disabled."""
    if not is_auth_enabled():
        return True
    path = path.rstrip("/") or "/"
    if path == "/":
        return False
    for prefix in get_public_paths():
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False
