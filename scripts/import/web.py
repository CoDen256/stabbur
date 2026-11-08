"""
scripts/import/web.py — the review server (import-review-web tasks 2.1-2.5).

A localhost-only Flask app over `import/candidates.db`: it is not served by
stabbur's `app.py`, nothing is added to `compose.yaml`, and it has no auth
because it is never reachable from anywhere but `127.0.0.1` (design D1).
This module holds only routes and audio I/O; every piece of queue logic —
`queue`, `pending_queue`, `progress`, `record_decision`, `undo_last_decision`,
`recent_decisions` — lives in `review.py` and is reused unchanged (task 2.2).

Audio (task 2.4, design D3): `(source, audio_ref) -> bytes` by `zipfile`
random access straight into the `.apkg` archives, no extraction step. Each
archive is opened once and its `zipfile.ZipFile` handle kept open for the
life of the process (`_ArchiveCache`) rather than reopened per request —
the risk design.md flags under D1. Only `ntnu` and `a1_31k` are ever human
sources (design D7/D10); any other source, or any audio reference that
doesn't resolve, is a 404 (task 2.5) rather than an error, so a UI bug
can never surface synthesised audio that `merge` already excluded.
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request

import ingest as ingest_stage
import review as review_stage
import store

# Design D7/D10 — the only two sources that ever supply human recordings.
# Kept in sync with merge.py's own constant of the same name; duplicated
# deliberately, the same belt-and-braces reasoning push.py's copy uses.
HUMAN_AUDIO_SOURCES = frozenset({"ntnu", "a1_31k"})


class _ArchiveCache:
    """Opens each `.apkg` archive at most once per process and reuses the
    `zipfile.ZipFile` handle for every subsequent audio request (task 2.4)."""

    def __init__(self) -> None:
        self._handles: dict[str, zipfile.ZipFile] = {}

    def get(self, source: str) -> zipfile.ZipFile | None:
        if source not in HUMAN_AUDIO_SOURCES:
            return None
        if source not in self._handles:
            path = ingest_stage.IMPORT_DIR / ingest_stage.APKG_SOURCES[source]["file"]
            if not path.exists():
                return None
            self._handles[source] = zipfile.ZipFile(path)
        return self._handles[source]


def _candidate_payload(row: sqlite3.Row) -> dict:
    """JSON shape of one candidate for the review UI (task 3.1): merged
    fields with source attribution, conflicts, verdict evidence, and
    whether it has (human) audio."""
    fields = json.loads(row["fields_json"])
    sources = json.loads(row["sources_json"])
    conflicts = json.loads(row["conflicts_json"])
    evidence = json.loads(row["verdict_evidence_json"])
    return {
        "signature_key": row["signature_key"],
        "verdict": row["verdict"],
        "evidence": evidence,
        "fields": fields,
        "sources": sources,
        "conflicts": conflicts,
        "has_audio": bool(fields.get("audio_ref")) and sources.get("audio_ref") in HUMAN_AUDIO_SOURCES,
    }


def _recent_payload(rows: list[sqlite3.Row]) -> list[dict]:
    out = []
    for row in rows:
        fields = json.loads(row["fields_json"])
        out.append(
            {
                "signature_key": row["signature_key"],
                "decision": row["decision"],
                "text": fields.get("text"),
            }
        )
    return out


def _state_payload(conn: sqlite3.Connection, skipped: set[str]) -> dict:
    """`skipped` is this server process's in-memory skip-for-now set
    (task 3.3) — it never touches `decision`, so a skipped candidate is
    still "undecided" for every resumability guarantee in review.py; it
    just isn't shown as current again until every other pending candidate
    has been (the `or pending` fallback below, once everything left is
    skipped)."""
    pending = review_stage.pending_queue(conn)
    visible = [row for row in pending if row["signature_key"] not in skipped] or pending
    reviewed, remaining = review_stage.progress(conn)

    # The next candidate's audio is preloaded while the current one is on
    # screen (task 3.7) — only its signature key is needed for that, not
    # its full payload.
    next_audio_signature = None
    if len(visible) > 1:
        upcoming = _candidate_payload(visible[1])
        if upcoming["has_audio"]:
            next_audio_signature = upcoming["signature_key"]

    return {
        "current": _candidate_payload(visible[0]) if visible else None,
        "next_audio_signature": next_audio_signature,
        "reviewed": reviewed,
        "remaining": remaining,
        "recent": _recent_payload(review_stage.recent_decisions(conn)),
    }


def _resolve_audio_bytes(conn: sqlite3.Connection, archives: _ArchiveCache, signature_key: str) -> bytes | None:
    candidate = conn.execute(
        "SELECT fields_json, sources_json FROM candidate WHERE signature_key = ?", (signature_key,)
    ).fetchone()
    if candidate is None:
        return None

    fields = json.loads(candidate["fields_json"])
    sources = json.loads(candidate["sources_json"])
    audio_ref = fields.get("audio_ref")
    winning_source = sources.get("audio_ref")
    if not audio_ref or winning_source not in HUMAN_AUDIO_SOURCES:
        return None

    row = conn.execute(
        """
        SELECT r.media_json
        FROM normalized n
        JOIN signature s ON s.normalized_id = n.id
        JOIN raw_note r ON r.id = n.raw_note_id
        WHERE s.signature_key = ? AND n.source = ? AND n.audio_ref = ?
        """,
        (signature_key, winning_source, audio_ref),
    ).fetchone()
    if row is None:
        return None

    member = json.loads(row["media_json"]).get(audio_ref)
    if member is None:
        return None

    archive = archives.get(winning_source)
    if archive is None:
        return None
    try:
        return archive.read(member)
    except KeyError:
        return None


def create_app(conn: sqlite3.Connection) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent / "static"),
    )
    archives = _ArchiveCache()
    skipped: set[str] = set()

    @app.get("/")
    def index():
        return render_template("review.html")

    @app.get("/api/state")
    def state():
        return jsonify(_state_payload(conn, skipped))

    @app.post("/api/decisions")
    def decide():
        body = request.get_json(silent=True) or {}
        signature_key = body.get("signature_key")
        decision = body.get("decision")
        if not signature_key or decision not in ("accept", "reject"):
            abort(400)
        review_stage.record_decision(conn, signature_key, decision)
        skipped.discard(signature_key)
        return jsonify(_state_payload(conn, skipped))

    @app.post("/api/skip")
    def skip():
        body = request.get_json(silent=True) or {}
        signature_key = body.get("signature_key")
        if signature_key:
            skipped.add(signature_key)
        return jsonify(_state_payload(conn, skipped))

    @app.post("/api/undo")
    def undo():
        review_stage.undo_last_decision(conn)
        return jsonify(_state_payload(conn, skipped))

    @app.get("/api/audio/<path:signature_key>")
    def audio(signature_key):
        data = _resolve_audio_bytes(conn, archives, signature_key)
        if data is None:
            abort(404)
        return Response(data, mimetype="audio/mpeg")

    return app


def main() -> None:
    conn = store.connect()
    app = create_app(conn)
    app.run(host="127.0.0.1", port=5057)


if __name__ == "__main__":
    main()
