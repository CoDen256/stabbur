## Why

An Anki import is about to add several thousand draft notes alongside the
operator's own hand-authored ones, and many will be near-duplicates of each
other. Not identical — `merge` already collapsed exact lexeme matches — but
*derivationally* related: `å oppleve` / `en opplevelse`, `å anerkjenne` /
`anerkjent` / `en anerkjennelse`, `en blogg` / `en blogger` / `å blogge`.
Both of the first two families are real rows in the current candidate store.

Today nothing surfaces them. The operator finds a duplicate only by
remembering they saw it, which does not scale past a few hundred notes. And
the notes are complementary in a way that makes picking one wasteful: one
carries human audio, another an IPA transcription, a third a better
translation. The useful action is not "delete the duplicate" but "take the
audio from that one into this one."

Measured on the real candidate store, trigram similarity at a 0.4 threshold
returns a mean of 1.76 similar notes per note (median 1, p90 of 4, only 1%
of notes exceed 10) — the "a couple, not just one" shape the operator asked
for. `oppleve`/`opplevelse` scores 0.583.

This is deliberately **not** automatic. Deciding that two notes are the same
word is a judgement the operator makes by looking; the system's job is to
put the candidates in front of them, labelled with why each surfaced.

## What Changes

- **Three similarity signals, each labelled distinctly in the UI** — because
  they are different claims that warrant different reactions:

  | signal | means | measured |
  |---|---|---|
  | trigram similarity (`pg_trgm`) | *spelled alike* | 1.76/note at 0.4 |
  | shared inflected form | *same word family* | 181 forms; catches cross-PoS (`blogg`/`blogge`) |
  | shared translation | *related, probably not a duplicate* | 848 glosses over 1,879 notes |

- **The shared-translation section is collapsed by default** and framed as
  interesting rather than actionable. `forbindelse` / `sammenheng` /
  `tilknytning` / `samband` all gloss as "connection" and are genuinely
  different words worth learning separately — seeing that is useful, acting
  on it usually is not.
- **`pg_trgm` is enabled** with a GIN index, so similarity is an indexed
  per-note lookup on demand rather than an all-pairs precomputation.
- **Field-level merge**: take any individual field from a similar note into
  the one being edited — notably `audio_blob`, which is content-addressed,
  so "take the audio" is copying a hash with no blob duplication.
- **Merge is many-to-one.** A note may absorb several others in one action.
- **Status governs which note survives**, and the rules are chosen so that
  merge can never touch anything Mjølnir might hold:

  ```
  ready  absorbs draft   ✓        draft  absorbs ready   ✗ forbidden
  draft  absorbs draft   ✓        ready  absorbs ready   ✗ forbidden
  ```

  The absorbed note is therefore **always a draft**, drafts are never
  returned by the read API, so no Mjølnir card can exist for one — the
  absorbed row is hard-deleted and `deleted_at` is never set by a merge.
  **No tombstone is ever created.**
- **Available in both the note editor and the triage belt**, since the
  operator reviews drafts in both.

## Capabilities

### Added Capabilities
- `similar-notes`: detecting related notes over the three signals,
  presenting them with their reason, and merging fields between them under
  the status rules.

## Impact

- **Migration**: `CREATE EXTENSION pg_trgm` plus a GIN index on the
  similarity-bearing expression of `notes.text`. The extension ships with
  the official `postgres:17-alpine` image's contrib set — **verify before
  building anything around its absence** (see design D2).
- **API** (`routes/notes.py`): a similar-notes lookup for a given note, and
  a merge endpoint. The merge endpoint enforces the status rules
  server-side; the UI must not be the only thing preventing a forbidden
  merge.
- **UI** (`ui/index.html`, `ui/ui.js`, `ui/ui.css`): a similar-notes panel
  in the note editor and in the triage belt, with per-field take actions and
  the collapsed shared-translation section.
- **Schema**: no new columns. The absorbed note's `import_ref` is lost on
  merge, which is accepted (operator decision) — so no `merged_from`
  provenance field is added.
- **No change to `notes-read-api`**, to Mjølnir, or to the import tool.
- **Out of scope**: automatic merging or auto-resolution of any kind;
  similarity inside the import review tool (operator decision — stabbur
  only); cross-`source_lang` similarity.
