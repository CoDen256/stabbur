## Context

Three facts in the existing code fix most of this design before it starts:

- **`notes` has nowhere to put a source.** Its columns are content and
  provenance-reference only (`db/models.py:58-137`). No `url`, no `source`,
  no timecode. `context_text` is surrounding prose, not a locator.
- **`origin` is immutable and the manual origin forbids provenance.**
  `routes/notes.py:193` rejects any `origin` change; `ck_notes_manual_origin_
  has_no_provenance` forbids a `capture_id` on a manual note. So a note
  created as `manual` can never be corrected into a capture. Getting this
  wrong once is permanent.
- **`origin=capture` is currently unreachable.**
  `ck_notes_capture_origin_requires_capture_id` demands a `capture_id`, and
  no table, route, or writer can produce one. The constraint has been
  guarding an empty set.

`tun/docs/03-data-model.md` already specifies the capture entity in full,
including its `source` shapes. This change implements that specification with
one deliberate subtraction (D2).

## Goals / Non-Goals

**Goals:**
- A capture's source — URL, title, YouTube video id and cue timecode — is
  stored in queryable structure, not flattened into prose.
- `origin=capture` becomes a legitimately reachable, referentially-backed state.
- An extension flushing an offline outbox can retry any request safely.
- Audio and note are decoupled: a recording can arrive before, with, or after
  the note it eventually belongs to.
- The public read API's contract is bit-for-bit unchanged.

**Non-Goals:**
- No capture triage UI. Promotion is automatic and the `origin`-scoped triage
  belt already reviews the resulting drafts.
- No server-side audio or video fetching. `manual-link-audio-capture`'s
  YouTube clipping remains known-blocked and this change does not touch it;
  the extension records audio in the browser instead.
- No `source` on `notes`, and no fourth `origin` value. The enum stays
  `manual|capture|import`.
- No changes to `POST /blobs`. Audio arrives as a sha256 the client already
  uploaded.
- No audio *requirement*. A text capture has `audio_blob = NULL`, which is
  what `03-data-model.md` already specifies for text sources.

## Decisions

### D1 — A `captures` table, not a `source` column on `notes`

Alternatives considered: add `source` JSONB to `notes` and a fourth origin
value; store the URL in `context_text`; a generic `note_metadata` key/value
table.

Chosen: implement `captures` as `03-data-model.md` specifies it.

Rationale: the three-entity split (capture / note / card) is load-bearing in
this ecosystem, and `03-data-model.md` opens with "do not merge them." A
capture is *raw, unreviewed intent with a provenance*; a note is *authored
content*. They have different mutability: the note gets edited freely, the
capture is the immutable record of what the page actually said.

Putting `source` on `notes` would also widen the origin enum, which the
triage belt filters on and which `note-origin-provenance` deliberately
designed as a total partition. Adding a fourth value to carry a *source
shape* confuses "where did this come from" with "what kind of place was it."

`context_text` was rejected outright: a URL in a prose field is unqueryable,
and the whole point of the change is provenance you can filter on.

### D2 — No `status` column on `captures` (supersedes part of `03-data-model.md`)

`03-data-model.md` specifies `status inbox|promoted|discarded`. This change
drops it.

Rationale: that status presumes a human triages captures *before* they become
notes. With auto-promotion (D3), every capture is `promoted` the instant it
exists, so `inbox` is a state no row ever occupies and `discarded` duplicates
deleting the promoted draft. A lifecycle column whose domain is effectively
one value is a field that lies about how the system works.

What replaces it already exists: the promoted note's own `draft`/`ready`
status, and `origin-scoped-triage-belt`'s queue, which is **already scoped by
origin** — so `origin=capture` gets a review belt with no new work.

This is a deviation from a cross-repo document, so it is recorded as an ADR
row in `tun/docs/07-decisions.md` and annotated in place in
`tun/docs/03-data-model.md`, per tun's convention that superseded decisions
are marked rather than deleted. Reintroducing a capture-side status later is
additive (a nullable column plus a filter) and costs no migration of meaning.

