## 1. Backend plumbing

- [ ] 1.1 `blob_storage.py`: add `read(sha256) -> bytes`.
- [ ] 1.2 `smia_client.py`: add `post_multipart(path, files, data, timeout) -> (status, body)`.
- [ ] 1.3 `routes/enrich.py`: add `POST /api/enrich/stt` — reads `{provider, audio_blob}` from the JSON body, loads bytes via `blob_storage.read`, forwards via `smia_client.post_multipart` to smia's `/stt` with `provider` and `lang` (mapped via the same `source_lang` convention the other routes use), returns the response unchanged. 400 if `audio_blob` doesn't exist locally or `provider` is missing.

## 2. UI

- [ ] 2.1 `ui/index.html`: add a "Propose from audio" button + suggest panel (`e_stt_suggest`) near the audio section of the existing-note editor, hidden by default.
- [ ] 2.2 `ui/ui.js`: show/hide `e_stt_suggest`'s toggle based on `currentNote.audio_blob` (alongside the existing `updateNoAudioWarning`/`renderAudioSection` logic).
- [ ] 2.3 `ui/ui.js`: add `renderSttResult(prefix)` — renders a provider's `{provider, text}` response as a single block with one "Use" button (not a `candidates` array).
- [ ] 2.4 `ui/ui.js`: `openSuggestPanel`'s `kind === 'stt'` branch — one row per provider from the catalog's `stt` list, each firing `POST /api/enrich/stt` with `{provider, audio_blob: currentNote.audio_blob}` on open (manual-trigger-on-open, consistent with every other kind).
- [ ] 2.5 `ui/ui.js`: "Use" handler confirms via `confirm()` before overwriting a non-empty `e_text`; writes directly when empty.

## 3. Tests

- [ ] 3.1 Backend test for `POST /api/enrich/stt`: happy path (forwards correctly, returns `{provider, text}`), missing provider (400, no smia call made), unknown/missing blob (400, no smia call made).

## 4. Verification

- [ ] 4.1 Manually verify: a note with audio shows "Propose from audio"; a note without audio does not.
- [ ] 4.2 Manually verify: using a transcription on an empty `text` field writes immediately; on a non-empty field, prompts first.
