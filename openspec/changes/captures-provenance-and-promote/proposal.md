## Why

`origin=capture` has been a claim stabbur cannot back. `note-origin-provenance`
added the constraint `origin <> 'capture' OR capture_id IS NOT NULL`, but
`db/models.py:91` still carries its own admission:

```python
# Provenance; null for hand-authored entries. No FK — P7's `captures`
# table does not exist yet in this change.
```

So today no note can legitimately be created with `origin=capture`: there is
nothing for `capture_id` to point at, no `POST /api/captures`, and — the part
that actually bites — **no column anywhere on `notes` that can hold a URL, a
page title, or a YouTube timecode.** `notes` has `context_text` and nothing
else resembling a source.

`hover-translate` is being adapted into the capture client it was always
meant to be (that repo's `smia-translation-and-stabbur-capture`). It needs to
send two genuinely different things:

- **a manual note** — the operator types a word into the extension popup with
  no page involved. This already works: `POST /api/notes` derives
  `origin=manual`. Nothing in this change is needed for it.
- **a capture** — text selected on a page, carrying the URL, the page title,
  the surrounding context, and on YouTube the video id and cue timecode.
  This is impossible today, and it is what this change makes possible.

Without this, the extension's only option is to post capture-shaped content
as `origin=manual` and flatten the provenance into `context_text` prose. That
is unqueryable, and because `origin` is immutable and
`ck_notes_manual_origin_has_no_provenance` forbids attaching a `capture_id`
later, **it is permanent**. Every such note would be mislabelled forever. The
table has to exist before the client ships, not after.

## What Changes

- **A `captures` table**, holding the raw lexical intent and — uniquely — its
  source: `source` JSONB shaped per `tun/docs/03-data-model.md`
  (`{web: url, title}` | `{youtube: videoId, cueStartMs, cueEndMs, url,
  title}`), plus `selected_text`, `context_text`, `translations` as captured,
  and optional `audio_blob` / `audio_sel_ms`.

- **No `status` column on `captures`.** `03-data-model.md` specifies
  `status inbox|promoted|discarded`; this change drops it. Captures
  auto-promote on arrival, so the promoted note's own `draft`/`ready` status
  is the only lifecycle there is, and the `origin`-scoped triage belt is
  already the review surface. A second lifecycle would be a queue with
  nothing ever in it. **This supersedes part of `03-data-model.md` and needs
  an ADR row in `tun/docs/07-decisions.md` plus an in-place annotation in
  that doc** — tun's convention is that superseded decisions are marked,
  never deleted.

- **`POST /api/captures` creates the capture *and* its draft note in one
  transaction**, returning both. The note is written with `origin=capture`
  and `capture_id` set, which is the first time that origin becomes
  legitimately reachable.

- **The client supplies the capture id.** The extension flushes from an
  offline outbox and will retry a request whose response it never saw;
  without a client-supplied id, every retry mints a duplicate note. A
  client-generated UUID plus upsert-on-conflict semantics makes the flush
  safely repeatable.

- **`GET /api/captures/<id>`** so a note's provenance can be read back, and
  **`GET /api/captures?unattached=true`** listing captures whose audio has
  not yet been claimed by any note — the surface the extension's recorder and
  the editor's audio field both read, instead of talking to each other.

- **A real foreign key from `notes.capture_id` to `captures.id`.** The
  existing check constraint already guarantees non-null for `origin=capture`;
  this makes it referential. Same-database, same-service — not a cross-service
  FK, so D42/D43 are untouched.

- **The public read API is unchanged.** `GET /api/notes` already exposes
  `capture_id` and nothing more; whether a note came from a web page or a
  YouTube cue is none of Mjølnir's business (D44). No `source` leaks into
  `_serialize_public`.

## Capabilities

### Added Capabilities

- `captures-ingestion`: the capture entity, its source shapes, idempotent
  client-id ingestion, auto-promotion to a draft note, and the unattached-audio
  query. New capability — `notes-authoring` describes authoring a note, not
  recording where one came from.

### Modified Capabilities

- `notes-schema`: `capture_id` becomes a referential foreign key rather than a
  free-floating text column, and `origin=capture` becomes a reachable state
  rather than one no caller can legitimately produce.

### Unchanged (explicitly)

- `notes-read-api`: no change to request or response shape.
- `note-editor`, `notes-browser`, `note-triage`: a promoted capture is an
  ordinary `origin=capture` draft. The belt is already origin-scoped, so a
  capture review queue appears with no work in those capabilities.

## Impact

- **Schema** (`db/models.py`, one Alembic migration): new `captures` table;
  `notes.capture_id` gains a FK. No backfill — no row can currently have a
  non-null `capture_id`, since nothing could legitimately write one.
- **API** (new `routes/captures.py`, registered in `app.py`):
  `POST /api/captures`, `GET /api/captures/<id>`, `GET /api/captures`.
  `routes/notes.py` is touched only if `_serialize_authoring` should expose
  the joined capture — see design.
- **Blobs**: unchanged. The extension uploads audio through the existing
  `POST /blobs` first and passes the resulting sha256, which is why
  `blobs.py`'s size bound already names "P7's capture ingestion" as its
  reason to exist.
- **Tests**: ingestion, idempotent replay, auto-promotion writing a valid
  `origin=capture` note, source-shape validation, the unattached query, FK
  enforcement, and an explicit assertion that `_serialize_public` is unchanged.
- **Docs**: an ADR row in `tun/docs/07-decisions.md` and an annotation in
  `tun/docs/03-data-model.md` for the dropped `status`.
- **Blocks** `hover-translate`'s `smia-translation-and-stabbur-capture` phase 3.
  That change's phases 1–2 (decommission, smia-backed tooltip) do not depend
  on this one and can proceed in parallel.
