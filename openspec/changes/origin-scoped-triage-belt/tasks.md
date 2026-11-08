## 1. Queue retrieval

- [ ] 1.1 Confirm `GET /api/notes/authoring` already answers the queue with
      `?status=draft&origin=<x>&sort=updated_asc` — `origin` landed with
      `note-origin-provenance` and `updated_asc` is already in
      `AUTHORING_SORTS`. Add nothing to the backend if so.
- [ ] 1.2 Decide and record the fetch strategy: fetch the whole queue once,
      or page through it. A large import makes "fetch everything" costly;
      a page size with a prefetch of the next note is likely right.
- [ ] 1.3 Return a remaining count per origin for the queue selector.

## 2. Deferral

- [ ] 2.1 Implement "send to back" by saving the note, so it sorts last
      under `updated_asc` (design D3). No new column.
- [ ] 2.2 Verify a deferred note genuinely returns only after the rest of
      the queue, including after a page reload.
- [ ] 2.3 Record in the change log whether the `updated_at` conflation
      proved acceptable in use, so the fallback (`triage_deferred_at`) is a
      decision with evidence rather than a rewrite.

## 3. Triage surface

- [ ] 3.1 `ui/index.html`: triage page section and a rail entry under a
      review group, alongside — not replacing — Notes.
- [ ] 3.2 `ui/ui.js`: triage route, queue state, advance logic.
- [ ] 3.3 `ui/ui.js` / `ui/ui.css`: belt layout per
      `assets/triage-belt-mock.html`, including the remaining count and a
      separate deferred count.
- [ ] 3.4 `ui/ui.js`: origin selector; one queue at a time, no all-origins
      option (design D2).
- [ ] 3.5 Show the note's origin read-only on the triage form.
- [ ] 3.6 Reuse the editor's field components rather than duplicating
      field markup, so the two surfaces cannot drift.

## 4. Verdicts

- [ ] 4.1 `ui/ui.js`: accept — save edits, `PATCH` status to `ready`,
      advance.
- [ ] 4.2 `ui/ui.js`: send to back — save edits, requeue, advance.
- [ ] 4.3 `ui/ui.js`: skip — advance with no write.
- [ ] 4.4 `ui/ui.js`: delete — existing delete endpoint, advance. Every
      note in this queue is a `draft`, so this is always a hard delete and
      never creates a tombstone.
- [ ] 4.5 `ui/ui.css`: fixed-position verdict bar that does not move as
      note content changes height.
- [ ] 4.6 Keyboard bindings for all four. **Place delete away from accept
      in the key layout** — a mis-keyed delete on a draft is unrecoverable
      (design Risks).
- [ ] 4.7 Confirm no verdict introduces a status outside `draft`/`ready`.

## 5. Prefill

- [ ] 5.1 `ui/ui.js`: resolve each kind's provider order from settings and
      walk it, stopping at the first provider that answers.
- [ ] 5.2 `ui/ui.js`: issue each step as an ordinary
      `POST /api/enrich/<kind>` from the browser. **Add no chain logic to
      `routes/enrich.py`** — that module's docstring forbids exactly this,
      and `operator-settings`' carve-out only permits the walk because it
      is client-side and visible (design D4).
- [ ] 5.3 `ui/ui.js`: skip any field that already has a value; never
      overwrite (design D5).
- [ ] 5.4 `ui/ui.js`: honour the prefill-timing setting — on open, or on
      the fill control (design D6).
- [ ] 5.5 `ui/ui.js`: provide the fill control in both modes, so a note can
      be refilled after its query changes.
- [ ] 5.6 `ui/ui.js` / `ui/ui.css`: per-field provenance showing which
      provider answered. Required by the enrichment carve-out, not
      decorative.
- [ ] 5.7 `ui/ui.js`: present each note with every suggestion panel closed
      and empty.

## 6. Link-shaped audio capture

- [ ] 6.1 `routes/enrich.py`: an endpoint accepting a pasted URL and
      routing on the link itself, reusing `_validate_fetch_url` and
      `_parse_youtube_timecode` rather than reimplementing either.
- [ ] 6.2 Keep `/api/enrich/manual-link/forvo` and `.../filmot` working as
      thin aliases so the per-provider paste-back rows are unaffected.
- [ ] 6.3 Return a clear error for a link that is neither direct audio nor
      a recognised video URL with a timecode.
- [ ] 6.4 Confirm the safety check runs before any network request, for
      the new entry point as for the existing ones.
- [ ] 6.5 `ui/index.html` / `ui/ui.js`: a paste box in the audio area, not
      tied to a provider row.
- [ ] 6.6 Mark the YouTube/timecode path as known-blocked in the UI, and
      still attempt it when used so the real failure is reported
      (design D7). Do not present it as working.

## 7. Verification

- [ ] 7.1 Verify the import queue shows only `origin=import` drafts, and
      the manual queue only `origin=manual` drafts.
- [ ] 7.2 Verify switching queues leaves the other's count unaffected.
- [ ] 7.3 Verify accept sets `ready`, saves edits, and advances.
- [ ] 7.4 Verify send-to-back preserves edits and the note returns only
      after the rest of the queue — **including across a page reload**,
      which is the case the rejected client-side approach would have
      failed.
- [ ] 7.5 Verify skip writes nothing at all.
- [ ] 7.6 Verify delete removes the draft and advances.
- [ ] 7.7 Verify prefill fills only empty fields, across several notes with
      differing amounts of pre-existing content.
- [ ] 7.8 Verify the provider walk falls through correctly when the primary
      has no entry, and that provenance names the provider that actually
      answered — not the primary.
- [ ] 7.9 Verify both prefill timing modes.
- [ ] 7.10 Verify panels are closed and empty on every note, including
      after opening one on the previous note.
- [ ] 7.11 Verify link capture with a direct audio URL end to end,
      including trim availability afterwards.
- [ ] 7.12 Attempt link capture with a YouTube URL and record the current
      real-world result, continuing the archived change's history rather
      than restating it as fixed.
- [ ] 7.13 Run the belt over a non-trivial slice of a real import —
      `bulk-import-anki-csv` is the source of that data — and record how
      the queue indicator reads after several deferrals (design Risks).
- [ ] 7.14 Re-run the backend suite against a real Postgres container and
      record the count. `routes/enrich.py` is touched.

## 8. Boundary checks

- [ ] 8.1 Confirm no Mjølnir concept entered this capability: no decks, no
      card ids, no occurrences, no card types, and the word "card" nowhere
      in the spec, UI copy, or code.
- [ ] 8.2 Confirm `status` remains `draft`/`ready` only — no "triaged",
      "reviewed", or "published" state was added.
- [ ] 8.3 Confirm nothing tracks whether a downstream consumer took a
      note.
- [ ] 8.4 Confirm `assets/triage-belt-mock.html` is committed and
      referenced from the proposal as the agreed design.