### D3 — `POST /api/captures` promotes in the same transaction

Alternatives considered: two calls from the client (`POST /api/captures` then
`POST /api/notes`); a background promoter; promotion on first read.

Chosen: one request, one transaction, writing both rows; response carries
both.

```
POST /api/captures
{ "id": "<client uuid>",
  "selected_text": "hunden løper",
  "context_text": "Se, hunden løper etter ballen.",
  "translations": [{"provider": "dictcc_static", "lang": "en", "text": "the dog runs"}],
  "source": {"youtube": "dQw4w9WgXcQ", "cueStartMs": 73120, "cueEndMs": 75400,
             "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=73",
             "title": "..."},
  "audio_blob": null,
  "type": "expression",
  "source_lang": "no" }
→ 201 { "capture": {...}, "note": {...origin:"capture", capture_id:"<id>"...} }
```

Rationale: two client calls can half-fail, leaving a capture with no note —
exactly the orphan state the dropped `status` column would otherwise have to
describe. One transaction makes "a capture exists" and "a draft exists"
the same fact, which is what justifies D2.

The note is created as `status=draft` always. `type` and `source_lang` come
from the request because `notes` requires them (`REQUIRED_CREATE_FIELDS`);
`type` defaults to `word` and `source_lang` to `no` when omitted, so a
minimal capture is still a valid one.

