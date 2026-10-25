"""
auth.py — shared-bearer-token auth middleware, matching smia's auth.py
pattern exactly (D-N1), with stabbur's own env var name in place of smia's.

One long-lived token, env-configured, checked on every request. No per-client
identity, no scopes — matches the ecosystem-wide pattern (D01).
"""

from __future__ import annotations

import os

from flask import jsonify, request

AUTH_TOKEN_ENV = "STABBUR_AUTH_TOKEN"


def register_auth(app):
    @app.before_request
    def _require_bearer_token():
        # /ui's static HTML/CSS/JS must load unauthenticated — that's where
        # an operator pastes the token in the first place (D46's
        # database-exploration UI, chicken-and-egg otherwise). /blob/<sha256>
        # also stays open: a note's audio is served to whatever renders the
        # authoring UI's <audio> preview, which does not carry the bearer
        # header.
        if request.path == "/ui" or request.path.startswith("/ui/"):
            return None
        if request.path.startswith("/blob/"):
            return None

        token = os.environ.get(AUTH_TOKEN_ENV)
        header = request.headers.get("Authorization", "")
        provided = header[len("Bearer "):] if header.startswith("Bearer ") else None

        # An unset token and a wrong token both resolve to 401, not two
        # different statuses — a caller can never distinguish "no token
        # configured" from "wrong token" anyway, and a 500 here would leak
        # the server's misconfiguration to any unauthenticated caller.
        if not token or provided != token:
            return jsonify({"error": "unauthorized"}), 401
