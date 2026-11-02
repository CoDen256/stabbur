## 1. Dependencies

- [x] 1.1 Add `yt-dlp` to `requirements.txt`.
- [x] 1.2 Add `ffmpeg` to `Dockerfile`'s `apt-get install` list.
- [x] 1.3 Confirm `yt-dlp`/`ffmpeg` are available in local dev (`shell.nix`) for anyone running stabbur outside the container.

## 2. URL safety helper

- [x] 2.1 Add a shared `_validate_fetch_url(url)` check (scheme is `http`/`https`; resolved address is not private/loopback/link-local) used by both new routes, per design D5.

## 3. Forvo capture route

- [x] 3.1 `routes/enrich.py`: `POST /api/enrich/manual-link/forvo` — validate URL (task 2.1), `GET` it server-side, sanity-check content-type/size looks like audio, store via `blob_storage.store`, return `{sha256}`.
- [x] 3.2 Backend test: happy path, non-audio response rejected, unsafe URL rejected.

## 4. filmot/YouTube capture route

- [x] 4.1 `routes/enrich.py`: `POST /api/enrich/manual-link/filmot` — validate URL (task 2.1), parse the timecode (`?t=` / `?start=`, yt-dlp/YouTube's own convention), reject if no timecode found.
- [x] 4.2 Invoke `yt-dlp` with `--download-sections "*<t-2>-<t+2>"` and audio extraction to a temp file; read bytes, store via `blob_storage.store`, clean up the temp file, return `{sha256}`.
- [x] 4.3 Backend test: happy path (mock/stub `yt-dlp` invocation), missing timecode rejected, unsafe URL rejected.

## 5. UI

- [x] 5.1 `ui/ui.js`: `buildEnrichProviderRow`'s `fire()` — branch on `candidates.length === 0 && body.url` to render the "Open ↗" link + paste-back input instead of the generic "No entry found" message, per design D1.
- [x] 5.2 `ui/ui.js`/`ui/index.html`: paste-back input + submit action for the `forvo` row, calling the new forvo capture route, then attaching via the existing `audio_blob` + `audio_sel_ms: null` PATCH flow (same as `renderTtsCandidate`'s existing attach code) and triggering `renderAudioSection`.
- [x] 5.3 Same for the `filmot` row against the filmot capture route.
- [x] 5.4 Reuse this attach pattern identically on both the new-note and existing-note forms (consistent with every other suggest-panel capability). **Implemented via a shared `attachAudioToNote(prefix, ...)` helper, factored out of `renderTtsCandidate`'s existing e/c branching and reused by the manual-link paste-back flow — no duplicated attach logic.**

## 6. Verification

- [x] 6.1 Manually verify: a `forvo` row shows the "Open forvo.com ↗" link instead of "No entry found." **Confirmed by the operator in the real UI (reported the next two bugs from this exact screen).**
- [x] 6.2 Manually verify: pasting a real Forvo audio link attaches audio and the trim UI appears. **Operator first hit a 403 (fixed in round 1 of section 7), then confirmed "forvo working properly" after the fix.**
- [ ] 6.3 Manually verify: pasting a real filmot-found YouTube URL+timecode downloads a short clip, attaches it, and the trim UI appears. **Three rounds of real failures fixed so far (stale pin/flags → bot-check/JS-runtime → read-only cookies file/format selection), each independently reproduced and confirmed resolved directly against `yt-dlp` outside the route. Still not confirmed working end-to-end through the actual browser → route → attach → trim path on the operator's deployment.**
- [x] 6.4 Manually verify: pasting a non-audio link, a URL with no timecode, and an unsafe (private-address) URL each fail with a clear message and no blob is created. **Verified via the full automated test suite (67/67) run against a real throwaway Postgres container, plus `_validate_fetch_url`/`_parse_youtube_timecode` exercised standalone.**

## 7. Fixes from live operator testing

### Round 1
- [x] 7.1 `ui.css`: "Fetch & attach" didn't fit next to the paste-back input in the (narrow) audio panel sidebar — `.manual-link-paste` now stacks the input and button vertically instead of a side-by-side flex row.
- [x] 7.2 `routes/enrich.py`: filmot capture failed with a bare "non-zero exit status 1" — added `--force-keyframes-at-cuts` (yt-dlp's own recommendation for `--download-sections`) and switched the yt-dlp pin from `==` to `>=` (YouTube's extractor compatibility breaks on old pins often enough that this is the realistic fix for this failure mode, not a code change — see design.md's already-called-out risk). Re-ran the operator's exact failing URL/timecode directly against `yt-dlp` post-fix and it succeeded. Also now surfaces yt-dlp's actual stderr in the error response instead of just the exit code, so the next failure (whatever it turns out to be) is diagnosable without re-deriving this from scratch.
- [x] 7.3 `routes/enrich.py`: forvo capture failed with HTTP 403 — Forvo's audio CDN rejects requests with no (or an obviously scripted) User-Agent; added a real-browser User-Agent and a `Referer: https://forvo.com/` header to the forvo fetch. **Operator confirmed forvo now works.**

### Round 2 (operator's filmot retry hit a second, different failure)
- [x] 7.4 `Dockerfile`/`shell.nix`: yt-dlp warned "No supported JavaScript runtime could be found" — added `deno` (yt-dlp's default-supported runtime) to both the Docker image (via its own install script, no apt package) and local dev.
- [x] 7.5 `routes/enrich.py`: the operator's deployment then hit YouTube's "Sign in to confirm you're not a bot" — independent of the JS-runtime fix, this is IP-reputation-based, not something a code change alone can bypass. Added an optional `YTDLP_COOKIES_FILE` env var: when set and the file exists, passed as `--cookies <path>` to yt-dlp (yt-dlp's own documented workaround — a cookies.txt exported from an authenticated browser session). Backend-tested (present-and-set, present-but-missing-file, and unset cases); not verified end-to-end against the operator's real deployment since that requires them to actually export and configure a cookies file.
- [x] 7.6 `compose.yaml`: operator asked where the cookies file actually goes under Docker — there was no mount point for it at all. Set `YTDLP_COOKIES_FILE: /app/cookies.txt` on the `backend` service (harmless while absent) and added a commented-out `./cookies.txt:/app/cookies.txt:ro` bind mount to uncomment once a real cookies file exists; `.gitignore` now excludes `/cookies.txt`.

### Round 3 (operator mounted the cookies file `:ro`, per 7.6's own suggestion — two more real failures surfaced)
- [x] 7.7 `routes/enrich.py`: yt-dlp doesn't just *read* `--cookies`, it writes updated cookies back to that same file after the session — crashed with `OSError: Read-only file system` against the `:ro` mount 7.6 itself suggested. Rather than asking the operator to mount it read-write (which would let yt-dlp silently rewrite their exported session file), the route now copies the configured cookies file into its own per-request temp directory and points `--cookies` at that copy — always writable, never touches the operator's original file, and the `:ro` mount from 7.6 is correct as-is and doesn't need to change. Reproduced the exact `PermissionError`/`OSError` against a real read-only file locally, confirmed the per-request-copy fix resolves it.
- [x] 7.8 `routes/enrich.py`: the same failure also surfaced "Requested format is not available" — yt-dlp's default video+audio format selection can fail to find a mergeable pair even when a perfectly good audio-only stream exists, which is all an audio extraction ever needed in the first place. Added `-f bestaudio/best` so the command never considers video formats at all. Verified against the operator's exact URL/timecode (both with and without a cookies file) — succeeds in both cases now.

(The paradigm-grid "chaotic" layout bug and the inflection row-grouping revision the operator also reported in this session are tracked and fixed under `inflection-rows-and-fill`'s own tasks.md, section 4 — a different change's UI, not this one.)
