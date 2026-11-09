"""Tests for scripts/import/push.py — section 7 of bulk-import-anki-csv
(tasks 7.1-7.4). HTTP calls are mocked throughout — this module never
needs a running stabbur instance to be unit-tested; the real end-to-end
check against a throwaway database is task 8.2, done manually/in CI, not
here.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import push as import_push  # noqa: E402
import store as import_store  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    return import_store.connect(tmp_path / "candidates.db")


def _insert_raw_note(conn, run_id, source, source_note_id, media=None):
    cur = conn.execute(
        "INSERT INTO raw_note (run_id, source, source_note_id, note_type, fields_json, media_json) "
        "VALUES (?, ?, ?, 'word', '{}', ?)",
        (run_id, source, source_note_id, json.dumps(media or {})),
    )
    return cur.lastrowid


def _insert_normalized(conn, run_id, raw_note_id, source, text, audio_ref=None):
    cur = conn.execute(
        "INSERT INTO normalized (run_id, raw_note_id, source, note_type, text, audio_ref) "
        "VALUES (?, ?, ?, 'word', ?, ?)",
        (run_id, raw_note_id, source, text, audio_ref),
    )
    return cur.lastrowid


def _insert_signature(conn, run_id, normalized_id, signature_key):
    conn.execute(
        "INSERT INTO signature (run_id, normalized_id, signature_key, head_lemma) VALUES (?, ?, ?, ?)",
        (run_id, normalized_id, signature_key, signature_key),
    )


def _insert_candidate(conn, run_id, signature_key, fields, sources):
    conn.execute(
        """
        INSERT INTO candidate (run_id, signature_key, fields_json, sources_json, verdict)
        VALUES (?, ?, ?, ?, 'import')
        """,
        (run_id, signature_key, json.dumps(fields), json.dumps(sources)),
    )


# ---------------------------------------------------------------------------
# resolve_audio_bytes (task 7.1, design D10)
# ---------------------------------------------------------------------------


def test_audio_rejected_when_winning_source_is_core6k(tmp_path, conn):
    run_id = import_store.start_run(conn, "ingest")
    raw_id = _insert_raw_note(conn, run_id, "core6k", "c1", media={"hypertts-123.mp3": "7"})
    norm_id = _insert_normalized(conn, run_id, raw_id, "core6k", "hund", audio_ref="hypertts-123.mp3")
    _insert_signature(conn, run_id, norm_id, "hund/[]/0/[]")
    rows = import_push.signature_rows(conn, "hund/[]/0/[]")

    audio = import_push.resolve_audio_bytes(rows, {"audio_ref": "core6k"}, "hypertts-123.mp3")
    assert audio is None


def test_audio_rejected_when_winning_source_is_freq6k(tmp_path, conn):
    run_id = import_store.start_run(conn, "ingest")
    raw_id = _insert_raw_note(conn, run_id, "freq6k", "f1", media={"ordpar-9.mp3": "3"})
    norm_id = _insert_normalized(conn, run_id, raw_id, "freq6k", "hus", audio_ref="ordpar-9.mp3")
    _insert_signature(conn, run_id, norm_id, "hus/[]/0/[]")
    rows = import_push.signature_rows(conn, "hus/[]/0/[]")

    audio = import_push.resolve_audio_bytes(rows, {"audio_ref": "freq6k"}, "ordpar-9.mp3")
    assert audio is None


def test_audio_accepted_when_winning_source_is_ntnu(tmp_path, conn, monkeypatch):
    archive_path = tmp_path / "NTNU_Norskkurs_Now_1_Complete_Vocabulary_Deck.apkg"
    with zipfile.ZipFile(archive_path, "w") as z:
        z.writestr("3", b"fake-mp3-bytes")

    monkeypatch.setattr(import_push.ingest_stage, "IMPORT_DIR", tmp_path)
    run_id = import_store.start_run(conn, "ingest")
    raw_id = _insert_raw_note(conn, run_id, "ntnu", "n1", media={"abc.mp3": "3"})
    norm_id = _insert_normalized(conn, run_id, raw_id, "ntnu", "hund", audio_ref="abc.mp3")
    _insert_signature(conn, run_id, norm_id, "hund/[]/0/[]")
    rows = import_push.signature_rows(conn, "hund/[]/0/[]")

    audio = import_push.resolve_audio_bytes(rows, {"audio_ref": "ntnu"}, "abc.mp3")
    assert audio == b"fake-mp3-bytes"


def test_no_audio_ref_returns_none(conn):
    assert import_push.resolve_audio_bytes([], {}, None) is None


# ---------------------------------------------------------------------------
# build_note_payload / status/origin invariants (tasks 7.2, D12)
# ---------------------------------------------------------------------------


def test_payload_is_always_draft_never_ready():
    fields = {"text": "hund", "note_type": "word"}
    payload = import_push.build_note_payload(fields, {"text": "ntnu"}, None, "n1", run_id=5)
    assert payload["status"] == "draft"
    assert payload["origin"] == "import"
    assert payload["import_ref"] == {"source": "ntnu", "source_note_id": "n1", "run_id": 5}


def test_payload_carries_merged_fields():
    fields = {
        "text": "hund",
        "note_type": "word",
        "translations": [{"lang": "en", "text": "dog"}],
        "pos": "noun",
        "context_text": "Jeg har en hund.",
        "transcription": "/hun/",
        "inflections": {"sg_indef": "hund"},
    }
    payload = import_push.build_note_payload(fields, {"text": "ntnu"}, "sha256hash", "n1", run_id=1)
    assert payload["text"] == "hund"
    assert payload["translations"] == [{"lang": "en", "text": "dog"}]
    assert payload["pos"] == "noun"
    assert payload["context_text"] == "Jeg har en hund."
    assert payload["transcription"] == "/hun/"
    assert payload["inflections"] == {"sg_indef": "hund"}
    assert payload["audio_blob"] == "sha256hash"


def test_payload_carries_lemma():
    """Task 4.4: push.py already sends `pos`; the payload now also sends
    `lemma`."""
    fields = {"text": "katt", "note_type": "word", "lemma": "katt"}
    payload = import_push.build_note_payload(fields, {"text": "ntnu"}, None, "n1", run_id=1)
    assert payload["lemma"] == "katt"


def test_payload_lemma_is_none_when_absent():
    fields = {"text": "bli kvitt", "note_type": "expression"}
    payload = import_push.build_note_payload(fields, {"text": "herpaberget"}, None, "n1", run_id=1)
    assert payload["lemma"] is None


# ---------------------------------------------------------------------------
# push_one / run — idempotency (task 7.3, D12) and the queue (only accepted)
# ---------------------------------------------------------------------------


def test_run_only_pushes_accepted_candidates(conn):
    run_id = import_store.start_run(conn, "merge")
    _insert_candidate(conn, run_id, "a", {"text": "hund", "note_type": "word"}, {"text": "ntnu"})
    _insert_candidate(conn, run_id, "b", {"text": "katt", "note_type": "word"}, {"text": "ntnu"})
    conn.execute("INSERT INTO decision (signature_key, decision, decided_at) VALUES ('a', 'accept', '2026-01-01')")
    conn.execute("INSERT INTO decision (signature_key, decision, decided_at) VALUES ('b', 'reject', '2026-01-01')")
    conn.commit()

    with patch.object(import_push, "push_one", return_value="note-123") as mock_push_one:
        count_in, pushed, skipped = import_push.run(conn, run_id=99)

    assert count_in == 1  # only the accepted one is in the queue at all
    assert pushed == 1
    assert skipped == 0
    mock_push_one.assert_called_once()
    assert mock_push_one.call_args[0][1]["signature_key"] == "a"


def test_run_skips_candidates_already_pushed(conn):
    run_id = import_store.start_run(conn, "merge")
    _insert_candidate(conn, run_id, "a", {"text": "hund", "note_type": "word"}, {"text": "ntnu"})
    conn.execute("UPDATE candidate SET note_id = 'already-pushed-id' WHERE signature_key = 'a'")
    conn.execute("INSERT INTO decision (signature_key, decision, decided_at) VALUES ('a', 'accept', '2026-01-01')")
    conn.commit()

    with patch.object(import_push, "push_one") as mock_push_one:
        count_in, pushed, skipped = import_push.run(conn, run_id=99)

    assert pushed == 0
    assert skipped == 1
    mock_push_one.assert_not_called()


def test_push_one_stores_note_id_on_candidate(conn):
    run_id = import_store.start_run(conn, "ingest")
    raw_id = _insert_raw_note(conn, run_id, "ntnu", "n1")
    norm_id = _insert_normalized(conn, run_id, raw_id, "ntnu", "hund")
    _insert_signature(conn, run_id, norm_id, "hund/[]/0/[]")
    _insert_candidate(conn, run_id, "hund/[]/0/[]", {"text": "hund", "note_type": "word"}, {"text": "ntnu"})

    with patch.object(import_push, "create_note", return_value="new-note-id"):
        note_id = import_push.push_one(conn, conn.execute("SELECT * FROM candidate").fetchone(), run_id=42)

    assert note_id == "new-note-id"
    row = conn.execute("SELECT note_id FROM candidate WHERE signature_key = 'hund/[]/0/[]'").fetchone()
    assert row["note_id"] == "new-note-id"


def test_create_note_posts_to_api_base(monkeypatch):
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "abc"}
    mock_response.raise_for_status.return_value = None
    with patch.object(import_push.requests, "post", return_value=mock_response) as mock_post:
        note_id = import_push.create_note({"text": "hund"})
    assert note_id == "abc"
    mock_post.assert_called_once()
    assert mock_post.call_args[0][0] == f"{import_push.api_base()}/api/notes"


def test_upload_audio_posts_multipart(monkeypatch):
    mock_response = MagicMock()
    mock_response.json.return_value = {"sha256": "deadbeef"}
    mock_response.raise_for_status.return_value = None
    with patch.object(import_push.requests, "post", return_value=mock_response) as mock_post:
        sha256 = import_push.upload_audio(b"bytes")
    assert sha256 == "deadbeef"
    assert mock_post.call_args[0][0] == f"{import_push.api_base()}/blobs"
    assert "audio" in mock_post.call_args.kwargs["files"]
