"""Tests for scripts/import/review.py — section 6 of bulk-import-anki-csv
(tasks 6.1-6.4). Uses a small hand-built candidate table so these run
without the real archives or stock bundle.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "import"))

import review as import_review  # noqa: E402
import store as import_store  # noqa: E402


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
# run_interactive (tasks 6.1-6.4 wired together, scripted input)
# ---------------------------------------------------------------------------


def test_run_interactive_accept_reject_and_quit(conn):
    _insert_candidate(conn, "a")
    _insert_candidate(conn, "b")
    _insert_candidate(conn, "c")
    answers = iter(["a", "r", "q"])
    recorded = import_review.run_interactive(conn, input_fn=lambda _prompt: next(answers), print_fn=lambda *_a: None)
    assert recorded == 2
    assert conn.execute("SELECT decision FROM decision WHERE signature_key='a'").fetchone()["decision"] == "accept"
    assert conn.execute("SELECT decision FROM decision WHERE signature_key='b'").fetchone()["decision"] == "reject"
    assert conn.execute("SELECT 1 FROM decision WHERE signature_key='c'").fetchone() is None


def test_run_interactive_skip_leaves_candidate_undecided(conn):
    _insert_candidate(conn, "a")
    answers = iter(["s"])
    import_review.run_interactive(conn, input_fn=lambda _prompt: next(answers), print_fn=lambda *_a: None)
    assert conn.execute("SELECT 1 FROM decision WHERE signature_key='a'").fetchone() is None


def test_run_interactive_edit_then_accept_records_edited_fields(conn):
    _insert_candidate(conn, "a", fields={"text": "legge til"})
    answers = iter(["e", "translations", "to add", ""])
    import_review.run_interactive(conn, input_fn=lambda _prompt: next(answers), print_fn=lambda *_a: None)
    row = conn.execute("SELECT decision, edited_fields_json FROM decision WHERE signature_key='a'").fetchone()
    assert row["decision"] == "accept"
    assert json.loads(row["edited_fields_json"]) == {"translations": "to add"}
