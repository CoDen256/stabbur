## Context

`smia/adapters/manual_link.py` registers `forvo` and `filmot` as `tts`
providers that always return `{candidates: [], url}` — a link to that
provider's own site with the word/language pre-filled, never real audio
(confirmed: neither site has a usable free API, and that's permanent, not a
temporary gap). stabbur's `buildEnrichProviderRow` currently can't tell this
apart from a provider that genuinely found nothing — both paths hit
`candidates.length === 0` and render "No entry found for ...".

stabbur already has everything needed downstream of "bytes become a blob":
`blob_storage.store(bytes) -> sha256`, and the note editor's waveform trim UI
(`audio_sel_ms`, `renderAudioSection`, `wireTrimHandle`) already activates on
any note with `audio_blob` set, regardless of how that blob arrived. Neither
of those needs to change — this design is entirely about how bytes get from
"a URL the operator pasted" to "a stored blob."

## Goals / Non-Goals

**Goals:**
- Surface the `url` smia already computes, with zero smia-side changes.
- Forvo: operator pastes a direct audio link → stabbur fetches and stores it
  exactly as given (no transcoding) → existing trim UI takes over.
- filmot: operator pastes a YouTube URL with a timecode → stabbur downloads
  only a ±2s audio window around that timecode (not the full video) →
  existing trim UI takes over for final narrowing.
- Both end at the exact same "attach this blob to the note" step the TTS
  "Use" button and "Replace audio" already use.

**Non-Goals:**
- No video storage or playback — only extracted audio ever reaches
  `blob_storage`.
- No validation that a pasted link actually came from forvo.com/filmot.com/
  youtube.com — arbitrary URLs are accepted (confirmed with operator); this
  is a single-operator internal tool.
- No batch/background processing — both downloads happen synchronously
  within the request that the operator's paste-and-fetch action triggers
  (same spirit as every other enrich call being a direct, waited-on action).
- No change to the trim UI itself — it already works on any `audio_blob`.

## Decisions

### D1 — Suggest-panel rendering: `{candidates: [], url}` is a distinct state, not a failure
`buildEnrichProviderRow`'s `fire()` currently treats
`!candidates.length` uniformly as "no entry found." It needs a third branch:
`candidates.length === 0 && body.url` renders an "Open <provider> ↗" link
(`target="_blank"`) plus a provider-specific paste-back input (and its own
fetch button), instead of the generic error message. A provider that returns
neither candidates nor a `url` (an actual failure) keeps today's "No entry
found" message unchanged.

### D2 — Forvo: a thin "fetch this URL, store the bytes" route
`POST /api/enrich/manual-link/forvo` takes `{url}`, performs a server-side
`GET`, and stores the raw response bytes via `blob_storage.store` — no
transcoding, no validation beyond a basic content-type/size sanity check (so
a pasted HTML page, e.g. the operator accidentally pasting the forvo *word*
page link instead of the *audio file* link, fails fast with a clear error
rather than silently storing an HTML blob). Returns `{sha256}`, matching the
response shape `/api/enrich/tts/use` already returns, so the client-side
"attach + trim" code path is identical regardless of which route produced
the hash.

### D3 — filmot: `yt-dlp --download-sections` for a ±2s window, not a full download
`POST /api/enrich/manual-link/filmot` takes `{url}` where `url` is a YouTube
link carrying a timecode (`t=123` or `t=123s`, yt-dlp/YouTube's own
convention). The route:
1. Parses the timecode from the URL's `t` query parameter (reject if absent
   — the whole point of the filmot flow is a word-level timecode, not a full
   video).
2. Invokes `yt-dlp` with `--download-sections "*<t-2>-<t+2>"` (yt-dlp's
   native partial-download feature — avoids pulling the entire video) and
   `-x --audio-format mp3` (audio-only extraction), writing to a temp file.
3. Reads the resulting file's bytes, stores via `blob_storage.store`,
   deletes the temp file, returns `{sha256}`.
Rejected alternative: download the full video then trim with `ffmpeg`
separately — wastes bandwidth/time for what's often a multi-minute video
when only a 4-second window is needed; `yt-dlp`'s own section-download
feature does the equivalent of a server-side pre-trim in one step.
`ffmpeg` is still a required system dependency either way (`yt-dlp` shells
out to it for extraction/format conversion).

### D4 — No new dependency isolation; `yt-dlp`/`ffmpeg` go straight into the existing image
Rejected alternative: a separate microservice/sidecar for the download step,
to isolate `yt-dlp`'s larger footprint and faster-moving release cadence
from stabbur's otherwise minimal `requirements.txt`. Rejected as
over-engineering for a single-operator internal tool — `pip install yt-dlp`
and `apt-get install ffmpeg` in the existing `Dockerfile` is simpler to
operate, and this isn't a path with uptime/scaling requirements.

