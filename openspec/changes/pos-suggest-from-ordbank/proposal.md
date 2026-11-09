## Why

Roughly 1,729 imported word notes will arrive with no part of speech, and
`import-pos-lemma-inference`'s offline rules deliberately stop there rather
than guess — about 1,266 of them are single content words whose class cannot
be read off their spelling or their inflection shape (`hallo`, `seks`,
`langt`, `unnskyld`, `greide`, `begge`, `seint`). The operator's own
hand-authored notes have the same gap.

The answer is already in the ecosystem and already on screen. smia's
inflections provider resolves a surface form through Norsk Ordbank
(`oppslag → ordbank_fullform.paradigme_id → ordbank_paradigme.ordklasse`)
and returns `{lemma, pos, paradigm}` — and `_SLOT_MAPS` emits **exactly
stabbur's canonical vocabulary** (`substantiv`, `adjektiv`, `verb`,
`adverb`). The editor's inflections panel already renders that value in each
candidate's header (`ui.js:2114`, `"oppleve · verb"`) and already uses it to
group and order the paradigm rows. Nothing writes it to the note.

There is also a live friction this closes. `pos` **gates which inflection
fields exist** (`ui.js:448` — the field block is hidden entirely when
`INFLECTION_SHAPES[pos]` is undefined), and the current spec says that where
a paradigm key has no matching field, *"only the copy action is offered."*
So on a note with no part of speech, the panel displays a full, correct
paradigm that cannot be filled anywhere — every form is copy-only, because
no field exists to fill. Setting the part of speech is a precondition for
using the paradigm at all, which is why the two must be applied together.

## What Changes

- **A whole-paradigm apply action** on each inflections provider's
  candidate: sets the note's part of speech and fills every matching
  inflection form in one action, instead of requiring the operator to pick
  the part of speech by hand first and then fill form by form.
- **That action is non-destructive**: it sets `pos` **only when the note has
  none**. A part of speech the operator already chose is never overwritten
  by applying a paradigm, because a wrong part of speech routes a card to a
  permanently wrong deck.
- **A standalone part-of-speech suggest control** next to the part-of-speech
  field, following the same combined-control pattern as the existing
  transcription/translations/audio suggests. Its explicit "use" action
  **does** overwrite, because asking for a part-of-speech suggestion and
  then applying it is an unambiguous instruction.
- **Word classes with no canonical equivalent are reported, not proposed.**
  smia's `_pos_for()` falls back to raw Ordbank tokens for classes with no
  inflection shape; `prep`→`preposisjon` and `konj`/`sbu`→`konjunksjon` map
  cleanly, but `pron`, `det` and `interj` have no canonical value. Those are
  shown as what Ordbank said, with no apply action offered, rather than
  proposing something outside the six.
- **No lookup fires on its own.** Both entry points remain explicit operator
  actions, preserving `note-editor`'s existing rule that no provider call
  happens as the operator types.

## Capabilities

### Modified Capabilities
- `note-editor`: the inflections panel gains a whole-candidate apply that
  also sets the part of speech, and the part-of-speech field gains its own
  suggest control. Both are requirement-level changes to how suggestions
  reach the note, not internal detail — and the first narrows the existing
  "every fill remains an explicit, per-field operator action" rule.

## Impact

- **UI** (`ui/ui.js`): `buildInflectionsProviderBlock` gains a
  per-candidate apply action; a new part-of-speech suggest control reusing
  the existing combined-control markup; `setPosValue` /
  `updateEditInflectionFields` called in the right order so the fields exist
  before they are written into.
- **UI** (`ui/index.html`, `ui/ui.css`): the suggest control beside the
  part-of-speech field, and styling for the candidate-level apply.
- **Backend**: none. `routes/enrich.py` already proxies `inflections`, and
  the response already carries `pos` — this change consumes a field that is
  already arriving and already displayed.
- **smia**: none. No new endpoint, no new provider, no schema change.
- **Tests**: `tests/` — the editor is UI-only here, so coverage is the
  existing backend-regression run plus manual verification, matching how
  `lemma-first-suggestions` handled the same situation.
- **Out of scope**: derivational-suffix fallback for words Ordbank does not
  know (operator decision — rule-based inference stays in
  `import-pos-lemma-inference`, so the two cannot drift apart); bulk
  backfill across all notes; any change to deck assignment.
