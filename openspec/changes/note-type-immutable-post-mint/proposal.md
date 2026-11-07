## Why

`mjolnir`'s `deck-consolidation` migration derives a card's deck family from
the deck code it was **minted under**, not its note's current `type` — a
note's `type` can be edited here in stabbur at any time, including after
Mjølnir has already minted a permanent card from it. That gap caused a real
drift: two notes (now `pronunciation`) were minted as Lexic cards back when
they carried a different `type`, landing permanently in the wrong family.
Mjølnir's own `practice-deck-remint` change corrects that one instance with a
precondition-gated, one-time tool — but nothing stops the same class of
drift from recurring the next time any note's `type` is edited after being
picked up. stabbur has no notion today of whether a note has been minted at
all (D74: "stabbur never learns whether Mjølnir picked a note up, by
design") — a note's `type` is a fully mutable column
(`db/models.py`'s `Note.type`, `NOTE_TYPES = ("word", "expression",
"listening", "pronunciation", "grammar")`), with no immutability guard of
any kind.

## What Changes

- Decide how stabbur learns a note is "minted" without violating D74's
  boundary (stabbur must not know Mjølnir exists, let alone its internal
  ledger) — most likely an opaque, Mjølnir-owned flag/event stabbur stores
  but never interprets (e.g. a boolean set via a narrow API call from
  Mjølnir's own pull/mint step), not a query *into* Mjølnir's database.
- Once a note is flagged minted, reject any edit to its `type` field (a 409
  or 422 on the notes-write endpoint, with a clear message), while every
  other field remains editable as today (translations, inflections,
  context, audio, grammar rule) — this is scoped to `type` alone.
- Decide what "already minted, type already wrong" notes (if any exist
  beyond the two already corrected) should look like in the UI — likely a
  visible badge/warning on the note, not a silent block, so an operator
  understands why the type field is now read-only.

## Capabilities

### New Capabilities
- `note-type-immutability`: once a note has been consumed by a downstream
  minting pipeline, its `type` becomes permanently read-only — the specific
  mechanism for stabbur to learn "minted" status (without depending on
  Mjølnir's internals) is this change's main open design question.

## Impact

- `db/models.py` — a new column (or equivalent) marking a note as minted;
  migration required.
- The notes-write API — a new rejection path for a type edit on a minted
  note.
- A new, narrow integration point for Mjølnir to signal "this note was just
  minted" back to stabbur — the first case of Mjølnir writing anything into
  stabbur's side, where today the relationship is pull-only. Needs explicit
  design care against D43/D44/D45/D74's existing boundary, not a casual
  addition.
- No change to Mjølnir's own `deck-consolidation` policy (derive family from
  mint-time deck code) — this prevents the drift at the source, it does not
  revisit how Mjølnir already handles a card whose note was reclassified
  before this guard existed.

## Non-Goals

- Not a general "lock a note" feature — scoped specifically to the `type`
  field, the one property Mjølnir's family derivation actually depends on.
- Not a retroactive fix for any other notes already affected by past type
  changes post-mint — `practice-deck-remint` (mjolnir repo) is the one-time
  correction tool for instances found so far; this change only stops new
  occurrences.
