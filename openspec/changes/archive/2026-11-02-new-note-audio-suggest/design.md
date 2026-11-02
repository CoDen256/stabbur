## Context

The existing-note editor's TTS "Use" handler (`renderTtsCandidate` in
`ui/ui.js`) assumes a saved note: it calls `POST /api/enrich/tts/use` to get
a stabbur `sha256`, then immediately `PATCH /api/notes/${currentNote.id}`
with `audio_blob` set. The new-note form has no note id until
`POST /api/notes` succeeds, so the same handler can't be reused unmodified.

## Goals / Non-Goals

**Goals:**
- One operator action ("Use" on a TTS candidate, then the normal Save) results
  in a created note with `audio_blob` already set — no extra click, no
  reopening the note after save.
- Reuse `buildEnrichProviderRow`/`openSuggestPanel` exactly as they already
  work for `ipa`/`translations` on the new-note form — only the TTS
  candidate's "Use" behavior needs a prefix-aware branch.

**Non-Goals:**
- No change to the existing-note (`e_*`) TTS flow — it keeps PATCHing
  immediately, since that's correct for an already-saved note.
- No change to the dropzone file-upload path's create-then-PATCH flow — it's
  unrelated (needs multipart bytes, which only exist client-side until
  `/blobs` is called) and already works.
- No new validation preventing an operator from picking both a TTS
  suggestion and a dropzone file — last one applied wins, same as any other
  form field.

## Decisions

### D1 — Stash the stabbur `sha256` in form state, include it in the create payload
`renderTtsCandidate(prefix)`'s "Use" handler branches on `prefix`:
- `prefix === 'e'`: unchanged — PATCH the existing note immediately.
- `prefix === 'c'`: call `POST /api/enrich/tts/use` the same way, but instead
  of PATCHing, store the returned `sha256` on a small piece of new-note form
  state (e.g. a hidden input or a module-level variable
  `newNoteAudioFromSuggest`), mark the suggestion "✓ Used" as already done
  for the `e` path, and show the chosen candidate inline near the dropzone
  so the operator can see what will be attached.
- `submitNewNote` reads that stashed value and sets `payload.audio_blob`
  directly in the `POST /api/notes` body (already an accepted field per
  `create_note`) when present — no PATCH call needed for this path at all.

Rejected alternative: keep using create-then-PATCH for the TTS path too
(mirroring the dropzone file-upload code exactly). Rejected because it's pure
unnecessary complexity here — unlike the dropzone, the TTS path already has
the final `sha256` *before* the note exists, so there's no reason to defer
attaching it to a second request.

### D2 — Last-write-wins between TTS "Use" and the dropzone file input
If the operator uses a TTS candidate and then also picks a file (or vice
versa), whichever happened most recently is what gets submitted — the TTS
stash variable is simply overwritten/cleared by picking a file, and the file
input is effectively ignored if a TTS stash is present and no file was
picked afterward. Rejected alternative: disabling one control once the other
is used — unnecessary friction for a reorderable, low-stakes choice (the
operator can always redo the one they want).

## Risks / Trade-offs

- **[Risk]** An operator clicks "Use" on a TTS candidate, then abandons the
  new-note form without saving — the fetched audio bytes are already stored
  in stabbur's content-addressed blob store (`blob/<sha256>`) but never
  referenced by any note. → **Mitigation**: accepted, same as today's
  existing-note flow and the dropzone path already (both can "orphan" a blob
  the same way); content-addressed storage means this merely wastes a little
  disk, never corrupts anything, and stabbur has no GC story for blobs today
  regardless.

## Migration Plan

- Additive UI-only change; no schema, no new routes. Rollback is reverting
  the `ui/index.html`/`ui/ui.js` edits.
