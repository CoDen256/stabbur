## Context

Read these before writing code, in this order:

1. `tun/docs/03-data-model.md` — the exact `notes`/`grammar_rule` schema,
   the five note types, and why `audio_blob` is required for Mjølnir
   eligibility but not for `status=ready`. This document is the source of
   truth for every column and every constraint below; this design does not
   repeat its reasoning, only its implementation.
2. `tun/docs/07-decisions.md`, **D43, D44, D45, D74** — why stabbur knows
   nothing about decks/ids/occurrences, why the pull is one-directional with
   no callback, why audio is stabbur's own canonical store, and the exact
   rename/shape history (`item`→`note`) so nothing reverts it by accident.
3. `tun/docs/02-services.md` — the repo/service boundary, and the "every
   service ships its own UI" convention this authoring surface follows at a
   minimal scale.
4. **`smia`'s actual code, read directly, not described secondhand**:
   `smia/app.py`, `smia/db/session.py`, `smia/db/models.py`, `smia/auth.py`.
   stabbur is the second service built in this ecosystem after `smia`; it
   should look like `smia`'s sibling, not a reinvention. `smia/db/session.py`
   already says in its own comment that it expects this ("Matches phonexa's
   db/session.py pattern... same stack, same shape" — read: every service
   here shares this shape, stabbur included).

## Goals / Non-Goals

**Goals:**
- A `notes`/`grammar_rule` schema that is a faithful, exact implementation
  of `03-data-model.md` — no speculative columns, no narrowing either.
- Content-addressed audio storage that `mjolnir/hub` can later snapshot from
  (D45), without stabbur needing to know that consumer exists.
- Just enough authoring to hand-create 10 real notes with real audio —
  the literal bar P4 needs to clear.
- A read API whose shape `mjolnir/builder` can be built against via a fixture
  today and the real thing later, with zero contract drift between the two.

**Non-Goals:**
- Capture ingestion, hover-translate integration, `smia` enrichment
  orchestration — P7.
- The triage UI (inbox, dedup, enrichment suggestions, bulk review) — P8.
- Anything Mjølnir-shaped: no decks, no card ids, no occurrences, ever, in
  this schema (D43 is a hard boundary, not a style preference).
- A "published" or "minted" status on notes. stabbur genuinely does not know
  whether Mjølnir ever picked a note up (D44) — do not add a column for this
  "to be safe." Its absence is the point, not an oversight.

## Decisions

### D-N1 — Flask + SQLAlchemy + Alembic + psycopg2, matching `smia` exactly

Not evaluated against alternatives — this is a consistency decision, not a
technical one. One operator maintaining four services benefits far more from
"every service looks the same" than from any per-service optimization. Copy
`smia`'s `db/session.py` near-verbatim (only `DATABASE_URL`'s default and the
module docstring change); copy `smia`'s `auth.py` shared-bearer-token
middleware exactly, with stabbur's own env var name (`STABBUR_AUTH_TOKEN`)
in place of `SMIA_AUTH_TOKEN`.

### D-N2 — Audio blobs are files on disk, addressed by sha256, not a DB column

```
stabbur/blobs/<sha256>.mp3           -- the file
notes.audio_blob = "<sha256>" | null  -- a reference, not the bytes
```

