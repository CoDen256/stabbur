## 0. Before you write any code — read this first

- `tun/docs/03-data-model.md` — the exact schema and the five note types.
  Every column in task 1 traces back to this document; don't improvise a
  field that isn't there, and don't drop one that is.
- `tun/docs/07-decisions.md`, **D43, D44, D45, D74** — the boundaries this
  schema must respect (language-agnostic, one-directional pull, audio
  ownership, the `item`→`note` rename history).
- **Read `smia`'s actual code before writing stabbur's**, not a description
  of it: `/home/coden/dev/smia/app.py`, `db/session.py`, `db/models.py`,
  `auth.py`. stabbur should look like `smia`'s sibling. Copying
  `db/session.py` nearly verbatim (swap the env var default and the
  docstring) is correct, not lazy — `smia`'s own comment says this is the
  expected pattern for every service in this ecosystem.
- `design.md` in this change, **D-N4**, is the exact wire contract the
  parallel `p4-builder` change in the `mjolnir` repo is being built against
  as a fixture. Do not change a field name or drop a field without checking
  that change's fixture file and updating both together — this is the one
  place a silent mismatch between the two repos would actually break
  something.

This is a new service with no prior consumers — nothing here is a migration
in the risky sense, and nothing here touches the Mjølnir app, the APK, or
anything native. Normal iteration applies.

## 1. `notes` and `grammar_rule` schema

- [x] 1.1 Set up the Flask skeleton mirroring `smia`: `app.py`,
      `db/session.py` (copy `smia`'s, change only `DATABASE_URL`'s default
      and `STABBUR_AUTH_TOKEN` in place of `SMIA_AUTH_TOKEN`), `auth.py`
      (same shared-bearer-token middleware), Alembic wired the same way.
- [x] 1.2 `db/models.py`: `Note` and `GrammarRule` SQLAlchemy models, every
      field from `03-data-model.md`'s `note` schema exactly —
      `id, created_at, capture_id, type, source_lang, text, translations
      (JSONB), transcription, pos, lemma, inflections (JSONB), context_text,
      audio_blob, audio_sel_ms, grammar_rule_id, seq, status`. `status`
      constrained to `draft`/`ready` only.
- [x] 1.3 Alembic migration for both tables. No `captures` table in this
      change (P7's concern) — `capture_id` on `Note` stays nullable and
      unenforced by a foreign key to a table that doesn't exist yet.
- [x] 1.4 Unit tests: creating a note with each of the five `type` values
      and their documented inflection shapes; rejecting an invalid `status`;
      allowing `status=ready` with `audio_blob=null`.
- [x] 1.5 Tombstone behavior (`notes-schema`'s spec): deleting a `draft` note
      removes the row; deleting a `ready` note does not free its id. Decide
      and implement the concrete mechanism (a `deleted_at` column is the
      obvious one, but check `design.md`'s Open Questions before committing
      to it — it's flagged there as still open).

## 2. Blob storage

- [x] 2.1 `POST /blobs`: accept audio bytes, compute sha256, write to
      `stabbur/blobs/<sha256>.mp3` if not already present, return the hash.
      Idempotent — re-uploading identical bytes must not error or duplicate.
- [x] 2.2 `GET /blob/<sha256>`: serve the file, immutable cache headers.
- [x] 2.3 Wire `Note.audio_blob` to accept any hash previously returned by
      2.1 — attaching audio to a note is a separate step from uploading it
      (D-N2), so a note can be created, have its audio uploaded and
      previewed, and only then have `audio_blob` set.
- [x] 2.4 Test: upload the same bytes twice, confirm one file on disk and
      the same hash both times.

## 3. Authoring surface

- [x] 3.1 `POST /api/notes`, `GET /api/notes/{id}`, `PATCH /api/notes/{id}`,
      `DELETE /api/notes/{id}` per `design.md` D-N3.
- [x] 3.2 `GET /ui`: a bare HTML form — create a note, edit its fields,
      upload/attach audio via task 2, flip `draft`→`ready`. No inbox, no
      suggestions, no bulk actions — resist the urge to build toward P8 here.
- [x] 3.3 Test: the full hand-authoring flow end to end — create a draft
      note, attach audio, mark ready, confirm it now appears in the read
      API's output (task 4).

## 4. Read API

- [x] 4.1 `GET /api/notes?source_lang=&status=&since=` exactly per
      `design.md` D-N4's response shape. `status` filter always implicitly
      excludes `draft` regardless of what's requested (per
      `notes-read-api`'s spec — there is no way to ask for drafts through
      this endpoint).
- [x] 4.2 No acknowledgment/callback mechanism of any kind (D44) — do not add
      one "for convenience." If `mjolnir/hub` ever seems to need one, that's
      a decision for `tun/docs/07-decisions.md`, not a quiet addition here.
- [x] 4.3 Test: querying with `since=` after creating some notes and editing
      others; confirm `draft` notes never appear under any filter
      combination.
- [x] 4.4 Write down the final, shipped response shape (field names, types,
      one real example) somewhere durable — update `design.md` D-N4 itself
      if anything changed from the sketch during implementation, since that
      section is the contract the `mjolnir` side's fixture depends on.

## 5. Integration

- [x] 5.1 Hand-author 10 real notes through the UI from task 3, with real
      audio, covering at least three of the five note types — this is P4's
      actual finish line, not just a schema exercise.

      Done via `scripts/seed_p4_notes.py`, which drives the real HTTP API
      (not direct DB writes) exactly as `/ui` would: 10 notes across 4 types
      (word ×6, expression ×2, listening ×1, pronunciation ×1), each with
      real audio sourced from `phonexa/lang/no/audio` (per-clip durations
      measured with ffprobe and stored as `audio_sel_ms`), all marked ready.
- [x] 5.2 Confirm the read API (task 4) returns all 10 correctly once marked
      `ready`.

      Verified: `GET /api/notes?source_lang=no&status=ready` returns all 10,
      `set(types) == {word, expression, listening, pronunciation}`, and a
      sampled `audio_blob` hash round-trips real, non-empty mp3 bytes via
      `GET /blob/<sha256>`.
- [ ] 5.3 Once the `mjolnir` repo's `p4-builder` change has a real pull step
      (its own task 4.1), hand it this service's real URL and confirm its
      fixture and this API agree byte-for-byte on shape. Fix whichever side
      drifted — check with the other change's author/session before
      resolving a mismatch unilaterally, since both sides have reasons for
      their current shape.

      Checked 2026-10-25: `p4-builder` is 0/37 tasks complete, no pull step
      and no fixture file exist yet. Genuinely blocked on that change, not
      on anything here — revisit once it lands.
- [x] 5.4 If anything here diverged from `tun/docs/03-data-model.md` during
      implementation, record it as an ADR amendment in
      `tun/docs/07-decisions.md`, not a silent deviation — this project's
      established practice for exactly this situation.

      Recorded as D82 (D81 was taken concurrently by `p4-builder`'s own
      session): `notes` gained `updated_at` (so `since` catches edits to
      already-`ready` notes, not just new notes) and `deleted_at` (the
      concrete tombstone mechanism). `03-data-model.md`'s schema sketch
      updated to match.
