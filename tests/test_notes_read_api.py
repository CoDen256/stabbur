"""Task 4.3 — the read API: filters, draft exclusion under every filter
combination, and the exact D-N4 response shape (task 4.1/4.4)."""

from __future__ import annotations

import datetime
import urllib.parse

from tests.conftest import AUTH

READ_API_FIELDS = {
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
}


def _create(client, **overrides):
    payload = {"type": "word", "source_lang": "no", "text": "hus", "status": "ready"}
    payload.update(overrides)
    resp = client.post("/api/notes", json=payload, headers=AUTH)
    assert resp.status_code == 201
    return resp.get_json()


def test_draft_notes_never_appear(client):
    _create(client, status="draft")
    _create(client, status="ready")

    for query in ("", "?status=ready", "?status=draft", "?source_lang=no"):
        resp = client.get(f"/api/notes{query}", headers=AUTH)
        statuses = {n["status"] for n in resp.get_json()}
        assert "draft" not in statuses


def test_filters_by_source_lang(client):
    _create(client, source_lang="no", text="hus")
    _create(client, source_lang="de", text="Haus")

    resp = client.get("/api/notes?source_lang=no", headers=AUTH)
    notes = resp.get_json()
    assert all(n["source_lang"] == "no" for n in notes)
    assert any(n["text"] == "hus" for n in notes)
    assert not any(n["text"] == "Haus" for n in notes)


def test_since_filter_catches_edits_to_already_ready_notes(client):
    note = _create(client, text="hus")
    note_id = note["id"]

    cutoff = urllib.parse.quote(datetime.datetime.now(datetime.timezone.utc).isoformat())

    # No edits yet since cutoff -> excluded.
    resp = client.get(f"/api/notes?since={cutoff}", headers=AUTH)
    assert note_id not in [n["id"] for n in resp.get_json()]

    client.patch(f"/api/notes/{note_id}", json={"text": "huset"}, headers=AUTH)

    resp = client.get(f"/api/notes?since={cutoff}", headers=AUTH)
    assert note_id in [n["id"] for n in resp.get_json()]


def test_tombstoned_notes_are_excluded(client):
    note = _create(client)
    note_id = note["id"]
    client.delete(f"/api/notes/{note_id}", headers=AUTH)

    resp = client.get("/api/notes", headers=AUTH)
    assert note_id not in [n["id"] for n in resp.get_json()]


def test_response_shape_matches_documented_contract_exactly(client):
    _create(
        client,
        type="word",
        pos="substantiv",
        lemma="hus",
        translations=[{"lang": "en", "text": "house"}],
        inflections={"article": "et", "sg_indef": "hus", "sg_def": "huset", "pl_indef": "hus", "pl_def": "husene"},
        context_text="Jeg bor i et hus.",
    )

    resp = client.get("/api/notes?source_lang=no", headers=AUTH)
    notes = resp.get_json()
    assert len(notes) >= 1
    for note in notes:
        assert set(note.keys()) == READ_API_FIELDS


def test_no_acknowledgment_endpoint_exists(client):
    """D44/4.2: no mechanism to report back what was pulled."""
    for path in ("/api/notes/ack", "/api/notes/acknowledge", "/api/pulls"):
        resp = client.post(path, json={}, headers=AUTH)
        # 405 for "/api/notes/ack" (matches the /api/notes/<id> route, but
        # POST isn't a method it supports) or 404 for a path that doesn't
        # match any route at all — either way, no acknowledgment mechanism.
        assert resp.status_code in (404, 405)
