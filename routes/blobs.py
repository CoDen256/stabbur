"""
routes/blobs.py — `POST /blobs` (upload-and-hash) and `GET /blob/<sha256>`
(immutable serve), per this change's `blob-storage` spec and design.md D-N2.
"""

from __future__ import annotations

import os
import re

from flask import jsonify, request, send_file

import blob_storage

# Task 6.3 — low stakes today (operator-only authoring UI), but bound this
# before it's ever reachable from anything less trusted (P7's capture ingestion).
MAX_BLOB_SIZE_BYTES = int(os.environ.get("STABBUR_MAX_BLOB_SIZE_BYTES", 50 * 1024 * 1024))

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def register_blob_routes(app):
    @app.route("/blobs", methods=["POST"])
    def post_blob():
        audio_file = request.files.get("audio")
        if audio_file is None:
            return jsonify({"error": "audio file is required (multipart field 'audio')"}), 400
        data = audio_file.read(MAX_BLOB_SIZE_BYTES + 1)
        if len(data) > MAX_BLOB_SIZE_BYTES:
            return jsonify({"error": f"audio exceeds max size of {MAX_BLOB_SIZE_BYTES} bytes"}), 413
        sha256 = blob_storage.store(data)
        return jsonify({"sha256": sha256}), 200

    @app.route("/blob/<sha256>", methods=["GET"])
    def get_blob(sha256):
        if not _SHA256_RE.match(sha256):
            return jsonify({"error": "not found"}), 404
        if not blob_storage.exists(sha256):
            return jsonify({"error": "not found"}), 404
        response = send_file(blob_storage.path(sha256), mimetype="audio/mpeg")
        # Content-addressed and immutable once stored (blob-storage spec) —
        # a given hash's bytes never change, so cache forever.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