**Language-code seam**: smia speaks `nb` (its `/examples` route rejects
anything else; `dictcc_static`'s `_PAIRS` are keyed `nb`), while `notes.source_lang`
is `no`. The extension's `translations` arrive tagged with smia's codes. This
change stores `translations` verbatim as captured — it does not rewrite
provider language codes — and `source_lang` is stabbur's own field in
stabbur's own vocabulary. The two never need to agree, and conflating them
would corrupt the record of what the provider actually answered.

### D4 — The client supplies the capture id; ingestion is idempotent on it

Alternatives considered: server-generated uuid like `notes`; an
`Idempotency-Key` header; dedupe on content hash.

Chosen: `id` is required in the request body, and a replay of the same id
returns the existing capture and note with `200` instead of creating a second
pair.

Rationale: the extension holds an **offline outbox** (its own change's design)
and flushes it opportunistically. The failure that matters is not "the
request failed" — it is "the request succeeded and the response was lost,"
after which an honest client retries. With a server-generated id, every such
retry mints a duplicate note, and duplicates in a learning deck are worse
than a dropped capture because they survive into Mjølnir.

A content hash was rejected: capturing the same sentence twice from two
different videos is legitimate and must produce two captures.

Replay returns `200`, not `201`, and not `409` — the client's intent
("this capture should exist") is satisfied, so an error would push it into
retry logic for a state that is already correct.

### D5 — Audio is referenced, never uploaded here; unattached audio is a query

`audio_blob` is a sha256 the client already stored via the existing
`POST /blobs`. This route never accepts bytes.

The genuinely useful part is `GET /api/captures?unattached=true`: captures
with a non-null `audio_blob` whose promoted note does not (yet) carry that
same `audio_blob`.

Rationale: the extension's recorder and stabbur's note editor both need to
answer "is there a recording waiting for a note?" The obvious designs — the
editor asking the extension, or the extension reading the editor's open tab —
both make the two systems know about each other. This ecosystem has refused
that coupling everywhere (D43/D44; `import_ref` is deliberately "a reference,
not a dependency").

So the rendezvous is the blob store plus this query. The extension writes the
recording and walks away; the editor's audio field runs a `WHERE` clause
against its own database. Neither process addresses the other, and the
handoff survives a closed tab, a browser restart, or a week's delay.

Attaching stays an ordinary `PATCH /api/notes/<id> {audio_blob, audio_sel_ms}`
— already supported (`routes/notes.py:206`), no new endpoint.

### D6 — `audio_blob` on the capture is the WIDE clip; selection is a range

Per `03-data-model.md`, `audio_blob` is the padded clip and
`audio_sel_ms [start, end]` is the selection inside it. This change stores
both unchanged and interprets neither.

Rationale: trimming is a judgement that should stay revisable. Keeping the
wide clip means a bad trim is re-doable in the editor months later; storing
only trimmed bytes makes it permanent. stabbur does no audio processing here
at all — it records two values the client supplies.

### D7 — A real foreign key, `ON DELETE RESTRICT`

`notes.capture_id` gains `ForeignKey("captures.id")`.

Rationale: `ck_notes_capture_origin_requires_capture_id` already guarantees
the column is populated for `origin=capture`; this makes the target exist.
`note-origin-provenance`'s own risk note anticipated exactly this ("when
`captures` lands, the D4 constraint already guarantees a non-null
`capture_id`, which is what a future FK would need").

`RESTRICT`, not `CASCADE`: deleting a capture out from under a live note
would destroy the provenance of content that may already be minted into
Mjølnir. Captures are not deleted in normal operation; a note is.

This is intra-service and intra-database. D42/D43's prohibition is on
*cross-service* FKs, which this is not.

### D8 — `source` is validated on shape, loosely

Validation: `source` must be an object, and must contain either a `web` or a
`youtube` key (or a future sibling). `youtube` requires `videoId`; `web`
requires `url`. Unknown sibling keys inside a recognised shape are stored
unchanged.

Rationale: this mirrors how `translations` and `inflections` already carry
evolving JSONB shapes — validated enough that a client bug surfaces, loose
enough that adding a field costs no migration. `03-data-model.md` already
anticipates a third shape (`{shadowing_segment_id}`) that no client produces
yet; rejecting unknown top-level shapes outright would make adding it a
server change for no benefit.

Note what is *not* validated: a `youtube` source with a timecode makes no
claim about audio. Per the operator's decision, the timecode is provenance
("this is where I found it"), not a promise that a clip exists or can be
fetched. `audio_blob` stays independently nullable.

### D9 — The public read API stays untouched, asserted by test

`_serialize_public` already emits `capture_id` and will not gain `source`.

Rationale: D44 is one-directional. Mjølnir reasons about whether a note is
correct, reviewed, and audio'd — never about which web page it came from.
`note-origin-provenance` made the same call for `origin` and locked it with a
test rather than a comment; this change follows that precedent exactly.

Whether `_serialize_authoring` should join and inline the capture is a smaller
question: the editor wants to *show* provenance ("captured from youtube.com,
1:13"). Chosen: it does **not** inline it. The editor fetches
`GET /api/captures/<id>` when `capture_id` is present, keeping the list
endpoint's per-row cost flat for a notes browser that already pages through
thousands of import drafts.

## Risks / Open Questions

- **`translations` duplicates between capture and note.** Deliberate (the
  capture is the immutable "as captured" record, per the operator's explicit
  decision) but it does mean two copies that will diverge as the note is
  edited. That divergence is the feature; it should be documented in the
  editor so it does not read as a bug.
- **`GET /api/captures?unattached=true` is defined by a join against the
  note's `audio_blob`.** If an operator attaches the *same* recording to a
  second note by hand, the capture stops looking unattached while one note's
  audio came from somewhere it does not reference. Harmless, but the query is
  a heuristic for "waiting for a home," not a referential truth.
- **Open**: whether the auto-promoted note should start at `type=word` or
  infer from the selection (multi-word → `expression`). Inference is cheap
  and the operator corrects it in the belt either way; defaulting to `word`
  with a client-supplied override is the conservative start.
- **Open**: whether a capture should record which extension version produced
  it. `note-origin-provenance` deferred the same question for `import_ref`.
  Additive to `source` whenever wanted.
