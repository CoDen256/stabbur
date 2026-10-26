"""
app.py — stabbur's Flask entrypoint. Mirrors smia's app.py shape (D-N1):
registers auth, then mounts blob storage and notes routes.

Run: `flask --app app run` (dev) with DATABASE_URL and STABBUR_AUTH_TOKEN set.
"""

from __future__ import annotations

import os

from flask import Flask, request, send_from_directory
from flask_cors import CORS

from auth import register_auth
from routes.blobs import register_blob_routes
from routes.notes import register_notes_routes

app = Flask(__name__)
CORS(app)
app.json.ensure_ascii = False  # Norwegian characters as literal UTF-8, not \uXXXX escapes
register_auth(app)
register_blob_routes(app)
register_notes_routes(app)


@app.route("/ui", methods=["GET"])
@app.route("/ui/", methods=["GET"])
def ui_index():
    # Mounted at the domain root in local dev, but under a path prefix
    # (e.g. /stabbur) once reverse-proxied on the VPS — the proxy strips
    # that prefix before forwarding here (so every other route stays
    # prefix-agnostic), but the browser still needs it for its own
    # absolute asset/API requests. The proxy is expected to pass it along
    # as X-Forwarded-Prefix; ui/ui.js reads it back via `window.STABBUR_PREFIX`.
    prefix = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")
    with open(os.path.join(app.root_path, "ui", "index.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__STABBUR_PREFIX__", prefix)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/ui/<path:filename>", methods=["GET"])
def ui_asset(filename):
    return send_from_directory("ui", filename)


if __name__ == "__main__":
    import os as _os

    debug = _os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5056, debug=debug)
