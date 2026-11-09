"""Task group 4 — `captures-ingestion`: atomic promote, idempotent replay,
source-shape validation, the unattached-audio query, FK enforcement, and
the public read API's unchanged contract."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.models import Capture, Note
from db.session import get_sessionmaker
from routes.notes import READ_API_FIELDS
from tests.conftest import AUTH


def _capture_payload(**overrides):
    payload = {
        "id": "cap-1",
        "selected_text": "hunden løper",
        "context_text": "Se, hunden løper etter ballen.",
        "translations": [{"provider": "dictcc_static", "lang": "en", "text": "the dog runs"}],
        "source": {"web": "https://example.com/page", "title": "Example"},
    }
    payload.update(overrides)
    return payload


def test_ingestion_writes_both_rows(client):
    resp = client.post("/api/captures", json=_capture_payload(), headers=AUTH)
    assert resp.status_code == 201
    body = resp.get_json()

    assert body["capture"]["id"] == "cap-1"
    assert body["capture"]["selected_text"] == "hunden løper"
    note = body["note"]
    assert note["origin"] == "capture"
    assert note["capture_id"] == "cap-1"
    assert note["status"] == "draft"
    assert note["text"] == "hunden løper"


def test_replaying_the_same_id_creates_nothing_new(client):
    first = client.post("/api/captures", json=_capture_payload(), headers=AUTH)
    assert first.status_code == 201
    first_note_id = first.get_json()["note"]["id"]

    second = client.post("/api/captures", json=_capture_payload(selected_text="different text!"), headers=AUTH)
    assert second.status_code == 200
    # D2.6: the replay's (different) body is ignored — the stored pair,
    # from the original request, is returned unchanged.
    assert second.get_json()["capture"]["selected_text"] == "hunden løper"
    assert second.get_json()["note"]["id"] == first_note_id

    Session = get_sessionmaker()
    with Session() as db:
        assert db.scalar(select(Capture).where(Capture.id == "cap-1")) is not None
        notes = db.scalars(select(Note).where(Note.capture_id == "cap-1")).all()
        assert len(notes) == 1


def test_no_id_is_rejected(client):
    payload = _capture_payload()
    del payload["id"]
    resp = client.post("/api/captures", json=payload, headers=AUTH)
    assert resp.status_code == 400


def test_same_text_different_ids_and_sources_produce_two_pairs(client):
    client.post("/api/captures", json=_capture_payload(id="cap-1", source={"web": "https://a.example"}), headers=AUTH)
    client.post("/api/captures", json=_capture_payload(id="cap-2", source={"web": "https://b.example"}), headers=AUTH)

    Session = get_sessionmaker()
    with Session() as db:
        assert db.scalar(select(Capture).where(Capture.id == "cap-1")) is not None
        assert db.scalar(select(Capture).where(Capture.id == "cap-2")) is not None
        notes = db.scalars(select(Note).where(Note.capture_id.in_(["cap-1", "cap-2"]))).all()
        assert len(notes) == 2


def test_youtube_source_without_video_id_is_rejected(client):
    resp = client.post("/api/captures", json=_capture_payload(source={"youtube": ""}), headers=AUTH)
    assert resp.status_code == 400


def test_web_source_without_url_is_rejected(client):
    resp = client.post("/api/captures", json=_capture_payload(source={"web": ""}), headers=AUTH)
    assert resp.status_code == 400


def test_unrecognised_source_shape_is_rejected(client):
    resp = client.post("/api/captures", json=_capture_payload(source={"shadowing_segment_id": "abc"}), headers=AUTH)
    assert resp.status_code == 400


def test_recognised_shape_with_extra_sibling_keys_is_stored_unchanged(client):
    source = {
        "youtube": "dQw4w9WgXcQ",
        "cueStartMs": 73120,
        "cueEndMs": 75400,
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=73",
        "title": "A video",
    }
    resp = client.post("/api/captures", json=_capture_payload(source=source), headers=AUTH)
    assert resp.status_code == 201
    assert resp.get_json()["capture"]["source"] == source


def test_youtube_capture_with_timecode_and_no_audio_is_accepted(client):
    source = {"youtube": "dQw4w9WgXcQ", "cueStartMs": 1000, "cueEndMs": 2000, "url": "https://youtu.be/x"}
    resp = client.post("/api/captures", json=_capture_payload(source=source, audio_blob=None), headers=AUTH)
    assert resp.status_code == 201
    assert resp.get_json()["capture"]["audio_blob"] is None
    assert resp.get_json()["note"]["audio_blob"] is None


def test_editing_promoted_note_leaves_capture_unchanged(client):
    create = client.post("/api/captures", json=_capture_payload(), headers=AUTH)
    note_id = create.get_json()["note"]["id"]

    client.patch(
        f"/api/notes/{note_id}",
        json={"text": "rewritten entirely", "translations": [{"lang": "en", "text": "something else"}]},
        headers=AUTH,
    )

    capture = client.get("/api/captures/cap-1", headers=AUTH).get_json()
    assert capture["selected_text"] == "hunden løper"
    assert capture["translations"] == [{"provider": "dictcc_static", "lang": "en", "text": "the dog runs"}]


def test_unattached_audio_query_lifecycle(client):
    """Task 2.3's atomic promote copies the capture's audio onto its own
    note at creation, so the capture is attached from birth in the common
    case. The query (task 3.2/4.7) earns its keep once that note's audio
    is cleared or reassigned — e.g. the operator replaces the wide clip
    with a trimmed one (design.md D6) — leaving the capture's own
    recording unclaimed until something references it again."""
    create = client.post(
        "/api/captures",
        json=_capture_payload(id="cap-audio", audio_blob="a" * 64, audio_sel_ms=[0, 1000]),
        headers=AUTH,
    )
    note_id = create.get_json()["note"]["id"]

    listing = client.get("/api/captures?unattached=true", headers=AUTH).get_json()
    assert not any(c["id"] == "cap-audio" for c in listing)

    client.patch(f"/api/notes/{note_id}", json={"audio_blob": "b" * 64}, headers=AUTH)

    listing_after_reassign = client.get("/api/captures?unattached=true", headers=AUTH).get_json()
    assert any(c["id"] == "cap-audio" for c in listing_after_reassign)

    client.patch(f"/api/notes/{note_id}", json={"audio_blob": "a" * 64}, headers=AUTH)

    listing_after_reattach = client.get("/api/captures?unattached=true", headers=AUTH).get_json()
    assert not any(c["id"] == "cap-audio" for c in listing_after_reattach)


def test_audio_less_capture_never_appears_unattached(client):
    client.post("/api/captures", json=_capture_payload(audio_blob=None), headers=AUTH)
    listing = client.get("/api/captures?unattached=true", headers=AUTH).get_json()
    assert not any(c["id"] == "cap-1" for c in listing)


def test_note_cannot_reference_a_nonexistent_capture(client):
    resp = client.post(
        "/api/notes",
        json={"type": "word", "source_lang": "no", "text": "hus", "origin": "capture", "capture_id": "ghost"},
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_deleting_a_referenced_capture_is_rejected(client):
    client.post("/api/captures", json=_capture_payload(), headers=AUTH)

    Session = get_sessionmaker()
    with Session() as db:
        capture = db.get(Capture, "cap-1")
        db.delete(capture)
        try:
            db.commit()
            assert False, "expected deleting a referenced capture to fail"
        except IntegrityError:
            db.rollback()


def test_serialize_public_key_set_is_unchanged_for_capture_origin_notes(client):
    create = client.post("/api/captures", json=_capture_payload(), headers=AUTH)
    note_id = create.get_json()["note"]["id"]
    client.patch(f"/api/notes/{note_id}", json={"status": "ready"}, headers=AUTH)

    public = client.get("/api/notes?source_lang=no", headers=AUTH).get_json()
    note = next(n for n in public if n["id"] == note_id)
    assert set(note.keys()) == set(READ_API_FIELDS)
    assert "source" not in note


def test_invalid_note_from_capture_stores_neither_row(client):
    resp = client.post("/api/captures", json=_capture_payload(type="bogus"), headers=AUTH)
    assert resp.status_code == 400

    Session = get_sessionmaker()
    with Session() as db:
        assert db.get(Capture, "cap-1") is None
        assert db.scalar(select(Note).where(Note.capture_id == "cap-1")) is None
