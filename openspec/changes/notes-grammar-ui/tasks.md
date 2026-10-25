## 0. Before you write any code — read this first

- `tun/docs/13-operator-console-ux.md` and its mockup — every page here is
  specified there.
- **Read `routes/notes.py` in full.** Two things it tells you that change
  what you build: `GET /api/notes` is the frozen public contract (D44) and
  must never grow a parameter that can return a draft — the authoring list
  is a *new, separate* route (task 1.1), not a flag on this one. And there
  is currently no single-grammar-rule `GET`/`PATCH`/`DELETE` at all — task 4
  is new backend work, not just new UI.
- `design.md` D-S1 through D-S4 — each names an approach that was considered
  and rejected (a shared list route, a waveform library, a server-side
  PoS-fields endpoint). Read the rejection before reaching for it yourself.

## 1. Authoring-list route

- [ ] 1.1 `GET /api/notes/authoring` — every status, filters for
      `status`/`type`/`pos`, sort, text search across `text`/
      `translations`/`lemma`. Never touches or relaxes `list_notes`'s
      existing `status == "ready"` filter.
- [ ] 1.2 Test: a draft note appears here and never via `GET /api/notes`, in
      the same test file, asserting both at once so a future change can't
      silently merge the two paths.

## 2. Notes browser page

- [ ] 2.1 List UI: table with filter/sort controls per the mockup, each row
      linking to the editor (task 3).
- [ ] 2.2 Status/audio-presence shown as pills per the mockup (ready/draft,
      audio present/missing).

## 3. Note editor page

- [ ] 3.1 Structured-field form: every `note` column, editable, PATCHes
      `/api/notes/{id}`.
- [ ] 3.2 Raw-JSON toggle: a read-only `<pre>` of the note's serialized
      form, kept in sync with the structured form's current (possibly
      unsaved) values.
- [ ] 3.3 Audio player (`<audio>` element) + static waveform preview
      (Web Audio API `decodeAudioData` → `<canvas>`, per D-S2 — no new
      dependency) + two draggable trim handles backed by `audio_sel_ms`.
- [ ] 3.4 "Preview trim" — plays back only the selected range using the
      existing `<audio>` element's playback controls.
- [ ] 3.5 "Replace audio" — uploads via the existing `POST /blobs`,
      updates `audio_blob` on save; previous blob is left alone (it's
      content-addressed, nothing special to clean up).
- [ ] 3.6 Delete action: ready notes get `deleted_at` set (existing
      tombstone behavior from `p4-notes`); draft notes hard-delete. Confirm
      the UI makes this distinction visible, not silent.

## 4. Grammar rule backend

- [ ] 4.1 `GET /api/grammar_rules/<id>` — single rule.
- [ ] 4.2 `PATCH /api/grammar_rules/<id>` — edit title/html.
- [ ] 4.3 `DELETE /api/grammar_rules/<id>` — refuse with a reference count if
      any note's `grammar_rule_id` points to it; succeed otherwise. Guard
      the check-then-delete against a race (D-S4's transaction note).
- [ ] 4.4 A way to list notes by `grammar_rule_id` (either a query param on
      the authoring-list route from task 1, or a dedicated endpoint —
      whichever fits `routes/notes.py`'s existing shape better).
- [ ] 4.5 Tests: delete blocked at 1+ references, succeeds at 0; the
      reference-count message matches the actual count.

## 5. Grammar rule pages

- [ ] 5.1 List page: sortable (including by usage count from task 4.4),
      searchable by title.
- [ ] 5.2 Detail/edit page: title/html fields, the reverse usage list
      (each entry linking to that note's editor), delete button (disabled
      with the reference count shown, when blocked).
- [ ] 5.3 New-rule creation form.

## 6. New-note creation, with prefill

- [ ] 6.1 Hardcode the five types' field shapes (per `03-data-model.md`)
      client-side; selecting a PoS for `type=word` swaps in the right
      inflection fields live, per D-S4 — no new endpoint.
- [ ] 6.2 Audio upload on the creation form, same upload path as task 3.5.
- [ ] 6.3 Test (manual acceptance, not automatable from here): create one
      real note of each of the five types through this form, confirm each
      reaches `status=ready` cleanly.

## 7. Integration and sign-off

- [ ] 7.1 Full regression on `routes/notes.py`'s existing tests — confirm
      nothing here touched `GET /api/notes`'s behavior.
- [ ] 7.2 Hand-author a handful of real notes and at least one grammar rule
      through the new UI end to end — the actual acceptance bar, not just
      passing automated tests.
- [ ] 7.3 Record any real divergence from `design.md` found during
      implementation as an ADR amendment in `tun/docs/07-decisions.md` —
      this project's established practice.