### D5 — Minimal SSRF hygiene despite accepting arbitrary URLs
"Arbitrary URLs are fine" (confirmed) means no allowlist restricting *which
domains* can be pasted — it does not mean stabbur's backend should blindly
fetch `http://169.254.169.254/...` or `http://localhost:5432/...` just
because an operator (or a compromised browser tab) pasted it. Both new
routes SHALL reject non-`http(s)` schemes and SHALL reject URLs resolving to
a private/loopback/link-local address, using the same spirit as any
server-side-fetch feature would need regardless of this being an internal
tool — this is a cheap, standard safeguard, not a scope-creeping feature.

## Risks / Trade-offs

- **[Risk]** Downloading YouTube content server-side may conflict with
  YouTube's Terms of Service. → **Accepted** (confirmed with operator): this
  is a private, single-operator tool for personal language-learning capture,
  not a redistribution or public service; the operator has explicitly
  accepted this trade-off.
- **[Risk]** `yt-dlp` requires ongoing maintenance — YouTube changes its
  page/player internals periodically and `yt-dlp` releases frequent fixes;
  an un-updated pin can silently stop working. → **Mitigation**: the
  `requirements.txt` pin is a floor (`>=`), not exact, so re-resolving
  dependencies is the actual fix for most such breaks, not a code change.
  Confirmed live during implementation: an old exact pin genuinely did fail
  this way against a real video.
- **[Risk]** (found live, post-implementation) A server IP calling YouTube
  with no authenticated session is routinely flagged — "Sign in to confirm
  you're not a bot" — independent of yt-dlp's version or JS-runtime support.
  → **Mitigation**: `YTDLP_COOKIES_FILE`, an optional env var pointing at a
  cookies.txt exported from an authenticated browser session (yt-dlp's own
  documented workaround for this exact error); passed as `--cookies` when
  set. Not configured by default — most captures won't need it until/unless
  YouTube starts flagging this deployment's specific IP.
- **[Risk]** (found live, post-implementation) yt-dlp warns "No supported
  JavaScript runtime could be found" without one installed, and recent
  YouTube extraction increasingly depends on solving a JS challenge.
  → **Mitigation**: `deno` (yt-dlp's default-supported runtime) added to the
  Docker image (via its own install script — no apt package) and
  `shell.nix`, so it's present wherever stabbur runs, not just in whichever
  environment happened to have it already.
- **[Risk]** (found live, post-implementation) yt-dlp's `--cookies` writes
  updated cookies back to the given file after the session, not just reads
  it — crashes with `OSError: Read-only file system` against a `:ro`-mounted
  cookies file (the natural way to mount an operator's exported session
  file). → **Mitigation**: the route copies the configured file into its own
  per-request temp directory and points `--cookies` at that copy, so the
  configured file can stay read-only and is never at risk of being mutated
  by yt-dlp.
- **[Risk]** (found live, post-implementation) yt-dlp's unrestricted player-
  client rotation can surface a format whose signed URL only works for
  yt-dlp's own downloader, not for ffmpeg's plain HTTP GET (what
  `--download-sections` hands the URL to) — observed as a 403 from a
  `visionos`-client-sourced URL. → **Mitigation**:
  `--extractor-args "youtube:player_client=android,web_embedded"` restricts
  extraction to two clients confirmed (by repeated live testing) to produce
  ffmpeg-fetchable URLs. Same "needs ongoing maintenance" caveat as the
  version pin above — this is the second time that accepted risk has
  materialized in practice, not a one-off, and this specific client pin may
  itself need revisiting as YouTube's own client support shifts.
- **[Risk]** A pasted Forvo "direct link" that's actually the word page
  (HTML, not audio) would otherwise store garbage. → **Mitigation**: D2's
  content-type/size sanity check surfaces this as a clear error instead of a
  silently broken blob.
- **[Trade-off]** Both routes are synchronous, blocking the request for as
  long as the download takes (a few seconds typically for a ±2s YouTube
  audio clip). Accepted — matches every other enrich action's synchronous,
  waited-on UX; a background job queue would be real complexity for a
  low-frequency operator action.

## Migration Plan

- Additive only: two new routes, new UI states on the TTS panel, new
  dependencies in `requirements.txt`/`Dockerfile`. No existing route, field,
  or UI behavior changes shape.
- `compose.yaml`'s `backend` service sets `YTDLP_COOKIES_FILE: /app/cookies.txt`
  unconditionally (harmless when absent — `routes/enrich.py` checks
  `os.path.exists` before using it) and has a commented-out bind mount
  (`./cookies.txt:/app/cookies.txt:ro`) ready to uncomment once an operator
  actually needs to supply one; `.gitignore` excludes `/cookies.txt` since
  it's live session credentials, not a code asset.
- Rollback: remove the new routes/UI branches and the two new dependencies;
  no persisted state is unique to this feature (it only ever produces
  ordinary content-addressed blobs).

## Open Questions

- Exact accepted YouTube timecode formats to parse from a pasted URL
  (`?t=123`, `?t=123s`, `&start=123`, a `#t=1m2s` fragment) — resolve during
  implementation by checking what filmot's own "open in YouTube" links
  actually produce live, rather than guessing every possible YouTube URL
  shape.
