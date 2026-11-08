## Context

`Note` today has exactly one provenance column:

```python
# db/models.py
# Provenance; null for hand-authored entries. No FK — P7's `captures`
# table does not exist yet in this change.
capture_id: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Its comment already names the problem: "null for hand-authored entries"
conflates *hand-authored* with *unknown*. Today that conflation is harmless
because captures are the only non-manual source. It stops being harmless the
moment a bulk import adds a third origin.

`list_notes_authoring` (`routes/notes.py:235`) is the operator-only list —
"every status, filterable/sortable/searchable" — and already carries
`status`, `type`, `pos`, `grammar_rule_id`, and `q` filters built as
progressive `stmt.where(...)` clauses. An `origin` filter is one more clause
in that same shape, not a new query path.

`list_notes` (the public, ready-only D44 contract) is a deliberately separate
function with a separate serializer. This change must not touch either.

## Goals / Non-Goals

**Goals:**
- Every note asserts its origin positively; no origin is inferable only from
  the absence of data.
- The three origins form a total partition, so a UI filter over them is
  exhaustive.
- An origin claim is backed by integrity constraints, not convention.
- Provenance is immutable once written.
- Existing API clients continue to work without passing `origin`.
- The public read API's contract is bit-for-bit unchanged.

**Non-Goals:**
- No import machinery, no candidate tables, no parsers. This change only
  provides the field an importer will later stamp.
- No foreign key from `import_ref` to anything. The import tool's candidate
  store is a local SQLite file, not a service — a FK to it is impossible,
  and even a nominal reference would invert the dependency.
- No `origin` on `captures`. A capture has exactly one origin by definition.
- No change to how `capture_id` itself behaves.
- No history/audit table. `origin` records *where a note came from*, not a
  log of what happened to it.

## Decisions

### D1 — `origin` is a required enum column, not a boolean or a nullable tag

Alternatives considered: an `is_manual` boolean; leaving `origin` nullable
and treating null as manual; deriving origin at read time from which
provenance columns are populated.

Chosen: `origin TEXT NOT NULL` with a `CHECK (origin IN ('manual',
'capture', 'import'))`, mirroring how `type` and `status` are already
constrained in `db/models.py` (`ck_notes_type`, `ck_notes_status`). Same
idiom, same enforcement location, no new pattern.

Rationale: the whole point is to stop expressing an origin as the *absence*
of other data. A nullable `origin` or a derived-at-read-time origin
reproduces exactly the defect being fixed. A boolean cannot express three
cases and would need widening again the next time a source appears.

Derived-at-read-time additionally fails because `origin=manual` and a
future "provenance was lost in a migration" are different facts that a
derivation cannot separate — which is the `capture_id` problem all over
again.

### D2 — Three origins, chosen to be total and mutually exclusive

```
manual   the operator typed it in the triage UI
capture  promoted from a hover-translate capture      → capture_id
import   written by a bulk import of an external source → import_ref
```

These are exhaustive over every way a note can currently come into
existence, which is what makes the UI filter complete. A fourth origin
(e.g. a future API-driven source) is a new enum value plus one constraint —
additive, no migration of existing rows.

Note the deliberate asymmetry with `status`: `status` describes a note's
*lifecycle* and changes over time; `origin` describes its *birth* and never
changes (D5).

### D3 — `import_ref` is JSONB, shaped `{source, source_note_id, run_id}`

Alternatives considered: three separate columns; a single opaque text
reference; a FK to an import table in stabbur.

Chosen: one nullable JSONB column.

```json
{"source": "ntnu", "source_note_id": "1719297480704", "run_id": "2026-11-08T15:04:02Z/01"}
```

Rationale: this mirrors how `translations` and `inflections` already carry
structured, evolving shapes as JSONB in this schema, so it introduces no new
convention. The fields an importer wants to record are likely to grow (a
source revision, a merge trail naming which sources contributed which
field), and that growth should not cost a migration each time.

Crucially, **this is a reference, not a foreign key, and not a dependency**.
The import tool's candidate store lives outside stabbur entirely (see
`bulk-import-anki-csv`). `import_ref` is a note saying "this came from over
there," readable and auditable on its own, and it stays meaningful even if
the import store is deleted. That is the same stance D42/D43 take on
cross-service references: structural independence, not nominal.

A FK was rejected outright — it would make stabbur depend on a local
developer artifact, which is strictly worse than depending on another
service.

### D4 — Constraints tie each origin to the evidence that justifies it

```sql
CHECK (origin <> 'capture' OR capture_id IS NOT NULL)
CHECK (origin <> 'import'  OR import_ref IS NOT NULL)
CHECK (origin <> 'manual'  OR (capture_id IS NULL AND import_ref IS NULL))
```

Written in the same `origin <> X OR <requirement>` shape as the existing
`ck_notes_grammar_requires_rule` (`type != 'grammar' OR grammar_rule_id IS
NOT NULL`), so the table's constraint vocabulary stays uniform.

Rationale: without these, `origin` is just a label a buggy client can
contradict — `origin='import'` with no `import_ref` would be accepted and
the provenance silently lost. With them, an origin claim is unfalsifiable at
the storage layer, which is what makes the UI filter trustworthy rather than
merely indicative.

The third constraint (manual implies *both* null) is what keeps the partition
honest: without it, a note could claim `manual` while carrying a
`capture_id`, and the filter would show it in one bucket while the data said
another.

### D5 — `origin` and `import_ref` are immutable; `PATCH` rejects them

Alternatives considered: allow edits; allow edits only from `manual`;
silently ignore the fields on patch.

Chosen: reject the request with `400` if either field appears in a `PATCH`
body with a value different from the stored one.

Rationale: changing a note's origin does not correct a record, it falsifies
one. There is no legitimate operator workflow for "this imported note is now
a manual one" — editing an imported note's *content* heavily is expected and
fine, and it stays an imported note, because that is where it came from.

Rejecting loudly rather than ignoring silently is chosen so a client bug
surfaces immediately instead of appearing to work. Sending the *same* value
back is permitted, so a client that round-trips a full note object through
`GET` → `PATCH` is not broken by this rule.

### D6 — Omitted `origin` is derived; `import` is never derived

```
origin omitted, capture_id present  → capture
origin omitted, capture_id absent   → manual
origin omitted, import_ref present  → 400 (import must be explicit)
```

Rationale: every existing caller of `POST /api/notes` — the triage UI, the
seed script, the tests — omits `origin` because it does not exist yet, and
all of them mean either `manual` or `capture`. Deriving keeps them all
working with no coordinated change, and the derivation is exactly the same
rule the backfill uses (D7), so new and old rows get identical treatment.

`import` is excluded from derivation deliberately: it is the one origin with
no legacy callers, so there is no compatibility argument for inferring it,
and requiring it to be stated means a bulk importer can never create
thousands of notes with an accidentally-defaulted origin.

### D7 — Backfill mirrors D6's derivation, then `NOT NULL` is enforced

Migration order, in one Alembic revision:

```
1. add `origin` as nullable, add `import_ref` as nullable
2. UPDATE notes SET origin = CASE WHEN capture_id IS NOT NULL
                                  THEN 'capture' ELSE 'manual' END
