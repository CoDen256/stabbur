"""
routes/enrich.py — proxies the note editor's suggestion panels to smia
(smia-enrichment spec). The browser never calls smia directly: every request
here is authenticated with stabbur's own bearer token (auth.py's existing
before_request hook), and this module is the only thing holding smia's
token/address. Responses are passed through as smia reported them — no
retry, no fallback, no reinterpretation of its error shapes (design.md D3).
"""

from __future__ import annotations

from flask import jsonify, request

import blob_storage
import smia_client

# stabbur only proxies the kinds a note actually has fields for — /stt has
# no corresponding note field today, so it's deliberately not exposed here.
ENRICHABLE_KINDS = ("ipa", "translations", "inflections", "tts")


def register_enrich_routes(app):
    @app.route("/api/enrich/providers", methods=["GET"])
    def get_enrich_providers():
        try:
            status, body = smia_client.get("/providers")
        except smia_client.SmiaUnavailableError as exc:
            return jsonify({"error": f"smia unavailable: {exc}"}), 502
        return jsonify(body), status

    @app.route("/api/enrich/<kind>", methods=["POST"])
    def post_enrich(kind):
        if kind not in ENRICHABLE_KINDS:
            return jsonify({"error": f"unknown kind {kind!r}", "available": list(ENRICHABLE_KINDS)}), 400

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "a JSON body is required"}), 400

        try:
            status, response_body = smia_client.post(f"/{kind}", json=body)
        except smia_client.SmiaUnavailableError as exc:
            return jsonify({"error": f"smia unavailable: {exc}"}), 502
        return jsonify(response_body), status

    @app.route("/api/enrich/tts/use", methods=["POST"])
    def post_enrich_tts_use():
        """The one enrichment route that does more than pass through: a
        chosen /tts candidate's audio has to land in stabbur's own canonical
        blob store (D45), never stay a reference into smia's private,
        non-canonical cache. The candidate's own `sha256` (from a prior
        POST /api/enrich/tts response) is smia's audio-content hash, which
        smia's GET /tts/{sha256} serves as raw bytes directly — no need to
        re-run the provider lookup."""
        body = request.get_json(silent=True) or {}
        candidate_sha256 = body.get("sha256")
        if not candidate_sha256:
            return jsonify({"error": "sha256 is required"}), 400

        try:
            status, data, _content_type = smia_client.get_bytes(f"/tts/{candidate_sha256}")
        except smia_client.SmiaUnavailableError as exc:
            return jsonify({"error": f"smia unavailable: {exc}"}), 502
        if status != 200:
            return jsonify({"error": "smia could not serve that candidate's audio"}), 502

        stored_sha256 = blob_storage.store(data)
        return jsonify({"sha256": stored_sha256}), 200
