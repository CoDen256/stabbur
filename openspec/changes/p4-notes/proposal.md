## Why

`stabbur` does not exist yet beyond a README and a decision record. P4's
finish line — "hand-write 10 notes with audio, publish, study them on the
phone" — needs a real `notes` schema and a read API before `mjolnir/builder`
(the parallel `p4-builder` change in the `mjolnir` repo) has anything to
pull. This change builds exactly that: enough of `stabbur` to author content
and serve it, nothing from the richer capture/enrichment/triage pipeline
that comes later (P7/P8).

The data model this change implements is already finalized
(`tun/docs/03-data-model.md`, D74) — this is the build, not the design.

## What Changes

- **New `notes` and `grammar_rule` schema**, matching `03-data-model.md`
  exactly: `source_lang`, `translations` as `[{lang, text}]` (any languages),
  `inflections` as a flat Norwegian-shaped JSONB (no per-language schema
  until a second `source_lang` exists), `status` as `draft`/`ready` only —
  stabbur never learns whether Mjølnir picked a note up (D44).
- **Content-addressed audio blob storage** (D45): upload-and-hash, served by
  sha256. stabbur owns the canonical learning audio; `audio_blob` is not
  required to reach `status=ready`, but is required for Mjølnir to ever pick
  a note up, with no type-based exception (D74).
- **A minimal authoring surface** — enough to hand-create and edit notes
  directly, including uploading their audio. **This is explicitly not P8's
  triage UI** (no capture inbox, no enrichment suggestions, no dedup) and
  **not P7's capture ingestion** (no `POST /captures`, no hover-translate
  integration). Both are real, separate, later work; building them now would
  be solving a problem P4 doesn't have yet.
- **The read API `mjolnir/hub` pulls from**: `GET /api/notes?source_lang=
  no&status=ready&since=…`, returning exactly the fields `03-data-model.md`
  specifies. One-directional (D44) — this change adds no mechanism for
  Mjølnir to report back what it did with a note, by design.
- **BREAKING**: none — `stabbur` has no prior consumers.

Follows the established stack of its siblings (`smia`, `phonexa`): Flask +
SQLAlchemy + Alembic + psycopg2, shared-bearer-token auth matching `smia`'s
`auth.py` pattern almost exactly. Not a new choice — `smia`'s own
`db/session.py` already anticipates this ("Matches phonexa's db/session.py
pattern... same stack, same shape").

## Capabilities

### New Capabilities
- `notes-schema`: the `notes` and `grammar_rule` tables, migrations, and the
  five note-type shapes from `03-data-model.md`.
- `blob-storage`: content-addressed audio storage, upload and serve by
  sha256, owned entirely by stabbur (D45).
- `notes-authoring`: a minimal CRUD surface sufficient to hand-create and
  edit notes with audio — not the eventual triage UI.
- `notes-read-api`: the one-directional pull endpoint `mjolnir/hub` consumes.

### Modified Capabilities
<!-- None. stabbur has no existing specs. -->

## Impact

- **New service**: `stabbur` goes from README-only to a real Flask app,
  mirroring `smia`'s layout (`app.py`, `db/models.py`, `db/session.py`,
  `auth.py`, `routes/`, Alembic migrations).
- **Depends on nothing else in this ecosystem** (D43 — stabbur is
  Mjølnir-independent and language-agnostic by design; it does not know
  `mjolnir/hub` exists).
- **Consumed by**: the parallel `p4-builder` change in the `mjolnir` repo,
  via the `notes-read-api` capability's exact response shape. That change is
  being built against a fixture of this API and does not block on this one
  landing first — but the two must agree on the wire shape, which is why
  this proposal's API shape is specified precisely rather than loosely.
- **Out of scope, flagged so it isn't assumed**: capture ingestion
  (`POST /captures`, hover-translate integration) — P7. The rich triage UI
  (capture inbox, enrichment suggestions from `smia`, dedup) — P8. Both are
  real future work, not forgotten, just not this change.
