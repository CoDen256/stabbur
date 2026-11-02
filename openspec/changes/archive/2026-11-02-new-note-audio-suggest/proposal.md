## Why

The `smia-enrichment-panel` change wired per-field "Suggest" accordions
(transcription, translations, inflections, audio) into the existing-note
editor (`#/notes/:id`), but the new-note form (`#/new-note`) only ever got
the transcription/translations/inflections panels — audio was left as a
plain file-upload dropzone with no provider suggestions at all. An operator
authoring a brand-new note has to save a draft first, reopen it, and only
then can they ask smia for a TTS candidate. That extra round trip is exactly
the friction the enrichment panel was built to remove for every other field.

## What Changes

- Add a `c_tts_suggest` accordion to the new-note form, identical in behavior
  to the existing-note editor's `e_tts_suggest` (same provider rows, same
  "Use" button per candidate).
- Clicking "Use" on a new-note TTS candidate fetches/stores the audio via the
  existing `POST /api/enrich/tts/use` route (unchanged — it only needs smia's
  candidate `sha256`, never a note id) and holds the resulting stabbur
  `sha256` in the new-note form's client-side state.
- `POST /api/notes` (note creation) already accepts `audio_blob` directly in
  its body (`routes/notes.py`'s `create_note`) — the new-note submit handler
  includes that stashed `sha256` as `audio_blob` in the create payload, so
  the note is created with its audio already attached in one save action.
  No separate attach step, no PATCH-after-create for this path (the existing
  file-upload dropzone keeps its current PATCH-after-create flow, since it
  genuinely needs the created note's id to call the multipart `/blobs`
  upload; the TTS path doesn't have that constraint since smia-fetched bytes
  are already content-addressed and stored before the note exists).
- If the operator both picks a TTS "Use" candidate and separately chooses a
  file in the dropzone, the later of the two actions wins (last-write, same
  as any other form field being edited twice) — no new validation needed.

## Capabilities

### Modified Capabilities
- `note-editor`: the "Transcription, translations, and audio fields offer
  provider-sourced suggestions" requirement currently only describes the
  audio panel in general terms; this change makes explicit that it applies
  identically on the new-note form, including the create-time attach
  behavior.

## Impact

- `stabbur` UI (`ui/index.html`): add the `c_tts_suggest` panel markup next
  to the new-note form's audio dropzone, mirroring `e_tts_suggest`'s markup.
- `stabbur` UI (`ui/ui.js`): `openSuggestPanel`'s `tts` branch already works
  for any `prefix`; the only prefix-specific code to change is
  `renderTtsCandidate`'s "Use" handler, which currently assumes
  `currentNote` exists (PATCHes `/api/notes/${currentNote.id}`) — it needs a
  `prefix === 'c'` path that stashes the `sha256` instead of PATCHing, and
  `submitNewNote` needs to read that stashed value into the create payload.
- No backend route changes — `POST /api/enrich/tts/use` and
  `POST /api/notes` already support everything this needs.
- No schema changes.
