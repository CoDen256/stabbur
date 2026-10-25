"""
app.py — stabbur's Flask entrypoint. Mirrors smia's app.py shape (D-N1):
registers auth, then mounts blob storage and notes routes.

Run: `flask --app app run` (dev) with DATABASE_URL and STABBUR_AUTH_TOKEN set.
"""

from __future__ import annotations

from flask import Flask, send_from_directory
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
    return send_from_directory("ui", "index.html")


@app.route("/ui/<path:filename>", methods=["GET"])
def ui_asset(filename):
    return send_from_directory("ui", filename)


if __name__ == "__main__":
    import os as _os

    debug = _os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=5056, debug=debug)
