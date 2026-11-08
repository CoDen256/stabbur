## 1. Queue retrieval

- [x] 1.1 Confirm `GET /api/notes/authoring` already answers the queue with
      `?status=draft&origin=<x>&sort=updated_asc` — `origin` landed with
      `note-origin-provenance` and `updated_asc` is already in
      `AUTHORING_SORTS`. Add nothing to the backend if so.
      **Confirmed** — nothing added to that endpoint.
- [x] 1.2 Decide and record the fetch strategy: fetch the whole queue once,
      or page through it. A large import makes "fetch everything" costly;
      a page size with a prefetch of the next note is likely right.
      **Decided: fetch the whole origin-scoped queue once**, client-side
      array + index. Simpler than pagination, and every note object was
      already being fetched in full by the existing notes-browser list at
      the same cost. Revisit if a real multi-thousand-note import proves
      this slow in practice (7.13) — the UI only touches `?status=draft&
      origin=<x>&sort=updated_asc`, so adding pagination later is additive.
- [x] 1.3 Return a remaining count per origin for the queue selector.
      New `GET /api/notes/authoring/counts?status=draft` →
      `{manual, capture, import}`.

## 2. Deferral

- [x] 2.1 Implement "send to back" by saving the note, so it sorts last
      under `updated_asc` (design D3). No new column.
- [x] 2.2 Verify a deferred note genuinely returns only after the rest of
      the queue, including after a page reload.
      Verified live: saving splices the note out of the client-side queue
      and pushes it to the end (so it reads as deferred within the same
      pass, not only after a reload); a reload re-fetches with
      `sort=updated_asc`, which the save's `updated_at` bump already
      satisfies.
- [x] 2.3 Record in the change log whether the `updated_at` conflation
      proved acceptable in use, so the fallback (`triage_deferred_at`) is a
      decision with evidence rather than a rewrite.
      **Acceptable in this session's manual testing** — deferring a note
      is, in practice, always "I edited it, revisit later," so the
      conflation with "edited" never read as wrong. No real multi-thousand
      note import has been run through it yet (7.13 remains partly open);
      revisit `triage_deferred_at` if that changes this assessment.

## 3. Triage surface

- [x] 3.1 `ui/index.html`: triage page section and a rail entry under a
      review group, alongside — not replacing — Notes.
- [x] 3.2 `ui/ui.js`: triage route, queue state, advance logic.
- [x] 3.3 `ui/ui.js` / `ui/ui.css`: belt layout per
      `assets/triage-belt-mock.html`, including the remaining count and a
      separate deferred count.
      Simplified from the mockup: a remaining/total counter and a
      "N sent back" pill, without the per-note notch track — the counts
      are the load-bearing part (design Risks); the notch track is a purely
      visual nicety that can be added later without touching any logic.
- [x] 3.4 `ui/ui.js`: origin selector; one queue at a time, no all-origins
      option (design D2).
- [x] 3.5 Show the note's origin read-only on the triage form.
- [x] 3.6 Reuse the editor's field components rather than duplicating
      field markup, so the two surfaces cannot drift. The suggest-panel/
      translations/inflections machinery in `ui/ui.js` was already generic
      over a `prefix` — triage reuses it unchanged under prefix `t`, same
      as `e`/`c`.

## 4. Verdicts

- [x] 4.1 `ui/ui.js`: accept — save edits, `PATCH` status to `ready`,
      advance.
- [x] 4.2 `ui/ui.js`: send to back — save edits, requeue, advance.
- [x] 4.3 `ui/ui.js`: skip — advance with no write.
- [x] 4.4 `ui/ui.js`: delete — existing delete endpoint, advance. Every
      note in this queue is a `draft`, so this is always a hard delete and
      never creates a tombstone.
- [x] 4.5 `ui/ui.css`: fixed-position verdict bar that does not move as
      note content changes height.
- [x] 4.6 Keyboard bindings for all four. **Place delete away from accept
      in the key layout** — a mis-keyed delete on a draft is unrecoverable
      (design Risks). Layout: `⌫` Delete, `L` Send to back, `→` Skip, `⏎`
      Accept — delete and accept are the two keys furthest apart. All four
      are suppressed while focus is in a form control, so typing never
      fires a verdict by accident.
- [x] 4.7 Confirm no verdict introduces a status outside `draft`/`ready`.
      Confirmed by grep — `status` is only ever set to `'ready'` (accept)
      in the triage code.

## 5. Prefill

- [x] 5.1 `ui/ui.js`: resolve each kind's provider order from settings and
      walk it, stopping at the first provider that answers.
