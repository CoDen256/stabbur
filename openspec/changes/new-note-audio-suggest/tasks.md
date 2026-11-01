## 1. UI markup

- [ ] 1.1 `ui/index.html`: add a `c_tts_suggest` suggest-panel + toggle button next to the new-note form's audio dropzone, mirroring `e_tts_suggest`'s markup and placement.

## 2. Suggest/use wiring

- [ ] 2.1 `ui/ui.js`: give `renderTtsCandidate(prefix)`'s "Use" handler a `prefix === 'c'` branch that calls `POST /api/enrich/tts/use` and stashes the returned `sha256` in new-note form state instead of PATCHing a note.
- [ ] 2.2 Show the chosen candidate's provenance (provider, meta) inline near the dropzone on the new-note form once stashed, so the operator can see what will be attached before saving.
- [ ] 2.3 Wire the dropzone file `change` handler to clear the stash (and vice versa) so whichever happened last wins, per design D2.

## 3. Create payload

- [ ] 3.1 `submitNewNote`: include `audio_blob` (the stashed sha256) directly in the `POST /api/notes` payload when present, skipping the create-then-PATCH flow for this path.
- [ ] 3.2 Confirm the existing dropzone file-upload create-then-PATCH flow is unchanged when no TTS suggestion was used.

## 4. Verification

- [ ] 4.1 Manually verify in a browser: create a new note, use a TTS suggestion, save — the resulting note detail page shows the audio already attached with no extra step.
- [ ] 4.2 Manually verify: pick a dropzone file after using a TTS suggestion (or vice versa) — the later choice is what's attached.
- [ ] 4.3 Confirm existing-note (`e_*`) TTS suggest/use behavior is unaffected.
