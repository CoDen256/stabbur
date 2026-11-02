## Context

`suggestFieldValue(prefix, field)` already exists and is already used for
the one panel that gets this right today: `openSuggestPanel`'s `inflections`
branch computes `suggestFieldValue(prefix, 'lemma') || suggestFieldValue(prefix, 'text')`.
The `ipa`/`tts` branch and `buildTranslationsSuggestPanel` both call
`suggestFieldValue(prefix, 'text')` only. `lemma` is only ever visible/filled
for `type=word` (`TYPE_VISIBLE_FIELDS`), so reusing the exact same `lemma ||
text` expression everywhere needs no additional type check — an empty/hidden
lemma already falls through to `text` on its own.

PoS select ids are inconsistent between the two forms (an existing quirk,
not introduced here): the new-note form uses `c_pos`/`c_pos_custom`, the
edit form uses `e_pos_select`/`e_pos_custom`. Both already have a single
`wirePosCustomToggle(..., onChange)` hook that currently only updates
inflection field visibility — this change adds a second responsibility to
each existing callback rather than a parallel listener.

The mockup (`assets/lemma-first-suggestions-mock.html`) is the source of
truth for the combined suggest-control's visual language, mirroring how
`smia-enrichment-panel`'s own mock was treated.

## Goals / Non-Goals

**Goals:**
- `ipa`/`tts`/`translations` suggestion queries default to `lemma || text`,
  matching inflections.
- A verb-only "From text" button fills `lemma` from `text` with the leading
  `"å "` infinitive marker stripped.
- The query about to be used is visible on the suggest control before the
  panel is even opened, and editable there to affect every provider in that
  panel at once.
- Per-provider query overrides still exist, but are hidden by default
  (progressive disclosure) rather than always-visible.

**Non-Goals:**
- No automatic stripping of `"å "` from the `text` *fallback* itself when no
  lemma is set — only the explicit "From text" button performs that
  transform. A verb note with no lemma yet still queries providers against
  the raw `text` value until the operator clicks the button, consistent with
  the existing "no suggestion-affecting action happens implicitly" rule
  (`smia-enrichment-panel`'s "Suggestions fire only on explicit operator
  action").
- No change to the `inflections` panel (already lemma-first and
  intentionally read-only/copy-or-fill — unrelated interaction model) or the
  `stt` panel (one transcription per provider, not a candidate list — no
  per-provider query to begin with, since its input is the note's audio, not
  text).
- No change to translations' per-language-group structure — the shared query
  field is panel-wide (one query, same for every language group and every
  provider within each group), not per-language.
- No backend/API changes.

## Decisions

### D1 — Apply `lemma || text` at the same two call sites already computing a default query
`buildTranslationsSuggestPanel` and `openSuggestPanel`'s generic (ipa/tts)
branch both currently do `const defaultQuery = suggestFieldValue(prefix, 'text')`.
Both change to `suggestFieldValue(prefix, 'lemma') || suggestFieldValue(prefix, 'text')`
— textually identical to what the inflections branch already does. No new
helper needed; if this expression needs to change again later it's worth
factoring into a `defaultSuggestQuery(prefix)` helper, but duplicating a
one-line `||` expression three times isn't worth a function yet.

### D2 — "From text" lemma-suggest button, visibility driven by the existing PoS-change hooks
A small ghost/dashed button next to the Lemma field
(`<prefix>_lemma_suggest_btn`), shown only when `getPosValue(...) === 'verb'`.
Visibility is computed inside each form's existing `wirePosCustomToggle`
callback (and on initial render — `renderNoteDetail`/`renderNewNote`) rather
than a new listener, since those callbacks already run exactly when PoS
changes. Click handler:
```js
function deriveLemmaFromText(text) {
  return text.trim().replace(/^å\s+/i, '');
}
```
Unconditional regex, not gated on PoS at the transform level — a non-verb
`text` value simply won't start with `"å "` and the replace is a no-op, so
there's no reason to branch on PoS inside the function itself, only on
whether the button is shown at all.

### D3 — The combined suggest control replaces the static toggle button
Today: `<button class="btn-ghost btn-suggest" data-suggest-toggle="...">Suggest pronunciations</button>`.
New: a pill (`.suggest-control`) containing the same toggle button (now
showing a live provider count, e.g. `✨ Suggest pronunciations 3`) fused to
an always-visible `<input class="suggest-query">` prefilled with
`lemma || text`, updated live via `input` listeners on both the lemma and
text fields (and, for word notes, a PoS-change listener, since switching PoS
can hide/clear the lemma field's relevance). Opening the panel (click or
Enter in the query field) fires every provider using the query field's
*current* value, not a freshly recomputed default — so an operator who
edited the pill before opening gets what they typed, not what the field
defaulted to a moment earlier.

### D4 — Firing stays manual: Enter in the shared field re-fires, no fire-on-keystroke
Matches the existing "no auto-fire while typing" rule. The shared query
input fires (opens the panel if closed, re-fires every provider if already
open) on `Enter`, exactly mirroring today's per-provider input's
`keydown Enter → retry.click()` pattern. Typing alone does nothing until
Enter (or the toggle button) is pressed — rejected alternative: debounced
auto-fire on keystroke, which would silently reintroduce the exact behavior
`smia-enrichment-panel` explicitly ruled out for cost/rate-limit reasons
(several providers are live scrapes or quota'd APIs).

### D5 — Per-provider override: hidden by default, revealed by a pencil icon
Each provider row keeps its own override capability (needed for "retry just
this one against something else" — e.g. one provider has no entry for the
lemma, try the surface form for that provider only) but the input is
`display:none` until a small ✎ button on that row is clicked. Revealed, it
starts **empty with a placeholder**, not prefilled with the shared query's
current value — an empty, obviously-different input makes it visually clear
this is a per-row override, not a copy of the shared value. Retrying that
row uses its own override input's value if revealed and non-empty,
otherwise falls back to the shared query field's current value (so
collapsing the override back doesn't strand the row on a stale query).

## Risks / Trade-offs

- **[Trade-off]** Collapsing per-provider inputs by default makes the "retry
  one provider differently" feature slightly less discoverable than today's
  always-visible input. Accepted — it was the explicit ask (progressive
  disclosure), and the common case (everyone sharing lemma) is now correct
  by default, making the override a rarer need than before.
- **[Risk]** The live button-label/query-field update needs listeners wired
  on four fields per form (`lemma`, `text`, and the PoS select/custom pair)
  across two forms (`c_`/`e_`) — more wiring surface than today's static
  labels. Mitigated by reusing the existing `wirePosCustomToggle` callback
  slot rather than adding a parallel listener chain.

## Migration Plan

- Additive/UI-only; no schema or route changes. Rollback is reverting the
  `ui.js`/`ui.css`/`index.html` changes.
