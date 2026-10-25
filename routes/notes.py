"""
routes/notes.py — the authoring CRUD (`notes-authoring` spec, design.md
D-N3) and the one-directional read API (`notes-read-api` spec, D-N4) that
`mjolnir/hub` pulls from.
"""

from __future__ import annotations

import datetime

from flask import jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.models import NOTE_STATUSES, NOTE_TYPES, GrammarRule, Note
from db.session import session_scope

REQUIRED_CREATE_FIELDS = ("type", "source_lang", "text")

# Every field in design.md D-N4's exact response shape, in that order.
READ_API_FIELDS = (
    "id",
    "created_at",
    "capture_id",
    "type",
    "source_lang",
    "text",
    "translations",
    "transcription",
    "pos",
    "lemma",
    "inflections",
    "context_text",
    "audio_blob",
    "audio_sel_ms",
    "grammar_rule_id",
    "status",
)


def _iso(dt: datetime.datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _serialize_public(note: Note) -> dict:
    """The exact `notes-read-api` contract (D-N4) — no more, no less."""
    return {
        "id": note.id,
        "created_at": _iso(note.created_at),
        "capture_id": note.capture_id,
        "type": note.type,
        "source_lang": note.source_lang,
        "text": note.text,
        "translations": note.translations,
        "transcription": note.transcription,
        "pos": note.pos,
        "lemma": note.lemma,
        "inflections": note.inflections,
        "context_text": note.context_text,
        "audio_blob": note.audio_blob,
        "audio_sel_ms": note.audio_sel_ms,
        "grammar_rule_id": note.grammar_rule_id,
        "status": note.status,
    }


def _serialize_authoring(note: Note) -> dict:
    """The authoring surface's own representation — a superset of the
    public contract with the fields an editor needs (`seq`, `updated_at`,
    tombstone state) that `notes-read-api` deliberately does not expose."""
    data = _serialize_public(note)
    data["seq"] = note.seq
    data["updated_at"] = _iso(note.updated_at)
    data["deleted_at"] = _iso(note.deleted_at)
    return data


def _validate_type_and_status(body: dict, existing_type: str | None, existing_status: str | None) -> str | None:
    type_ = body.get("type", existing_type)
    status = body.get("status", existing_status)
    if type_ is not None and type_ not in NOTE_TYPES:
        return f"type must be one of {NOTE_TYPES}"
    if status is not None and status not in NOTE_STATUSES:
        return f"status must be one of {NOTE_STATUSES}"
    return None


def register_notes_routes(app):
    @app.route("/api/notes", methods=["POST"])
    def create_note():
        body = request.get_json(silent=True)
        if body is None:
            return jsonify({"error": "JSON body required"}), 400

        missing = [f for f in REQUIRED_CREATE_FIELDS if not body.get(f)]
        if missing:
            return jsonify({"error": f"missing required fields: {missing}"}), 400

        error = _validate_type_and_status(body, None, None)
        if error:
            return jsonify({"error": error}), 400

        note = Note(
            type=body["type"],
            source_lang=body["source_lang"],
            text=body["text"],
            status=body.get("status", "draft"),
            capture_id=body.get("capture_id"),
            translations=body.get("translations", []),
            transcription=body.get("transcription"),
            pos=body.get("pos"),
            lemma=body.get("lemma"),
            inflections=body.get("inflections", {}),
            context_text=body.get("context_text"),
            audio_blob=body.get("audio_blob"),
            audio_sel_ms=body.get("audio_sel_ms"),
            grammar_rule_id=body.get("grammar_rule_id"),
        )

        with session_scope() as db:
            db.add(note)
            try:
                db.flush()
            except IntegrityError as exc:
                db.rollback()
                return jsonify({"error": _integrity_error_message(exc)}), 400
            return jsonify(_serialize_authoring(note)), 201

    @app.route("/api/notes/<note_id>", methods=["GET"])
    def get_note(note_id):
        with session_scope() as db:
            note = db.get(Note, note_id)
            if note is None:
                return jsonify({"error": "not found"}), 404
            return jsonify(_serialize_authoring(note)), 200

    @app.route("/api/notes/<note_id>", methods=["PATCH"])
    def patch_note(note_id):
        body = request.get_json(silent=True)
        if body is None:
            return jsonify({"error": "JSON body required"}), 400

        with session_scope() as db:
            note = db.get(Note, note_id)
            if note is None:
                return jsonify({"error": "not found"}), 404

            error = _validate_type_and_status(body, note.type, note.status)
            if error:
                return jsonify({"error": error}), 400

            for field in (
                "type",
                "source_lang",
                "text",
                "status",
                "capture_id",
                "translations",
                "transcription",
                "pos",
                "lemma",
                "inflections",
                "context_text",
                "audio_blob",
                "audio_sel_ms",
                "grammar_rule_id",
            ):
                if field in body:
                    setattr(note, field, body[field])

            try:
                db.flush()
            except IntegrityError as exc:
                db.rollback()
                return jsonify({"error": _integrity_error_message(exc)}), 400
            return jsonify(_serialize_authoring(note)), 200

    @app.route("/api/notes/<note_id>", methods=["DELETE"])
    def delete_note(note_id):
        with session_scope() as db:
            note = db.get(Note, note_id)
            if note is None:
                return jsonify({"error": "not found"}), 404

            # A draft has never been eligible for the read API to have
            # pulled it — safe to free the id entirely. Anything that has
            # ever reached `ready` could plausibly already be minted
            # (notes-schema spec), so it becomes a tombstone instead.
            if note.status == "draft":
                db.delete(note)
                return "", 204

            if note.deleted_at is None:
                note.deleted_at = datetime.datetime.now(datetime.timezone.utc)
            return jsonify(_serialize_authoring(note)), 200

    @app.route("/api/notes", methods=["GET"])
    def list_notes():
        """`notes-read-api`'s one-directional pull endpoint (D-N4). `status`
        is accepted but has no effect beyond the hard `status=ready` filter
        below — there is no way to ask this endpoint for drafts, regardless
        of what `status=` is set to."""
        source_lang = request.args.get("source_lang")
        since = request.args.get("since")

        stmt = select(Note).where(Note.status == "ready", Note.deleted_at.is_(None))
        if source_lang:
            stmt = stmt.where(Note.source_lang == source_lang)
        if since:
            try:
                since_dt = datetime.datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                return jsonify({"error": "since must be ISO8601"}), 400
            # Filters on updated_at, not created_at, so an edit to an
            # already-ready note is picked up by a later `since` pull too
            # (design.md's Risks/Trade-offs: builder's content-regeneration
            # needs this, not just newly-created notes).
            stmt = stmt.where(Note.updated_at >= since_dt)
        stmt = stmt.order_by(Note.created_at)

        with session_scope() as db:
            notes = db.scalars(stmt).all()
            return jsonify([_serialize_public(n) for n in notes]), 200

    @app.route("/api/grammar_rules", methods=["POST"])
    def create_grammar_rule():
        # Minimal support so the authoring UI can create a grammar_rule row
        # for `type=grammar` notes to reference (03-data-model.md), without
        # building any of P8's triage machinery around it.
        body = request.get_json(silent=True)
        if body is None or not body.get("title") or not body.get("html"):
            return jsonify({"error": "title and html are required"}), 400
        rule = GrammarRule(title=body["title"], html=body["html"])
        with session_scope() as db:
            db.add(rule)
            db.flush()
            return jsonify({"id": rule.id, "title": rule.title, "html": rule.html}), 201

    @app.route("/api/grammar_rules", methods=["GET"])
    def list_grammar_rules():
        with session_scope() as db:
            rules = db.scalars(select(GrammarRule)).all()
            return jsonify([{"id": r.id, "title": r.title, "html": r.html} for r in rules]), 200


def _integrity_error_message(exc: IntegrityError) -> str:
    if "ck_notes_grammar_requires_rule" in str(exc.orig):
        return "type=grammar notes require grammar_rule_id"
    if "ck_notes_type" in str(exc.orig):
        return f"type must be one of {NOTE_TYPES}"
    if "ck_notes_status" in str(exc.orig):
        return f"status must be one of {NOTE_STATUSES}"
    return "invalid note data"
