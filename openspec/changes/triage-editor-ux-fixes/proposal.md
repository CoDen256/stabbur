## Why

Five small frictions have accumulated in the triage belt and note editor
since `similar-notes-merge` and `operator-settings` landed, surfaced by
actually using the tool day to day: a stale guard silently breaks audio
"Use" on triage; "Skip" and "Go to previous" discard edits with no warning
while "Send to back" always saves, an inconsistency with no escape hatch;
the similar-notes panel asks the operator to take a field "blind" (no
preview of what they'd be taking); long joined-pronunciation-variant
strings blow out the suggest panel's width; and audio/examples queries
don't strip the leading article/infinitive-marker the way inflections/pos
queries already do, so a bare noun with its indefinite article still
attached queries worse than it has to.

None of these change what the data model means — they're corrections to
UI behavior that's already wrong today, plus one small new capability
(explicit save, independent of any verdict).

## What Changes

- **Fix**: the tts candidate's "Use" button is wired to work on triage
  (`t` prefix) — it was silently blocked by a stale guard, even though the
  attach path underneath it already supports triage.
- **Fix**: suggest-panel candidate rows (`.candidate-row`/`.candidate-text`,
  shared by ipa/translations/tts/examples) keep a fixed width with the
  "Use" button pinned to the right; a long value (smia's own
  `/`-joined pronunciation variants) scrolls horizontally inside its own
  space instead of widening the row and the panel around it.
- **Change**: the tts (audio) suggest control's default query strips a
  leading indefinite article / infinitive marker (`en`/`et`/`ei`/`å`) the
  same way the examples query already does — one shared helper, not two
  near-identical ones.
- **New**: an explicit "Save" action in the triage belt, bound to key `m`,
  that persists the current card's edits via the same PATCH `saveTriageEdits`
  already uses, without touching `status` or advancing the queue — usable at
  any point, independent of any verdict.
- **Change**: a new operator setting controls whether "Send to back",
  "Skip", and "Go to previous" save the current card's edits before moving
  on. Today "Send to back" always saves and the other two never do — an
  inconsistency with no visible control. The setting picks one of two
  consistent behaviors across all three: autosave-on-navigate (today's
  "Send to back" behavior, extended to the other two) or manual-only (none
  of the three save; only the new explicit Save action does).
- **Change**: the similar-notes panel (editor and triage) shows each
  match's actual translations/context/inflections/transcription/audio
  (with an audio preview) next to its "Take" button, instead of a bare
  boolean-gated button with no preview of what would be taken. The existing
  take-staging + merge-bar-absorption mechanism is unchanged; only the row
  content is richer.

## Capabilities

### New Capabilities
(none — every item above modifies behavior an existing capability already
owns)

### Modified Capabilities
- `note-editor`: the audio suggest query gains the same article-stripping
  transform the examples query already has.
- `note-triage`: the four-verdicts requirement's "Send to back"/"Skip"
  behavior becomes governed by a new operator preference instead of being
  hardcoded (Send to back always saves, Skip never does); a new,
  verdict-independent Save action is added, bound to key `m`; "Go to
  previous" also respects the new preference; the audio suggest panel's
  "Use" action is fixed to actually attach a candidate (it silently
  no-ops today).
- `similar-notes`: a match's row gains the actual field values and an
  audio preview, not just presence booleans — changes what the endpoint
  returns and what the panel shows.
- `operator-settings`: a new scalar preference (triage navigation autosave
  vs. manual-only) joins the existing ones.

The candidate-row width fix is a visual-only correction with no testable
behavior change, so it carries no spec delta — it's recorded in design.md
and tasks.md only.

## Impact

- **Backend** (`routes/notes.py`): `_serialize_similar_match` returns the
  actual field values (translations, context_text, inflections,
  transcription, audio_blob) alongside (or instead of) the presence
  booleans.
- **Backend** (`db/models.py`, new Alembic migration, `settings_store.py`,
  `routes/settings.py`): one new nullable `Settings` column for the
  triage-autosave preference, same pattern as `prefill_timing`.
- **UI** (`ui/ui.js`): tts "Use" guard fix; shared article-stripping helper
  reused by tts and examples; new `saveTriageCard`-style action + key `m`;
  autosave gating in the send-back/skip/previous handlers, read from
  settings; richer similar-note row rendering.
- **UI** (`ui/index.html`): new "Save" button in triage's verdict bar; new
  settings-page control for the autosave preference.
- **UI** (`ui/ui.css`): `.candidate-text` width/overflow fix.
- **smia**: none.
- **Tests**: `tests/` — the similar-notes serializer change and the new
  settings column both get backend test coverage; the UI changes are
  manual-verification, matching this repo's existing convention for
  UI-only work.
- **Out of scope**: no change to deck assignment, to `origin`/`status`
  semantics, or to the merge/absorb mechanism itself.
