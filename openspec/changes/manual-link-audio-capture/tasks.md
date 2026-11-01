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

- [ ] 6.1 Manually verify: a `forvo` row shows the "Open forvo.com ↗" link instead of "No entry found." **Not verified in this session — no running backend/browser available.**
- [ ] 6.2 Manually verify: pasting a real Forvo audio link attaches audio and the trim UI appears. **Not verified in this session.**
- [ ] 6.3 Manually verify: pasting a real filmot-found YouTube URL+timecode downloads a short clip, attaches it, and the trim UI appears. **Not verified in this session — also depends on `yt-dlp` actually succeeding against live YouTube, which wasn't exercised.**
- [ ] 6.4 Manually verify: pasting a non-audio link, a URL with no timecode, and an unsafe (private-address) URL each fail with a clear message and no blob is created. **The URL-safety and timecode-parsing logic was verified directly (`_validate_fetch_url`/`_parse_youtube_timecode` run standalone, see commit), and the corresponding backend tests were written — full end-to-end browser verification not done.**
