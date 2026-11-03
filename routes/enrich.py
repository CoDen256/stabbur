"""
routes/enrich.py — proxies the note editor's suggestion panels to smia
(smia-enrichment spec). The browser never calls smia directly: every request
here is authenticated with stabbur's own bearer token (auth.py's existing
before_request hook), and this module is the only thing holding smia's
token/address. Responses are passed through as smia reported them — no
retry, no fallback, no reinterpretation of its error shapes (design.md D3).
"""

from __future__ import annotations

import ipaddress
import os
import shutil
import socket
import subprocess
import tempfile
from urllib.parse import parse_qs, urlparse

import requests
from flask import Response, jsonify, request

import blob_storage
import smia_client

# stabbur only proxies the kinds a note actually has fields for — /stt has
# no corresponding note field today, so it's deliberately not exposed here.
ENRICHABLE_KINDS = ("ipa", "translations", "inflections", "tts")


class UnsafeUrlError(Exception):
    """A pasted URL failed the minimal safety check below — never fetched."""


def _validate_fetch_url(url: str) -> None:
    """Manual-link-audio-capture accepts arbitrary operator-pasted URLs
    (confirmed with operator — no domain allowlist), but that's not the same
    as blindly fetching whatever a pasted (or injected) URL happens to
    resolve to. Rejects non-http(s) schemes and any hostname that resolves
    to a private/loopback/link-local address, before any request is made
    (design.md D5)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"unsupported URL scheme {parsed.scheme!r}")
    if not parsed.hostname:
        raise UnsafeUrlError("URL has no hostname")
    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"could not resolve host: {exc}") from exc
    for *_rest, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise UnsafeUrlError(f"URL resolves to a disallowed address ({ip})")


# Forvo's audio CDN (and similar hotlink-protected hosts) rejects requests
# with no User-Agent or an obviously-scripted one, and some also check
# Referer — discovered live as a 403 on a real Forvo audio link with
# `requests`' default UA. A real browser UA (not a self-identifying one
# like smia's adapters use for Wikimedia, which Forvo specifically seems to
# still reject) plus a Referer pointing at forvo.com satisfies both checks.
_DIRECT_AUDIO_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://forvo.com/",
}


# yt-dlp/YouTube's own timecode query-param convention: `?t=123` or
# `?t=123s`. filmot's "open in YouTube" links use this same convention —
# confirmed against filmot's actual output would further narrow this, but
# this covers the documented/standard shape either way.
def _parse_youtube_timecode(url: str) -> int | None:
    query = parse_qs(urlparse(url).query)
    values = query.get("t") or query.get("start")
    if not values:
        return None
    raw = values[0].rstrip("s")
    try:
        return int(raw)
    except ValueError:
        return None


def register_enrich_routes(app):
    @app.route("/api/enrich/providers", methods=["GET"])
    def get_enrich_providers():
        try:
            status, body = smia_client.get("/providers")
        except smia_client.SmiaUnavailableError as exc:
            return jsonify({"error": f"smia unavailable: {exc}"}), 502
        return jsonify(body), status

    @app.route("/api/enrich/<kind>", methods=["POST"])
    def post_enrich(kind):
        if kind not in ENRICHABLE_KINDS:
            return jsonify({"error": f"unknown kind {kind!r}", "available": list(ENRICHABLE_KINDS)}), 400

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "a JSON body is required"}), 400

        try:
            status, response_body = smia_client.post(f"/{kind}", json=body)
        except smia_client.SmiaUnavailableError as exc:
            return jsonify({"error": f"smia unavailable: {exc}"}), 502
        return jsonify(response_body), status

    @app.route("/api/enrich/tts/use", methods=["POST"])
    def post_enrich_tts_use():
        """The one enrichment route that does more than pass through: a
        chosen /tts candidate's audio has to land in stabbur's own canonical
        blob store (D45), never stay a reference into smia's private,
        non-canonical cache. The candidate's own `sha256` (from a prior
        POST /api/enrich/tts response) is smia's audio-content hash, which
        smia's GET /tts/{sha256} serves as raw bytes directly — no need to
        re-run the provider lookup."""
        body = request.get_json(silent=True) or {}
        candidate_sha256 = body.get("sha256")
        if not candidate_sha256:
            return jsonify({"error": "sha256 is required"}), 400

        try:
            status, data, _content_type = smia_client.get_bytes(f"/tts/{candidate_sha256}")
        except smia_client.SmiaUnavailableError as exc:
            return jsonify({"error": f"smia unavailable: {exc}"}), 502
        if status != 200:
            return jsonify({"error": "smia could not serve that candidate's audio"}), 502

        stored_sha256 = blob_storage.store(data)
        return jsonify({"sha256": stored_sha256}), 200

    @app.route("/api/enrich/tts/preview/<sha256>", methods=["GET"])
    def get_enrich_tts_preview(sha256):
        """Lets the operator listen to a /tts candidate before deciding to
        "Use" it — streams smia's cached bytes straight through, unlike
        tts/use, which commits them to stabbur's own blob store. No auth
        header: an <audio src=...> element can't send one (same reasoning
        as /blob/<sha256>'s exemption in auth.py), and the sha256 itself is
        the only thing identifying the content, same as that route."""
        try:
            status, data, content_type = smia_client.get_bytes(f"/tts/{sha256}")
        except smia_client.SmiaUnavailableError as exc:
            return jsonify({"error": f"smia unavailable: {exc}"}), 502
        if status != 200:
            return jsonify({"error": "smia could not serve that candidate's audio"}), 502
        return Response(data, mimetype=content_type)

    @app.route("/api/enrich/stt", methods=["POST"])
    def post_enrich_stt():
        """Unlike every other kind, /stt's input is audio bytes, not an
        operator-typed field — so this reads the audio from stabbur's own
        blob storage (by sha256, same reference already stored as a note's
        audio_blob) rather than forwarding a JSON body as-is (design.md D1)."""
        body = request.get_json(silent=True) or {}
        provider = body.get("provider")
        audio_blob = body.get("audio_blob")
        if not provider:
            return jsonify({"error": "provider is required"}), 400
        if not audio_blob:
            return jsonify({"error": "audio_blob is required"}), 400
        if not blob_storage.exists(audio_blob):
            return jsonify({"error": "no stored audio for that audio_blob"}), 400

        audio_bytes = blob_storage.read(audio_blob)
        form_data = {"provider": provider}
        if body.get("lang"):
            form_data["lang"] = body["lang"]

        try:
            status, response_body = smia_client.post_multipart(
                "/stt", files={"audio": (f"{audio_blob}.mp3", audio_bytes, "audio/mpeg")}, data=form_data
            )
        except smia_client.SmiaUnavailableError as exc:
            return jsonify({"error": f"smia unavailable: {exc}"}), 502
        return jsonify(response_body), status

    @app.route("/api/enrich/manual-link/forvo", methods=["POST"])
    def post_enrich_manual_link_forvo():
        """forvo has no API (smia's `manual_link` adapter just hands back a
        link to forvo.com) — this is the other half: the operator pastes
        back a direct audio URL they found on that page, and stabbur fetches
        it server-side so it can become a real, stabbur-owned blob
        (manual-link-audio-capture design.md D2)."""
        body = request.get_json(silent=True) or {}
        url = body.get("url")
        if not url:
            return jsonify({"error": "url is required"}), 400
        try:
            _validate_fetch_url(url)
        except UnsafeUrlError as exc:
            return jsonify({"error": str(exc)}), 400

        try:
            resp = requests.get(url, timeout=30.0, headers=_DIRECT_AUDIO_FETCH_HEADERS)
        except requests.RequestException as exc:
            return jsonify({"error": f"could not fetch that url: {exc}"}), 502
        if resp.status_code != 200:
            return jsonify({"error": f"fetch failed with HTTP {resp.status_code}"}), 502

        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("audio/") and "octet-stream" not in content_type:
            return jsonify({"error": f"that URL did not return audio (Content-Type: {content_type or 'unknown'})"}), 400

        sha256 = blob_storage.store(resp.content)
        return jsonify({"sha256": sha256}), 200

    @app.route("/api/enrich/manual-link/filmot", methods=["POST"])
    def post_enrich_manual_link_filmot():
        """filmot has no API either — the operator pastes back a YouTube URL
        with a timecode they found via filmot's search, and stabbur downloads
        only a ~4-second audio window around it (not the full video) via
        yt-dlp, per design.md D3."""
        body = request.get_json(silent=True) or {}
        url = body.get("url")
        if not url:
            return jsonify({"error": "url is required"}), 400
        try:
            _validate_fetch_url(url)
        except UnsafeUrlError as exc:
            return jsonify({"error": str(exc)}), 400

        timecode = _parse_youtube_timecode(url)
        if timecode is None:
            return jsonify({"error": "could not find a timecode (?t=) in that URL"}), 400

        start = max(0, timecode - 2)
        end = timecode + 2
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_template = os.path.join(tmp_dir, "clip.%(ext)s")
            cmd = [
                "yt-dlp",
                "--no-playlist",
                # Audio-only, not yt-dlp's default video+audio selection —
                # we only ever want the sound, so this skips ever needing a
                # video format at all (discovered live: the default
                # selection's merge requirement failed with "Requested
                # format is not available" in a case where an audio-only
                # stream was actually fine on its own).
                "-f", "bestaudio/best",
                # Pin extraction to player clients whose signed URLs
                # actually work via ffmpeg's own plain HTTP GET (what
                # --download-sections hands the URL to) — discovered live
                # that yt-dlp's unrestricted client rotation can surface a
                # format from a client (e.g. "visionos") whose URL 403s under
                # ffmpeg even though yt-dlp itself resolved it successfully.
                # android/web_embedded were the two that worked reliably
                # across repeated tests; this is the kind of pin that can
                # need revisiting as YouTube's own client support shifts
                # (same already-accepted maintenance risk as the yt-dlp
                # version itself, design.md).
                "--extractor-args", "youtube:player_client=android,web_embedded",
                "--download-sections", f"*{start}-{end}",
                # Cut on exact section boundaries rather than the nearest
                # keyframe — yt-dlp's own recommendation for
                # --download-sections, otherwise a short window can silently
                # grab the wrong (much larger) span.
                "--force-keyframes-at-cuts",
                "-x", "--audio-format", "mp3",
                "-o", out_template,
            ]
            # A server-side IP calling YouTube directly (no logged-in
            # browser session) is routinely flagged with "Sign in to confirm
            # you're not a bot" regardless of JS-runtime support — yt-dlp's
            # own documented fix is a cookies file exported from an
            # authenticated browser session. Optional: most captures won't
            # need it until/unless YouTube starts flagging this deployment's
            # IP, at which point setting this env var (no code change) is
            # the fix, not touching this route again.
            cookies_file = os.environ.get("YTDLP_COOKIES_FILE")
            if cookies_file and os.path.exists(cookies_file):
                # yt-dlp doesn't just read this file, it writes updated
                # cookies back to it after the session — discovered live as
                # a crash (`OSError: Read-only file system`) against a
                # read-only-mounted cookies file. Working off a per-request
                # copy means --cookies always points at something writable
                # regardless of how the configured file is mounted, and a
                # given request can never corrupt the operator's original
                # exported cookies file.
                cookies_copy = os.path.join(tmp_dir, "cookies.txt")
                shutil.copyfile(cookies_file, cookies_copy)
                cmd += ["--cookies", cookies_copy]
            cmd.append(url)
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except subprocess.CalledProcessError as exc:
                # The bare exit status alone ("returned non-zero exit status
                # 1") is useless for diagnosing a live failure (expired
                # signature, YouTube bot-check, a genuinely bad URL, ...) —
                # surface yt-dlp's own stderr, which names the real cause.
                detail = (exc.stderr or exc.stdout or "").strip()
                return jsonify({"error": f"yt-dlp failed: {detail[-1500:] or exc}"}), 502
            except subprocess.TimeoutExpired as exc:
                return jsonify({"error": f"yt-dlp timed out: {exc}"}), 502

            clip_path = os.path.join(tmp_dir, "clip.mp3")
            if not os.path.exists(clip_path):
                return jsonify({"error": "yt-dlp did not produce an audio clip"}), 502
            with open(clip_path, "rb") as f:
                clip_bytes = f.read()

        sha256 = blob_storage.store(clip_bytes)
        return jsonify({"sha256": sha256}), 200