3. ALTER origin SET NOT NULL
4. add the four CHECK constraints (D1's enum + D4's three)
```

Rationale: adding a `NOT NULL` column with no default to a populated table
fails, and a server-side default of `'manual'` would be wrong for rows that
have a `capture_id`. The three-step add/populate/constrain is the standard
safe shape and keeps the migration forward-runnable against live data.

Constraints are added last, after the data already satisfies them, so the
migration cannot fail halfway with constraints applied to unbackfilled rows.

The downgrade drops the constraints and both columns — lossless in the sense
that matters, since every backfilled value is recomputable from `capture_id`.

### D8 — The public read API is explicitly untouched

`origin` is not added to `_serialize_public`, and `list_notes` gains no
filter.

Rationale: D44 is one-directional by design — stabbur does not know hub
exists, and hub has no interest in whether a note was typed or imported. A
note's provenance has no bearing on whether it is correct, reviewed, or
eligible, which is all the read API's consumer reasons about. Adding it
would widen a frozen contract for no consumer's benefit.

This is asserted as a test, not just a comment, so a future change cannot
widen the public shape by accident.

### D9 — Origin is displayed, not editable, in the note editor

Since D5 makes it immutable, offering it as a form input would be a lie. It
is rendered as read-only text alongside the note's other non-editable facts
(id, timestamps).

For `origin=import`, the editor shows the source name from `import_ref`
(e.g. "imported from ntnu") rather than the raw JSON, since the operator
reviewing a note cares which deck it came from, not the source's internal
note id. The full `import_ref` remains available via the API for auditing.

## Risks / Open Questions

- **`capture_id` has no FK today** (the `captures` table does not exist yet,
  per `db/models.py`'s own comment). `origin=capture` therefore asserts
  something that cannot be referentially checked. This is pre-existing and
  not made worse here; when `captures` lands, the D4 constraint already
  guarantees a non-null `capture_id` for every such note, which is what a
  future FK would need.
- **Derivation (D6) can mislabel a backfilled row** if any existing note was
  hand-authored *and* given a `capture_id` for an unrelated reason. Believed
  impossible given current write paths, but the backfill is a one-way
  judgement on existing data. Worth a row count sanity check (task 5.x)
  rather than a blind run.
- **Open**: whether `import_ref` should also be populated for
  `origin=capture` notes to record which capture client version produced
  them. Deferred — it is additive to the JSONB shape and needs no schema
  change if wanted later.
