"""Task 2.4 — blob storage: upload, idempotency, serving, wiring to
Note.audio_blob."""

from __future__ import annotations

import hashlib
import os

from db.models import Note
from db.session import get_sessionmaker
from tests.conftest import AUTH


def test_upload_returns_sha256(client):
    data = b"fake mp3 bytes"
    resp = client.post("/blobs", data={"audio": (_file(data), "clip.mp3")}, headers=AUTH, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.get_json()["sha256"] == hashlib.sha256(data).hexdigest()


def test_reuploading_same_bytes_is_idempotent(client):
    import blob_storage

    data = b"same bytes twice"
    resp1 = client.post("/blobs", data={"audio": (_file(data), "a.mp3")}, headers=AUTH, content_type="multipart/form-data")
    resp2 = client.post("/blobs", data={"audio": (_file(data), "b.mp3")}, headers=AUTH, content_type="multipart/form-data")

    sha = resp1.get_json()["sha256"]
    assert resp2.get_json()["sha256"] == sha

    files = [f for f in os.listdir(blob_storage.BLOB_DIR) if not f.endswith(".tmp")]
    assert files == [f"{sha}.mp3"]


def test_get_blob_serves_exact_bytes(client):
    data = b"the exact audio bytes"
    upload = client.post("/blobs", data={"audio": (_file(data), "clip.mp3")}, headers=AUTH, content_type="multipart/form-data")
    sha = upload.get_json()["sha256"]

    resp = client.get(f"/blob/{sha}")
    assert resp.status_code == 200
    assert resp.data == data
    assert "immutable" in resp.headers["Cache-Control"]


def test_get_unknown_blob_is_404(client):
    resp = client.get("/blob/" + "0" * 64)
    assert resp.status_code == 404


def test_get_blob_rejects_malformed_sha256(client):
    resp = client.get("/blob/not-a-sha256")
    assert resp.status_code == 404


def test_post_blob_rejects_oversized_upload(client, monkeypatch):
    import routes.blobs as blobs_module

    monkeypatch.setattr(blobs_module, "MAX_BLOB_SIZE_BYTES", 10)
    resp = client.post(
        "/blobs",
        data={"audio": (_file(b"this is definitely more than ten bytes"), "clip.mp3")},
        headers=AUTH,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 413


def test_note_audio_blob_accepts_uploaded_hash(client):
    data = b"attach me to a note"
    upload = client.post("/blobs", data={"audio": (_file(data), "clip.mp3")}, headers=AUTH, content_type="multipart/form-data")
    sha = upload.get_json()["sha256"]

    create = client.post(
        "/api/notes",
        json={"type": "word", "source_lang": "no", "text": "hus"},
        headers=AUTH,
    )
    note_id = create.get_json()["id"]

    patch = client.patch(f"/api/notes/{note_id}", json={"audio_blob": sha}, headers=AUTH)
    assert patch.status_code == 200
    assert patch.get_json()["audio_blob"] == sha

    Session = get_sessionmaker()
    with Session() as db:
        note = db.get(Note, note_id)
        assert note.audio_blob == sha


def _file(data: bytes):
    import io

    return io.BytesIO(data)
