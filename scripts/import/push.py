"""
scripts/import/push.py — section 7: accepted `candidate` -> stabbur
`POST /api/notes` + blob upload (tasks 7.1-7.4, design D10/D12).

This is the only stage that talks to a running stabbur instance — every
earlier stage is offline, reading only the archives in `import/` and the
local SQLite store. `STABBUR_IMPORT_API_BASE` selects the target
(default `http://localhost:5000`, overridable for a throwaway verification
database per task 8.2).

Audio (task 7.1, design D10): only NTNU and A1 31k ever supply human
recordings; core6k's `hypertts-*` and freq6k's `ordpar-*` files are
machine-synthesised and are rejected **unconditionally**, regardless of
what `merge`'s field-priority happened to pick as the `audio_ref` winner —
core6k out-ranks freq6k in that priority (task 5.2's `NTNU > A1 > core6k >
freq6k > CSV`) and could otherwise win a candidate's `audio_ref` field
whenever neither NTNU nor A1 has a recording for it. Re-checking the
winning *source* here, not just the file, is what keeps that rejection
unconditional rather than incidental to priority order.

Push is idempotent (task 7.3, design D12): the returned note id is stored
back on `candidate.note_id`, and any candidate that already has one is
skipped on a re-run, so an interrupted push resumes rather than
duplicating notes. Never `status=ready`, under any flag (task 7.2) — the
import's review decides inclusion; stabbur's own draft->ready pass decides
correctness, a deliberately separate judgement (D12).

No rate limiting (task 7.4): no external provider is ever called from this
tool, only stabbur's own API.
"""

from __future__ import annotations

import json
import os
import sqlite3
import zipfile

import ingest as ingest_stage
import requests

DEFAULT_API_BASE = "http://localhost:5000"

# Design D10 — the only two sources with human audio. Checked against the
# *winning source for the audio_ref field* (sources_json), not the source
# priority order itself, so a core6k/freq6k file can never slip through
# merely because NTNU/A1 lacked a recording for that lexeme.
HUMAN_AUDIO_SOURCES = frozenset({"ntnu", "a1_31k"})

SOURCE_LANG = "no"  # stabbur is Norwegian-shaped until a second source_lang exists (CLAUDE.md)


def api_base() -> str:
    return os.environ.get("STABBUR_IMPORT_API_BASE", DEFAULT_API_BASE)


def _auth_headers() -> dict:
    """stabbur's own `auth.py` requires a bearer token on every
    non-`/ui`/`/blob` request — `STABBUR_AUTH_TOKEN` matches the same env
    var name the app itself reads, so pointing this tool at a running
    instance needs no separate credential."""
    token = os.environ.get("STABBUR_AUTH_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def signature_rows(conn: sqlite3.Connection, signature_key: str) -> list[sqlite3.Row]:
    """Every normalized+raw_note row contributing to one signature — the
    raw material push needs to resolve audio bytes and the primary
    source/source_note_id for `import_ref` (task 7.2)."""
    return conn.execute(
        """
        SELECT n.id AS normalized_id, n.source, n.audio_ref, r.source_note_id, r.media_json
        FROM normalized n
        JOIN signature s ON s.normalized_id = n.id
        JOIN raw_note r ON r.id = n.raw_note_id
        WHERE s.signature_key = ?
        """,
        (signature_key,),
    ).fetchall()


def resolve_audio_bytes(rows: list[sqlite3.Row], sources: dict, audio_ref: str | None) -> bytes | None:
    """Task 7.1: only pull bytes from the archive when the field's winning
    source is one of the two human-audio sources. Returns `None` whenever
    there's nothing eligible to upload — the candidate is still pushed,
    just without audio (design D10's own accepted consequence)."""
    if not audio_ref:
        return None
    winning_source = sources.get("audio_ref")
    if winning_source not in HUMAN_AUDIO_SOURCES:
        return None

    row = next((r for r in rows if r["source"] == winning_source and r["audio_ref"] == audio_ref), None)
    if row is None:
        return None

    media = json.loads(row["media_json"])
    member = media.get(audio_ref)
    if member is None:
        return None

    archive_path = ingest_stage.IMPORT_DIR / ingest_stage.APKG_SOURCES[winning_source]["file"]
    with zipfile.ZipFile(archive_path) as archive:
        return archive.read(member)


def primary_text_row(rows: list[sqlite3.Row], text_source: str | None) -> sqlite3.Row | None:
    for row in rows:
        if row["source"] == text_source:
            return row
    return rows[0] if rows else None


def upload_audio(audio_bytes: bytes) -> str:
    response = requests.post(
        f"{api_base()}/blobs",
        files={"audio": ("audio.mp3", audio_bytes, "audio/mpeg")},
        headers=_auth_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["sha256"]


def build_note_payload(fields: dict, sources: dict, audio_blob: str | None, source_note_id: str, run_id: int) -> dict:
    return {
        "type": fields.get("note_type", "word"),
        "source_lang": SOURCE_LANG,
        "text": fields["text"],
        "status": "draft",  # D12: never "ready", under any flag or option
        "origin": "import",
        "import_ref": {
            "source": sources.get("text"),
            "source_note_id": source_note_id,
            "run_id": run_id,
        },
        "translations": fields.get("translations", []),
        "transcription": fields.get("transcription"),
        "pos": fields.get("pos"),
        "inflections": fields.get("inflections", {}),
        "context_text": fields.get("context_text"),
        "audio_blob": audio_blob,
    }


def create_note(payload: dict) -> str:
    response = requests.post(f"{api_base()}/api/notes", json=payload, headers=_auth_headers(), timeout=30)
    response.raise_for_status()
    return response.json()["id"]


def push_one(conn: sqlite3.Connection, candidate_row: sqlite3.Row, run_id: int) -> str:
    """Pushes a single accepted candidate, returns the created note id.
    Raises on any HTTP failure — the caller decides whether to continue
    past one failed candidate or stop (CLI default: stop, so a broken run
    is visible immediately rather than silently partial)."""
    signature_key = candidate_row["signature_key"]
    fields = json.loads(candidate_row["fields_json"])
    sources = json.loads(candidate_row["sources_json"])

    rows = signature_rows(conn, signature_key)
    audio_bytes = resolve_audio_bytes(rows, sources, fields.get("audio_ref"))
    audio_blob = upload_audio(audio_bytes) if audio_bytes else None

    primary_row = primary_text_row(rows, sources.get("text"))
    source_note_id = primary_row["source_note_id"] if primary_row else ""

    payload = build_note_payload(fields, sources, audio_blob, source_note_id, run_id)
    note_id = create_note(payload)

    conn.execute("UPDATE candidate SET note_id = ? WHERE signature_key = ?", (note_id, signature_key))
    conn.commit()
    return note_id


def run(conn: sqlite3.Connection, run_id: int) -> tuple[int, int, int]:
    accepted = conn.execute(
        """
        SELECT c.* FROM candidate c
        JOIN decision d ON d.signature_key = c.signature_key
        WHERE d.decision = 'accept'
        """
    ).fetchall()
    count_in = len(accepted)

    pushed = 0
    skipped_already_pushed = 0
    for row in accepted:
        if row["note_id"]:
            skipped_already_pushed += 1
            continue
        push_one(conn, row, run_id)
        pushed += 1

    print(f"push: {pushed} pushed, {skipped_already_pushed} already pushed (skipped, task 7.3)")
    return count_in, pushed, skipped_already_pushed
