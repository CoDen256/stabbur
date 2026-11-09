## 1. Schema

- [x] 1.1 Add a `Capture` model to `db/models.py`: `id` (Text PK, **client
      supplied**, no default — D4), `created_at`, `selected_text` (Text, not
      null), `context_text` (Text, nullable), `translations` (JSONB, default
      list), `source` (JSONB, not null), `audio_blob` (Text, nullable),
      `audio_sel_ms` (JSONB, nullable). **No `status` column** (D2).
- [x] 1.2 Add a CHECK constraint that `source` contains a recognised shape
      key (`web` or `youtube`), named in the existing `ck_captures_*` idiom.
      Keep it shape-level only — per-shape required keys are validated in
      the route (D8), since a JSONB CHECK cannot express them readably.
- [x] 1.3 Change `notes.capture_id` to carry `ForeignKey("captures.id")`
      with `ondelete="RESTRICT"` (D7). Leave the existing check constraints
      exactly as they are.
- [x] 1.4 Alembic migration: create `captures`, then add the FK on
      `notes.capture_id`. **No backfill** — assert first that zero rows have
      a non-null `capture_id` (nothing could legitimately have written one),
      and fail the migration loudly rather than silently if that is false.
- [x] 1.5 Confirm the downgrade drops the FK before dropping the table, in
      that order, or it will fail on a populated database.

## 2. Ingestion endpoint

- [x] 2.1 New `routes/captures.py` with `register_capture_routes(app)`,
      registered in `app.py` alongside the existing registrars.
- [x] 2.2 `POST /api/captures`: require `id`, `selected_text`, `source`.
      Validate the source shape per D8 (`youtube` requires `videoId`, `web`
      requires `url`; unknown sibling keys pass through unchanged).
- [x] 2.3 Implement the atomic promote (D3): in one `session_scope`, write
      the `Capture`, then a `Note` with `origin="capture"`,
      `capture_id=<id>`, `status="draft"`, `type=body.get("type", "word")`,
      `source_lang=body.get("source_lang", "no")`, copying
      `selected_text → text`, `context_text`, `translations`, `audio_blob`,
      `audio_sel_ms`. Return `{"capture": ..., "note": ...}` with `201`.
- [x] 2.4 Reuse `routes/notes.py`'s `_serialize_authoring` for the note half
      rather than writing a second serializer. Extract it if it is not
      importable as-is; do not duplicate it.
- [x] 2.5 Idempotent replay (D4): if the id already exists, return the
      existing capture and its note with `200`, not `201` and not `409`.
      Resolve the note by `capture_id`, not by remembering an insert.
- [x] 2.6 Decide and record how a replay carrying *different* content for a
      known id behaves. Recommendation: ignore the new body and return the
      stored pair — a retry is meant to be the same capture, and silently
      overwriting a reviewed note from a stale outbox entry is the worse
      failure. Write the decision down either way.
- [x] 2.7 Map the `IntegrityError` path through the existing
      `_integrity_error_message` helper so constraint violations read the
      same as they do on `POST /api/notes`.

## 3. Read endpoints

- [x] 3.1 `GET /api/captures/<id>` → the capture alone (D9: the editor
      fetches it when a note has a `capture_id`; it is **not** inlined into
      note listings).
- [x] 3.2 `GET /api/captures` with `?unattached=true` (D5): captures whose
      `audio_blob` is non-null and where no note referencing that capture
      carries the same `audio_blob`. Express it as one query, not a
      fetch-then-filter in Python.
- [x] 3.3 Confirm the unattached query's ordering is newest-first — the
      recorder's "what did I just capture?" list is the primary consumer.
- [x] 3.4 Leave `routes/notes.py`'s `_serialize_public` and `list_notes`
      untouched. Do not add `source` anywhere near them.

## 4. Tests

- [x] 4.1 Ingestion writes both rows; the note validates against every
      existing `origin=capture` constraint.
- [x] 4.2 Replaying the same id creates nothing new and returns `200`.
- [x] 4.3 Two different ids with identical `selected_text` and different
      sources produce two captures and two notes.
- [x] 4.4 Source-shape validation: `youtube` without `videoId`, `web`
      without `url`, and an unrecognised shape are each rejected; a
      recognised shape with extra sibling keys is stored unchanged.
- [x] 4.5 A YouTube capture with a timecode and no audio is accepted and
      triggers no fetch of any kind (assert no outbound call is attempted).
- [x] 4.6 Editing the promoted note's `text`/`translations` leaves the
      capture's own copies unchanged.
- [x] 4.7 The unattached query: appears with audio and no note reference;
      disappears after `PATCH /api/notes/<id> {audio_blob}`; never appears
      for an audio-less capture.
- [x] 4.8 FK enforcement: a note cannot reference a non-existent capture;
      deleting a referenced capture is rejected.
- [x] 4.9 **Assert `_serialize_public`'s key set is unchanged**, in the same
      style `note-origin-provenance` used, so no future change widens the
      public contract by accident.
- [x] 4.10 A capture whose note creation would be invalid (e.g. a bad
      `type`) stores neither row.

## 5. Docs

- [x] 5.1 ADR row in `tun/docs/07-decisions.md`: captures carry no status
      column; auto-promotion replaces the `inbox|promoted|discarded`
      lifecycle; the origin-scoped triage belt is the review surface (D2).
- [x] 5.2 Annotate `tun/docs/03-data-model.md`'s capture schema **in place**
      — the `status` line marked superseded with a pointer to that ADR, not
      deleted. tun's convention: a stale claim must not be readable without
      its correction.
- [x] 5.3 ADR row: the audio rendezvous is the blob store plus the
      unattached query, never a channel between stabbur and the extension
      (D5) — this is the decision that keeps D43/D44's non-coupling intact
      when a browser extension enters the system.
- [x] 5.4 Update `stabbur/CLAUDE.md`'s status line: `captures` exists, and
      `origin=capture` is now reachable. Its "Not implemented" claim is
      already stale and gets more so with this change.
- [x] 5.5 Note in `tun/docs/03-data-model.md` that the capture's
      `translations` keep provider-native language codes (`nb`) while
      `notes.source_lang` is stabbur's own (`no`), and that the two are
      deliberately not reconciled (D3).

## 6. Verification

- [x] 6.1 Run the real flow end to end against a local stack: `POST /blobs`
      with an audio file → `POST /api/captures` referencing it → confirm the
      note appears in the notes browser filtered to `origin=capture`.
- [x] 6.2 Confirm the `origin-scoped-triage-belt` queue picks up
      `origin=capture` drafts with **no change to that change's code** — if
      it does not, say so here rather than patching the belt silently; it
      would mean D2's "the belt is already the review surface" is wrong.
- [x] 6.3 Kill the request mid-flight (or simulate a lost response) and
      replay the outbox entry; confirm exactly one note exists.
- [x] 6.4 Record whether `audio_sel_ms` round-trips unchanged through
      capture → note → editor, since nothing in this change interprets it
      and a silent reshaping would only surface much later.
