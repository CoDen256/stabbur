"""Tests for scripts/import/review.py — section 6 of bulk-import-anki-csv
(tasks 6.1-6.4) and import-review-web's review server (section 2, task
4.4). Uses a small hand-built candidate table so these run without the
real archives or stock bundle.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import review as import_review  # noqa: E402
import store as import_store  # noqa: E402
import web as import_web  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    return import_store.connect(tmp_path / "candidates.db")


def _insert_candidate(
    conn,
    signature_key,
    *,
    verdict="import",
    fields=None,
    sources=None,
    conflicts=None,
    order_key=None,
    evidence=None,
):
    run_id = import_store.start_run(conn, "merge")
    conn.execute(
        """
        INSERT INTO candidate (
            run_id, signature_key, fields_json, sources_json, conflicts_json,
            verdict, verdict_evidence_json, order_key_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            signature_key,
            json.dumps(fields or {"text": signature_key}),
            json.dumps(sources or {"text": "ntnu"}),
            json.dumps(conflicts or {}),
            verdict,
            json.dumps(evidence or {}),
            json.dumps(order_key or {"frequency_index": None, "cefr": None, "chapter": None}),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# queue (task 6.1)
# ---------------------------------------------------------------------------


def test_queue_excludes_skipped_candidates(conn):
    _insert_candidate(conn, "a", verdict="import")
    _insert_candidate(conn, "b", verdict="skip")
    q = import_review.queue(conn)
    assert [row["signature_key"] for row in q] == ["a"]


def test_queue_ordered_by_order_key(conn):
    _insert_candidate(conn, "low-freq", order_key={"frequency_index": 500, "cefr": None, "chapter": None})
    _insert_candidate(conn, "high-freq", order_key={"frequency_index": 5, "cefr": None, "chapter": None})
    _insert_candidate(conn, "no-signal", order_key={"frequency_index": None, "cefr": None, "chapter": None})
    q = import_review.queue(conn)
    assert [row["signature_key"] for row in q] == ["high-freq", "low-freq", "no-signal"]


# ---------------------------------------------------------------------------
# record_decision / decision table (task 6.3)
# ---------------------------------------------------------------------------


def test_record_decision_writes_only_to_decision_table(conn):
    _insert_candidate(conn, "a")
    import_review.record_decision(conn, "a", "accept")
    row = conn.execute("SELECT * FROM decision WHERE signature_key = 'a'").fetchone()
    assert row["decision"] == "accept"
    # candidate row itself is untouched
    candidate = conn.execute("SELECT verdict FROM candidate WHERE signature_key = 'a'").fetchone()
    assert candidate["verdict"] == "import"


def test_record_decision_rejects_invalid_decision(conn):
    _insert_candidate(conn, "a")
    with pytest.raises(ValueError):
        import_review.record_decision(conn, "a", "maybe")


def test_re_deciding_a_candidate_replaces_its_own_decision(conn):
    _insert_candidate(conn, "a")
    import_review.record_decision(conn, "a", "accept")
    import_review.record_decision(conn, "a", "reject")
    rows = conn.execute("SELECT decision FROM decision WHERE signature_key = 'a'").fetchall()
    assert len(rows) == 1
    assert rows[0]["decision"] == "reject"


# ---------------------------------------------------------------------------
# resumability (task 6.4)
# ---------------------------------------------------------------------------


def test_pending_queue_excludes_already_decided(conn):
    _insert_candidate(conn, "a")
    _insert_candidate(conn, "b")
    import_review.record_decision(conn, "a", "accept")
    pending = import_review.pending_queue(conn)
    assert [row["signature_key"] for row in pending] == ["b"]


def test_progress_counts_reviewed_and_remaining(conn):
    _insert_candidate(conn, "a")
    _insert_candidate(conn, "b")
    _insert_candidate(conn, "c")
    import_review.record_decision(conn, "a", "accept")
    reviewed, remaining = import_review.progress(conn)
    assert (reviewed, remaining) == (1, 2)


def test_rerunning_judge_and_merge_preserves_decisions(conn):
    """Task 6.3/D2: re-running merge (replacing `candidate` wholesale)
    must not touch `decision` — review survives a known-set correction."""
    _insert_candidate(conn, "a")
    import_review.record_decision(conn, "a", "accept")

    import store

    store.replace_stage_table(conn, "merge")  # simulates merge re-running
    _insert_candidate(conn, "a")  # merge re-inserts the same signature

    assert import_review.decided_signature_keys(conn) == {"a"}
    reviewed, _remaining = import_review.progress(conn)
    assert reviewed == 1


# ---------------------------------------------------------------------------
# format_candidate (task 6.2)
# ---------------------------------------------------------------------------


def test_format_candidate_shows_fields_sources_conflicts_and_evidence(conn):
    _insert_candidate(
        conn,
        "a",
        fields={"text": "legge til", "audio_ref": None},
        sources={"text": "ntnu"},
        conflicts={"translations": [{"source": "core6k", "value": "to add"}]},
        evidence={"rule": "same-head-different-particle", "cf_stock": {"text": "å legge til noen i kopi"}},
    )
    row = conn.execute("SELECT * FROM candidate WHERE signature_key = 'a'").fetchone()
    text = import_review.format_candidate(row)
    assert "legge til" in text
    assert "ntnu" in text
    assert "core6k" in text
    assert "same-head-different-particle" in text
    assert "cf. stock" in text
    assert "audio: no" in text


def test_format_candidate_shows_audio_present(conn):
    _insert_candidate(conn, "a", fields={"text": "hund", "audio_ref": "blob/abc123"})
    row = conn.execute("SELECT * FROM candidate WHERE signature_key = 'a'").fetchone()
    assert "audio: yes" in import_review.format_candidate(row)


# ---------------------------------------------------------------------------
# undo_last_decision / recent_decisions (design D5, tasks 3.6, 4.4)
# ---------------------------------------------------------------------------


def test_record_decision_never_writes_edited_fields(conn):
    """Task 3.4: review is triage only — `record_decision` takes no
    `edited_fields` argument at all, so no caller can write one."""
    _insert_candidate(conn, "a")
    import_review.record_decision(conn, "a", "accept")
    row = conn.execute("SELECT edited_fields_json FROM decision WHERE signature_key='a'").fetchone()
    assert row["edited_fields_json"] is None


def test_undo_reverses_the_most_recent_decision(conn):
    _insert_candidate(conn, "a")
    _insert_candidate(conn, "b")
    import_review.record_decision(conn, "a", "accept")
    import_review.record_decision(conn, "b", "reject")

    undone = import_review.undo_last_decision(conn)
    assert undone == "b"
    assert conn.execute("SELECT 1 FROM decision WHERE signature_key='b'").fetchone() is None
    assert conn.execute("SELECT 1 FROM decision WHERE signature_key='a'").fetchone() is not None
    pending = import_review.pending_queue(conn)
    assert "b" in [row["signature_key"] for row in pending]


def test_undo_steps_back_multiple_levels(conn):
    _insert_candidate(conn, "a")
    _insert_candidate(conn, "b")
    _insert_candidate(conn, "c")
    import_review.record_decision(conn, "a", "accept")
    import_review.record_decision(conn, "b", "accept")
    import_review.record_decision(conn, "c", "reject")

    assert import_review.undo_last_decision(conn) == "c"
    assert import_review.undo_last_decision(conn) == "b"
    assert import_review.undo_last_decision(conn) == "a"
    assert import_review.decided_signature_keys(conn) == set()


def test_undo_with_nothing_decided_returns_none(conn):
    assert import_review.undo_last_decision(conn) is None


def test_recent_decisions_returns_newest_first(conn):
    _insert_candidate(conn, "a", fields={"text": "first"})
    _insert_candidate(conn, "b", fields={"text": "second"})
    import_review.record_decision(conn, "a", "accept")
    import_review.record_decision(conn, "b", "reject")

    recent = import_review.recent_decisions(conn)
    assert [row["signature_key"] for row in recent] == ["b", "a"]


# ---------------------------------------------------------------------------
# Review server routes (import-review-web tasks 2.3, 4.4) — replaces the
# old run_interactive/edit-path tests; the terminal loop is gone.
# ---------------------------------------------------------------------------


@pytest.fixture
def client(conn):
    app = import_web.create_app(conn)
    return app.test_client()


def test_state_route_shows_first_pending_candidate(conn, client):
    _insert_candidate(conn, "low", order_key={"frequency_index": 500, "cefr": None, "chapter": None})
    _insert_candidate(conn, "high", order_key={"frequency_index": 5, "cefr": None, "chapter": None})
    data = client.get("/api/state").get_json()
    assert data["current"]["signature_key"] == "high"
    assert data["remaining"] == 2
    assert data["reviewed"] == 0


def test_decide_route_records_decision_and_advances(conn, client):
    _insert_candidate(conn, "a", order_key={"frequency_index": 1, "cefr": None, "chapter": None})
    _insert_candidate(conn, "b", order_key={"frequency_index": 2, "cefr": None, "chapter": None})
    response = client.post("/api/decisions", json={"signature_key": "a", "decision": "reject"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["current"]["signature_key"] == "b"
    assert data["reviewed"] == 1
    assert conn.execute("SELECT decision FROM decision WHERE signature_key='a'").fetchone()["decision"] == "reject"


def test_decide_route_rejects_invalid_decision(conn, client):
    _insert_candidate(conn, "a")
    response = client.post("/api/decisions", json={"signature_key": "a", "decision": "maybe"})
    assert response.status_code == 400


def test_decide_route_never_writes_edited_fields(conn, client):
    _insert_candidate(conn, "a")
    client.post("/api/decisions", json={"signature_key": "a", "decision": "accept"})
    row = conn.execute("SELECT edited_fields_json FROM decision WHERE signature_key='a'").fetchone()
    assert row["edited_fields_json"] is None


def test_undo_route_reverses_last_decision(conn, client):
    _insert_candidate(conn, "a")
    client.post("/api/decisions", json={"signature_key": "a", "decision": "accept"})
    response = client.post("/api/undo")
    data = response.get_json()
    assert data["reviewed"] == 0
    assert data["current"]["signature_key"] == "a"


def test_skip_route_shows_next_candidate_without_deciding(conn, client):
    _insert_candidate(conn, "a", order_key={"frequency_index": 1, "cefr": None, "chapter": None})
    _insert_candidate(conn, "b", order_key={"frequency_index": 2, "cefr": None, "chapter": None})
    response = client.post("/api/skip", json={"signature_key": "a"})
    data = response.get_json()
    assert data["current"]["signature_key"] == "b"
    assert conn.execute("SELECT 1 FROM decision WHERE signature_key='a'").fetchone() is None
    assert data["remaining"] == 2  # still undecided, just not shown


def test_state_route_has_no_candidate_when_queue_is_empty(client):
    data = client.get("/api/state").get_json()
    assert data["current"] is None
    assert data["remaining"] == 0


def test_index_route_serves_the_review_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"<title>" in response.data


# ---------------------------------------------------------------------------
# Audio route (import-review-web tasks 2.4, 2.5, 4.5)
# ---------------------------------------------------------------------------


@pytest.fixture
def audio_env(tmp_path, monkeypatch):
    """A fake `ntnu` archive under a temp IMPORT_DIR with one member — lets
    the audio route's real zipfile-random-access path run without the
    real (gitignored) archives on disk."""
    import ingest as import_ingest

    archive_path = tmp_path / import_ingest.APKG_SOURCES["ntnu"]["file"]
    import zipfile

    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("1", b"FAKE-HUMAN-AUDIO-BYTES")
    monkeypatch.setattr(import_ingest, "IMPORT_DIR", tmp_path)
    return archive_path


def _insert_signature_chain(conn, signature_key, *, source, audio_ref, media_member):
    """A minimal raw_note -> normalized -> signature chain so the audio
    route's join can resolve (source, audio_ref) -> archive member."""
    run_id = import_store.start_run(conn, "ingest")
    cur = conn.execute(
        """
        INSERT INTO raw_note (run_id, source, source_note_id, note_type, fields_json, tags_json, media_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, source, "note-1", "word", "{}", "[]", json.dumps({audio_ref: media_member})),
    )
    raw_note_id = cur.lastrowid

    run_id = import_store.start_run(conn, "normalize")
    cur = conn.execute(
        "INSERT INTO normalized (run_id, raw_note_id, source, note_type, text, audio_ref) VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, raw_note_id, source, "word", "text", audio_ref),
    )
    normalized_id = cur.lastrowid

    run_id = import_store.start_run(conn, "key")
    conn.execute(
        "INSERT INTO signature (run_id, normalized_id, signature_key, head_lemma) VALUES (?, ?, ?, ?)",
        (run_id, normalized_id, signature_key, "text"),
    )
    conn.commit()


def test_audio_route_streams_bytes_for_a_human_source(conn, client, audio_env):
    _insert_signature_chain(conn, "a", source="ntnu", audio_ref="foo.mp3", media_member="1")
    _insert_candidate(conn, "a", fields={"audio_ref": "foo.mp3"}, sources={"audio_ref": "ntnu"})

    response = client.get("/api/audio/a")
    assert response.status_code == 200
    assert response.data == b"FAKE-HUMAN-AUDIO-BYTES"


def test_audio_route_404s_for_a_synthesised_source(conn, client, audio_env):
    _insert_signature_chain(conn, "a", source="core6k", audio_ref="hypertts-1.mp3", media_member="1")
    _insert_candidate(conn, "a", fields={"audio_ref": "hypertts-1.mp3"}, sources={"audio_ref": "core6k"})

    response = client.get("/api/audio/a")
    assert response.status_code == 404


def test_audio_route_404s_for_an_unknown_signature(client):
    response = client.get("/api/audio/does-not-exist")
    assert response.status_code == 404


def test_audio_route_404s_when_candidate_has_no_audio(conn, client):
    _insert_candidate(conn, "a", fields={"audio_ref": None}, sources={})
    response = client.get("/api/audio/a")
    assert response.status_code == 404


def test_candidate_payload_has_audio_only_for_human_winning_source(conn, client, audio_env):
    _insert_signature_chain(conn, "a", source="ntnu", audio_ref="foo.mp3", media_member="1")
    _insert_candidate(conn, "a", fields={"audio_ref": "foo.mp3"}, sources={"audio_ref": "ntnu"})
    data = client.get("/api/state").get_json()
    assert data["current"]["has_audio"] is True