`POST /blobs` accepts audio bytes, computes the sha256, writes the file if
not already present (idempotent — re-uploading identical bytes is a no-op,
same shape as `mjolnir`'s `ota-publish.sh` reuse guard), and returns the
hash. A note's `audio_blob` field is set to that hash separately, via the
authoring endpoint — upload and attach are two steps, not one, so an
author can preview/trim audio before committing it to a note.

### D-N3 — Authoring is a thin CRUD, deliberately not the triage UI

```
POST   /api/notes            create (status defaults to draft)
GET    /api/notes/{id}       read one
PATCH  /api/notes/{id}       edit any field, including flipping draft→ready
DELETE /api/notes/{id}       hard delete — only valid while draft; once a
                              note has ever been queried by notes-read-api
                              (i.e. could plausibly have been minted), treat
                              it as a tombstone instead (03-data-model.md:
                              "immutable forever, even once removed")
GET    /ui                   a bare HTML form over the above — no inbox, no
                              suggestions, no bulk actions
```

**Alternative considered:** build the real triage UI now, since it will be
needed eventually anyway. Rejected — P7/P8 depend on `smia` enrichment and
capture ingestion existing first; building the UI around data sources that
don't exist yet means redesigning it twice. Ten hand-written notes do not
need an inbox.

### D-N4 — the read API's exact contract

```
GET /api/notes?source_lang=no&status=ready&since=<ISO8601>

200 OK
[
  {
    "id": "...", "created_at": "...", "capture_id": null,
    "type": "word", "source_lang": "no",
    "text": "...", "translations": [{"lang": "en", "text": "..."}],
    "transcription": "...", "pos": "substantiv", "lemma": "...",
    "inflections": {"article": "...", "sg_indef": "...", ...},
    "context_text": "...", "audio_blob": "<sha256-or-null>",
    "audio_sel_ms": [0, 1200], "grammar_rule_id": null,
    "status": "ready"
  }
]
```

`since` filters on `notes.updated_at` (resolved during implementation — see
Open Questions: `updated_at` was added, and `since` filters on it rather
than `created_at` precisely so an edit to an already-`ready` note is picked
up by a later pull, not just newly-created notes). `updated_at` itself is
not part of the response body above — the shape stays exactly as shown;
`updated_at` is request-side filtering plumbing only. No pagination in this
change; 10 hand-written notes and even a few hundred fit in one response
without it. Revisit if `builder`'s pulls ever get slow.

`status=` is accepted on the request but has no effect beyond the hard,
always-on `status=ready` filter — there is no way to request drafts through
this endpoint regardless of what `status=` is set to (`notes-read-api`
spec). `since` values must be URL-encoded by the caller (a raw `+00:00`
UTC-offset collides with query-string space-encoding); this endpoint does
not attempt to recover a malformed value, matching normal HTTP client
responsibility.

**This exact shape is the contract `p4-builder` (the parallel `mjolnir`
change) is being built against as a fixture.** Changing a field name or
dropping a field here without updating that change's fixture breaks the
integration silently. If a field needs to change, grep the `mjolnir` repo's
`p4-builder` change for its fixture file and update both together.

## Risks / Trade-offs

- **The fixture in `p4-builder` drifting from this API's real shape** → D-N4
  states the contract explicitly for exactly this reason. Worth a
  cross-repo integration test once both changes land (task 5 in this
  change's tasks.md), not just trusting the two designs stayed in sync.
- **Hard-deleting a note that was already minted by Mjølnir** would violate
  "note ids are permanent, even once removed" from `03-data-model.md`. →
  D-N3's delete endpoint only hard-deletes drafts; anything that could
  plausibly have been pulled already becomes a tombstone (still queryable by
  id, excluded from `GET /api/notes`'s normal listing).
- **No "updated_at" in the original schema sketch** — `since=` filtering on
  `created_at` alone would miss edits to already-ready notes, which
  `builder`'s content-regeneration (D74) explicitly needs to pick up every
  run regardless of `since`. Resolved: `updated_at` was added and `since`
  filters on it instead (see Open Questions below).

## Migration Plan

New service, no prior state to migrate.

1. Schema + migrations first (`notes`, `grammar_rule`) — can be reviewed and
   tested against `03-data-model.md` in isolation.
2. Blob storage second — independent of the schema beyond the `audio_blob`
   column existing.
3. Authoring CRUD third — needs both of the above.
4. Read API last — needs real data to test against meaningfully, which the
   authoring surface now provides.
5. Hand-author the 10 notes P4's finish line calls for, using the authoring
   UI, once all four are done.

## Open Questions (resolved during implementation)

- **`updated_at`: added.** Cheap now, and it lets `since` catch edits to
  already-`ready` notes (see D-N4 above) rather than only new notes — closes
  the Risk noted below without requiring `builder` to special-case anything.
  Not part of the read API's response body; filtering plumbing only.
- **Tombstone mechanism: a `deleted_at` column, not a draft-only hard-delete.**
  `DELETE` on a `draft` note hard-deletes the row (never queryable, never
  could have been pulled). `DELETE` on a `ready` note sets `deleted_at`
  instead — the row stays, `GET /api/notes/{id}` still resolves it, but it's
  excluded from `GET /api/notes`'s listing. This is the literal reading of
  `status=ready` as the proxy for "could plausibly have been minted" from
  both `notes-schema`'s and `notes-authoring`'s scenarios — no need to track
  "has this id ever actually been returned by a query" separately.
