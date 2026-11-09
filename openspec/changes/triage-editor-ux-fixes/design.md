## Context

Five items, three of which are pure bug fixes (tts "Use" on triage, the
candidate-row width blowout, the missing article-stripping on tts's
query), and two of which are small new behavior (an explicit Save action,
and richer similar-note rows). None touch the data model's meaning —
`Settings` gains one more nullable scalar preference, following the exact
pattern `prefill_timing` already established; `/api/notes/<id>/similar`
starts returning field values it already has in hand (the match note is
already fully loaded server-side to compute `has_audio` etc. — it is never
re-fetched).

## Goals / Non-Goals

**Goals:**
- Fix the three UI bugs with minimal, targeted changes.
- Give the operator an explicit way to save a triage card's in-progress
  edits without accepting or deferring it, and a setting to choose whether
  navigation does this automatically.
- Let the operator preview what a similar-note "Take" button would actually
  bring in, before taking it.

**Non-Goals:**
- No change to what a merge actually does once committed (`commitSimilarMerge`,
  `routes/notes.py`'s merge endpoint) — only what the panel shows before
  that point.
- No change to accept/skip/delete's own semantics — skip and previous
  still never change `status`, autosave only ever means "PATCH the current
  edits," never "advance a verdict."
- No bulk-apply of the new query-stripping helper to every suggest kind —
  only tts and examples ever had an article in front of their query to
  begin with (inflections/pos already strip via `lemma`, ipa/translations
  key off `text` directly and are unaffected either way per the existing
  per-kind default-query design).

## Decisions

### D1 — One shared article-stripping helper, not two near-duplicates

`deriveExamplesQuery` (ui.js) already strips a leading
`en`/`et`/`ei`/`å` token from `text` before querying examples. tts's
default query currently reads `text` raw. Rather than copy the same
stopword-set logic into a second function, `defaultSuggestQuery`'s `tts`
branch calls the same `deriveExamplesQuery` helper examples already uses
— renamed in a follow-up only if it causes confusion; for this change the
existing name stays, since both kinds want exactly the same transform
("drop a leading indefinite article/infinitive marker before querying an
audio/example source"), not two independent policies that could drift.

### D2 — Triage Save is a bare PATCH, not a new endpoint

The existing `saveTriageEdits()` (ui.js) already PATCHes the current
`readTriageForm()` payload without setting `status`. The new "Save" action
and the autosave-before-navigate behavior both call this exact function —
no new backend route, no new payload shape. This is the same reasoning
`note-editor`'s existing deferral path (`Send to back`) already uses.

### D3 — Autosave is one two-valued setting governing all three navigation actions uniformly

```
triage_navigate_save: "autosave" | "manual"
  "autosave"  Send to back / Skip / Go to previous all call
              saveTriageEdits() first (today's Send-to-back behavior,
              extended to the other two)
  "manual"    none of the three save; only the explicit Save button
              (key m) does
```

Today's actual behavior — Send to back saves, Skip and Previous don't — is
an accident of implementation order, not a deliberate asymmetry anyone
chose (unlike, say, `pos-suggest-from-ordbank`'s apply-vs-suggest
asymmetry, which encodes a real difference in operator intent). There is
no reason an operator would want saving on deferral but not on skip; the
two-valued setting collapses the accident into one deliberate choice,
defaulting to "autosave" (`DEFAULT_TRIAGE_NAVIGATE_SAVE`) so existing
behavior on deferral is preserved and skip/previous gain the same
protection rather than losing it.

"Go to previous" saving is new behavior, not merely "also save" — going
back already has its own undo-stack bookkeeping (`triageHistoryStack`);
saving-on-navigate only changes whether the *card being left* is persisted
first, which is orthogonal to and composes cleanly with that stack.

Rejected: a three-way setting (autosave / ask / manual) — "ask" means a
confirm() dialog on every single navigation action, which defeats the
entire point of triage being a fast, keyboard-driven belt. Two values
only.

### D4 — Similar-note rows show values, not just presence, straight from the already-loaded match

`similarity.find_similar` already returns full `Note` ORM objects (not
just ids) to compute today's booleans — `_serialize_similar_match` reads
`note.audio_blob is not None` etc. directly off an object that already has
`note.translations`, `note.context_text`, `note.inflections`,
`note.transcription`, and `note.audio_blob` itself loaded. Returning the
actual values is reading fields already in memory, not an extra query or
join. The presence booleans (`has_audio` etc.) stay in the payload too —
existing UI logic (which take-buttons to render at all) still branches on
them — the new value fields are additive.

Audio gets a preview, matching the tts candidate's own pattern
(`buildAudioPreviewButton`, `GET /blob/<sha256>` — already auth-exempt for
exactly this `<audio src>` reason, see `auth.py`). No new audio route.

### D5 — Candidate-row width fix is CSS-only

`.candidate-row` is a flex row; `.candidate-text` has no `min-width: 0` or
`overflow` rule, so a long string (an IPA provider's own
`/`-joined-variants response) forces the flex item to its content width,
which forces the row — and the whole suggest-panel block — wider than
intended. Fix: `.candidate-text` gets `min-width: 0; overflow-x: auto;
white-space: nowrap` inside a row that keeps `.use-btn`
(`flex: none`, already true) pinned at a fixed width. This is the same
`min-width: 0; overflow: hidden; text-overflow: ellipsis` idiom already
used by `.paradigm-row-value .copy-cell` for exactly this reason, except
here the value should stay fully readable via horizontal scroll (a
pronunciation variant can't be meaningfully truncated with an ellipsis and
still be useful) rather than clipped. `.ipa-joined-row`'s own
`.candidate-text` reuses the same class, so it's fixed for free.

### D6 — tts "Use" triage fix is a one-line guard change

`renderTtsCandidate`'s click handler opens with
`if (prefix !== 'e' && prefix !== 'c') return;` — a leftover from before
triage prefill existed. `attachAudioToNote` already has a complete,
working `prefix === 't'` branch (`triageStagedAudio`,
`renderTriageAudioSection`, `markTriageFieldProvenance`) exercised today by
manual upload and link-capture on triage. The guard is simply deleted (or
widened to admit `'t'`); no other logic in the handler needs to change.

## Risks / Trade-offs

- **Richer similar-note rows add response payload size.** Bounded by the
  same data a note's own editor already displays — no new growth vector
  (a note's `translations`/`inflections`/`context_text` are already
  small, bounded fields; this isn't attaching audio bytes, just the sha256
  reference the preview route already streams from).
- **Changing today's Send-to-back-always-saves behavior to a setting
  defaults existing operators to the same behavior they have today**
  (`autosave`), so this ships with no behavior change until the operator
  opts into `manual`.

## Migration Plan

One new Alembic migration, following `prefill_timing`'s own migration
shape exactly: add `triage_navigate_save` as a nullable `Text` column on
`settings`, plus its `CheckConstraint` restricting it to
`("autosave", "manual")`. No backfill — existing rows read as `NULL`,
`settings_store.read_scalars` returns the code-level default. No rollback
complexity: the column is additive and nullable, so a reverse migration is
a plain `DROP COLUMN`.

## Open Questions

None outstanding — all five items are independently scoped and none
depends on a design choice in another.
