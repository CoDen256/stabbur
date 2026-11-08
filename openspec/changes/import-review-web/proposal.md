## Why

`bulk-import-anki-csv`'s pipeline is built and has produced a **7,022-item
review queue**. The review surface it ships with is a `print()` + `input()`
loop: every decision costs a letter *and* `Enter`, candidates scroll past
with no visual separation, there is no audio, and a stray `repr()` renders
`'å\xa0starte'` on screen. At 7,022 items that is not a cosmetic complaint —
it is the difference between the import happening and not happening.

But measuring the queue found three problems underneath the rendering, and
fixing the UI alone would leave the experience bad anyway:

- **59% of the queue has no ordering signal at all.** 4,145 of 7,022
  candidates have no frequency rank, no CEFR band and no chapter, so they
  sort arbitrarily. `bulk-import-anki-csv`'s D7 promises "review in
  usefulness order, stop whenever you like"; that promise currently holds
  for 41% of the queue. A prettier UI over an unordered list is still a
  grind.
- **Two thirds of the audio is machine TTS that will never be pushed.** Of
  6,269 queue items carrying an `audio_ref`, 4,167 are `core6k`'s
  `hypertts-*` output. D10's human-only rule is applied at `push`, so
  `merge` happily picked synthesised audio as the winner whenever no human
  recording existed. Real human coverage is 2,102 items (30%).
- **140 rows contain a U+00A0 non-breaking space** in `text`, always between
  article and word. Verdicts are unaffected (`\s` matches NBSP, so
  article-stripping worked and no `head_lemma` carries one), but `text` is
  what gets pushed — so without a fix 140 notes reach stabbur, and
  eventually Mjølnir cards, with an invisible character in them.

The ordering fix in particular is what makes a good UI feel good; they ship
together or the UI underdelivers.

## What Changes

- **A local web review interface replaces the terminal loop.** One candidate
  on screen at a time, swapped for the next on decision. Single keypress,
  no `Enter`. Served by Flask on localhost — already a stabbur dependency,
  so no new packages.
- **Review is reframed as the question the operator is actually answering.**
  Not abstract accept/reject, but *"do you already know this word?"* —
  **yes → reject** (don't import, it's known), **no → accept** (import it).
  The pipeline's vocabulary stays `accept`/`reject` in the `decision` table;
  only the operator-facing framing changes.
- **The edit action is removed entirely.** Review becomes pure triage.
  Every accepted candidate lands in stabbur as a `draft` that gets edited
  there anyway, so field editing here was a second authoring surface for no
  gain. `decision.edited_fields_json` stays in the schema, unwritten — it is
  never read by `push`, so nothing downstream changes.
- **Undo, multi-level.** Single-keypress decisions without confirmation make
  mis-presses certain over 7,022 items, so stepping back is a requirement,
  not a nicety. Cheap, because `decision` is already an upsert keyed by
  signature.
- **Audio playback during review**, served directly out of the `.apkg`
  archives by random access — no extraction step. **Human recordings only**;
  a candidate whose only audio is synthesised shows as having none.
- **`core6k`'s frequency rank is ingested.** Its `cards.due` column runs
  1..6000 with 6,000 distinct values and is a genuine frequency ordering
  (`å være · og · i · en · det · på · som · å ha …`, tail `å vispe · å elte ·
  å gjespe`). Capturing it ranks ~2,294 of the 4,145 unranked candidates,
  taking ordering coverage from 41% to roughly 74%.
- **The human-audio rule moves from `push` to `merge`**, so `audio_ref` is
  null when no human recording exists and the review UI shows the truth
  rather than offering a clip that will be discarded later.
- **U+00A0 is normalised** at the `normalize` stage, where the data is
  fixed, rather than hidden in a renderer.

## Capabilities

### Added Capabilities
- `import-review`: the operator-facing review surface over the candidate
  store — presentation, keyboard interaction, audio playback, undo, and the
  triage framing.

### Modified Capabilities
- `bulk-import`: three corrections to pipeline behaviour that the review
  experience depends on — ordering-signal coverage, human-audio selection at
  merge time, and text normalisation. All three supersede scenarios in
  `bulk-import-anki-csv`'s delta.

## Impact

- **New module** (`scripts/import/web.py` + static assets): a localhost
  Flask app reading `import/candidates.db`. `scripts/import/review.py`'s
  terminal loop and its `edit` branch are removed; its pure functions
  (`queue`, `pending_queue`, `progress`, `record_decision`) are kept and
  reused unchanged.
- **`scripts/import/ingest.py`**: capture `cards.due` for `core6k`.
- **`scripts/import/normalize.py`**: NBSP normalisation; carry the new
  ordering signal into `order_signal_json`.
- **`scripts/import/merge.py`**: human-audio-only selection; ordering key
  gains the core6k rank.
- **`scripts/import/push.py`**: unchanged — it never read `edited_fields`.
- **Tests**: `tests/test_import_review.py`'s `run_interactive` and edit
  cases are replaced by route-level tests; `test_import_normalize.py`,
  `test_import_merge.py`, `test_import_ingest.py` gain cases for the three
  fixes.
- **Re-runs required**: `ingest` → `normalize` → `key` → `judge` → `merge`.
  `decision` is untouched, so the 2 decisions already recorded survive —
  the same D2/task 1.3 guarantee that the D13 switch relied on.
- **Not in scope**: reviewing the 5,220 auto-skipped candidates (operator
  decision — the task 4.8 log dump stays as it is), editing candidate
  fields, and anything in the stabbur app itself.
