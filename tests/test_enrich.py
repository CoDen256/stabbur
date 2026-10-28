"""smia-enrichment proxy: routes/enrich.py forwards to smia_client and passes
its responses through unchanged — no retry, no fallback (tasks 7.1-7.4, 3.4).
Every test mocks smia_client itself, never a real network call."""

from __future__ import annotations

import smia_client
from tests.conftest import AUTH


def test_proxies_ipa_lookup_with_the_right_body_shape(client, monkeypatch):
    seen = {}

    def fake_post(path, json, timeout=20.0):
        seen["path"] = path
        seen["json"] = json
        return 200, {"provider": "nst", "candidates": [{"ipa": "'hʉːs", "variety": "standard"}]}

    monkeypatch.setattr(smia_client, "post", fake_post)
    resp = client.post(
        "/api/enrich/ipa", json={"text": "hus", "lang": "nb", "provider": "nst"}, headers=AUTH
    )
    assert resp.status_code == 200
    assert seen["path"] == "/ipa"
    assert seen["json"] == {"text": "hus", "lang": "nb", "provider": "nst"}
    assert resp.get_json()["provider"] == "nst"


def test_proxies_translations_lookup(client, monkeypatch):
    seen = {}

    def fake_post(path, json, timeout=20.0):
        seen["path"] = path
        seen["json"] = json
        return 200, {"provider": "deepl", "text": "the house"}

    monkeypatch.setattr(smia_client, "post", fake_post)
    resp = client.post(
        "/api/enrich/translations",
        json={"text": "huset", "from": "no", "to": "en", "provider": "deepl"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert seen["path"] == "/translations"
    assert resp.get_json()["text"] == "the house"


def test_proxies_inflections_and_tts_lookups(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        smia_client, "post", lambda path, json, timeout=20.0: calls.append((path, json)) or (200, {"ok": True})
    )

    client.post("/api/enrich/inflections", json={"word": "hus", "lang": "no", "provider": "ordbank"}, headers=AUTH)
    client.post("/api/enrich/tts", json={"text": "hus", "lang": "no", "provider": "kaikki"}, headers=AUTH)

    assert calls[0][0] == "/inflections"
    assert calls[1][0] == "/tts"


def test_provider_failure_passes_through_unchanged_with_no_retry(client, monkeypatch):
    calls = []

    def fake_post(path, json, timeout=20.0):
        calls.append(json["provider"])
        return 404, {"error": "no entry found", "provider": json["provider"]}

    monkeypatch.setattr(smia_client, "post", fake_post)
    resp = client.post(
        "/api/enrich/ipa", json={"text": "huset", "lang": "nb", "provider": "nst"}, headers=AUTH
    )
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "no entry found"
    # No retry against a different provider — exactly one call was made.
    assert calls == ["nst"]


def test_smia_unreachable_is_a_502_not_a_crash(client, monkeypatch):
    def fake_post(path, json, timeout=20.0):
        raise smia_client.SmiaUnavailableError("connection refused")

    monkeypatch.setattr(smia_client, "post", fake_post)
    resp = client.post(
        "/api/enrich/ipa", json={"text": "hus", "lang": "nb", "provider": "nst"}, headers=AUTH
    )
    assert resp.status_code == 502


def test_unknown_kind_is_rejected_before_calling_smia(client, monkeypatch):
    called = []
    monkeypatch.setattr(smia_client, "post", lambda *a, **k: called.append(1) or (200, {}))

    resp = client.post("/api/enrich/stt", json={"provider": "hf_whisper"}, headers=AUTH)
    assert resp.status_code == 400
    assert "stt" in resp.get_json()["error"]
    assert called == []


def test_providers_catalog_is_proxied(client, monkeypatch):
    monkeypatch.setattr(
        smia_client, "get", lambda path, timeout=20.0: (200, {"ipa": ["nst", "kaikki"]})
    )
    resp = client.get("/api/enrich/providers", headers=AUTH)
    assert resp.status_code == 200
    assert resp.get_json() == {"ipa": ["nst", "kaikki"]}


def test_enrich_requires_auth(client):
    resp = client.post("/api/enrich/ipa", json={"text": "hus", "lang": "nb", "provider": "nst"})
    assert resp.status_code == 401


def test_tts_use_fetches_bytes_and_stores_a_real_stabbur_blob(client, monkeypatch):
    import hashlib

    audio_bytes = b"fake mp3 bytes for a tts candidate"

    def fake_get_bytes(path, timeout=30.0):
        assert path == "/tts/abc123"
        return 200, audio_bytes, "audio/mpeg"

    monkeypatch.setattr(smia_client, "get_bytes", fake_get_bytes)
    resp = client.post("/api/enrich/tts/use", json={"sha256": "abc123"}, headers=AUTH)
    assert resp.status_code == 200
    sha = resp.get_json()["sha256"]
    assert sha == hashlib.sha256(audio_bytes).hexdigest()

    # And it's a real stabbur blob, fetchable the normal way.
    blob_resp = client.get(f"/blob/{sha}")
    assert blob_resp.status_code == 200
    assert blob_resp.data == audio_bytes


def test_using_the_same_tts_candidate_twice_is_idempotent(client, monkeypatch):
    audio_bytes = b"same candidate bytes"
    monkeypatch.setattr(smia_client, "get_bytes", lambda path, timeout=30.0: (200, audio_bytes, "audio/mpeg"))

    first = client.post("/api/enrich/tts/use", json={"sha256": "xyz"}, headers=AUTH)
    second = client.post("/api/enrich/tts/use", json={"sha256": "xyz"}, headers=AUTH)
    assert first.get_json()["sha256"] == second.get_json()["sha256"]


def test_tts_use_surfaces_smia_fetch_failure(client, monkeypatch):
    monkeypatch.setattr(smia_client, "get_bytes", lambda path, timeout=30.0: (404, b"", "application/json"))
    resp = client.post("/api/enrich/tts/use", json={"sha256": "missing"}, headers=AUTH)
    assert resp.status_code == 502