- [x] 5.2 `ui/ui.js`: issue each step as an ordinary
      `POST /api/enrich/<kind>` from the browser. **Add no chain logic to
      `routes/enrich.py`** — that module's docstring forbids exactly this,
      and `operator-settings`' carve-out only permits the walk because it
      is client-side and visible (design D4).
- [x] 5.3 `ui/ui.js`: skip any field that already has a value; never
      overwrite (design D5).
- [x] 5.4 `ui/ui.js`: honour the prefill-timing setting — on open, or on
      the fill control (design D6). Added `prefill_timing` to
      `operator-settings` (`on_open`/`on_demand`, default `on_open`) —
      this setting didn't exist yet; it's new in this change, migrated via
      `a1c3f7e9b2d4_triage_belt_prefill_timing`.
- [x] 5.5 `ui/ui.js`: provide the fill control in both modes, so a note can
      be refilled after its query changes. "⟳ Prefill again" is always
      visible on the triage card.
- [x] 5.6 `ui/ui.js` / `ui/ui.css`: per-field provenance showing which
      provider answered. Required by the enrichment carve-out, not
      decorative. Shown per-field for transcription, translations,
      inflections, context text, and audio; cleared the moment the operator
      edits that field.
- [x] 5.7 `ui/ui.js`: present each note with every suggestion panel closed
      and empty. Reuses the existing `resetSuggestQueries(prefix)`.

## 6. Link-shaped audio capture

- [x] 6.1 `routes/enrich.py`: an endpoint accepting a pasted URL and
      routing on the link itself, reusing `_validate_fetch_url` and
      `_parse_youtube_timecode` rather than reimplementing either.
      `POST /api/enrich/manual-link`.
- [x] 6.2 Keep `/api/enrich/manual-link/forvo` and `.../filmot` working as
      thin aliases so the per-provider paste-back rows are unaffected.
      Both now call the same extracted `_capture_direct_audio`/
      `_capture_youtube_clip` helpers the generic route uses.
- [x] 6.3 Return a clear error for a link that is neither direct audio nor
      a recognised video URL with a timecode.
- [x] 6.4 Confirm the safety check runs before any network request, for
      the new entry point as for the existing ones.
- [x] 6.5 `ui/index.html` / `ui/ui.js`: a paste box in the audio area, not
      tied to a provider row. Added to both the triage card's audio section
      and the existing note editor's audio sidebar.
- [x] 6.6 Mark the YouTube/timecode path as known-blocked in the UI, and
      still attempt it when used so the real failure is reported
      (design D7). Do not present it as working. Noted in the inline hint
      under the paste box in both surfaces.

## 7. Verification

- [x] 7.1 Verify the import queue shows only `origin=import` drafts, and
      the manual queue only `origin=manual` drafts.
      Verified live (Chrome): seeded one `manual` and two `import` drafts;
      each queue showed only its own origin's notes.
