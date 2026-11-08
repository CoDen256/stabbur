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


def test_force_refresh_is_forwarded_when_the_client_sends_it(client, monkeypatch):
    # editor-session-hygiene: the client's explicit re-run is relayed as-is —
    # post_enrich forwards the whole JSON body, so forceRefresh needs no
    # dedicated handling on stabbur's side, only a passing test confirming
    # the pass-through hasn't acquired one.
    seen = {}

    def fake_post(path, json, timeout=20.0):
        seen["json"] = json
        return 200, {"provider": "nst", "candidates": []}

    monkeypatch.setattr(smia_client, "post", fake_post)
    client.post(
        "/api/enrich/ipa",
        json={"text": "hus", "lang": "nb", "provider": "nst", "forceRefresh": True},
        headers=AUTH,
    )
    assert seen["json"] == {"text": "hus", "lang": "nb", "provider": "nst", "forceRefresh": True}


def test_force_refresh_is_not_originated_by_the_proxy(client, monkeypatch):
    seen = {}

    def fake_post(path, json, timeout=20.0):
        seen["json"] = json
        return 200, {"provider": "nst", "candidates": []}

    monkeypatch.setattr(smia_client, "post", fake_post)
    client.post(
        "/api/enrich/ipa", json={"text": "hus", "lang": "nb", "provider": "nst"}, headers=AUTH
    )
    assert "forceRefresh" not in seen["json"]


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

    resp = client.post("/api/enrich/notakind", json={"provider": "hf_whisper"}, headers=AUTH)
    assert resp.status_code == 400
    assert "notakind" in resp.get_json()["error"]
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


def test_tts_preview_streams_bytes_without_storing_a_blob(client, monkeypatch):
    import blob_storage

    audio_bytes = b"fake mp3 bytes for a preview"

    def fake_get_bytes(path, timeout=30.0):
        assert path == "/tts/preview123"
        return 200, audio_bytes, "audio/mpeg"

    monkeypatch.setattr(smia_client, "get_bytes", fake_get_bytes)
    # No AUTH header — this route must be reachable from a plain <audio
    # src=...>, which can't attach one (same exemption as /blob/<sha256>).
    resp = client.get("/api/enrich/tts/preview/preview123")
    assert resp.status_code == 200
    assert resp.data == audio_bytes
    assert resp.content_type == "audio/mpeg"

    # Unlike tts/use, previewing never commits anything to stabbur's own
    # content-addressed store.
    import hashlib
    assert not blob_storage.exists(hashlib.sha256(audio_bytes).hexdigest())


def test_tts_preview_surfaces_smia_fetch_failure(client, monkeypatch):
    monkeypatch.setattr(smia_client, "get_bytes", lambda path, timeout=30.0: (404, b"", "application/json"))
    resp = client.get("/api/enrich/tts/preview/missing")
    assert resp.status_code == 502


def test_stt_forwards_blob_bytes_as_multipart(client, monkeypatch):
    import blob_storage

    sha256 = blob_storage.store(b"fake audio bytes for stt")
    seen = {}

    def fake_post_multipart(path, files, data=None, timeout=30.0):
        seen["path"] = path
        seen["files"] = files
        seen["data"] = data
        return 200, {"provider": "hf_whisper", "text": "hallo verden"}

    monkeypatch.setattr(smia_client, "post_multipart", fake_post_multipart)
    resp = client.post(
        "/api/enrich/stt", json={"provider": "hf_whisper", "audio_blob": sha256, "lang": "nb"}, headers=AUTH
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"provider": "hf_whisper", "text": "hallo verden"}
    assert seen["path"] == "/stt"
    assert seen["data"] == {"provider": "hf_whisper", "lang": "nb"}
    assert seen["files"]["audio"][1] == b"fake audio bytes for stt"


def test_stt_requires_provider(client, monkeypatch):
    called = []
    monkeypatch.setattr(smia_client, "post_multipart", lambda *a, **k: called.append(1) or (200, {}))
    resp = client.post("/api/enrich/stt", json={"audio_blob": "whatever"}, headers=AUTH)
    assert resp.status_code == 400
    assert called == []


def test_stt_requires_an_existing_blob(client, monkeypatch):
    called = []
    monkeypatch.setattr(smia_client, "post_multipart", lambda *a, **k: called.append(1) or (200, {}))
    resp = client.post(
        "/api/enrich/stt", json={"provider": "hf_whisper", "audio_blob": "not-a-real-sha"}, headers=AUTH
    )
    assert resp.status_code == 400
    assert called == []


# ── manual-link-audio-capture: forvo (direct audio URL) ──────────────────


def test_forvo_capture_downloads_and_stores_a_blob(client, monkeypatch):
    import routes.enrich as enrich_module

    class FakeResp:
        status_code = 200
        headers = {"Content-Type": "audio/mpeg"}
        content = b"real forvo mp3 bytes"

    monkeypatch.setattr(enrich_module.requests, "get", lambda url, timeout=30.0, headers=None: FakeResp())
    resp = client.post(
        "/api/enrich/manual-link/forvo", json={"url": "https://audio00.forvo.com/mp3/abc.mp3"}, headers=AUTH
    )
    assert resp.status_code == 200
    import hashlib

    assert resp.get_json()["sha256"] == hashlib.sha256(b"real forvo mp3 bytes").hexdigest()


