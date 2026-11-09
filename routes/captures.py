"""
routes/captures.py — `POST /api/captures` (ingest + atomic promote),
`GET /api/captures/<id>`, and `GET /api/captures?unattached=true`, per the
`captures-ingestion` spec and design.md D3-D9.
"""

from __future__ import annotations

import datetime

from flask import jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.models import NOTE_TYPES, Capture, Note
from db.session import session_scope
from routes.notes import _integrity_error_message, _serialize_authoring

REQUIRED_CAPTURE_FIELDS = ("selected_text", "source")


def _iso(dt: datetime.datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _serialize_capture(capture: Capture) -> dict:
    return {
        "id": capture.id,
        "created_at": _iso(capture.created_at),
        "selected_text": capture.selected_text,
        "context_text": capture.context_text,
        "translations": capture.translations,
        "source": capture.source,
        "audio_blob": capture.audio_blob,
        "audio_sel_ms": capture.audio_sel_ms,
    }


def _validate_source(source) -> str | None:
    """D8: shape-level only. `youtube`'s value IS the video id, `web`'s
    value IS the url (tun/docs/03-data-model.md's `{youtube: videoId, ...}`
    / `{web: url, ...}` notation) — a present, non-empty value under either
    key satisfies its shape. Unknown sibling keys pass through unchanged."""
    if not isinstance(source, dict):
        return "source must be an object"
    if "youtube" in source:
        if not source.get("youtube"):
            return "youtube source requires a video id"
        return None
    if "web" in source:
        if not source.get("web"):
            return "web source requires a url"
        return None
    return "source must contain a recognised shape (web or youtube)"


def register_capture_routes(app):
    @app.route("/api/captures", methods=["POST"])
    def create_capture():
        body = request.get_json(silent=True)
        if body is None:
            return jsonify({"error": "JSON body required"}), 400

        capture_id = body.get("id")
        if not capture_id:
            return jsonify({"error": "id is required"}), 400

        with session_scope() as db:
            # D4/task 2.5-2.6: a replay is resolved by id before any other
            # validation runs — the client's intent ("this capture should
            # exist") is already satisfied, so the new body's content is
            # ignored rather than re-validated or re-applied. Silently
            # overwriting a reviewed note from a stale outbox entry would
            # be worse than ignoring the replay.
            existing = db.get(Capture, capture_id)
            if existing is not None:
                note = db.scalar(select(Note).where(Note.capture_id == existing.id))
                return jsonify({"capture": _serialize_capture(existing), "note": _serialize_authoring(note)}), 200

            missing = [f for f in REQUIRED_CAPTURE_FIELDS if not body.get(f)]
            if missing:
                return jsonify({"error": f"missing required fields: {missing}"}), 400

            source_error = _validate_source(body["source"])
            if source_error:
                return jsonify({"error": source_error}), 400

            type_ = body.get("type", "word")
            if type_ not in NOTE_TYPES:
                return jsonify({"error": f"type must be one of {NOTE_TYPES}"}), 400

            translations = body.get("translations", [])
            context_text = body.get("context_text")
            audio_blob = body.get("audio_blob")
            audio_sel_ms = body.get("audio_sel_ms")

            capture = Capture(
                id=capture_id,
                selected_text=body["selected_text"],
                context_text=context_text,
                translations=translations,
                source=body["source"],
                audio_blob=audio_blob,
                audio_sel_ms=audio_sel_ms,
            )
            note = Note(
                origin="capture",
                capture_id=capture_id,
                status="draft",
                type=type_,
                source_lang=body.get("source_lang", "no"),
                text=body["selected_text"],
                translations=translations,
                context_text=context_text,
                audio_blob=audio_blob,
                audio_sel_ms=audio_sel_ms,
            )
            db.add(capture)
            db.add(note)
            try:
                db.flush()
            except IntegrityError as exc:
                db.rollback()
                return jsonify({"error": _integrity_error_message(exc)}), 400
            return jsonify({"capture": _serialize_capture(capture), "note": _serialize_authoring(note)}), 201

    @app.route("/api/captures/<capture_id>", methods=["GET"])
    def get_capture(capture_id):
        with session_scope() as db:
            capture = db.get(Capture, capture_id)
            if capture is None:
                return jsonify({"error": "not found"}), 404
            return jsonify(_serialize_capture(capture)), 200

    @app.route("/api/captures", methods=["GET"])
    def list_captures():
        # D5/task 3.2 — the only listing this change defines. A general
        # unfiltered capture list has no consumer yet.
        if request.args.get("unattached") != "true":
            return jsonify({"error": "unattached=true is required"}), 400

        with session_scope() as db:
            # One query (task 3.2): a capture is unattached if its audio
            # exists and no note referencing it carries that same blob.
            note_claims_audio = (
                select(Note.id)
                .where(Note.capture_id == Capture.id, Note.audio_blob == Capture.audio_blob)
                .exists()
            )
            stmt = (
                select(Capture)
                .where(Capture.audio_blob.isnot(None), ~note_claims_audio)
                # Newest-first (task 3.3) — the recorder's "what did I just
                # capture?" list is the primary consumer.
                .order_by(Capture.created_at.desc())
            )
            captures = db.scalars(stmt).all()
            return jsonify([_serialize_capture(c) for c in captures]), 200
