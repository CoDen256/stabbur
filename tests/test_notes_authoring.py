"""Task 3.3 — the full hand-authoring flow end to end, plus the CRUD
surface's own request-level tests (D-N3)."""

from __future__ import annotations

import io

from tests.conftest import AUTH


def test_create_requires_type_source_lang_text(client):
    resp = client.post("/api/notes", json={"type": "word"}, headers=AUTH)
    assert resp.status_code == 400


def test_create_defaults_to_draft(client):
    resp = client.post(
        "/api/notes", json={"type": "word", "source_lang": "no", "text": "hus"}, headers=AUTH
    )
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "draft"


def test_missing_auth_is_rejected(client):
    resp = client.post("/api/notes", json={"type": "word", "source_lang": "no", "text": "hus"})
    assert resp.status_code == 401


def test_editing_ready_note_keeps_status_unless_changed(client):
    create = client.post(
        "/api/notes",
        json={"type": "word", "source_lang": "no", "text": "hus", "status": "ready"},
        headers=AUTH,
    )
    note_id = create.get_json()["id"]

    patch = client.patch(f"/api/notes/{note_id}", json={"text": "huset"}, headers=AUTH)
    assert patch.status_code == 200
    assert patch.get_json()["status"] == "ready"
    assert patch.get_json()["text"] == "huset"


def test_deleting_ready_note_is_not_hard_deleted(client):
    create = client.post(
        "/api/notes",
        json={"type": "word", "source_lang": "no", "text": "hus", "status": "ready"},
        headers=AUTH,
    )
    note_id = create.get_json()["id"]

    delete = client.delete(f"/api/notes/{note_id}", headers=AUTH)
    assert delete.status_code == 200
    assert delete.get_json()["deleted_at"] is not None

    get_after = client.get(f"/api/notes/{note_id}", headers=AUTH)
    assert get_after.status_code == 200


def test_deleting_draft_note_hard_deletes(client):
    create = client.post(
        "/api/notes", json={"type": "word", "source_lang": "no", "text": "hus"}, headers=AUTH
    )
    note_id = create.get_json()["id"]

    delete = client.delete(f"/api/notes/{note_id}", headers=AUTH)
    assert delete.status_code == 204

    get_after = client.get(f"/api/notes/{note_id}", headers=AUTH)
    assert get_after.status_code == 404


def test_origin_derives_to_manual_when_omitted_and_no_capture(client):
    resp = client.post(
        "/api/notes", json={"type": "word", "source_lang": "no", "text": "hus"}, headers=AUTH
    )
    assert resp.status_code == 201
    assert resp.get_json()["origin"] == "manual"


def test_origin_derives_to_capture_when_capture_id_present(client):
    resp = client.post(
        "/api/notes",
        json={"type": "word", "source_lang": "no", "text": "hus", "capture_id": "cap-1"},
        headers=AUTH,
    )
    assert resp.status_code == 201
    assert resp.get_json()["origin"] == "capture"


def test_import_ref_without_explicit_origin_is_rejected(client):
    resp = client.post(
        "/api/notes",
        json={
            "type": "word", "source_lang": "no", "text": "hus",
            "import_ref": {"source": "ntnu", "source_note_id": "1", "run_id": "r1"},
        },
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_origin_import_without_import_ref_is_rejected(client):
    resp = client.post(
        "/api/notes",
        json={"type": "word", "source_lang": "no", "text": "hus", "origin": "import"},
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_origin_import_with_import_ref_is_accepted(client):
    resp = client.post(
        "/api/notes",
        json={
            "type": "word", "source_lang": "no", "text": "hus", "origin": "import",
            "import_ref": {"source": "ntnu", "source_note_id": "1", "run_id": "r1"},
        },
        headers=AUTH,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["origin"] == "import"
    assert body["import_ref"]["source"] == "ntnu"


def test_patching_origin_to_a_different_value_is_rejected(client):
    create = client.post(
        "/api/notes", json={"type": "word", "source_lang": "no", "text": "hus"}, headers=AUTH
    )
    note_id = create.get_json()["id"]

    patch = client.patch(f"/api/notes/{note_id}", json={"origin": "import"}, headers=AUTH)
    assert patch.status_code == 400

    get_after = client.get(f"/api/notes/{note_id}", headers=AUTH)
    assert get_after.get_json()["origin"] == "manual"


def test_patching_content_on_imported_note_succeeds_and_keeps_origin(client):
    create = client.post(
        "/api/notes",
        json={
            "type": "word", "source_lang": "no", "text": "hus", "origin": "import",
            "import_ref": {"source": "ntnu", "source_note_id": "1", "run_id": "r1"},
        },
        headers=AUTH,
    )
    note_id = create.get_json()["id"]

    patch = client.patch(f"/api/notes/{note_id}", json={"text": "huset"}, headers=AUTH)
    assert patch.status_code == 200
    assert patch.get_json()["text"] == "huset"
    assert patch.get_json()["origin"] == "import"


def test_patching_with_identical_origin_value_is_accepted(client):
    create = client.post(
        "/api/notes", json={"type": "word", "source_lang": "no", "text": "hus"}, headers=AUTH
    )
    note_id = create.get_json()["id"]

    patch = client.patch(f"/api/notes/{note_id}", json={"origin": "manual", "text": "huset"}, headers=AUTH)
    assert patch.status_code == 200
    assert patch.get_json()["origin"] == "manual"
    assert patch.get_json()["text"] == "huset"


def test_full_hand_authoring_flow_end_to_end(client):
    # 1. Create a draft note.
    create = client.post(
        "/api/notes",
        json={
            "type": "word",
            "source_lang": "no",
            "text": "hus",
            "pos": "substantiv",
            "translations": [{"lang": "en", "text": "house"}],
            "inflections": {
                "article": "et",
                "sg_indef": "hus",
                "sg_def": "huset",
                "pl_indef": "hus",
                "pl_def": "husene",
            },
        },
        headers=AUTH,
    )
    assert create.status_code == 201
    note = create.get_json()
    assert note["status"] == "draft"
    note_id = note["id"]

    # 2. Attach audio: upload, then PATCH audio_blob.
    upload = client.post(
        "/blobs",
        data={"audio": (io.BytesIO(b"hus.mp3 bytes"), "hus.mp3")},
        headers=AUTH,
        content_type="multipart/form-data",
    )
    sha = upload.get_json()["sha256"]
    patch_audio = client.patch(f"/api/notes/{note_id}", json={"audio_blob": sha}, headers=AUTH)
    assert patch_audio.status_code == 200
    assert patch_audio.get_json()["audio_blob"] == sha

    # 3. Mark ready.
    patch_ready = client.patch(f"/api/notes/{note_id}", json={"status": "ready"}, headers=AUTH)
    assert patch_ready.status_code == 200
    assert patch_ready.get_json()["status"] == "ready"

    # 4. Confirm it now appears in the read API's output.
    read = client.get("/api/notes?source_lang=no&status=ready", headers=AUTH)
    assert read.status_code == 200
    ids = [n["id"] for n in read.get_json()]
    assert note_id in ids
