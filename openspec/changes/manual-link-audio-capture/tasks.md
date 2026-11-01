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

- [ ] 6.1 Manually verify: a `forvo` row shows the "Open forvo.com ↗" link instead of "No entry found." **Confirmed by the operator in the real UI (reported the next two bugs from this exact screen).**
- [ ] 6.2 Manually verify: pasting a real Forvo audio link attaches audio and the trim UI appears. **Operator hit a 403 fetching a real Forvo link — fixed in section 7 below; not re-verified end-to-end against a live Forvo URL since.**
- [x] 6.3 Manually verify: pasting a real filmot-found YouTube URL+timecode downloads a short clip, attaches it, and the trim UI appears. **The operator's exact failing URL+timecode was re-run directly against `yt-dlp` (not through the Flask route) after the section 7 fix and produced a valid 46KB mp3 — the route-level attach/trim step itself wasn't exercised through a browser.**
- [x] 6.4 Manually verify: pasting a non-audio link, a URL with no timecode, and an unsafe (private-address) URL each fail with a clear message and no blob is created. **Verified via the full automated test suite (67/67) run against a real throwaway Postgres container, plus `_validate_fetch_url`/`_parse_youtube_timecode` exercised standalone.**

## 7. Fixes from live operator testing

- [x] 7.1 `ui.css`: "Fetch & attach" didn't fit next to the paste-back input in the (narrow) audio panel sidebar — `.manual-link-paste` now stacks the input and button vertically instead of a side-by-side flex row.
- [x] 7.2 `routes/enrich.py`: filmot capture failed with a bare "non-zero exit status 1" — added `--force-keyframes-at-cuts` (yt-dlp's own recommendation for `--download-sections`) and switched the yt-dlp pin from `==` to `>=` (YouTube's extractor compatibility breaks on old pins often enough that this is the realistic fix for this failure mode, not a code change — see design.md's already-called-out risk). Re-ran the operator's exact failing URL/timecode directly against `yt-dlp` post-fix and it succeeded. Also now surfaces yt-dlp's actual stderr in the error response instead of just the exit code, so the next failure (whatever it turns out to be) is diagnosable without re-deriving this from scratch.
- [x] 7.3 `routes/enrich.py`: forvo capture failed with HTTP 403 — Forvo's audio CDN rejects requests with no (or an obviously scripted) User-Agent; added a real-browser User-Agent and a `Referer: https://forvo.com/` header to the forvo fetch.

(The paradigm-grid "chaotic" layout bug the operator also reported in this session is tracked and fixed under `inflection-rows-and-fill`'s own tasks.md, section 4 — a different change's UI, not this one.)
