"""origin-scoped-triage-belt backend additions: a per-origin remaining count
(task 1.3) and the generic link-shaped audio capture endpoint (task 6)."""

from __future__ import annotations

import hashlib

from tests.conftest import AUTH


def _create(client, **overrides):
    payload = {"type": "word", "source_lang": "no", "text": "hus"}
    payload.update(overrides)
    resp = client.post("/api/notes", json=payload, headers=AUTH)
    assert resp.status_code == 201
    return resp.get_json()


# ── GET /api/notes/authoring/counts ───────────────────────────────────────


def test_counts_are_scoped_by_origin_and_default_status_draft(client):
    _create(client, text="manual one", origin="manual", status="draft")
    _create(client, text="manual two", origin="manual", status="draft")
    _create(client, text="manual ready", origin="manual", status="ready")
    _create(client, text="imported", origin="import", import_ref={"source": "anki"}, status="draft")

    resp = client.get("/api/notes/authoring/counts", headers=AUTH)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"manual": 2, "capture": 0, "import": 1}


def test_counts_honour_an_explicit_status(client):
    _create(client, text="manual ready", origin="manual", status="ready")
    resp = client.get("/api/notes/authoring/counts?status=ready", headers=AUTH)
    assert resp.get_json()["manual"] == 1


def test_counts_rejects_unknown_status(client):
    resp = client.get("/api/notes/authoring/counts?status=bogus", headers=AUTH)
    assert resp.status_code == 400


def test_counts_requires_auth(client):
    resp = client.get("/api/notes/authoring/counts")
    assert resp.status_code == 401


# ── POST /api/enrich/manual-link (link-shaped, provider-independent) ─────


def test_direct_audio_link_is_fetched_and_stored(client, monkeypatch):
    import routes.enrich as enrich_module

    class FakeResp:
        status_code = 200
        headers = {"Content-Type": "audio/mpeg"}
        content = b"generic direct audio bytes"

    monkeypatch.setattr(enrich_module.requests, "get", lambda url, timeout=30.0, headers=None: FakeResp())
    resp = client.post(
        "/api/enrich/manual-link", json={"url": "https://audio00.forvo.com/mp3/abc.mp3"}, headers=AUTH
    )
    assert resp.status_code == 200
    assert resp.get_json()["sha256"] == hashlib.sha256(b"generic direct audio bytes").hexdigest()


def test_video_link_with_timecode_is_clipped(client, monkeypatch):
    import routes.enrich as enrich_module

    def fake_run(cmd, check, capture_output, text, timeout):
        out_index = cmd.index("-o")
        out_template = cmd[out_index + 1]
        with open(out_template.replace("%(ext)s", "mp3"), "wb") as f:
            f.write(b"generic clipped youtube audio")
        return None

    monkeypatch.setattr(enrich_module.subprocess, "run", fake_run)
    resp = client.post(
        "/api/enrich/manual-link",
        json={"url": "https://www.youtube.com/watch?v=abc123&t=100s"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.get_json()["sha256"] == hashlib.sha256(b"generic clipped youtube audio").hexdigest()


def test_link_that_is_neither_gets_a_clear_error(client, monkeypatch):
    import routes.enrich as enrich_module

    class FakeResp:
        status_code = 200
        headers = {"Content-Type": "text/html"}
        content = b"<html>not audio</html>"

    monkeypatch.setattr(enrich_module.requests, "get", lambda url, timeout=30.0, headers=None: FakeResp())
    resp = client.post(
        "/api/enrich/manual-link", json={"url": "https://example.com/word/hygge/"}, headers=AUTH
    )
    assert resp.status_code == 400
    assert "neither" in resp.get_json()["error"]


def test_unsafe_link_is_rejected_before_any_request(client, monkeypatch):
    import routes.enrich as enrich_module

    called = []
    monkeypatch.setattr(enrich_module.requests, "get", lambda *a, **k: called.append(1))
    monkeypatch.setattr(enrich_module.subprocess, "run", lambda *a, **k: called.append(1))
    resp = client.post(
        "/api/enrich/manual-link", json={"url": "http://169.254.169.254/latest/meta-data"}, headers=AUTH
    )
    assert resp.status_code == 400
    assert called == []
