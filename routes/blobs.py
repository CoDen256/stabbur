"""
routes/blobs.py — `POST /blobs` (upload-and-hash) and `GET /blob/<sha256>`
(immutable serve), per this change's `blob-storage` spec and design.md D-N2.
"""

from __future__ import annotations

from flask import jsonify, request, send_file

import blob_storage


def register_blob_routes(app):
    @app.route("/blobs", methods=["POST"])
    def post_blob():
        audio_file = request.files.get("audio")
        if audio_file is None:
            return jsonify({"error": "audio file is required (multipart field 'audio')"}), 400
        sha256 = blob_storage.store(audio_file.read())
        return jsonify({"sha256": sha256}), 200

    @app.route("/blob/<sha256>", methods=["GET"])
    def get_blob(sha256):
        if not blob_storage.exists(sha256):
            return jsonify({"error": "not found"}), 404
        response = send_file(blob_storage.path(sha256), mimetype="audio/mpeg")
        # Content-addressed and immutable once stored (blob-storage spec) —
        # a given hash's bytes never change, so cache forever.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
