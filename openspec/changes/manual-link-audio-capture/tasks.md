## 1. Dependencies

- [ ] 1.1 Add `yt-dlp` to `requirements.txt`.
- [ ] 1.2 Add `ffmpeg` to `Dockerfile`'s `apt-get install` list.
- [ ] 1.3 Confirm `yt-dlp`/`ffmpeg` are available in local dev (`shell.nix`) for anyone running stabbur outside the container.

## 2. URL safety helper

- [ ] 2.1 Add a shared `_validate_fetch_url(url)` check (scheme is `http`/`https`; resolved address is not private/loopback/link-local) used by both new routes, per design D5.

## 3. Forvo capture route

- [ ] 3.1 `routes/enrich.py`: `POST /api/enrich/manual-link/forvo` — validate URL (task 2.1), `GET` it server-side, sanity-check content-type/size looks like audio, store via `blob_storage.store`, return `{sha256}`.
- [ ] 3.2 Backend test: happy path, non-audio response rejected, unsafe URL rejected.

## 4. filmot/YouTube capture route

- [ ] 4.1 `routes/enrich.py`: `POST /api/enrich/manual-link/filmot` — validate URL (task 2.1), parse the timecode (confirm filmot's actual "open in YouTube" link format during implementation per design's open question), reject if no timecode found.
- [ ] 4.2 Invoke `yt-dlp` with `--download-sections "*<t-2>-<t+2>"` and audio extraction to a temp file; read bytes, store via `blob_storage.store`, clean up the temp file, return `{sha256}`.
- [ ] 4.3 Backend test: happy path (mock/stub `yt-dlp` invocation), missing timecode rejected, unsafe URL rejected.

## 5. UI

- [ ] 5.1 `ui/ui.js`: `buildEnrichProviderRow`'s `fire()` — branch on `candidates.length === 0 && body.url` to render the "Open ↗" link + paste-back input instead of the generic "No entry found" message, per design D1.
- [ ] 5.2 `ui/ui.js`/`ui/index.html`: paste-back input + submit action for the `forvo` row, calling the new forvo capture route, then attaching via the existing `audio_blob` + `audio_sel_ms: null` PATCH flow (same as `renderTtsCandidate`'s existing attach code) and triggering `renderAudioSection`.
- [ ] 5.3 Same for the `filmot` row against the filmot capture route.
- [ ] 5.4 Reuse this attach pattern identically on both the new-note and existing-note forms (consistent with every other suggest-panel capability).

## 6. Verification

- [ ] 6.1 Manually verify: a `forvo` row shows the "Open forvo.com ↗" link instead of "No entry found."
- [ ] 6.2 Manually verify: pasting a real Forvo audio link attaches audio and the trim UI appears.
- [ ] 6.3 Manually verify: pasting a real filmot-found YouTube URL+timecode downloads a short clip, attaches it, and the trim UI appears.
- [ ] 6.4 Manually verify: pasting a non-audio link, a URL with no timecode, and an unsafe (private-address) URL each fail with a clear message and no blob is created.