def test_forvo_capture_rejects_non_audio_response(client, monkeypatch):
    import routes.enrich as enrich_module

    class FakeResp:
        status_code = 200
        headers = {"Content-Type": "text/html"}
        content = b"<html>not audio</html>"

    monkeypatch.setattr(enrich_module.requests, "get", lambda url, timeout=30.0, headers=None: FakeResp())
    resp = client.post(
        "/api/enrich/manual-link/forvo", json={"url": "https://forvo.com/word/hygge/"}, headers=AUTH
    )
    assert resp.status_code == 400


def test_forvo_capture_rejects_unsafe_url(client, monkeypatch):
    import routes.enrich as enrich_module

    called = []
    monkeypatch.setattr(enrich_module.requests, "get", lambda *a, **k: called.append(1))
    resp = client.post(
        "/api/enrich/manual-link/forvo", json={"url": "http://169.254.169.254/latest/meta-data"}, headers=AUTH
    )
    assert resp.status_code == 400
    assert called == []


def test_forvo_capture_rejects_non_http_scheme(client, monkeypatch):
    import routes.enrich as enrich_module

    called = []
    monkeypatch.setattr(enrich_module.requests, "get", lambda *a, **k: called.append(1))
    resp = client.post("/api/enrich/manual-link/forvo", json={"url": "file:///etc/passwd"}, headers=AUTH)
    assert resp.status_code == 400
    assert called == []


# ── manual-link-audio-capture: filmot (YouTube URL + timecode) ───────────


def test_filmot_capture_invokes_yt_dlp_for_a_window_around_the_timecode(client, monkeypatch):
    import routes.enrich as enrich_module

    seen = {}

    def fake_run(cmd, check, capture_output, text, timeout):
        seen["cmd"] = cmd
        # Emulate yt-dlp's output: write the expected clip file.
        out_index = cmd.index("-o")
        out_template = cmd[out_index + 1]
        clip_path = out_template.replace("%(ext)s", "mp3")
        with open(clip_path, "wb") as f:
            f.write(b"fake trimmed youtube audio")
        return None

    monkeypatch.setattr(enrich_module.subprocess, "run", fake_run)
    resp = client.post(
        "/api/enrich/manual-link/filmot",
        json={"url": "https://www.youtube.com/watch?v=abc123&t=100s"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    import hashlib

    assert resp.get_json()["sha256"] == hashlib.sha256(b"fake trimmed youtube audio").hexdigest()
    assert "*98-102" in seen["cmd"]
    assert "--cookies" not in seen["cmd"]


def test_filmot_capture_passes_cookies_file_when_configured(client, monkeypatch, tmp_path):
    import routes.enrich as enrich_module

    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(cookies_file))

    seen = {}

    def fake_run(cmd, check, capture_output, text, timeout):
        seen["cmd"] = cmd
        cookies_index = cmd.index("--cookies")
        cookies_arg = cmd[cookies_index + 1]
        # --cookies must point at a per-request copy, never the configured
        # path itself (yt-dlp writes back to this file, which must never
        # corrupt the operator's original exported cookies or require it to
        # be writable) — checked here, while the route's temp dir is still
        # alive, since it's cleaned up by the time this function returns.
        assert cookies_arg != str(cookies_file)
        with open(cookies_arg) as f:
            seen["cookies_content"] = f.read()
        out_index = cmd.index("-o")
        out_template = cmd[out_index + 1]
        with open(out_template.replace("%(ext)s", "mp3"), "wb") as f:
            f.write(b"clip with cookies")
        return None

    monkeypatch.setattr(enrich_module.subprocess, "run", fake_run)
    resp = client.post(
        "/api/enrich/manual-link/filmot",
        json={"url": "https://www.youtube.com/watch?v=abc123&t=100s"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert seen["cookies_content"] == "# Netscape HTTP Cookie File\n"


def test_filmot_capture_ignores_cookies_env_when_file_missing(client, monkeypatch, tmp_path):
    import routes.enrich as enrich_module

    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(tmp_path / "does-not-exist.txt"))
    seen = {}

    def fake_run(cmd, check, capture_output, text, timeout):
        seen["cmd"] = cmd
        out_index = cmd.index("-o")
        out_template = cmd[out_index + 1]
        with open(out_template.replace("%(ext)s", "mp3"), "wb") as f:
            f.write(b"clip without cookies")
        return None

    monkeypatch.setattr(enrich_module.subprocess, "run", fake_run)
    resp = client.post(
        "/api/enrich/manual-link/filmot",
        json={"url": "https://www.youtube.com/watch?v=abc123&t=100s"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert "--cookies" not in seen["cmd"]


def test_filmot_capture_requires_a_timecode(client, monkeypatch):
    import routes.enrich as enrich_module

    called = []
    monkeypatch.setattr(enrich_module.subprocess, "run", lambda *a, **k: called.append(1))
    resp = client.post(
        "/api/enrich/manual-link/filmot", json={"url": "https://www.youtube.com/watch?v=abc123"}, headers=AUTH
    )
    assert resp.status_code == 400
    assert called == []


def test_filmot_capture_rejects_unsafe_url(client, monkeypatch):
    import routes.enrich as enrich_module

    called = []
    monkeypatch.setattr(enrich_module.subprocess, "run", lambda *a, **k: called.append(1))
    resp = client.post(
        "/api/enrich/manual-link/filmot", json={"url": "http://localhost:8080/?t=10"}, headers=AUTH
    )
    assert resp.status_code == 400
    assert called == []