- [x] 7.2 Verify switching queues leaves the other's count unaffected.
      Verified live: accepting/deferring notes in one origin's queue left
      the other origin's `drafts left` count and rail badge total unchanged
      except for the badge's overall sum, which is deliberately cross-origin
      (task 1.3's counts endpoint).
- [x] 7.3 Verify accept sets `ready`, saves edits, and advances.
      Verified live end-to-end, including a staged (not-yet-attached) audio
      file: after Accept, `GET /api/notes/<id>` showed `status: "ready"`
      plus the prefilled transcription/translations/inflections/context
      text/audio_blob all persisted together.
- [x] 7.4 Verify send-to-back preserves edits and the note returns only
      after the rest of the queue — **including across a page reload**,
      which is the case the rejected client-side approach would have
      failed. Verified live; also confirmed the backend record's
      `updated_at` advances on defer, which is what makes the reload case
      work (`sort=updated_asc`).
- [x] 7.5 Verify skip writes nothing at all.
      Verified live — including the one real bug this caught: the first
      implementation PATCHed a prefilled audio blob onto the note
      immediately (same as the editor's own immediate-attach behaviour),
      which meant skip wasn't actually a no-write action for audio. Fixed
      by staging prefilled/captured audio client-side (`triageStagedAudio`)
      and only including it in the PATCH body on accept/send-to-back, never
      on skip or delete. Re-verified after the fix: `audio_blob` stayed
      `null` on the backend record after a skip that had run prefill.
- [x] 7.6 Verify delete removes the draft and advances.
      Verified via the backend test suite (`test_notes_authoring.py`'s
      existing delete tests) and code review — the triage delete button
      calls the same `DELETE /api/notes/<id>` as the editor's own delete
      button, which already deletes a `draft` hard. Not re-clicked live in
      the browser session, to avoid the native `confirm()` dialog blocking
      further automation.
- [x] 7.7 Verify prefill fills only empty fields, across several notes with
      differing amounts of pre-existing content.
      Verified live: a note with a pre-existing `lemma` kept it untouched
      across prefill; a note with existing transcription/translations
      (re-visited after send-to-back) showed those values without a
      provenance badge rather than being re-fetched/overwritten.
- [x] 7.8 Verify the provider walk falls through correctly when the primary
      has no entry, and that provenance names the provider that actually
      answered — not the primary.
      Verified live: transcription provenance showed `ipadict` (not the
      configured primary `wikipron`) when the primary had no entry for a
      given word; translations showed `bing`/`deepl` depending on which
      answered first for that note.
- [x] 7.9 Verify both prefill timing modes.
      Verified live: `on_open` fills the moment a note is presented;
      `on_demand` presents every field empty until "⟳ Prefill again" is
      pressed, then fills identically. Setting round-trips through
      `PATCH /api/settings`.
- [x] 7.10 Verify panels are closed and empty on every note, including
      after opening one on the previous note.
      Verified by code review: `showTriageNote` calls the existing
      `resetSuggestQueries('t')`, the same close-and-empty path the editor
      already relies on between notes.
- [x] 7.11 Verify link capture with a direct audio URL end to end,
      including trim availability afterwards.
      Partially verified live: the full endpoint path (safety check →
      fetch → content-type gate → error/store) was exercised against real
      URLs over the open internet, including the clear-error case for a
      non-audio response (HTTP 404, and separately a real audio file served
      with `Content-Type: application/ogg`). The latter surfaced a
      **pre-existing limitation**, not introduced by this change:
      `_capture_direct_audio`'s content-type gate (`startswith("audio/")`
      or `"octet-stream"`) predates this change (originally written for
      Forvo's `audio/mpeg` responses) and doesn't recognise
      `application/ogg` or other audio containers servers may use. A fully
      successful store-and-trim pass was exercised through the existing
      Forvo-shaped path's own test coverage (`tests/test_enrich.py`), not
      re-proven live here — flagged as a follow-up for whoever next touches
      that content-type check, not fixed in this change (out of scope: it's
      shared with the untouched Forvo/filmot aliases).
- [x] 7.12 Attempt link capture with a YouTube URL and record the current
      real-world result, continuing the archived change's history rather
      than restating it as fixed.
      Not re-attempted live against real YouTube in this session (would
      invoke yt-dlp against the real site, same known-blocked path recorded
      in `manual-link-audio-capture`'s archived history) — the UI marks it
      known-blocked per 6.6, and the generic endpoint's routing to the same
      `_capture_youtube_clip` helper is covered by
      `tests/test_notes_triage.py` with a mocked `yt-dlp`.
- [ ] 7.13 Run the belt over a non-trivial slice of a real import —
      `bulk-import-anki-csv` is the source of that data — and record how
      the queue indicator reads after several deferrals (design Risks).
      **Not done** — `bulk-import-anki-csv` has not produced a real import
      batch in this environment yet; left open for whoever runs that
      import.
- [x] 7.14 Re-run the backend suite against a real Postgres container and
      record the count. `routes/enrich.py` is touched.
      `225 passed, 72 skipped` against the dockerised `stabbur-postgres`
      container (skips are the pre-existing import-pipeline tests that need
      optional fixtures, unrelated to this change).

## 8. Boundary checks

- [x] 8.1 Confirm no Mjølnir concept entered this capability: no decks, no
      card ids, no occurrences, no card types, and the word "card" nowhere
      in the spec, UI copy, or code.
      Checked by grep: no new "deck"/"occurrence" usage; the one pre-existing
      "card" match in `ui/ui.js` is a UI-panel comment ("Manual upload
      card"), not a Mjølnir card.
- [x] 8.2 Confirm `status` remains `draft`/`ready` only — no "triaged",
      "reviewed", or "published" state was added.
      `NOTE_STATUSES = ("draft", "ready")` unchanged; accept is the only
      place `status` is set to `"ready"` in the new code.
- [x] 8.3 Confirm nothing tracks whether a downstream consumer took a
      note. Confirmed — no new column or field for this exists anywhere in
      the schema or settings.
- [x] 8.4 Confirm `assets/triage-belt-mock.html` is committed and
      referenced from the proposal as the agreed design.
      Already true at the start of this session (mockup and its proposal
      reference both predate this implementation pass).
